"""商业化 RAG 业务服务：分组数据权限 + 指代改写 + 混合检索 + 低分拒答护栏。"""

import hashlib
import json
from typing import Any
from uuid import UUID

from redis.asyncio import Redis

from src.core.event_context import emit_event, get_auth_context, get_recent_history
from src.repositories.doc_repo import DocRepo
from src.services.bm25 import rrf_fuse, tokenize
from src.services.chunker import chunk_markdown
from src.services.embedding_service import EmbeddingService
from src.services.llm_service import LLMService


class RagService:
    def __init__(
        self,
        doc_repo: DocRepo,
        embed_service: EmbeddingService,
        redis_client: Redis | None = None,
        llm_service: LLMService | None = None,
    ) -> None:
        self._docs = doc_repo
        self._embed = embed_service
        self._redis = redis_client
        self._llm = llm_service

    async def ingest_document(
        self,
        user_id: UUID,
        title: str,
        source_path: str,
        content: str,
        category: str = "general",
        allowed_groups: list[str] | None = None,
    ) -> dict[str, Any]:
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        raw_chunks = chunk_markdown(content)
        texts = [f"{c.heading_path}\n{c.content}" for c in raw_chunks]
        # 入库路径 on_error=raise：embedding 失败直接中止，避免两种向量空间混入同一张表
        embeddings = await self._embed.embed_texts(texts, on_error="raise")

        packed = [
            (c.chunk_index, c.heading_path, c.content, " ".join(tokenize(t)), emb)
            for c, t, emb in zip(raw_chunks, texts, embeddings)
        ]
        result = await self._docs.upsert_document_with_chunks(
            user_id=user_id,
            source_path=source_path,
            title=title,
            category=category,
            content_hash=content_hash,
            chunks=packed,
            allowed_groups=allowed_groups or ["private"],
        )
        if self._redis is not None and result["status"] == "indexed":
            async for key in self._redis.scan_iter(match="rag:cache:*"):
                await self._redis.delete(key)
        return result

    async def search(
        self,
        query: str,
        top_k: int = 3,
        category: str | None = None,
        min_score: float = 0.2,
    ) -> str:
        effective_query = query
        history = get_recent_history()
        if self._llm is not None and history:
            effective_query = await self._llm.rewrite_query(query, history)
            if effective_query != query:
                await emit_event("thought", {"step": 0, "status": f"指代改写: {effective_query}"})

        citations = await self.search_structured(
            query=effective_query, top_k=top_k, category=category, min_score=min_score
        )
        await emit_event("citations", {"items": citations})

        if not citations:
            return json.dumps(
                {
                    "query": effective_query,
                    "rejected": True,
                    "reason": "未在当前用户有权限的知识库中找到相关度达标的依据，禁止编造。",
                },
                ensure_ascii=False,
            )
        return json.dumps({"query": effective_query, "rejected": False, "hits": citations}, ensure_ascii=False)

    async def search_structured(
        self,
        query: str,
        top_k: int = 3,
        category: str | None = None,
        user_id: UUID | None = None,
        user_groups: list[str] | None = None,
        min_score: float = 0.0,
    ) -> list[dict[str, Any]]:
        auth = get_auth_context()
        uid = user_id or (auth.user_id if auth else None)
        groups = user_groups or (auth.groups if auth else ["public"])
        if uid is None:
            return []

        g_key = ",".join(sorted(groups))
        # 缓存键必须包含 min_score：不同阈值的结果集不同，否则低阈值调用会拿到已过滤的缓存
        cache_key = f"rag:cache:{uid}:{g_key}:{category or 'all'}:{min_score}:{hashlib.md5(query.encode()).hexdigest()}"
        if self._redis is not None:
            cached = await self._redis.get(cache_key)
            if cached:
                hits = json.loads(cached)
                return [h for h in hits if h.get("score", 1.0) >= min_score]

        q_emb = (await self._embed.embed_texts([query]))[0]
        vec_hits = await self._docs.vector_search(uid, q_emb, category=category, top_k=15, user_groups=groups)
        fts_hits = await self._docs.fulltext_search(uid, tokenize(query), category=category, top_k=15, user_groups=groups)

        fused = rrf_fuse(vec_hits, fts_hits)[:10]
        if not fused:
            return []

        reranked = await self._embed.rerank(
            query=query,
            docs=[f"{item['heading_path']}\n{item['content']}" for item in fused],
            top_n=top_k,
        )

        citations: list[dict[str, Any]] = []
        for rank_idx, (orig_idx, score) in enumerate(reranked, start=1):
            if score < min_score:
                continue
            hit = fused[orig_idx]
            adj = await self._docs.fetch_adjacent_chunks(
                document_id=hit["document_id"],
                user_id=uid,
                chunk_index=hit["chunk_index"],
                window=1,
                user_groups=groups,
            )
            merged_text = "\n".join(a["content"] for a in adj) if adj else hit["content"]
            citations.append(
                {
                    "index": rank_idx,
                    "title": hit["title"],
                    "source_path": hit["source_path"],
                    "heading_path": hit["heading_path"],
                    "category": hit["category"],
                    "score": score,
                    "snippet": merged_text,
                }
            )

        if self._redis is not None and citations:
            await self._redis.set(cache_key, json.dumps(citations, ensure_ascii=False), ex=600)
        return citations

    async def search_debug(
        self,
        query: str,
        user_id: UUID,
        user_groups: list[str] | None = None,
        top_k: int = 5,
        category: str | None = None,
        min_score: float = 0.2,
    ) -> dict[str, Any]:
        groups = user_groups or ["public"]
        q_tokens = tokenize(query)
        q_emb = (await self._embed.embed_texts([query]))[0]
        vec_hits = await self._docs.vector_search(user_id, q_emb, category=category, top_k=top_k, user_groups=groups)
        fts_hits = await self._docs.fulltext_search(user_id, q_tokens, category=category, top_k=top_k, user_groups=groups)

        fused = rrf_fuse(vec_hits, fts_hits)[:10]
        reranked_hits: list[dict[str, Any]] = []
        if fused:
            reranked = await self._embed.rerank(
                query=query,
                docs=[f"{item['heading_path']}\n{item['content']}" for item in fused],
                top_n=top_k,
            )
            for rank_idx, (orig_idx, score) in enumerate(reranked, start=1):
                hit = fused[orig_idx]
                reranked_hits.append(
                    {
                        "id": hit["id"],
                        "rank": rank_idx,
                        "title": hit["title"],
                        "source_path": hit["source_path"],
                        "heading_path": hit["heading_path"],
                        "score": round(float(score), 4),
                        "passed": float(score) >= min_score,
                        "snippet": hit["content"],
                    }
                )

        def _brief(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
            return [
                {
                    "id": r["id"],
                    "title": r["title"],
                    "heading_path": r["heading_path"],
                    "score": round(float(r.get("score", 0.0)), 4),
                    "preview": r["content"][:160],
                }
                for r in rows
            ]

        return {
            "query": query,
            "tokens": list(dict.fromkeys(q_tokens))[:20],
            "min_score": min_score,
            "rejected": not any(h["passed"] for h in reranked_hits),
            "vec_hits": _brief(vec_hits),
            "fts_hits": _brief(fts_hits),
            "reranked_hits": reranked_hits,
        }
