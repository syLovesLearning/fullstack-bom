"""大模型适配器（类 Axios 封装）：支持对话、工具调用、多轮指代改写及本地 Mock 模式。"""

import json
from typing import Any

import httpx

from src.config import settings
from src.schemas.models import ChatMessage, ToolCall


class LLMService:
    def __init__(self, http_client: httpx.AsyncClient) -> None:
        self._client = http_client

    async def rewrite_query(self, query: str, history: list[dict[str, str]]) -> str:
        """结合最近几轮对话历史，将含指代词的追问改写为独立检索词。"""
        if not history:
            return query
        if not settings.llm_api_key or settings.llm_api_key == "your_api_key":
            pronouns = ("它", "这个", "那个", "该", "上面")
            if any(p in query for p in pronouns):
                last_user = next((h["content"] for h in reversed(history) if h["role"] == "user"), "")
                if last_user:
                    return f"{last_user} {query}"
            return query

        hist_text = "\n".join(f"{h['role']}: {h['content'][:120]}" for h in history[-4:])
        prompt = (
            "根据以下对话历史，把用户的最新追问改写为一个独立、完整、适合知识库检索的短句。"
            "若无需改写则原样返回，不要解释。\n\n"
            f"对话历史：\n{hist_text}\n\n最新追问：{query}"
        )
        try:
            resp = await self._client.post(
                f"{settings.llm_base_url.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {settings.llm_api_key}"},
                json={
                    "model": settings.llm_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.0,
                },
            )
            resp.raise_for_status()
            rewritten = (resp.json()["choices"][0]["message"]["content"] or "").strip()
            return rewritten or query
        except Exception:
            return query

    async def chat_step(
        self,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]],
    ) -> tuple[str, list[ToolCall], int]:
        if not settings.llm_api_key or settings.llm_api_key == "your_api_key":
            return self._mock_step(messages, tools)

        payload: dict[str, Any] = {
            "model": settings.llm_model,
            "messages": [self._serialize_message(m) for m in messages],
            "temperature": 0.2,
        }
        if tools:
            payload["tools"] = tools

        resp = await self._client.post(
            f"{settings.llm_base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {settings.llm_api_key}"},
            json=payload,
        )
        if resp.status_code >= 400:
            detail = resp.text[:240]
            try:
                err_obj = resp.json()
                detail = str((err_obj.get("error") or {}).get("message") or err_obj.get("message") or detail)
            except Exception:
                pass
            if resp.status_code == 401:
                raise RuntimeError(f"模型 API Key 无效或已过期 (HTTP 401)：{detail}")
            if resp.status_code == 402:
                raise RuntimeError(f"模型账户余额或 Token 额度已耗尽 (HTTP 402)：{detail}")
            if resp.status_code == 429:
                raise RuntimeError(f"模型 Token 额度不足或触发限流 (HTTP 429)：{detail}")
            raise RuntimeError(f"大模型服务异常 (HTTP {resp.status_code})：{detail}")
        data = resp.json()
        choice = data["choices"][0]["message"]
        usage = data.get("usage", {}).get("total_tokens", 0)

        parsed_calls: list[ToolCall] = []
        for raw in choice.get("tool_calls") or []:
            args_str = raw["function"].get("arguments") or "{}"
            parsed_calls.append(
                ToolCall(
                    id=raw["id"],
                    name=raw["function"]["name"],
                    arguments=json.loads(args_str),
                )
            )
        return choice.get("content") or "", parsed_calls, int(usage)

    @staticmethod
    def _serialize_message(msg: ChatMessage) -> dict[str, Any]:
        out: dict[str, Any] = {"role": msg.role, "content": msg.content}
        if msg.tool_calls:
            out["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": json.dumps(tc.arguments, ensure_ascii=False),
                    },
                }
                for tc in msg.tool_calls
            ]
        if msg.tool_call_id:
            out["tool_call_id"] = msg.tool_call_id
        return out

    @staticmethod
    def _mock_step(
        messages: list[ChatMessage], tools: list[dict[str, Any]]
    ) -> tuple[str, list[ToolCall], int]:
        last = messages[-1]
        if last.role == "user" and tools and "rag" in last.content.lower():
            return (
                "",
                [ToolCall(id="mock_call_1", name="rag_search", arguments={"query": last.content})],
                12,
            )
        if last.role == "tool":
            if '"rejected": true' in last.content:
                return "知识库中未找到相关度达标的依据，请补充更具体的关键词后重试。", [], 20
            return f"（Mock 模式已收到工具结果）基于检索结果回答：{last.content[:140]}", [], 24
        return f"（Mock 模式）已收到你的消息：{last.content}。配置 .env 的 LLM_API_KEY 即可切换真实模型。", [], 18
