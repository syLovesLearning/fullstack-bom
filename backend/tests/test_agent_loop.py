"""AgentLoop + ToolRegistry + EventContext 离线单元测试（不依赖外部数据库）。"""

import asyncio
from typing import Any
from uuid import uuid4

from pydantic import BaseModel

from src.core.agent_loop import AgentLoop
from src.core.event_context import set_auth_context, set_event_queue
from src.core.tool_registry import ToolRegistry
from src.schemas.models import AgentState, AuthContext, ChatMessage, SSEEvent, ToolCall


class EchoArgs(BaseModel):
    text: str


class FakeLLM:
    def __init__(self) -> None:
        self.calls = 0

    async def chat_step(
        self, messages: list[ChatMessage], tools: list[dict[str, Any]]
    ) -> tuple[str, list[ToolCall], int]:
        self.calls += 1
        if self.calls == 1:
            return "", [ToolCall(id="c1", name="echo", arguments={"text": "hello"})], 10
        return f"Done: {messages[-1].content}", [], 15


def test_agent_loop_penetrates_events_and_respects_permissions() -> None:
    async def _run() -> None:
        queue: asyncio.Queue[SSEEvent | None] = asyncio.Queue()
        set_event_queue(queue)
        set_auth_context(
            AuthContext(user_id=uuid4(), username="tester", role="user", allowed_tools=["echo"])
        )

        registry = ToolRegistry()

        @registry.register(name="echo", description="echo text", args_model=EchoArgs)
        async def echo_tool(args: EchoArgs) -> str:
            return f"echo:{args.text}"

        @registry.register(name="admin_only", description="restricted", args_model=EchoArgs)
        async def admin_tool(args: EchoArgs) -> str:
            return args.text

        assert len(registry.list_schemas(allowed_tools=["echo"])) == 1

        state = AgentState(
            run_id=uuid4(),
            session_id=uuid4(),
            user_id=uuid4(),
            messages=[ChatMessage(role="user", content="test")],
        )
        answer = await AgentLoop(llm=FakeLLM(), registry=registry).run(state)
        assert answer == "Done: echo:hello"
        assert state.total_tokens == 25

        events: list[str] = []
        while not queue.empty():
            ev = queue.get_nowait()
            if ev is not None:
                events.append(ev.event)
        assert "tool_start" in events
        assert "tool_result" in events
        assert "token" in events

    asyncio.run(_run())
