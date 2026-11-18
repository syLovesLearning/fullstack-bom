"""BOM 成本试算服务：多级递归算价、余料阈值核算、报价快照与跨库库存齐套核查。"""

import json
from typing import Any
from uuid import UUID, uuid4

from src.repositories.bom_repo import BomRepo
from src.services.bom_formula import calc_remnant_qty, safe_eval_formula

DEFAULT_PARAMS_3D = {"H": 2200.0, "W": 800.0, "D": 600.0, "T": 2.0}


class BomCostingService:
    def __init__(self, repo: BomRepo, inventory_repo: Any = None) -> None:
        self._repo = repo
        self._inv_repo = inventory_repo

    async def build_rollup_tree(self, user_id: UUID, root_id: UUID, params_3d: dict[str, float] | None = None) -> dict[str, Any]:
        items = {i["id"]: i for i in await self._repo.list_items(user_id)}
        if root_id not in items:
            raise ValueError("未找到目标根节点物料")
        env = params_3d or dict(DEFAULT_PARAMS_3D)
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
            if m["sku_code"] not in agg:
                agg[m["sku_code"]] = {**m}
            else:
                agg[m["sku_code"]]["required_qty"] = round(agg[m["sku_code"]]["required_qty"] + m["required_qty"], 3)
        stock_map = await self._fetch_stock_map(list(agg.keys()))
        out = []
        for sku, m in agg.items():
            row = stock_map.get(sku)
            if row is None and self._inv_repo is not None:
                hits = await self._inv_repo.search_by_name(m["name"][:4], limit=1)
                row = hits[0] if hits else None
            stock_qty = float(row["stock_qty"]) if row else 0.0
            wh = row["warehouse"] if row else "未建档"
            status = "齐套" if row and stock_qty >= m["required_qty"] else ("缺料" if row else "未建档")
            out.append({**m, "stock_qty": stock_qty, "warehouse": wh, "status": status})
        return out

    async def _fetch_stock_map(self, sku_codes: list[str]) -> dict[str, dict[str, Any]]:
        if self._inv_repo is None or not sku_codes:
            return {}
        rows = await self._inv_repo.get_stock_by_skus(sku_codes)
        return {r["sku"]: r for r in rows}


def quote_snapshot_to_json(row: dict[str, Any]) -> str:
    """报价快照 JSON 序列化辅助（UUID/Decimal 安全）。"""
    return json.dumps(row, ensure_ascii=False, default=str)
