"""核心流式对话接口（SSE）：支持调试参数、引用持久化与全链路 Trace 记录。"""

import asyncio
from collections.abc import AsyncGenerator
import json
import time
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from src.api.deps import (
    get_bom_service,
    get_current_auth,
    get_llm_service,
    get_memory_service,
    get_rag_service,
    get_session_repo,
    get_trace_repo,
    get_inventory_repo,
    get_workflow_repo,
)
from src.config import settings
from src.core.agent_loop import AgentLoop
from src.core.event_context import (
    close_event_stream,
    emit_event,
    set_auth_context,
    set_event_queue,
    set_recent_history,
)
from src.core.hooks import AgentHooks
from src.repositories.session_repo import SessionRepo
from src.repositories.trace_repo import TraceRepo
from src.repositories.inventory_repo import InventoryRepo
from src.repositories.workflow_repo import WorkflowRepo
from src.schemas.models import AgentState, AuthContext, ChatRequest, SSEEvent, ToolCall
from src.services.llm_service import LLMService
from src.services.memory_service import MemoryService
from src.services.rag_service import RagService
from src.services.bom_service import BomService
from src.services.tool_setup import build_tool_registry
from src.services.workflow_skills import build_workflow_skill_prompt

router = APIRouter(prefix="/api/v1/sessions", tags=["chat"])


@router.post("/{session_id}/chat/stream")
async def chat_stream(
    session_id: UUID,
    body: ChatRequest,
    auth: AuthContext = Depends(get_current_auth),
    session_repo: SessionRepo = Depends(get_session_repo),
    trace_repo: TraceRepo = Depends(get_trace_repo),
    memory_service: MemoryService = Depends(get_memory_service),
    llm_service: LLMService = Depends(get_llm_service),
    rag_service: RagService = Depends(get_rag_service),
    workflow_repo: WorkflowRepo = Depends(get_workflow_repo),
    inventory_repo: InventoryRepo = Depends(get_inventory_repo),
    bom_service: BomService = Depends(get_bom_service),
) -> StreamingResponse:
    session = await session_repo.get_session(session_id=session_id, user_id=auth.user_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    if not body.enable_rag:
        filtered = [t for t in auth.allowed_tools if t != "rag_search"]
        set_auth_context(auth.model_copy(update={"allowed_tools": filtered}))

    async def event_generator() -> AsyncGenerator[str, None]:
        queue: asyncio.Queue[SSEEvent | None] = asyncio.Queue()
        set_event_queue(queue)

        run_id = await trace_repo.create_run(
            session_id=session_id, user_id=auth.user_id, model_name=settings.llm_model
        )
        allowed_defs = await workflow_repo.list_definitions(role=auth.role)
        skill_prompt = build_workflow_skill_prompt(allowed_defs)
        messages = await memory_service.build_context_messages(
            session_id=session_id, user_id=auth.user_id, user_text=body.message, extra_system_prompt=skill_prompt
        )
        await session_repo.append_message(
            session_id=session_id, user_id=auth.user_id, role="user", content=body.message, run_id=run_id
        )
        await trace_repo.append_step(
            run_id=run_id,
            user_id=auth.user_id,
            step_index=0,
            step_type="memory_write",
            tool_name="system_prompt_inject",
            input_payload={"max_steps": body.max_steps, "enable_rag": body.enable_rag},
            output_payload={"system_prompt_preview": messages[0].content[:400]},
            duration_ms=0,
        )

        history_pairs = [
            {"role": m.role, "content": m.content}
            for m in messages[:-1]
            if m.role in ("user", "assistant")
        ][-6:]
        set_recent_history(history_pairs)

        state = AgentState(
            run_id=run_id,
            session_id=session_id,
            user_id=auth.user_id,
            messages=messages,
            max_steps=body.max_steps,
        )
        collected_citations: list[dict[str, Any]] = []
        collected_cards: list[dict[str, Any]] = []

        async def record_tool_step(s: AgentState, call: ToolCall, res: str, ms: int) -> None:
            if call.name in ("submit_workflow_form", "query_recent_workflows", "query_inventory"):
                try:
                    parsed = json.loads(res)
                    if parsed.get("card"):
                        collected_cards.append(parsed["card"])
                    if isinstance(parsed.get("cards"), list):
                        collected_cards.extend(parsed["cards"])
                except Exception:
                    pass
            if call.name == "rag_search":
                try:
                    parsed = json.loads(res)
                    if isinstance(parsed.get("hits"), list):
                        collected_citations.extend(parsed["hits"])
                except Exception:
                    pass
            await trace_repo.append_step(
                run_id=s.run_id,
                user_id=s.user_id,
                step_index=s.step_count,
                step_type="tool_call",
                tool_name=call.name,
                input_payload=call.arguments,
                output_payload={"preview": res[:500]},
                duration_ms=ms,
            )

        hooks = AgentHooks(after_tool=[record_tool_step])
        registry = build_tool_registry(
            rag_service=rag_service,
            memory_service=memory_service,
            workflow_repo=workflow_repo,
            inventory_repo=inventory_repo,
            bom_service=bom_service,
            default_top_k=body.top_k,
            default_min_score=body.min_score,
        )
        loop = AgentLoop(llm=llm_service, registry=registry, hooks=hooks)

        async def run_agent() -> None:
            t0 = time.perf_counter()
            try:
                answer = await loop.run(state)
                await session_repo.append_message(
                    session_id=session_id,
                    user_id=auth.user_id,
                    role="assistant",
                    content=answer,
                    run_id=run_id,
                    citations=collected_citations or None,
                    action_cards=collected_cards or None,
                )
                await memory_service.invalidate_session_cache(session_id=session_id, user_id=auth.user_id)
                cost_ms = int((time.perf_counter() - t0) * 1000)
                await trace_repo.finish_run(run_id, "completed", state.total_tokens, cost_ms)
                await emit_event(
                    "done",
                    {"run_id": str(run_id), "total_tokens": state.total_tokens, "latency_ms": cost_ms},
                )
            except Exception as exc:
                cost_ms = int((time.perf_counter() - t0) * 1000)
                await trace_repo.finish_run(run_id, "failed", state.total_tokens, cost_ms, str(exc))
                await emit_event("error", {"message": str(exc)})
            finally:
                await memory_service.invalidate_session_cache(session_id=session_id, user_id=auth.user_id)
                await close_event_stream()

        task = asyncio.create_task(run_agent())
        try:
            while True:
                item = await queue.get()
                if item is None:
                    break
                payload = json.dumps(item.data, ensure_ascii=False)
                yield f"event: {item.event}\ndata: {payload}\n\n"
        finally:
            if not task.done():
                task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    return StreamingResponse(event_generator(), media_type="text/event-stream")
