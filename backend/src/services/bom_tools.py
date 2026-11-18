"""BOM 能力的智能体工具注册：成本试算报价与跨库库存齐套核查（挂载进 ToolRegistry）。"""

import json
from typing import Any

from pydantic import BaseModel, Field

from src.core.event_context import emit_event, get_auth_context
from src.core.tool_registry import ToolRegistry
from src.services.bom_service import BomService


class BomQuoteArgs(BaseModel):
    root_keyword: str = Field(description="成品/半成品物料的名称或 SKU 关键词，例如 GGD、PROD-GGD-01")
    h: float = Field(default=2200.0, gt=0, description="柜体高度 H（mm）")
    w: float = Field(default=800.0, gt=0, description="柜体宽度 W（mm）")
    d: float = Field(default=600.0, gt=0, description="柜体深度 D（mm）")
    t: float = Field(default=2.0, gt=0, description="板材厚度 T（mm）")
    margin_rate: float = Field(default=0.15, ge=0, le=1, description="毛利率（0.15 即 15%）")
    tax_rate: float = Field(default=0.13, ge=0, le=1, description="税率（0.13 即 13%）")


class BomStockArgs(BaseModel):
    root_keyword: str = Field(description="成品/半成品物料的名称或 SKU 关键词，例如 GGD、PROD-GGD-01")
    h: float = Field(default=2200.0, gt=0, description="柜体高度 H（mm）")
    w: float = Field(default=800.0, gt=0, description="柜体宽度 W（mm）")
    d: float = Field(default=600.0, gt=0, description="柜体深度 D（mm）")
    t: float = Field(default=2.0, gt=0, description="板材厚度 T（mm）")


def _match_root_item(items: list[dict[str, Any]], keyword: str) -> dict[str, Any] | None:
    kw = keyword.strip().lower()
    for it in items:
        if kw in str(it["sku_code"]).lower() or kw in str(it["name"]).lower():
            return it
    return None


def register_bom_tools(registry: ToolRegistry, bom_service: BomService) -> None:

    @registry.register(
        name="bom_quote",
        description="按 3D 参数（H/W/D/T）试算指定成品的 BOM 成本汇总与含毛利含税报价。",
        args_model=BomQuoteArgs,
    )
    async def bom_quote_tool(args: BomQuoteArgs) -> str:
        auth = get_auth_context()
        if auth is None:
            return json.dumps({"ok": False, "error": "缺少用户身份上下文"}, ensure_ascii=False)
        root = _match_root_item(await bom_service.list_items(auth.user_id), args.root_keyword)
        if root is None:
            return json.dumps({"ok": False, "error": f"未找到匹配 '{args.root_keyword}' 的 BOM 物料"}, ensure_ascii=False)
        env = {"H": args.h, "W": args.w, "D": args.d, "T": args.t}
        try:
            res = await bom_service.build_rollup_tree(user_id=auth.user_id, root_id=root["id"], params_3d=env)
        except ValueError as exc:
            return json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False)
        direct = float(res["root"]["subtotal"])
        final = round(direct * (1.0 + args.margin_rate) * (1.0 + args.tax_rate), 2)
        payload = {
            "ok": True, "root": root["name"], "params_3d": env, "direct_cost": direct, "final_price": final,
            "cost_summary": res["cost_summary"], "bom_summary": res["bom_summary"],
            "flat_materials": res["flat_materials"],
        }
        await emit_event("action_cards", {"items": [{
            "kind": "bom_quote", "root_name": root["name"], "params_3d": env,
            "direct_cost": direct, "final_price": final, "cost_summary": res["cost_summary"],
        }]})
        return json.dumps(payload, ensure_ascii=False)

    @registry.register(
        name="bom_stock_check",
        description="按 3D 参数试算指定成品的物料需求并核查跨库库存齐套状态（齐套/缺料/未建档）。",
        args_model=BomStockArgs,
    )
    async def bom_stock_tool(args: BomStockArgs) -> str:
        auth = get_auth_context()
        if auth is None:
            return json.dumps({"ok": False, "error": "缺少用户身份上下文"}, ensure_ascii=False)
        root = _match_root_item(await bom_service.list_items(auth.user_id), args.root_keyword)
        if root is None:
            return json.dumps({"ok": False, "error": f"未找到匹配 '{args.root_keyword}' 的 BOM 物料"}, ensure_ascii=False)
        env = {"H": args.h, "W": args.w, "D": args.d, "T": args.t}
        try:
            items = await bom_service.check_stock(user_id=auth.user_id, root_id=root["id"], env=env)
        except ValueError as exc:
            return json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False)
        lack_cards = [{
            "kind": "inventory_alert", "sku": m["sku_code"], "item_name": m["name"],
            "stock_qty": m["stock_qty"], "safety_stock": m["required_qty"], "unit": m["unit"],
            "warehouse": m["warehouse"],
        } for m in items if m["status"] != "齐套"]
        if lack_cards:
            await emit_event("action_cards", {"items": lack_cards})
        return json.dumps({"ok": True, "root": root["name"], "params_3d": env, "items": items}, ensure_ascii=False)
