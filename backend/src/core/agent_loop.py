"""透明可观测的智能体调度循环（Agent Kernel 核心）。"""

import time
from typing import Any, Protocol

from src.core.event_context import emit_event, get_auth_context
from src.core.hooks import AgentHooks
from src.core.tool_registry import ToolRegistry
from src.schemas.models import AgentState, ChatMessage, ToolCall


class LLMCallable(Protocol):
    async def chat_step(
        self,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]],
    ) -> tuple[str, list[ToolCall], int]:
        """返回 (assistant_text, tool_calls, tokens_used)。"""


class AgentLoop:
    def __init__(
        self,
        llm: LLMCallable,
        registry: ToolRegistry,
        hooks: AgentHooks | None = None,
    ) -> None:
        self._llm = llm
        self._registry = registry
        self._hooks = hooks or AgentHooks()

    async def run(self, state: AgentState) -> str:
        auth = get_auth_context()
        allowed = auth.allowed_tools if auth else ["*"]
        tool_schemas = self._registry.list_schemas(allowed_tools=allowed)

        final_answer = ""
        while state.step_count < state.max_steps:
            state.step_count += 1
            await self._hooks.run_before_step(state)
            await emit_event("thought", {"step": state.step_count, "status": "reasoning"})

            text, tool_calls, tokens = await self._llm.chat_step(state.messages, tool_schemas)
            state.total_tokens += tokens

            if not tool_calls:
                final_answer = text
                state.messages.append(ChatMessage(role="assistant", content=final_answer))
                # 按块发送而非逐字符：LLM 为整体返回（伪流式），逐字符会产生数千个 SSE 帧
                CHUNK = 24
                for i in range(0, len(final_answer), CHUNK):
                    await emit_event("token", {"text": final_answer[i : i + CHUNK]})
                break

            state.messages.append(
                ChatMessage(role="assistant", content=text, tool_calls=tool_calls)
            )
            for call in tool_calls:
                allowed_by_hook = await self._hooks.run_pre_tool(state, call)
                if not allowed_by_hook:
                    result = f"Tool '{call.name}' blocked by security hook."
                    state.messages.append(
                        ChatMessage(role="tool", content=result, tool_call_id=call.id)
                    )
                    continue

                await emit_event("tool_start", {"tool": call.name, "args": call.arguments})
                t0 = time.perf_counter()
                result = await self._registry.execute(call.name, call.arguments)
                cost_ms = int((time.perf_counter() - t0) * 1000)

                await self._hooks.run_after_tool(state, call, result, cost_ms)
                await emit_event(
                    "tool_result",
                    {"tool": call.name, "duration_ms": cost_ms, "preview": result[:200]},
                )
                state.messages.append(
                    ChatMessage(role="tool", content=result, tool_call_id=call.id)
                )

        if not final_answer:
            final_answer = "已达到最大调度步数限制，请细化问题后重试。"
            await emit_event("token", {"text": final_answer})

        return final_answer
