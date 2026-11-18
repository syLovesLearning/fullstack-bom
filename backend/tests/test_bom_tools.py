"""BOM 智能体工具（bom_quote / bom_stock_check）离线单元测试：FakeService，不依赖数据库。"""

import asyncio
import json
from typing import Any
from uuid import UUID, uuid4

from src.core.event_context import set_auth_context, set_event_queue
from src.core.tool_registry import ToolRegistry
from src.schemas.models import AuthContext, SSEEvent
from src.services.bom_tools import register_bom_tools


class FakeBomService:
    def __init__(self) -> None:
        self._prod = {"id": uuid4(), "sku_code": "PROD-GGD-01", "name": "GGD标准低压配电柜",
                      "category": "PRODUCT", "sub_type": "STANDARD", "unit": "台", "base_price": 0.0}

    async def list_items(self, user_id: UUID) -> list[dict[str, Any]]:
        return [self._prod]

    async def build_rollup_tree(self, user_id: UUID, root_id: UUID, params_3d: dict[str, float]) -> dict[str, Any]:
        return {
            "root": {**self._prod, "subtotal": 1000.0, "children": []},
            "params_3d": params_3d,
            "cost_summary": {"基材(固定)": 1000.0, "基材(非固定)": 0.0, "人工费(内)": 0.0, "人工费(外/机械)": 0.0},
            "bom_summary": {"人工": 0.0, "材料": 1000.0, "机械": 0.0},
            "flat_materials": [],
        }

    async def check_stock(self, user_id: UUID, root_id: UUID, env: dict[str, float]) -> list[dict[str, Any]]:
        return [{"sku_code": "MAT-STEEL-2MM", "name": "2.0mm冷轧钢板", "unit": "kg",
                 "required_qty": 180.0, "stock_qty": 50.0, "warehouse": "A01", "status": "缺料"}]


def _registry() -> ToolRegistry:
    registry = ToolRegistry()
    register_bom_tools(registry, FakeBomService())
    return registry


def _auth(allowed: list[str]) -> AuthContext:
    return AuthContext(user_id=uuid4(), username="tester", role="user", allowed_tools=allowed)


def test_bom_quote_tool_returns_price_and_card() -> None:
    async def _run() -> None:
        queue: asyncio.Queue[SSEEvent | None] = asyncio.Queue()
        set_event_queue(queue)
        set_auth_context(_auth(["bom_quote"]))
        res = json.loads(await _registry().execute("bom_quote", {"root_keyword": "GGD", "h": 2200, "w": 800, "d": 600, "t": 2.0}))
        assert res["ok"] is True
        assert res["root"] == "GGD标准低压配电柜"
        # 直接成本 1000 × (1+0.15) × (1+0.13) = 1299.5
        assert res["final_price"] == 1299.5
        collected: list[str] = []
        while not queue.empty():
            ev = queue.get_nowait()
            if ev is not None:
                collected.append(ev.event)
        assert "action_cards" in collected

    asyncio.run(_run())


def test_bom_quote_tool_unknown_keyword() -> None:
    async def _run() -> None:
        set_event_queue(asyncio.Queue())
        set_auth_context(_auth(["bom_quote"]))
        res = json.loads(await _registry().execute("bom_quote", {"root_keyword": "不存在的东西"}))
        assert res["ok"] is False
        assert "未找到匹配" in res["error"]

    asyncio.run(_run())


def test_bom_quote_tool_without_auth_context() -> None:
    async def _run() -> None:
        set_event_queue(asyncio.Queue())
        set_auth_context(None)  # type: ignore[arg-type]
        res = json.loads(await _registry().execute("bom_quote", {"root_keyword": "GGD"}))
        assert res["ok"] is False
        assert "身份" in res["error"]

    asyncio.run(_run())


def test_bom_stock_tool_emits_lack_alert_card() -> None:
    async def _run() -> None:
        queue: asyncio.Queue[SSEEvent | None] = asyncio.Queue()
        set_event_queue(queue)
        set_auth_context(_auth(["bom_stock_check"]))
        res = json.loads(await _registry().execute("bom_stock_check", {"root_keyword": "PROD-GGD-01"}))
        assert res["ok"] is True
        assert res["items"][0]["status"] == "缺料"
        while not queue.empty():
            ev = queue.get_nowait()
            if ev is not None and ev.event == "action_cards":
                card = ev.data["items"][0]  # type: ignore[index]
                assert card["kind"] == "inventory_alert"
                assert card["sku"] == "MAT-STEEL-2MM"
                assert card["safety_stock"] == 180.0

    asyncio.run(_run())


def test_registry_schemas_are_visible_and_trimmed_by_permission() -> None:
    schemas = _registry().list_schemas(allowed_tools=["bom_quote"])
    names = [s["function"]["name"] for s in schemas]
    assert names == ["bom_quote"]
    all_names = [s["function"]["name"] for s in _registry().list_schemas(allowed_tools=["*"])]
    assert set(all_names) == {"bom_quote", "bom_stock_check"}
