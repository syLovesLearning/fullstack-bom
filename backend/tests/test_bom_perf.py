"""200 节点多级递归 BOM + AST 3D 公式 + 余料阈值压测。"""

import asyncio
import time
from uuid import uuid4

from src.services.bom_costing import BomCostingService


class _PerfBomRepo:
    def __init__(self, n_nodes: int = 200) -> None:
        self.uid = uuid4()
        self.root_id = uuid4()
        self.items: list[dict] = [
            {"id": self.root_id, "sku_code": "PROD-PERF", "name": "压测整机", "category": "PRODUCT", "sub_type": "STANDARD", "unit": "台", "base_price": 0.0}
        ]
        self.edges: list[dict] = []
        semi_ids = [uuid4() for _ in range(10)]
        for idx, sid in enumerate(semi_ids):
            self.items.append({"id": sid, "sku_code": f"SEMI-{idx}", "name": f"半成品-{idx}", "category": "SEMI_FINISHED", "sub_type": "STANDARD", "unit": "套", "base_price": 0.0})
            self.edges.append({
                "id": uuid4(), "parent_id": self.root_id, "child_id": sid, "qty_mode": "FIXED", "base_qty": 1.0,
                "formula_expr": "", "extra_cost_expr": "", "remnant_policy": "CONTINUOUS", "unit_pack_size": 1.0,
                "min_remnant": 0.0, "loss_rate": 0.0, "float_factor": 1.0, "bom_group": "材料", "cost_group": "半成品",
            })
        for i in range(n_nodes - 11):
            lid = uuid4()
            parent = semi_ids[i % len(semi_ids)]
            self.items.append({"id": lid, "sku_code": f"MAT-{i}", "name": f"零件-{i}", "category": "BASE_MATERIAL", "sub_type": "NON_FIXED", "unit": "kg", "base_price": 12.5})
            self.edges.append({
                "id": uuid4(), "parent_id": parent, "child_id": lid, "qty_mode": "FORMULA_3D", "base_qty": 10.0,
                "formula_expr": "iif(W >= 800, (H * W / 100000.0) * T, base_qty)", "extra_cost_expr": "iif(W >= 1000, 15, 0)",
                "remnant_policy": "THRESHOLD_SCRAP", "unit_pack_size": 200.0, "min_remnant": 50.0,
                "loss_rate": 0.05, "float_factor": 1.0, "bom_group": "材料", "cost_group": "基材",
            })

    async def list_items(self, user_id):
        return self.items

    async def list_all_edges(self, user_id):
        return self.edges


def test_200_node_bom_rollup_under_50ms() -> None:
    repo = _PerfBomRepo(200)
    svc = BomCostingService(repo)  # type: ignore[arg-type]

    async def _run():
        t0 = time.perf_counter()
        res = await svc.build_rollup_tree(repo.uid, repo.root_id, {"H": 2200.0, "W": 1000.0, "D": 600.0, "T": 2.0})
        ms = (time.perf_counter() - t0) * 1000
        assert res["root"]["subtotal"] > 0
        assert len(res["flat_materials"]) == 189
        assert ms < 50.0, f"200-node BOM rollup too slow: {ms:.2f}ms"
        print(f"[BENCHMARK] 200-node BOM + AST + Remnant Rollup: {ms:.2f} ms")

    asyncio.run(_run())
