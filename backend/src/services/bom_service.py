"""BOM 业务编排门面：物料/结构 CRUD 与批量写入，成本试算委托 BomCostingService。"""

from typing import Any
from uuid import UUID

from src.repositories import bom_maint_repo
from src.repositories.bom_repo import BomRepo
from src.services.bom_costing import BomCostingService
from src.services.bom_seed import DEMO_RELATIONS, SEED_ITEMS


def _edge_payload(e: dict[str, Any]) -> dict[str, Any]:
    return {
        "child_item_id": e["child_item_id"], "qty_mode": e["qty_mode"], "base_qty": e["base_qty"],
        "formula_expr": e["formula_expr"], "extra_cost_expr": e.get("extra_cost_expr", ""),
        "remnant_policy": e.get("remnant_policy", "CONTINUOUS"), "unit_pack_size": e.get("unit_pack_size", 1.0),
        "min_remnant": e.get("min_remnant", 0.0), "loss_rate": e.get("loss_rate", 0.0),
        "float_factor": e["float_factor"], "bom_group": e["bom_group"], "cost_group": e["cost_group"],
    }


class BomService:
    def __init__(self, repo: BomRepo, inventory_repo: Any = None) -> None:
        self._repo = repo
        self._costing = BomCostingService(repo, inventory_repo)

    # ---------- 物料 CRUD ----------

    async def list_items(self, user_id: UUID) -> list[dict[str, Any]]:
        return await self._repo.list_items(user_id)

    async def upsert_item(self, user_id: UUID, data: dict[str, Any]) -> dict[str, Any]:
        return await self._repo.upsert_item(user_id, data)

    async def delete_item(self, item_id: UUID, user_id: UUID) -> bool:
        refs = await self._repo.find_referencing_parents(item_id, user_id)
        if refs:
            raise ValueError(f"该物料仍被以下 BOM 引用，请先移除子件关系：{', '.join(refs)}")
        return await self._repo.soft_delete_item(item_id, user_id)

    # ---------- BOM 结构（父子关系） ----------

    async def list_edges(self, user_id: UUID, parent_id: UUID) -> list[dict[str, Any]]:
        return await self._repo.list_edges(user_id, parent_id)

    async def add_edge(self, user_id: UUID, parent_id: UUID, data: dict[str, Any]) -> dict[str, Any]:
        # 已知竞态（TOCTOU）：环检测与写入分属两个连接窗口，并发挂载可绕过检测。
        # demo 规模可接受；生产化时应将「拉边+检测+写 header+写边」收敛进单事务。
        await self._assert_acyclic(user_id, parent_id, [data["child_item_id"]])
        header_id = await self._repo.get_or_create_header(user_id, parent_id)
        return await self._repo.add_edge(user_id, header_id, data)

    async def add_edges_batch(self, user_id: UUID, parent_id: UUID, rows: list[dict[str, Any]]) -> int:
        """拖拽多选批量挂载：一次环检测 + 单事务 executemany，避免部分插入。

        已知竞态（TOCTOU）：环检测读边与批量写入不在同一事务，并发修改可能绕过检测，见 add_edge 注释。
        """
        await self._assert_acyclic(user_id, parent_id, [r["child_item_id"] for r in rows])
        header_id = await self._repo.get_or_create_header(user_id, parent_id)
        await self._repo.add_edges_batch(user_id, header_id, [_edge_payload(r) for r in rows])
        return len(rows)

    async def update_edge(self, user_id: UUID, edge_id: UUID, data: dict[str, Any]) -> dict[str, Any] | None:
        return await self._repo.update_edge(edge_id, user_id, data)

    async def delete_edge(self, edge_id: UUID, user_id: UUID) -> bool:
        return await self._repo.soft_delete_edge(edge_id, user_id)

    async def move_edge(self, user_id: UUID, edge_id: UUID, new_parent_id: UUID) -> dict[str, Any]:
        """拖拽换父级：边本身保留（公式/余料策略/附加费全部跟着走），只改挂载点。

        已知竞态（TOCTOU）：同 add_edge，环检测与 move 写入不在同一事务。
        DFS 会把待移动边按「旧挂载点仍在」计算——因边方向是 parent→child，旧边不影响
        child 可达性判定，语义安全；但并发新增边仍可能绕过检测。
        """
        edge = await self._repo.get_edge(edge_id, user_id)
        if edge is None:
            raise ValueError("未找到待移动的子件关系")
        if edge["parent_id"] == new_parent_id:
            raise ValueError("目标父级与当前父级相同，无需移动")
        await self._assert_acyclic(user_id, new_parent_id, [edge["child_id"]])
        header_id = await self._repo.get_or_create_header(user_id, new_parent_id)
        if not await self._repo.move_edge(edge_id, user_id, header_id):
            raise ValueError("移动失败，子件关系可能已被移除")
        return {"edge_id": str(edge_id), "parent_id": str(new_parent_id), "child_id": str(edge["child_id"])}

    async def _assert_acyclic(self, user_id: UUID, parent_id: UUID, child_ids: list[UUID]) -> None:
        """单次全量拉边 + 内存环检测：任一 child 已可达 parent 则挂载必成环。

        以 child_ids 为多源起点沿 parent->child 方向 DFS，命中 parent_id 即拒绝。
        """
        if parent_id in child_ids:
            raise ValueError("不能将物料挂载为自身的子件")
        adj: dict[UUID, list[UUID]] = {}
        for edge in await self._repo.list_all_edges(user_id):
            adj.setdefault(edge["parent_id"], []).append(edge["child_id"])
        stack, visited = list(child_ids), set()
        while stack:
            curr = stack.pop()
            if curr == parent_id:
                raise ValueError("检测到 BOM 递归环路，禁止添加该子件")
            if curr not in visited:
                visited.add(curr)
                stack.extend(adj.get(curr, []))

    async def clone_bom(self, user_id: UUID, source_id: UUID, target_id: UUID) -> int:
        if source_id == target_id:
            raise ValueError("源父级与目标父级不能相同")
        src_edges = await self._repo.list_edges(user_id, source_id)
        if not src_edges:
            raise ValueError("源 BOM 下暂无可克隆的子件")
        # 一次环检测覆盖全部子件；通过后单事务批量写入，避免 O(E²) 与部分插入
        await self._assert_acyclic(user_id, target_id, [e["child_item_id"] for e in src_edges])
        header_id = await self._repo.get_or_create_header(user_id, target_id)
        await self._repo.add_edges_batch(user_id, header_id, [_edge_payload(e) for e in src_edges])
        return len(src_edges)

    async def seed_demo_bom(self, user_id: UUID) -> dict[str, int]:
        sku_map: dict[str, UUID] = {}
        for item in SEED_ITEMS:
            sku_map[item["sku_code"]] = (await self._repo.upsert_item(user_id, item))["id"]
        if await self._repo.list_all_edges(user_id):
            return {"seeded_items": len(sku_map), "seeded_edges": 0}
        by_parent: dict[UUID, list[dict[str, Any]]] = {}
        for p_s, c_s, mode, q, expr, ext, pol, pack, mrem, loss, flt, bg, cg in DEMO_RELATIONS:
            by_parent.setdefault(sku_map[p_s], []).append({
                "child_item_id": sku_map[c_s], "qty_mode": mode, "base_qty": q, "formula_expr": expr,
                "extra_cost_expr": ext, "remnant_policy": pol, "unit_pack_size": pack,
                "min_remnant": mrem, "loss_rate": loss, "float_factor": flt, "bom_group": bg, "cost_group": cg,
            })
        seeded = 0
        for parent_id, rows in by_parent.items():
            header_id = await self._repo.get_or_create_header(user_id, parent_id)
            await self._repo.add_edges_batch(user_id, header_id, rows)
            seeded += len(rows)
        return {"seeded_items": len(sku_map), "seeded_edges": seeded}

    # ---------- 成本试算（委托 BomCostingService） ----------

    async def build_rollup_tree(self, user_id: UUID, root_id: UUID, params_3d: dict[str, float] | None = None) -> dict[str, Any]:
        return await self._costing.build_rollup_tree(user_id, root_id, params_3d)

    async def save_quote(self, user_id: UUID, req: dict[str, Any]) -> dict[str, Any]:
        return await self._costing.save_quote(user_id, req)

    async def list_quotes(self, user_id: UUID) -> list[dict[str, Any]]:
        return await self._costing.list_quotes(user_id)

    async def check_stock(self, user_id: UUID, root_id: UUID, env: dict[str, float]) -> list[dict[str, Any]]:
        return await self._costing.check_stock(user_id, root_id, env)

    async def where_used(self, user_id: UUID, item_id: UUID) -> list[dict[str, Any]]:
        return await bom_maint_repo.list_where_used(self._repo._pool, user_id, item_id)

    async def replace_item(self, user_id: UUID, old_id: UUID, new_id: UUID) -> int:
        if old_id == new_id:
            raise ValueError("旧物料与新物料不能相同")
        refs = await bom_maint_repo.list_where_used(self._repo._pool, user_id, old_id)
        for r in refs:
            await self._assert_acyclic(user_id, r["parent_id"], [new_id])
        return await bom_maint_repo.replace_child_item(self._repo._pool, user_id, old_id, new_id)

    async def batch_adjust_price(self, user_id: UUID, category: str, pct_delta: float) -> int:
        return await bom_maint_repo.batch_adjust_price(self._repo._pool, user_id, category, pct_delta)
