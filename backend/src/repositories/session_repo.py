"""情景记忆仓库：sessions 与 messages 持久化（含引用快照与重命名/删除）。"""

import json
from typing import Any
from uuid import UUID

from psycopg_pool import AsyncConnectionPool


class SessionRepo:
    def __init__(self, pool: AsyncConnectionPool) -> None:
        self._pool = pool

    async def create_session(self, user_id: UUID, agent_name: str, title: str) -> dict[str, Any]:
        sql = """
            INSERT INTO sessions (user_id, agent_name, title)
            VALUES (%s, %s, %s)
            RETURNING id, user_id, agent_name, title, created_at, updated_at;
        """
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, (user_id, agent_name, title))
                row = await cur.fetchone()
                assert row is not None
                return dict(row)

    async def list_sessions(self, user_id: UUID, limit: int = 30) -> list[dict[str, Any]]:
        sql = """
            SELECT id, agent_name, title, created_at, updated_at
            FROM sessions
            WHERE user_id = %s
            ORDER BY updated_at DESC
            LIMIT %s;
        """
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, (user_id, limit))
                return [dict(r) for r in await cur.fetchall()]

    async def rename_session(self, session_id: UUID, user_id: UUID, title: str) -> dict[str, Any] | None:
        sql = """
            UPDATE sessions SET title = %s, updated_at = NOW()
            WHERE id = %s AND user_id = %s
            RETURNING id, agent_name, title, updated_at;
        """
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, (title, session_id, user_id))
                row = await cur.fetchone()
                return dict(row) if row else None

    async def delete_session(self, session_id: UUID, user_id: UUID) -> bool:
        sql = "DELETE FROM sessions WHERE id = %s AND user_id = %s RETURNING id;"
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, (session_id, user_id))
                return await cur.fetchone() is not None

    async def get_session(self, session_id: UUID, user_id: UUID) -> dict[str, Any] | None:
        sql = "SELECT id, user_id, agent_name, title FROM sessions WHERE id = %s AND user_id = %s;"
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, (session_id, user_id))
                row = await cur.fetchone()
                return dict(row) if row else None

    async def append_message(
        self,
        session_id: UUID,
        user_id: UUID,
        role: str,
        content: str,
        run_id: UUID | None = None,
        tool_calls: list[dict[str, Any]] | None = None,
        tool_call_id: str | None = None,
        citations: list[dict[str, Any]] | None = None,
        action_cards: list[dict[str, Any]] | None = None,
    ) -> int:
        sql = """
            INSERT INTO messages (session_id, user_id, run_id, role, content, tool_calls, tool_call_id, citations, action_cards)
            VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s, %s::jsonb, %s::jsonb)
            RETURNING id;
        """
        tc_json = json.dumps(tool_calls, ensure_ascii=False) if tool_calls else None
        cite_json = json.dumps(citations, ensure_ascii=False) if citations else None
        card_json = json.dumps(action_cards, ensure_ascii=False) if action_cards else None
        async with self._pool.connection() as conn:
            async with conn.transaction():
                async with conn.cursor() as cur:
                    await cur.execute(
                        sql, (session_id, user_id, run_id, role, content, tc_json, tool_call_id, cite_json, card_json)
                    )
                    row = await cur.fetchone()
                    assert row is not None
                    await cur.execute("UPDATE sessions SET updated_at = NOW() WHERE id = %s;", (session_id,))
                    return int(row["id"])

    async def list_messages(self, session_id: UUID, user_id: UUID, limit: int = 60) -> list[dict[str, Any]]:
        sql = """
            SELECT * FROM (
                SELECT id, run_id, role, content, citations, action_cards, tool_calls, tool_call_id, created_at
                FROM messages
                WHERE session_id = %s AND user_id = %s
                ORDER BY id DESC
                LIMIT %s
            ) recent
            ORDER BY id ASC;
        """
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, (session_id, user_id, limit))
                return [dict(r) for r in await cur.fetchall()]
