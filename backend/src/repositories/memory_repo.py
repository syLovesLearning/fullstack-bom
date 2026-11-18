"""语义记忆仓库：memories 表读写（强制 user_id 隔离）。"""

from typing import Any
from uuid import UUID

from psycopg_pool import AsyncConnectionPool


class MemoryRepo:
    def __init__(self, pool: AsyncConnectionPool) -> None:
        self._pool = pool

    async def create_memory(
        self,
        user_id: UUID,
        memory_type: str,
        content: str,
        importance: int = 3,
        source_session: UUID | None = None,
    ) -> dict[str, Any]:
        sql = """
            INSERT INTO memories (user_id, source_session, memory_type, content, importance)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id, memory_type, content, importance, created_at;
        """
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, (user_id, source_session, memory_type, content, importance))
                row = await cur.fetchone()
                assert row is not None
                return dict(row)

    async def list_memories(self, user_id: UUID, limit: int = 20) -> list[dict[str, Any]]:
        sql = """
            SELECT id, memory_type, content, importance, created_at
            FROM memories
            WHERE user_id = %s AND is_active = TRUE
            ORDER BY importance DESC, created_at DESC
            LIMIT %s;
        """
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, (user_id, limit))
                return [dict(r) for r in await cur.fetchall()]

    async def soft_delete(self, memory_id: UUID, user_id: UUID) -> bool:
        sql = """
            UPDATE memories SET is_active = FALSE, updated_at = NOW()
            WHERE id = %s AND user_id = %s
            RETURNING id;
        """
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, (memory_id, user_id))
                return await cur.fetchone() is not None
