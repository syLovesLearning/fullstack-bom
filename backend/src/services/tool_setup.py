"""将 Services 能力（RAG、记忆、配置化流程、近期流程查询、库存检索、BOM 试算）注册为 Tool。"""

import json
from typing import Any, Literal
from pydantic import BaseModel, Field

from src.core.event_context import emit_event, get_auth_context
from src.core.tool_registry import ToolRegistry
from src.repositories.inventory_repo import InventoryRepo
from src.repositories.workflow_repo import WorkflowRepo
from src.services.bom_service import BomService
from src.services.bom_tools import register_bom_tools
from src.services.demand_tools import register_demand_tools
from src.services.memory_service import MemoryService
from src.services.rag_service import RagService
from src.services.workflow_skills import validate_dynamic_workflow


class RagSearchArgs(BaseModel):
    query: str = Field(description="需要检索的研发文档或知识库问题")
    top_k: int | None = Field(default=None, ge=1, le=10, description="返回最相关的片段数量；不传则使用本次会话的默认值")


class MemorySaveArgs(BaseModel):
    content: str = Field(description="需要长期记住的用户偏好或关键事实")
    memory_type: Literal["fact", "preference", "summary"] = Field(default="fact")


class WorkflowSubmitArgs(BaseModel):
    flow_code: str = Field(description="流程编码，例如 oa_approval、srm_bidding、visitor_pass")
    form_data: dict[str, Any] = Field(description="严格符合对应流程 Skill 字段规范的表单 JSON")


class WorkflowQueryArgs(BaseModel):
    flow_code: str = Field(default="", description="可选过滤流程编码")
    limit: int = Field(default=5, ge=1, le=10)


class InventoryQueryArgs(BaseModel):
    keyword: str = Field(description="物料名称、型号规格或分类关键词，例如 服务器、交换机、工控机")


def build_tool_registry(
    rag_service: RagService,
    memory_service: MemoryService,
    workflow_repo: WorkflowRepo | None = None,
    inventory_repo: InventoryRepo | None = None,
    bom_service: BomService | None = None,
    default_top_k: int = 3,
    default_min_score: float = 0.2,
) -> ToolRegistry:
    """构建工具注册表。default_top_k / default_min_score 来自请求级调试参数（ChatRequest），
    LLM 未显式传 top_k 时回落到会话默认值，保证前端调试面板真实生效。"""
    registry = ToolRegistry()

    @registry.register(
        name="rag_search",
        description="检索内部研发文档与知识库，回答技术方案或项目规范问题。",
        args_model=RagSearchArgs,
    )
    async def rag_search_tool(args: RagSearchArgs) -> str:
        top_k = args.top_k if args.top_k is not None else default_top_k
        return await rag_service.search(query=args.query, top_k=top_k, min_score=default_min_score)

    @registry.register(
        name="memory_save",
        description="将用户的长期偏好或重要事实写入 PostgreSQL 长期记忆库。",
        args_model=MemorySaveArgs,
    )
    async def memory_save_tool(args: MemorySaveArgs) -> str:
        return await memory_service.save_memory_from_tool(
            content=args.content, memory_type=args.memory_type
        )

    if workflow_repo is not None:
        @registry.register(
            name="submit_workflow_form",
            description="校验并提交当前用户有权限的企业流程表单（按 flow_code 与 form_data）入库。",
            args_model=WorkflowSubmitArgs,
        )
        async def submit_workflow_tool(args: WorkflowSubmitArgs) -> str:
            auth = get_auth_context()
            if auth is None:
                return json.dumps({"ok": False, "error": "缺少用户身份上下文"}, ensure_ascii=False)
            defn = await workflow_repo.get_definition(args.flow_code)
            if defn is None:
                return json.dumps({"ok": False, "error": f"未找到流程定义: {args.flow_code}"}, ensure_ascii=False)
            if auth.role not in defn.get("allowed_roles", []):
                return json.dumps(
                    {"ok": False, "error": f"权限不足：角色 {auth.role} 无权发起 {args.flow_code}"},
                    ensure_ascii=False,
                )
            try:
                title, clean_data = validate_dynamic_workflow(defn, args.form_data)
            except ValueError as exc:
                return json.dumps({"ok": False, "error": f"表单校验失败：{exc}"}, ensure_ascii=False)

            row = await workflow_repo.create_instance(
                user_id=auth.user_id, flow_code=args.flow_code, title=title, form_data=clean_data
            )
            card = {
                "kind": "workflow",
                "id": str(row["id"]),
                "flow_code": args.flow_code,
                "title": title,
                "status": row["status"],
                "form_data": clean_data,
            }
            await emit_event("action_cards", {"items": [card]})
            return json.dumps({"ok": True, "card": card}, ensure_ascii=False)

        @registry.register(
            name="query_recent_workflows",
            description="查询当前用户近期发起的流程列表，并在对话中生成可点击卡片。",
            args_model=WorkflowQueryArgs,
        )
        async def query_workflows_tool(args: WorkflowQueryArgs) -> str:
            auth = get_auth_context()
            if auth is None:
                return json.dumps({"items": []}, ensure_ascii=False)
            res = await workflow_repo.list_instances(
                owner_user_id=auth.user_id, flow_code=args.flow_code or None, page=1, page_size=args.limit
            )
            cards = [
                {
                    "kind": "workflow",
                    "id": str(it["id"]),
                    "flow_code": it["flow_code"],
                    "title": it["title"],
                    "status": it["status"],
                    "form_data": it["form_data"],
                }
                for it in res["items"]
            ]
            if cards:
                await emit_event("action_cards", {"items": cards})
            return json.dumps({"total": res["total"], "cards": cards}, ensure_ascii=False)

    if inventory_repo is not None:
        @registry.register(
            name="query_inventory",
            description="模糊检索仓库物料库存（支持类似名称、规格、SKU），并自动提示低库存预警。",
            args_model=InventoryQueryArgs,
        )
        async def query_inventory_tool(args: InventoryQueryArgs) -> str:
            rows = await inventory_repo.search_by_name(keyword=args.keyword, limit=8)
            low_cards = [
                {
                    "kind": "inventory_alert",
                    "sku": r["sku"],
                    "item_name": r["item_name"],
                    "stock_qty": r["stock_qty"],
                    "safety_stock": r["safety_stock"],
                    "unit": r["unit"],
                    "warehouse": r["warehouse"],
                }
                for r in rows
                if r["is_low_stock"]
            ]
            if low_cards:
                await emit_event("action_cards", {"items": low_cards})
            return json.dumps({"keyword": args.keyword, "items": rows, "cards": low_cards}, ensure_ascii=False)

    if bom_service is not None:
        register_bom_tools(registry, bom_service)
    register_demand_tools(registry)

    return registry
