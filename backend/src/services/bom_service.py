"""BOM 业务编排服务：支持余料阈值算料、iif() 特殊附加成本、报价快照与跨库库存齐套核查。"""

from typing import Any
from uuid import UUID, uuid4

from src.repositories.bom_repo import BomRepo
from src.services.bom_formula import calc_remnant_qty, safe_eval_formula

SEED_ITEMS: list[dict[str, Any]] = [
    {"sku_code": "PROD-GGD-01", "name": "GGD标准低压配电柜", "category": "PRODUCT", "sub_type": "STANDARD", "unit": "台", "base_price": 0.0},
    {"sku_code": "SEMI-FRAME-01", "name": "柜体钣金骨架(半成品)", "category": "SEMI_FINISHED", "sub_type": "STANDARD", "unit": "套", "base_price": 0.0},
    {"sku_code": "SEMI-DRAWER-01", "name": "标准抽屉单元(半成品)", "category": "SEMI_FINISHED", "sub_type": "STANDARD", "unit": "套", "base_price": 0.0},
    {"sku_code": "MAT-STEEL-2MM", "name": "2.0mm冷轧钢板(整块200kg)", "category": "BASE_MATERIAL", "sub_type": "NON_FIXED", "unit": "kg", "base_price": 5.8},
    {"sku_code": "MAT-COPPER-BAR", "name": "TMY主母线铜排", "category": "BASE_MATERIAL", "sub_type": "NON_FIXED", "unit": "kg", "base_price": 86.0},
    {"sku_code": "OUT-BREAKER-250", "name": "塑壳断路器3P-250A(外购)", "category": "OUTSOURCED", "sub_type": "FIXED", "unit": "台", "base_price": 680.0},
    {"sku_code": "LAB-INT-ASSY", "name": "内部装配与二次接线(人工-内)", "category": "LABOR", "sub_type": "INTERNAL", "unit": "工时", "base_price": 65.0},
    {"sku_code": "LAB-EXT-PAINT", "name": "外协静电喷塑(人工-外/特殊工艺)", "category": "LABOR", "sub_type": "EXTERNAL", "unit": "㎡", "base_price": 35.0},
    {"sku_code": "MAC-LASER-CUT", "name": "光纤激光切割台班(机械)", "category": "MACHINE", "sub_type": "SPECIAL_PROCESS", "unit": "台班", "base_price": 180.0},
]


class BomService:
    def __init__(self, repo: BomRepo, inventory_repo: Any = None) -> None:
        self._repo = repo
        self._inv_repo = inventory_repo

    async def list_items(self, user_id: UUID) -> list[dict[str, Any]]:
        return await self._repo.list_items(user_id)

    async def upsert_item(self, user_id: UUID, data: dict[str, Any]) -> dict[str, Any]:
        return await self._repo.upsert_item(user_id, data)

    async def delete_item(self, item_id: UUID, user_id: UUID) -> bool:
        refs = await self._repo.find_referencing_parents(item_id, user_id)
        if refs:
            raise ValueError(f"该物料仍被以下 BOM 引用，请先移除子件关系：{', '.join(refs)}")
        return await self._repo.soft_delete_item(item_id, user_id)

    async def list_edges(self, user_id: UUID, parent_id: UUID) -> list[dict[str, Any]]:
        return await self._repo.list_edges(user_id, parent_id)

    async def add_edge(self, user_id: UUID, parent_id: UUID, data: dict[str, Any]) -> dict[str, Any]:
        child_id = data["child_item_id"]
        if parent_id == child_id:
            raise ValueError("不能将物料挂载为自身的子件")
        all_edges = await self._repo.list_all_edges(user_id)
        adj: dict[UUID, list[UUID]] = {}
        for edge in all_edges:
            adj.setdefault(edge["parent_id"], []).append(edge["child_id"])
        stack, visited = [child_id], set()
        while stack:
            curr = stack.pop()
            if curr == parent_id:
                raise ValueError("检测到 BOM 递归环路，禁止添加该子件")
            if curr not in visited:
                visited.add(curr)
                stack.extend(adj.get(curr, []))
        header_id = await self._repo.get_or_create_header(user_id, parent_id)
        return await self._repo.add_edge(user_id, header_id, data)

    async def update_edge(self, user_id: UUID, edge_id: UUID, data: dict[str, Any]) -> dict[str, Any] | None:
        return await self._repo.update_edge(edge_id, user_id, data)

    async def delete_edge(self, edge_id: UUID, user_id: UUID) -> bool:
        return await self._repo.soft_delete_edge(edge_id, user_id)

    async def clone_bom(self, user_id: UUID, source_id: UUID, target_id: UUID) -> int:
        if source_id == target_id:
            raise ValueError("源父级与目标父级不能相同")
        src_edges = await self._repo.list_edges(user_id, source_id)
        if not src_edges:
            raise ValueError("源 BOM 下暂无可克隆的子件")
        for e in src_edges:
            await self.add_edge(user_id, target_id, {
                "child_item_id": e["child_item_id"], "qty_mode": e["qty_mode"], "base_qty": e["base_qty"],
                "formula_expr": e["formula_expr"], "extra_cost_expr": e.get("extra_cost_expr", ""),
                "remnant_policy": e.get("remnant_policy", "CONTINUOUS"), "unit_pack_size": e.get("unit_pack_size", 1.0),
                "min_remnant": e.get("min_remnant", 0.0), "loss_rate": e.get("loss_rate", 0.0),
                "float_factor": e["float_factor"], "bom_group": e["bom_group"], "cost_group": e["cost_group"],
            })
        return len(src_edges)

    async def seed_demo_bom(self, user_id: UUID) -> dict[str, int]:
        sku_map: dict[str, UUID] = {}
        for item in SEED_ITEMS:
            sku_map[item["sku_code"]] = (await self._repo.upsert_item(user_id, item))["id"]
        if await self._repo.list_all_edges(user_id):
            return {"seeded_items": len(sku_map), "seeded_edges": 0}
        demo_relations = [
            ("PROD-GGD-01", "SEMI-FRAME-01", "FIXED", 1.0, "", "", "CONTINUOUS", 1.0, 0.0, 0.0, 1.0, "材料", "半成品"),
            ("PROD-GGD-01", "SEMI-DRAWER-01", "FIXED", 2.0, "", "", "CONTINUOUS", 1.0, 0.0, 0.0, 1.0, "材料", "半成品"),
            ("PROD-GGD-01", "MAT-COPPER-BAR", "FORMULA_3D", 14.5, "(dist3d(0, H*0.8, 0, W*0.9, H*0.2, D*0.8) / 1000.0) * 6.8", "iif(W >= 1000, 120, 0)", "CONTINUOUS", 1.0, 0.0, 0.05, 1.0, "材料", "基材"),
            ("PROD-GGD-01", "OUT-BREAKER-250", "FIXED", 1.0, "", "", "CONTINUOUS", 1.0, 0.0, 0.0, 1.0, "材料", "基材"),
            ("PROD-GGD-01", "LAB-INT-ASSY", "FIXED", 4.5, "", "", "CONTINUOUS", 1.0, 0.0, 0.0, 1.0, "人工", "人工费"),
            ("PROD-GGD-01", "MAC-LASER-CUT", "FIXED", 1.0, "", "", "CONTINUOUS", 1.0, 0.0, 0.0, 1.0, "机械", "人工费"),
            ("SEMI-FRAME-01", "MAT-STEEL-2MM", "FORMULA_3D", 180.0, "(2*(H*W + H*D + W*D) / 1000000.0) * T * 7.85", "", "THRESHOLD_SCRAP", 200.0, 50.0, 0.0, 1.0, "材料", "基材"),
            ("SEMI-FRAME-01", "LAB-EXT-PAINT", "FORMULA_3D", 9.6, "(2*(H*W + H*D) / 1000000.0) * 1.4", "", "CONTINUOUS", 1.0, 0.0, 0.0, 1.0, "人工", "人工费"),
            ("SEMI-DRAWER-01", "MAT-STEEL-2MM", "FIXED", 13.5, "", "", "CONTINUOUS", 1.0, 0.0, 0.08, 1.0, "材料", "基材"),
            ("SEMI-DRAWER-01", "LAB-INT-ASSY", "FIXED", 1.2, "", "", "CONTINUOUS", 1.0, 0.0, 0.0, 1.0, "人工", "人工费"),
        ]
        for p_s, c_s, mode, q, expr, ext, pol, pack, mrem, loss, flt, bg, cg in demo_relations:
            await self.add_edge(user_id, sku_map[p_s], {
                "child_item_id": sku_map[c_s], "qty_mode": mode, "base_qty": q, "formula_expr": expr,
                "extra_cost_expr": ext, "remnant_policy": pol, "unit_pack_size": pack,
                "min_remnant": mrem, "loss_rate": loss, "float_factor": flt, "bom_group": bg, "cost_group": cg,
            })
        return {"seeded_items": len(sku_map), "seeded_edges": len(demo_relations)}

    async def build_rollup_tree(self, user_id: UUID, root_id: UUID, params_3d: dict[str, float] | None = None) -> dict[str, Any]:
        items = {i["id"]: i for i in await self._repo.list_items(user_id)}
        if root_id not in items:
            raise ValueError("未找到目标根节点物料")
        env = params_3d or {"H": 2200.0, "W": 800.0, "D": 600.0, "T": 2.0}
        edges_by_parent: dict[UUID, list[dict[str, Any]]] = {}
        for e in await self._repo.list_all_edges(user_id):
            edges_by_parent.setdefault(e["parent_id"], []).append(e)
        cost_summary = {"基材(固定)": 0.0, "基材(非固定)": 0.0, "人工费(内)": 0.0, "人工费(外/机械)": 0.0}
        bom_summary = {"人工": 0.0, "材料": 0.0, "机械": 0.0}
        flat_materials: list[dict[str, Any]] = []

        def _walk(item_id: UUID, mult_qty: float, b_grp: str, edge_meta: dict[str, Any] | None, visited: set[UUID]) -> dict[str, Any]:
            it = items[item_id]
            ch_edges = edges_by_parent.get(item_id, [])
            if not ch_edges or item_id in visited:
                pol = edge_meta.get("remnant_policy", "CONTINUOUS") if edge_meta else "CONTINUOUS"
                pack = float(edge_meta.get("unit_pack_size", 1.0)) if edge_meta else 1.0
                mrem = float(edge_meta.get("min_remnant", 0.0)) if edge_meta else 0.0
                bill_qty, scrap_qty, rem_note = calc_remnant_qty(mult_qty, pack, pol, mrem)
                extra_cost = safe_eval_formula(edge_meta.get("extra_cost_expr", "") if edge_meta else "", {**env, "qty": bill_qty, "base_qty": mult_qty}, 0.0)
                sub = round(bill_qty * float(it["base_price"]) + extra_cost, 2)
                if it["category"] == "LABOR":
                    k = "人工费(内)" if it["sub_type"] == "INTERNAL" else "人工费(外/机械)"
                    cost_summary[k] = round(cost_summary[k] + sub, 2)
                elif it["category"] == "MACHINE":
                    cost_summary["人工费(外/机械)"] = round(cost_summary["人工费(外/机械)"] + sub, 2)
                else:
                    k = "基材(非固定)" if it["sub_type"] == "NON_FIXED" else "基材(固定)"
                    cost_summary[k] = round(cost_summary[k] + sub, 2)
                    flat_materials.append({"sku_code": it["sku_code"], "name": it["name"], "unit": it["unit"], "required_qty": bill_qty})
                if b_grp in bom_summary:
                    bom_summary[b_grp] = round(bom_summary[b_grp] + sub, 2)
                return {**it, "qty": bill_qty, "raw_qty": round(mult_qty, 3), "scrap_qty": scrap_qty, "remnant_note": rem_note, "extra_cost": round(extra_cost, 2), "subtotal": sub, "children": []}

            children_nodes, node_total = [], 0.0
            for ed in ch_edges:
                raw_q = safe_eval_formula(ed["formula_expr"], {**env, "base_qty": float(ed["base_qty"])}, float(ed["base_qty"])) if ed["qty_mode"] == "FORMULA_3D" else float(ed["base_qty"])
                eff_qty = mult_qty * raw_q * (1.0 + float(ed.get("loss_rate", 0.0))) * float(ed["float_factor"])
                ch_node = _walk(ed["child_id"], eff_qty, ed["bom_group"], ed, visited | {item_id})
                ch_node.update({"edge_id": ed["id"], "qty_mode": ed["qty_mode"], "formula_expr": ed["formula_expr"], "extra_cost_expr": ed.get("extra_cost_expr", ""), "remnant_policy": ed.get("remnant_policy", "CONTINUOUS"), "float_factor": ed["float_factor"]})
                children_nodes.append(ch_node)
                node_total += ch_node["subtotal"]
            return {**it, "qty": round(mult_qty, 3), "subtotal": round(node_total, 2), "children": children_nodes}

        root_node = _walk(root_id, 1.0, "成品", None, set())
        return {"root": root_node, "params_3d": env, "cost_summary": cost_summary, "bom_summary": bom_summary, "flat_materials": flat_materials}

    async def save_quote(self, user_id: UUID, req: dict[str, Any]) -> dict[str, Any]:
        env = {"H": req["h"], "W": req["w"], "D": req["d"], "T": req["t"]}
        res = await self.build_rollup_tree(user_id, req["root_id"], env)
        direct_cost = float(res["root"]["subtotal"])
        final_price = round(direct_cost * (1.0 + req["margin_rate"]) * (1.0 + req["tax_rate"]), 2)
        return await self._repo.insert_quote_snapshot(user_id, {
            "quote_no": f"QT-{uuid4().hex[:8].upper()}", "root_item_id": req["root_id"], "root_name": res["root"]["name"],
            "params_3d": env, "result": res, "direct_cost": direct_cost, "final_price": final_price, "note": req.get("note", ""),
        })

    async def list_quotes(self, user_id: UUID) -> list[dict[str, Any]]:
        return await self._repo.list_quote_snapshots(user_id)

    async def check_stock(self, user_id: UUID, root_id: UUID, env: dict[str, float]) -> list[dict[str, Any]]:
        res = await self.build_rollup_tree(user_id, root_id, env)
        agg: dict[str, dict[str, Any]] = {}
        for m in res["flat_materials"]:
            k = m["sku_code"]
            if k not in agg:
                agg[k] = {**m}
            else:
                agg[k]["required_qty"] = round(agg[k]["required_qty"] + m["required_qty"], 3)
        out = []
        for m in agg.values():
            hits = await self._inv_repo.search_items(m["name"][:4]) if self._inv_repo else []
            stock_qty = float(hits[0]["stock_qty"]) if hits else 0.0
            wh = hits[0]["warehouse"] if hits else "未建档"
            status = "齐套" if hits and stock_qty >= m["required_qty"] else ("缺料" if hits else "未建档")
            out.append({**m, "stock_qty": stock_qty, "warehouse": wh, "status": status})
        return out
