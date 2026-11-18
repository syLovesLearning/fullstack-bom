"""四级记忆编排服务：协调 Redis 短期缓冲与 Postgres 情景/语义记忆。"""

import json
from typing import Any
from uuid import UUID

from redis.asyncio import Redis

from src.core.event_context import get_auth_context
from src.repositories.memory_repo import MemoryRepo
from src.repositories.session_repo import SessionRepo
from src.schemas.models import ChatMessage


class MemoryService:
    def __init__(
        self,
        session_repo: SessionRepo,
        memory_repo: MemoryRepo,
        redis_client: Redis | None = None,
    ) -> None:
        self._sessions = session_repo
        self._memories = memory_repo
        self._redis = redis_client

    async def build_context_messages(
        self, session_id: UUID, user_id: UUID, user_text: str, extra_system_prompt: str = ""
    ) -> list[ChatMessage]:
        long_memories = await self._memories.list_memories(user_id=user_id, limit=5)
        mem_lines = "\n".join(f"- [{m['memory_type']}] {m['content']}" for m in long_memories)
        sys_prompt = "你是一个透明可控的企业智能体助手。"
        if extra_system_prompt:
            sys_prompt += f"\n\n{extra_system_prompt}"
        if mem_lines:
            sys_prompt += f"\n\n用户长期记忆：\n{mem_lines}"

        messages = [ChatMessage(role="system", content=sys_prompt)]
        history = await self._load_recent_history(session_id=session_id, user_id=user_id)
        messages.extend(history)
        messages.append(ChatMessage(role="user", content=user_text))
        return messages

    async def save_memory_from_tool(self, content: str, memory_type: str = "fact") -> str:
        auth = get_auth_context()
        if auth is None:
            return "未获取到用户身份上下文，无法写入长期记忆。"
        row = await self._memories.create_memory(
            user_id=auth.user_id,
            memory_type=memory_type,
            content=content,
        )
        return f"已保存长期记忆（id={row['id']}）：{content}"

    async def _load_recent_history(self, session_id: UUID, user_id: UUID) -> list[ChatMessage]:
        cache_key = f"session:{user_id}:{session_id}:recent"
        if self._redis is not None:
            cached = await self._redis.get(cache_key)
            if cached:
                return [ChatMessage.model_validate(item) for item in json.loads(cached)]

        rows = await self._sessions.list_messages(session_id=session_id, user_id=user_id, limit=12)
        history = [ChatMessage(role=r["role"], content=r["content"]) for r in rows]
        if self._redis is not None and history:
            # 缓存与 DB 路径使用同一窗口（12 条），避免命中缓存与否导致上下文长度漂移
            serialized = json.dumps([m.model_dump() for m in history], ensure_ascii=False)
            await self._redis.set(cache_key, serialized, ex=1800)
        return history

    async def invalidate_session_cache(self, session_id: UUID, user_id: UUID) -> None:
        if self._redis is not None:
            await self._redis.delete(f"session:{user_id}:{session_id}:recent")

    async def list_user_memories(self, user_id: UUID) -> list[dict[str, Any]]:
        return await self._memories.list_memories(user_id=user_id)
