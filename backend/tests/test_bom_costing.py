"""BOM 成本试算（build_rollup_tree）离线单元测试：FakeRepo 内存数据，不依赖数据库。

覆盖：多级用量乘法链、FORMULA_3D 公式与损耗率、THRESHOLD_SCRAP 余料报废、
iif() 特殊附加成本与人工费分类汇总、根节点不存在时的报错。
"""

import asyncio
from typing import Any
from uuid import UUID, uuid4

import pytest

from src.services.bom_service import BomService


class FakeBomRepo:
    def __init__(self, items: list[dict[str, Any]], edges: list[dict[str, Any]]) -> None:
        self._items = items
        self._edges = edges

    async def list_items(self, user_id: UUID) -> list[dict[str, Any]]:
        return self._items

    async def list_all_edges(self, user_id: UUID) -> list[dict[str, Any]]:
        return self._edges


def _item(sku: str, category: str, sub_type: str, price: float) -> dict[str, Any]:
    return {"id": uuid4(), "sku_code": sku, "name": f"物料-{sku}", "category": category,
            "sub_type": sub_type, "unit": "个", "base_price": price}


def _edge(parent: UUID, child: UUID, **overrides: Any) -> dict[str, Any]:
    base = {"id": uuid4(), "parent_id": parent, "child_id": child, "qty_mode": "FIXED",
            "base_qty": 1.0, "formula_expr": "", "extra_cost_expr": "",
            "remnant_policy": "CONTINUOUS", "unit_pack_size": 1.0, "min_remnant": 0.0,
            "loss_rate": 0.0, "float_factor": 1.0, "bom_group": "材料", "cost_group": "基材"}
    base.update(overrides)
    return base


def _service(items: list[dict[str, Any]], edges: list[dict[str, Any]]) -> BomService:
    return BomService(repo=FakeBomRepo(items, edges), inventory_repo=None)


def test_rollup_multiplies_qty_across_levels_with_formula_and_loss() -> None:
    async def _run() -> None:
        prod, semi = _item("PROD", "PRODUCT", "STANDARD", 0.0), _item("SEMI", "SEMI_FINISHED", "STANDARD", 0.0)
        mat = _item("MAT", "BASE_MATERIAL", "NON_FIXED", 10.0)
        edges = [
            _edge(prod["id"], semi["id"], base_qty=2.0),
            _edge(semi["id"], mat["id"], qty_mode="FORMULA_3D", base_qty=1.0,
                  formula_expr="H * W / 1000000.0", loss_rate=0.1),
        ]
        res = await _service([prod, semi, mat], edges).build_rollup_tree(
            user_id=uuid4(), root_id=prod["id"], params_3d={"H": 2000.0, "W": 1000.0, "D": 500.0, "T": 2.0}
        )
        # 用量链：root(1) × 半成品(2) × 公式(H*W/1e6=2.0) × (1+损耗0.1) = 4.4
        mat_node = res["root"]["children"][0]["children"][0]
        assert mat_node["qty"] == 4.4
        assert mat_node["subtotal"] == 44.0
        assert res["root"]["subtotal"] == 44.0
        assert res["cost_summary"]["基材(非固定)"] == 44.0
        assert res["bom_summary"]["材料"] == 44.0
        assert res["flat_materials"][0]["required_qty"] == 4.4

    asyncio.run(_run())


def test_rollup_threshold_scrap_bills_whole_pack() -> None:
    async def _run() -> None:
        prod, mat = _item("PROD", "PRODUCT", "STANDARD", 0.0), _item("MAT", "BASE_MATERIAL", "NON_FIXED", 1.0)
        edges = [
            _edge(prod["id"], mat["id"], base_qty=180.0, remnant_policy="THRESHOLD_SCRAP",
                  unit_pack_size=200.0, min_remnant=50.0),
        ]
        res = await _service([prod, mat], edges).build_rollup_tree(
            user_id=uuid4(), root_id=prod["id"], params_3d={"H": 2200.0, "W": 800.0, "D": 600.0, "T": 2.0}
        )
        mat_node = res["root"]["children"][0]
        # 180 < 整包 200 且余料 20 < 阈值 50 → 整块报废计价 200
        assert mat_node["qty"] == 200.0
        assert mat_node["scrap_qty"] == 20.0
        assert "整块报废" in mat_node["remnant_note"]
        assert mat_node["subtotal"] == 200.0

    asyncio.run(_run())


def test_rollup_labor_cost_with_iif_extra_cost() -> None:
    async def _run() -> None:
        prod = _item("PROD", "PRODUCT", "STANDARD", 0.0)
        labor = _item("LAB", "LABOR", "INTERNAL", 65.0)
        edges = [
            _edge(prod["id"], labor["id"], base_qty=4.5, bom_group="人工", cost_group="人工费",
                  extra_cost_expr="iif(H >= 1000, 120, 0)"),
        ]
        res = await _service([prod, labor], edges).build_rollup_tree(
            user_id=uuid4(), root_id=prod["id"], params_3d={"H": 2200.0, "W": 800.0, "D": 600.0, "T": 2.0}
        )
        # 4.5 工时 × 65 + iif(H>=1000,120,0) = 292.5 + 120
        labor_node = res["root"]["children"][0]
        assert labor_node["extra_cost"] == 120.0
        assert labor_node["subtotal"] == 412.5
        assert res["cost_summary"]["人工费(内)"] == 412.5
        assert res["bom_summary"]["人工"] == 412.5

    asyncio.run(_run())


def test_rollup_unknown_root_raises() -> None:
    async def _run() -> None:
        prod = _item("PROD", "PRODUCT", "STANDARD", 0.0)
        with pytest.raises(ValueError, match="未找到目标根节点物料"):
            await _service([prod], []).build_rollup_tree(
                user_id=uuid4(), root_id=uuid4(), params_3d={"H": 2200.0, "W": 800.0, "D": 600.0, "T": 2.0}
            )

    asyncio.run(_run())
