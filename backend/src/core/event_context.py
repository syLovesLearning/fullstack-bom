"""跨层上下文穿透通道：EventQueue（SSE）、AuthContext（权限）与 RecentHistory（指代改写）。"""

import asyncio
from contextvars import ContextVar
from typing import Any

from src.schemas.models import AuthContext, SSEEvent

_event_queue_var: ContextVar[asyncio.Queue[SSEEvent | None] | None] = ContextVar(
    "event_queue", default=None
)
_auth_ctx_var: ContextVar[AuthContext | None] = ContextVar("auth_context", default=None)
_recent_history_var: ContextVar[list[dict[str, str]]] = ContextVar("recent_history", default=[])


def set_event_queue(queue: asyncio.Queue[SSEEvent | None]) -> None:
    _event_queue_var.set(queue)


async def emit_event(event: str, data: dict[str, Any] | None = None) -> None:
    """任意内层（Kernel / RAG / Tool）调用此函数，事件直接穿透到最外层 SSE。"""
    queue = _event_queue_var.get()
    if queue is not None:
        await queue.put(SSEEvent(event=event, data=data or {}))  # type: ignore[arg-type]


async def close_event_stream() -> None:
    queue = _event_queue_var.get()
    if queue is not None:
        await queue.put(None)


def set_auth_context(auth: AuthContext) -> None:
    _auth_ctx_var.set(auth)


def get_auth_context() -> AuthContext | None:
    return _auth_ctx_var.get()


def set_recent_history(history: list[dict[str, str]]) -> None:
    _recent_history_var.set(history)


def get_recent_history() -> list[dict[str, str]]:
    return _recent_history_var.get()
