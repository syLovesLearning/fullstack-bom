"""企业物料库存仓库（支持模糊名称检索与安全库存预警判定）。"""

from typing import Any

from psycopg_pool import AsyncConnectionPool


class InventoryRepo:
    def __init__(self, pool: AsyncConnectionPool) -> None:
        self._pool = pool

    async def get_stock_by_skus(self, skus: list[str], limit: int = 200) -> list[dict[str, Any]]:
        """按 SKU 精确批量查库存（BOM 齐套核查的主匹配路径）。"""
        if not skus:
            return []
        sql = """
            SELECT id, sku, item_name, category, spec, stock_qty::float AS stock_qty,
                   safety_stock::float AS safety_stock, unit, warehouse,
                   (stock_qty < safety_stock) AS is_low_stock
            FROM inventory_items
            WHERE sku = ANY(%s)
            LIMIT %s;
        """
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, (skus, limit))
                return [dict(r) for r in await cur.fetchall()]

    async def search_by_name(self, keyword: str, limit: int = 10) -> list[dict[str, Any]]:
        pattern = f"%{keyword.strip()}%"
        sql = """
            SELECT id, sku, item_name, category, spec, stock_qty, safety_stock, unit, warehouse,
                   (stock_qty < safety_stock) AS is_low_stock
            FROM inventory_items
            WHERE item_name ILIKE %s OR spec ILIKE %s OR category ILIKE %s OR sku ILIKE %s
            ORDER BY (stock_qty < safety_stock) DESC, id ASC
            LIMIT %s;
        """
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, (pattern, pattern, pattern, pattern, limit))
                return [dict(r) for r in await cur.fetchall()]
