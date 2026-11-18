"""报价快照持久化：BomRepo 委托到此模块，避免仓库文件超出行数上限。"""

import json
from typing import Any
from uuid import UUID

from psycopg_pool import AsyncConnectionPool


async def insert_quote_snapshot(pool: AsyncConnectionPool, user_id: UUID, row: dict[str, Any]) -> dict[str, Any]:
    sql = """
        INSERT INTO quote_snapshots (user_id, quote_no, root_item_id, root_name, params_3d_json, result_json, direct_cost, final_price, note)
        VALUES (%s, %s, %s, %s, %s::jsonb, %s::jsonb, %s, %s, %s)
        RETURNING id, quote_no, root_name, direct_cost::float AS direct_cost, final_price::float AS final_price, note, created_at;
    """
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                sql,
                (user_id, row["quote_no"], row["root_item_id"], row["root_name"],
                 json.dumps(row["params_3d"], default=str), json.dumps(row["result"], default=str),
                 row["direct_cost"], row["final_price"], row.get("note", "")),
            )
            return dict(await cur.fetchone())  # type: ignore[arg-type]


async def list_quote_snapshots(pool: AsyncConnectionPool, user_id: UUID) -> list[dict[str, Any]]:
    sql = "SELECT id, quote_no, root_name, params_3d_json, direct_cost::float AS direct_cost, final_price::float AS final_price, note, created_at FROM quote_snapshots WHERE user_id = %s ORDER BY created_at DESC LIMIT 20;"
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(sql, (user_id,))
            return [dict(r) for r in await cur.fetchall()]
