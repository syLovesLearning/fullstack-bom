"""BOM 维护扩展仓库：物料反查 (Where-Used)、批量替料与按大类批量调价（强制 user_id 隔离）。"""

from typing import Any
from uuid import UUID


async def list_where_used(pool: Any, user_id: UUID, item_id: UUID) -> list[dict[str, Any]]:
    sql = """
        SELECT h.item_id AS parent_id, p.sku_code AS parent_sku, p.name AS parent_name,
               p.category AS parent_category, e.id AS edge_id, e.qty_mode, e.base_qty::float AS base_qty
        FROM bom_edges e
        JOIN bom_headers h ON e.bom_header_id = h.id
        JOIN bom_items p ON h.item_id = p.id
        WHERE e.user_id = %s AND e.child_item_id = %s AND e.is_active = TRUE AND p.is_active = TRUE AND h.status = 'ACTIVE'
        ORDER BY p.sku_code ASC;
    """
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(sql, (user_id, item_id))
            return [dict(r) for r in await cur.fetchall()]


async def replace_child_item(pool: Any, user_id: UUID, old_item_id: UUID, new_item_id: UUID) -> int:
    sql = """
        UPDATE bom_edges
        SET child_item_id = %s
        WHERE user_id = %s AND child_item_id = %s AND is_active = TRUE;
    """
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(sql, (new_item_id, user_id, old_item_id))
            return cur.rowcount or 0


async def batch_adjust_price(pool: Any, user_id: UUID, category: str, pct_delta: float) -> int:
    sql = """
        UPDATE bom_items
        SET base_price = ROUND((base_price * (1.0 + %s / 100.0))::numeric, 2), updated_at = NOW()
        WHERE user_id = %s AND category = %s AND is_active = TRUE;
    """
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(sql, (pct_delta, user_id, category))
            return cur.rowcount or 0
