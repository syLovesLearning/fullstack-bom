"""AI 对话需求分析工具：将用户的自然语言需求拆解为可确认的结构化清单。"""

import json
import re
from pydantic import BaseModel, Field

from src.core.tool_registry import ToolRegistry


class ToolDemandAnalyzeArgs(BaseModel):
    demand_text: str = Field(description="用户在对话中提出的原始微工具或项目功能需求描述")
    target_users: str = Field(default="admin,user", description="预期使用角色，如 admin,user")


def register_demand_tools(registry: ToolRegistry) -> None:
    @registry.register(
        name="analyze_tool_demand",
        description="对用户在对话中提出的新微工具或项目功能需求做初步结构化分析，生成供用户确认的需求清单（未确认前不要直接提交审批流程）。",
        args_model=ToolDemandAnalyzeArgs,
    )
    async def analyze_tool_demand_tool(args: ToolDemandAnalyzeArgs) -> str:
        text = args.demand_text.strip()
        is_ext = any(k in text for k in ("外部", "独立", "微服务", "爬虫", "第三方", "webhook", "iframe"))
        mode = "EXTERNAL_SERVICE" if is_ext else "LOCAL_MODULE"
        short_title = re.sub(r"[，。！？\s]+", "", text)[:16] or "定制微工具"
        checklist = {
            "suggested_flow_code": "tool_demand",
            "title": short_title,
            "problem_desc": text,
            "input_fields": "待确认：核心输入参数（如规格/数量/阈值）与输出结果格式",
            "delivery_mode": mode,
            "delivery_mode_label": "外部微服务挂载 (EXTERNAL_SERVICE)" if is_ext else "本地模块开发更新 (LOCAL_MODULE)",
            "target_roles": args.target_users,
            "next_instruction": (
                "请先向用户清晰展示上述《微工具需求确认清单》，并询问用户是否确认或需要修改字段；"
                "只有当用户明确回复确认后，再调用 submit_workflow_form(flow_code='tool_demand', form_data=...) 提交研发审批。"
            ),
        }
        return json.dumps(checklist, ensure_ascii=False)
