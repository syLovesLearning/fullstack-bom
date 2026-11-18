"""商业化 RAG 全链路离线测试：结构化切片、BM25+RRF 融合、增量去重与检索闭环。"""

import asyncio
import math
from typing import Any
from uuid import UUID, uuid4

import httpx

from src.services.bm25 import bm25_rank, rrf_fuse
from src.services.chunker import chunk_markdown
from src.services.embedding_service import EmbeddingService
from src.services.rag_service import RagService


class FakeDocRepo:
    def __init__(self) -> None:
        self.docs: dict[tuple[UUID, str], dict[str, Any]] = {}
        self.chunks: list[dict[str, Any]] = []
        self._seq = 1

    async def upsert_document_with_chunks(
        self,
        user_id: UUID,
        source_path: str,
        title: str,
        category: str,
        content_hash: str,
        chunks: list[tuple[int, str, str, str, list[float]]],
        allowed_groups: list[str] | None = None,
    ) -> dict[str, Any]:
        key = (user_id, source_path)
        existing = self.docs.get(key)
        if existing and existing["content_hash"] == content_hash:
            return {"document_id": str(existing["id"]), "status": "skipped", "chunks": 0}

        doc_id = existing["id"] if existing else uuid4()
        self.docs[key] = {
            "id": doc_id,
            "user_id": user_id,
            "source_path": source_path,
            "title": title,
            "category": category,
            "content_hash": content_hash,
        }
        self.chunks = [c for c in self.chunks if c["document_id"] != doc_id]
        for idx, h_path, body, search_text, emb in chunks:
            self.chunks.append(
                {
                    "id": self._seq,
                    "document_id": doc_id,
                    "user_id": user_id,
                    "chunk_index": idx,
                    "heading_path": h_path,
                    "content": body,
                    "search_text": search_text,
                    "embedding": emb,
                    "title": title,
                    "source_path": source_path,
                    "category": category,
                }
            )
            self._seq += 1
        return {"document_id": str(doc_id), "status": "indexed", "chunks": len(chunks)}

    async def vector_search(
        self, user_id: UUID, query_embedding: list[float], category: str | None = None, top_k: int = 15, user_groups: list[str] | None = None
    ) -> list[dict[str, Any]]:
        def cos(a: list[float], b: list[float]) -> float:
            dot = sum(x * y for x, y in zip(a, b))
            na = math.sqrt(sum(x * x for x in a)) or 1.0
            nb = math.sqrt(sum(y * y for y in b)) or 1.0
            return dot / (na * nb)

        filtered = [
            c for c in self.chunks if c["user_id"] == user_id and (category is None or c["category"] == category)
        ]
        filtered.sort(key=lambda c: cos(query_embedding, c["embedding"]), reverse=True)
        return filtered[:top_k]

    async def fulltext_search(
        self, user_id: UUID, query_tokens: list[str], category: str | None = None, top_k: int = 15, user_groups: list[str] | None = None
    ) -> list[dict[str, Any]]:
        candidates = [
            c for c in self.chunks if c["user_id"] == user_id and (category is None or c["category"] == category)
        ]
        return bm25_rank(" ".join(query_tokens), candidates, top_k=top_k)

    async def fetch_adjacent_chunks(
        self, document_id: UUID, user_id: UUID, chunk_index: int, window: int = 1, user_groups: list[str] | None = None
    ) -> list[dict[str, Any]]:
        rows = [
            c
            for c in self.chunks
            if c["document_id"] == document_id
            and c["user_id"] == user_id
            and (chunk_index - window) <= c["chunk_index"] <= (chunk_index + window)
        ]
        rows.sort(key=lambda x: x["chunk_index"])
        return rows


def test_markdown_chunker_preserves_headings_and_code_blocks() -> None:
    md = "# 指南\n\n## 快速开始\n```python\n# 注释不是标题\nprint('ok')\n```\n\n完成安装。"
    chunks = chunk_markdown(md, max_chars=200)
    assert any(c.heading_path == "指南 > 快速开始" for c in chunks)
    assert any("print('ok')" in c.content for c in chunks)


def test_rag_ingest_dedup_and_hybrid_search() -> None:
    async def _run() -> None:
        uid = uuid4()
        other_uid = uuid4()
        repo = FakeDocRepo()
        async with httpx.AsyncClient() as client:
            rag = RagService(doc_repo=repo, embed_service=EmbeddingService(client))  # type: ignore[arg-type]

            doc_text = "# 部署手册\n\n## 数据库配置\n使用 PostgreSQL 17 和 pgvector 扩展存储 1024 维向量。"
            r1 = await rag.ingest_document(uid, "部署手册", "docs/ops.md", doc_text, category="ops")
            assert r1["status"] == "indexed"

            r2 = await rag.ingest_document(uid, "部署手册", "docs/ops.md", doc_text, category="ops")
            assert r2["status"] == "skipped"

            hits = await rag.search_structured("pgvector 向量维度", top_k=2, user_id=uid)
            assert len(hits) == 1
            assert hits[0]["heading_path"] == "部署手册 > 数据库配置"

            other_hits = await rag.search_structured("pgvector", top_k=2, user_id=other_uid)
            assert other_hits == []

    asyncio.run(_run())


def test_bm25_and_rrf_fusion() -> None:
    docs = [
        {"id": 1, "heading_path": "A", "content": "FastAPI SSE 流式输出"},
        {"id": 2, "heading_path": "B", "content": "Vue 3 前端组件通信"},
    ]
    bm25_hits = bm25_rank("FastAPI SSE", docs, top_k=2)
    assert bm25_hits[0]["id"] == 1
    fused = rrf_fuse([docs[1], docs[0]], bm25_hits)
    assert len(fused) == 2


def test_query_rewrite_and_low_score_refusal() -> None:
    from src.core.event_context import set_auth_context, set_recent_history
    from src.schemas.models import AuthContext
    from src.services.llm_service import LLMService

    async def _run() -> None:
        uid = uuid4()
        set_auth_context(AuthContext(user_id=uid, username="u", role="admin", allowed_tools=["rag_search"]))
        set_recent_history([{"role": "user", "content": "PostgreSQL 连接池"}])

        repo = FakeDocRepo()
        async with httpx.AsyncClient() as client:
            rag = RagService(
                doc_repo=repo,  # type: ignore[arg-type]
                embed_service=EmbeddingService(client),
                llm_service=LLMService(client),
            )
            await rag.ingest_document(uid, "数据库", "docs/db.md", "# 数据库\nPostgreSQL 连接池默认大小 10。", "ops")

            # 无关问题在高阈值下应触发拒答
            refused = await rag.search("火星探测器发射时间", top_k=2, min_score=0.95)
            assert '"rejected": true' in refused

            # 含指代词“它”的追问应自动带上“PostgreSQL 连接池”上下文
            ok = await rag.search("它的默认大小是多少？", top_k=2, min_score=0.1)
            assert '"rejected": false' in ok and "PostgreSQL 连接池" in ok

    asyncio.run(_run())


def test_zip_archive_filters_junk_and_traversal() -> None:
    import io
    import zipfile
    from src.services.file_parser import expand_uploaded_archive

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("__MACOSX/._guide.md", b"junk")
        zf.writestr(".DS_Store", b"junk")
        zf.writestr("../evil.md", b"traversal")
        zf.writestr("docs/guide.md", b"# Guide\nValid content")
        zf.writestr("img/logo.png", b"binary")

    items = expand_uploaded_archive(buf.getvalue())
    assert len(items) == 1
    assert items[0][0] == "docs/guide.md"
