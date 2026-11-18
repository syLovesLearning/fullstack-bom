"""商业化 RAG 文档与切片仓库（事务原子更新 + 分组数据权限 + GIN 全文检索）。"""

from typing import Any
from uuid import UUID

from psycopg_pool import AsyncConnectionPool


def _format_vector(vec: list[float]) -> str:
    return "[" + ",".join(f"{v:.6f}" for v in vec) + "]"


class DocRepo:
    def __init__(self, pool: AsyncConnectionPool) -> None:
        self._pool = pool

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
        groups = allowed_groups or ["private"]
        async with self._pool.connection() as conn:
            async with conn.transaction():
                async with conn.cursor() as cur:
                    await cur.execute(
                        "SELECT id, content_hash, allowed_groups FROM kb_documents WHERE user_id = %s AND source_path = %s;",
                        (user_id, source_path),
                    )
                    existing = await cur.fetchone()
                    if existing and existing["content_hash"] == content_hash and existing["allowed_groups"] == groups:
                        return {"document_id": str(existing["id"]), "status": "skipped", "chunks": 0}

                    if existing:
                        doc_id = existing["id"]
                        await cur.execute(
                            """
                            UPDATE kb_documents
                            SET title=%s, category=%s, content_hash=%s, allowed_groups=%s, updated_at=NOW()
                            WHERE id=%s;
                            """,
                            (title, category, content_hash, groups, doc_id),
                        )
                        await cur.execute("DELETE FROM kb_chunks WHERE document_id = %s;", (doc_id,))
                    else:
                        await cur.execute(
                            """
                            INSERT INTO kb_documents (user_id, source_path, title, category, content_hash, allowed_groups)
                            VALUES (%s, %s, %s, %s, %s, %s) RETURNING id;
                            """,
                            (user_id, source_path, title, category, content_hash, groups),
                        )
                        row = await cur.fetchone()
                        assert row is not None
                        doc_id = row["id"]

                    for idx, heading_path, body, search_text, emb in chunks:
                        await cur.execute(
                            """
                            INSERT INTO kb_chunks (
                                document_id, user_id, chunk_index, heading_path, content, search_tsv, embedding
                            )
                            VALUES (%s, %s, %s, %s, %s, to_tsvector('simple', %s), %s::vector);
                            """,
                            (doc_id, user_id, idx, heading_path, body, search_text, _format_vector(emb)),
                        )
                    return {"document_id": str(doc_id), "status": "indexed", "chunks": len(chunks)}

    async def list_documents(self, user_id: UUID, user_groups: list[str] | None = None) -> list[dict[str, Any]]:
        groups = user_groups or ["public"]
        sql = """
            SELECT d.id, d.user_id, d.source_path, d.title, d.category, d.allowed_groups,
                   d.updated_at, COUNT(c.id) AS chunk_count
            FROM kb_documents d
            LEFT JOIN kb_chunks c ON c.document_id = d.id
            WHERE d.status = 'active'
              AND (d.user_id = %s OR d.allowed_groups && %s::text[])
            GROUP BY d.id
            ORDER BY d.updated_at DESC;
        """
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, (user_id, groups))
                return [dict(r) for r in await cur.fetchall()]

    async def delete_document(self, doc_id: UUID, user_id: UUID) -> bool:
        sql = "DELETE FROM kb_documents WHERE id = %s AND user_id = %s RETURNING id;"
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, (doc_id, user_id))
                return await cur.fetchone() is not None

    async def vector_search(
        self,
        user_id: UUID,
        query_embedding: list[float],
        category: str | None = None,
        top_k: int = 15,
        user_groups: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        vec_str = _format_vector(query_embedding)
        groups = user_groups or ["public"]
        sql = """
            SELECT c.id, c.document_id, c.chunk_index, c.heading_path, c.content,
                   d.title, d.source_path, d.category,
                   1 - (c.embedding <=> %s::vector) AS score
            FROM kb_chunks c
            JOIN kb_documents d ON d.id = c.document_id
            WHERE d.status = 'active'
              AND (c.user_id = %s OR d.allowed_groups && %s::text[])
              AND (%s::text IS NULL OR d.category = %s)
            ORDER BY c.embedding <=> %s::vector
            LIMIT %s;
        """
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, (vec_str, user_id, groups, category, category, vec_str, top_k))
                return [dict(r) for r in await cur.fetchall()]

    async def fulltext_search(
        self,
        user_id: UUID,
        query_tokens: list[str],
        category: str | None = None,
        top_k: int = 15,
        user_groups: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        clean_tokens = [t for t in dict.fromkeys(query_tokens) if t.isalnum()]
        if not clean_tokens:
            return []
        tsquery_str = " | ".join(clean_tokens[:24])
        groups = user_groups or ["public"]
        sql = """
            SELECT c.id, c.document_id, c.chunk_index, c.heading_path, c.content,
                   d.title, d.source_path, d.category,
                   ts_rank_cd(c.search_tsv, to_tsquery('simple', %s)) AS score
            FROM kb_chunks c
            JOIN kb_documents d ON d.id = c.document_id
            WHERE d.status = 'active'
              AND (c.user_id = %s OR d.allowed_groups && %s::text[])
              AND (%s::text IS NULL OR d.category = %s)
              AND c.search_tsv @@ to_tsquery('simple', %s)
            ORDER BY score DESC
            LIMIT %s;
        """
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, (tsquery_str, user_id, groups, category, category, tsquery_str, top_k))
                return [dict(r) for r in await cur.fetchall()]

    async def fetch_adjacent_chunks(
        self,
        document_id: UUID,
        user_id: UUID,
        chunk_index: int,
        window: int = 1,
        user_groups: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        groups = user_groups or ["public"]
        sql = """
            SELECT c.chunk_index, c.content
            FROM kb_chunks c
            JOIN kb_documents d ON d.id = c.document_id
            WHERE c.document_id = %s
              AND (c.user_id = %s OR d.allowed_groups && %s::text[])
              AND c.chunk_index BETWEEN %s AND %s
            ORDER BY c.chunk_index ASC;
        """
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, (document_id, user_id, groups, chunk_index - window, chunk_index + window))
                return [dict(r) for r in await cur.fetchall()]
