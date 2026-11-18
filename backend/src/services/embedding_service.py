"""向量化与精排服务：支持 429/5xx 指数退避重试与本地 Mock 向量降级。"""

import asyncio
import hashlib
import logging
import math
from typing import Any, Literal

import httpx

from src.config import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    def __init__(self, http_client: httpx.AsyncClient, dim: int = 1024) -> None:
        self._client = http_client
        self._dim = dim

    async def embed_texts(
        self, texts: list[str], on_error: Literal["degrade", "raise"] = "degrade"
    ) -> list[list[float]]:
        """on_error=raise 供入库路径使用：失败即中止，杜绝真实向量与本地 hash 向量混入同一向量空间。"""
        if not texts:
            return []
        if not settings.llm_api_key or settings.llm_api_key == "your_api_key":
            return [self._local_hash_embedding(t) for t in texts]

        base = (settings.embed_base_url or settings.llm_base_url).rstrip("/")
        key = settings.embed_api_key or settings.llm_api_key
        if key == "local":
            return [self._local_hash_embedding(t) for t in texts]
        payload = {"model": settings.embed_model, "input": texts}
        try:
            resp = await self._client.post(
                f"{base}/embeddings",
                headers={"Authorization": f"Bearer {key}"},
                json=payload,
            )
            resp.raise_for_status()
            items = sorted(resp.json()["data"], key=lambda x: x["index"])
            return [item["embedding"] for item in items]
        except Exception:
            logger.exception("Embedding API 调用失败（model=%s, %d 条文本）", settings.embed_model, len(texts))
            if on_error == "raise":
                raise
            logger.warning("Embedding 降级为本地 hash 向量：查询结果质量可能下降，不会写入向量库")
            return [self._local_hash_embedding(t) for t in texts]

    async def rerank(self, query: str, docs: list[str], top_n: int = 3) -> list[tuple[int, float]]:
        """返回 [(原始下标, 相关性分数)]。未配置 Key 时使用词面重合度降级排序。"""
        if not docs:
            return []
        if not settings.llm_api_key or settings.llm_api_key == "your_api_key":
            return self._local_rerank(query, docs, top_n)

        payload = {"model": "rerank", "query": query, "documents": docs, "top_n": top_n}
        try:
            data = await self._post_with_retry(
                f"{settings.llm_base_url.rstrip('/')}/rerank",
                payload,
            )
            return [(int(r["index"]), float(r["relevance_score"])) for r in data.get("results", [])]
        except Exception:
            logger.exception("Rerank API 调用失败，降级为词面重合度排序")
            return self._local_rerank(query, docs, top_n)

    async def _post_with_retry(self, url: str, payload: dict[str, Any], retries: int = 3) -> dict[str, Any]:
        delay = 0.5
        for attempt in range(retries):
            resp = await self._client.post(
                url,
                headers={"Authorization": f"Bearer {settings.llm_api_key}"},
                json=payload,
            )
            if resp.status_code in (429, 500, 502, 503, 504) and attempt < retries - 1:
                await asyncio.sleep(delay)
                delay *= 2
                continue
            resp.raise_for_status()
            return resp.json()
        raise RuntimeError("Embedding API retries exhausted")

    def _local_hash_embedding(self, text: str) -> list[float]:
        """确定性 1024 维特征哈希向量，保证离线/Mock 环境可测余弦检索。"""
        vec = [0.0] * self._dim
        for token in text.lower().split():
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            idx = int.from_bytes(digest[:4], "big") % self._dim
            vec[idx] += 1.0
        for ch in text.lower():
            if "\u4e00" <= ch <= "\u9fff":
                digest = hashlib.sha256(ch.encode("utf-8")).digest()
                idx = int.from_bytes(digest[:4], "big") % self._dim
                vec[idx] += 1.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    @staticmethod
    def _local_rerank(query: str, docs: list[str], top_n: int) -> list[tuple[int, float]]:
        q_chars = set(query.lower())
        scored: list[tuple[int, float]] = []
        for idx, doc in enumerate(docs):
            d_chars = set(doc.lower())
            overlap = len(q_chars & d_chars) / max(len(q_chars), 1)
            scored.append((idx, round(overlap, 4)))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_n]
