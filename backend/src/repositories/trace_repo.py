"""轨迹审计仓库：记录每次智能体运行的步骤、耗时与 Token（强制 user_id 隔离）。"""

import json
from typing import Any
from uuid import UUID

from psycopg_pool import AsyncConnectionPool


class TraceRepo:
    def __init__(self, pool: AsyncConnectionPool) -> None:
        self._pool = pool

    async def create_run(self, session_id: UUID, user_id: UUID, model_name: str) -> UUID:
        sql = """
            INSERT INTO agent_runs (session_id, user_id, status, model_name)
            VALUES (%s, %s, 'running', %s)
            RETURNING id;
        """
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, (session_id, user_id, model_name))
                row = await cur.fetchone()
                assert row is not None
                return row["id"]

    async def finish_run(
        self, run_id: UUID, status: str, total_tokens: int, latency_ms: int, error: str | None = None
    ) -> None:
        sql = """
            UPDATE agent_runs
            SET status = %s, total_tokens = %s, latency_ms = %s, error_message = %s, finished_at = NOW()
            WHERE id = %s;
        """
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, (status, total_tokens, latency_ms, error, run_id))

    async def append_step(
        self,
        run_id: UUID,
        user_id: UUID,
        step_index: int,
        step_type: str,
        tool_name: str | None,
        input_payload: dict[str, Any],
        output_payload: dict[str, Any],
        duration_ms: int,
    ) -> None:
        sql = """
            INSERT INTO run_steps (
                run_id, user_id, step_index, step_type, tool_name,
                input_payload, output_payload, duration_ms
            )
            VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s);
        """
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    sql,
                    (
                        run_id,
                        user_id,
                        step_index,
                        step_type,
                        tool_name,
                        json.dumps(input_payload, ensure_ascii=False),
                        json.dumps(output_payload, ensure_ascii=False),
                        duration_ms,
                    ),
                )

    async def get_run_trace(self, run_id: UUID, user_id: UUID) -> dict[str, Any] | None:
        run_sql = "SELECT * FROM agent_runs WHERE id = %s AND user_id = %s;"
        steps_sql = """
            SELECT step_index, step_type, tool_name, input_payload, output_payload, duration_ms, status, created_at
            FROM run_steps
            WHERE run_id = %s AND user_id = %s
            ORDER BY step_index ASC, id ASC;
        """
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(run_sql, (run_id, user_id))
                run_row = await cur.fetchone()
                if not run_row:
                    return None
                await cur.execute(steps_sql, (run_id, user_id))
                steps = [dict(r) for r in await cur.fetchall()]
                return {"run": dict(run_row), "steps": steps}
