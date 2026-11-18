"""智能体生命周期钩子（对标 Vue 生命周期 / 中间件），用于轨迹审计与高危拦截。"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from src.schemas.models import AgentState, ToolCall

StepHook = Callable[[AgentState], Awaitable[None]]
PreToolHook = Callable[[AgentState, ToolCall], Awaitable[bool]]
AfterToolHook = Callable[[AgentState, ToolCall, str, int], Awaitable[None]]


@dataclass
class AgentHooks:
    before_step: list[StepHook] = field(default_factory=list)
    pre_tool: list[PreToolHook] = field(default_factory=list)
    after_tool: list[AfterToolHook] = field(default_factory=list)

    async def run_before_step(self, state: AgentState) -> None:
        for hook in self.before_step:
            await hook(state)

    async def run_pre_tool(self, state: AgentState, call: ToolCall) -> bool:
        """返回 False 表示拦截本次工具执行（例如权限不足或需人工确认）。"""
        for hook in self.pre_tool:
            allowed = await hook(state, call)
            if not allowed:
                return False
        return True

    async def run_after_tool(
        self, state: AgentState, call: ToolCall, result: str, duration_ms: int
    ) -> None:
        for hook in self.after_tool:
            await hook(state, call, result, duration_ms)


def make_noop_hooks() -> AgentHooks:
    return AgentHooks()


def build_trace_payload(call: ToolCall, result: str) -> dict[str, Any]:
    return {"tool": call.name, "args": call.arguments, "result_preview": result[:300]}
