"""BOM 仓库：独立库 bom_db 读写与自动增量列迁移（强制 user_id 隔离）。"""

from typing import Any
from uuid import UUID

from psycopg_pool import AsyncConnectionPool

from src.repositories.bom_quote_repo import insert_quote_snapshot, list_quote_snapshots
from src.repositories.bom_schema import run_v3_migration


class BomRepo:
    def __init__(self, pool: AsyncConnectionPool) -> None:
        self._pool = pool
        self._migrated = False

    async def ensure_v3_schema(self) -> None:
        if self._migrated:
            return
        await run_v3_migration(self._pool)
        self._migrated = True

    async def list_items(self, user_id: UUID) -> list[dict[str, Any]]:
        await self.ensure_v3_schema()
        sql = "SELECT id, sku_code, name, category, sub_type, unit, base_price::float AS base_price, created_at FROM bom_items WHERE user_id = %s AND is_active = TRUE ORDER BY created_at DESC;"
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, (user_id,))
                return [dict(r) for r in await cur.fetchall()]

    async def upsert_item(self, user_id: UUID, data: dict[str, Any]) -> dict[str, Any]:
        await self.ensure_v3_schema()
        sql = """
            INSERT INTO bom_items (user_id, sku_code, name, category, sub_type, unit, base_price)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (user_id, sku_code) DO UPDATE
            SET name = EXCLUDED.name, category = EXCLUDED.category, sub_type = EXCLUDED.sub_type,
                unit = EXCLUDED.unit, base_price = EXCLUDED.base_price, is_active = TRUE, updated_at = NOW()
            RETURNING id, sku_code, name, category, sub_type, unit, base_price::float AS base_price, created_at;
        """
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, (user_id, data["sku_code"], data["name"], data["category"], data["sub_type"], data["unit"], data["base_price"]))
                return dict(await cur.fetchone())  # type: ignore[arg-type]

    async def find_referencing_parents(self, item_id: UUID, user_id: UUID) -> list[str]:
        sql = """
            SELECT DISTINCT p.sku_code || ' · ' || p.name AS parent_label
            FROM bom_edges e JOIN bom_headers h ON e.bom_header_id = h.id JOIN bom_items p ON h.item_id = p.id
            WHERE e.user_id = %s AND e.child_item_id = %s AND e.is_active = TRUE AND p.is_active = TRUE;
        """
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, (user_id, item_id))
                return [r["parent_label"] for r in await cur.fetchall()]

    async def soft_delete_item(self, item_id: UUID, user_id: UUID) -> bool:
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("UPDATE bom_items SET is_active = FALSE, updated_at = NOW() WHERE id = %s AND user_id = %s RETURNING id;", (item_id, user_id))
                return await cur.fetchone() is not None

    async def get_or_create_header(self, user_id: UUID, item_id: UUID) -> UUID:
        # INSERT ON CONFLICT 消除 SELECT-then-INSERT 竞态（并发创建撞 UNIQUE(item_id, version) 直接 500）
        sql = """
            INSERT INTO bom_headers (user_id, item_id, version, status)
            VALUES (%s, %s, 'V1.0', 'ACTIVE')
            ON CONFLICT (item_id, version) DO UPDATE SET status = 'ACTIVE'
            RETURNING id;
        """
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, (user_id, item_id))
                return (await cur.fetchone())["id"]  # type: ignore[index]

    async def list_edges(self, user_id: UUID, parent_id: UUID) -> list[dict[str, Any]]:
        await self.ensure_v3_schema()
        sql = """
            SELECT e.id, h.item_id AS parent_item_id, e.child_item_id, c.sku_code AS child_sku, c.name AS child_name,
                   c.category AS child_category, c.sub_type AS child_sub_type, c.unit AS child_unit, c.base_price::float AS child_price,
                   e.qty_mode, e.base_qty::float AS base_qty, e.formula_expr, e.extra_cost_expr,
                   e.remnant_policy, e.unit_pack_size::float AS unit_pack_size, e.min_remnant::float AS min_remnant,
                   e.loss_rate::float AS loss_rate, e.float_factor::float AS float_factor, e.bom_group, e.cost_group
            FROM bom_edges e JOIN bom_headers h ON e.bom_header_id = h.id JOIN bom_items c ON e.child_item_id = c.id
            WHERE e.user_id = %s AND h.item_id = %s AND h.status = 'ACTIVE' AND e.is_active = TRUE AND c.is_active = TRUE
            ORDER BY e.created_at ASC;
        """
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, (user_id, parent_id))
                return [dict(r) for r in await cur.fetchall()]

    async def list_all_edges(self, user_id: UUID) -> list[dict[str, Any]]:
        await self.ensure_v3_schema()
        sql = """
            SELECT e.id, h.item_id AS parent_id, e.child_item_id AS child_id, e.qty_mode, e.base_qty::float AS base_qty,
                   e.formula_expr, e.extra_cost_expr, e.remnant_policy, e.unit_pack_size::float AS unit_pack_size,
                   e.min_remnant::float AS min_remnant, e.loss_rate::float AS loss_rate,
                   e.float_factor::float AS float_factor, e.bom_group, e.cost_group
            FROM bom_edges e JOIN bom_headers h ON e.bom_header_id = h.id JOIN bom_items c ON e.child_item_id = c.id
            WHERE e.user_id = %s AND h.status = 'ACTIVE' AND e.is_active = TRUE AND c.is_active = TRUE;
        """
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, (user_id,))
                return [dict(r) for r in await cur.fetchall()]

    async def add_edge(self, user_id: UUID, header_id: UUID, data: dict[str, Any]) -> dict[str, Any]:
        sql = """
            INSERT INTO bom_edges (user_id, bom_header_id, child_item_id, qty_mode, base_qty, formula_expr,
                                   extra_cost_expr, remnant_policy, unit_pack_size, min_remnant, loss_rate, float_factor, bom_group, cost_group)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id, child_item_id, qty_mode, base_qty::float AS base_qty, formula_expr, extra_cost_expr,
                      remnant_policy, unit_pack_size::float AS unit_pack_size, min_remnant::float AS min_remnant,
                      loss_rate::float AS loss_rate, float_factor::float AS float_factor, bom_group, cost_group;
        """
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    sql,
                    (user_id, header_id, data["child_item_id"], data["qty_mode"], data["base_qty"], data.get("formula_expr", ""),
                     data.get("extra_cost_expr", ""), data.get("remnant_policy", "CONTINUOUS"), data.get("unit_pack_size", 1.0),
                     data.get("min_remnant", 0.0), data.get("loss_rate", 0.0), data.get("float_factor", 1.0), data["bom_group"], data["cost_group"]),
                )
                return dict(await cur.fetchone())  # type: ignore[arg-type]

    async def add_edges_batch(self, user_id: UUID, header_id: UUID, rows: list[dict[str, Any]]) -> None:
        """单事务批量写入 BOM 子件（executemany），用于 clone 与 seed 的 O(E) 写入路径。"""
        sql = """
            INSERT INTO bom_edges (user_id, bom_header_id, child_item_id, qty_mode, base_qty, formula_expr,
                                   extra_cost_expr, remnant_policy, unit_pack_size, min_remnant, loss_rate,
                                   float_factor, bom_group, cost_group)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
        """
        params = [
            (user_id, header_id, r["child_item_id"], r["qty_mode"], r["base_qty"], r.get("formula_expr", ""),
             r.get("extra_cost_expr", ""), r.get("remnant_policy", "CONTINUOUS"), r.get("unit_pack_size", 1.0),
             r.get("min_remnant", 0.0), r.get("loss_rate", 0.0), r.get("float_factor", 1.0), r["bom_group"], r["cost_group"])
            for r in rows
        ]
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.executemany(sql, params)

    async def update_edge(self, edge_id: UUID, user_id: UUID, data: dict[str, Any]) -> dict[str, Any] | None:
        sql = """
            UPDATE bom_edges
            SET qty_mode = %s, base_qty = %s, formula_expr = %s, extra_cost_expr = %s, remnant_policy = %s,
                unit_pack_size = %s, min_remnant = %s, loss_rate = %s, float_factor = %s, bom_group = %s, cost_group = %s
            WHERE id = %s AND user_id = %s AND is_active = TRUE
            RETURNING id, child_item_id, qty_mode, base_qty::float AS base_qty, formula_expr, extra_cost_expr,
                      remnant_policy, unit_pack_size::float AS unit_pack_size, min_remnant::float AS min_remnant,
                      loss_rate::float AS loss_rate, float_factor::float AS float_factor, bom_group, cost_group;
        """
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    sql,
                    (data["qty_mode"], data["base_qty"], data.get("formula_expr", ""), data.get("extra_cost_expr", ""),
                     data.get("remnant_policy", "CONTINUOUS"), data.get("unit_pack_size", 1.0), data.get("min_remnant", 0.0),
                     data.get("loss_rate", 0.0), data["float_factor"], data["bom_group"], data["cost_group"], edge_id, user_id),
                )
                row = await cur.fetchone()
                return dict(row) if row else None

    async def get_edge(self, edge_id: UUID, user_id: UUID) -> dict[str, Any] | None:
        """取单条边的当前父级与子件，供拖拽移动时做环检测与回滚定位。"""
        sql = """
            SELECT e.id, h.item_id AS parent_id, e.child_item_id AS child_id
            FROM bom_edges e JOIN bom_headers h ON e.bom_header_id = h.id
            WHERE e.id = %s AND e.user_id = %s AND e.is_active = TRUE AND h.status = 'ACTIVE';
        """
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, (edge_id, user_id))
                row = await cur.fetchone()
                return dict(row) if row else None

    async def move_edge(self, edge_id: UUID, user_id: UUID, header_id: UUID) -> bool:
        """把已有边挂到新父级的 header 下（拖拽换父级）。"""
        sql = "UPDATE bom_edges SET bom_header_id = %s WHERE id = %s AND user_id = %s AND is_active = TRUE RETURNING id;"
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, (header_id, edge_id, user_id))
                return await cur.fetchone() is not None

    async def soft_delete_edge(self, edge_id: UUID, user_id: UUID) -> bool:
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("UPDATE bom_edges SET is_active = FALSE WHERE id = %s AND user_id = %s RETURNING id;", (edge_id, user_id))
                return await cur.fetchone() is not None

    async def insert_quote_snapshot(self, user_id: UUID, row: dict[str, Any]) -> dict[str, Any]:
        await self.ensure_v3_schema()
        return await insert_quote_snapshot(self._pool, user_id, row)

    async def list_quote_snapshots(self, user_id: UUID) -> list[dict[str, Any]]:
        await self.ensure_v3_schema()
        return await list_quote_snapshots(self._pool, user_id)
