"""RAG 自动化评测服务：加载黄金测试集并计算 Hit Rate@3、MRR 与关键词命中率。"""

import json
from pathlib import Path
import time
from typing import Any
from uuid import UUID

from src.services.rag_service import RagService

_SAMPLE_DOCS = [
    {
        "title": "分层与事件穿透架构",
        "source_path": "docs/arch.md",
        "category": "arch",
        "content": (
            "# 总体架构\n\n## EventContext 跨层穿透\n"
            "通过 Python 标准库 contextvars 与 asyncio.Queue 实现 EventContext 穿透，"
            "让最底层的 RagService 直接向最外层 SSE Controller 发射 citations 事件。\n\n"
            "## RAG 在 Services 中的定位\n"
            "RAG 只是 Services 的一部分，通过 Tool 注册给 AgentLoop 调度，保持内核与业务解耦。"
        ),
    },
    {
        "title": "四级记忆持久化设计",
        "source_path": "docs/memory.md",
        "category": "memory",
        "content": (
            "# 四级记忆体系\n\n## Redis 与 PostgreSQL 分工\n"
            "Redis 负责最近对话窗口的短期缓冲与限流；PostgreSQL 17 负责会话历史持久化，"
            "并通过 pgvector 扩展存储 1024 维长期语义记忆。"
        ),
    },
    {
        "title": "双层权限与隔离规范",
        "source_path": "docs/security.md",
        "category": "security",
        "content": (
            "# 权限隔离\n\n## 行级隔离与工具白名单\n"
            "鉴权后将 AuthContext(user_id, role, allowed_tools) 写入 ContextVar，"
            "所有 Repository SQL 强制携带 user_id 过滤，AgentLoop 按 allowed_tools 裁剪工具。"
        ),
    },
    {
        "title": "商业化 RAG 混合检索管线",
        "source_path": "docs/rag.md",
        "category": "rag",
        "content": (
            "# 商业化 RAG 管线\n\n## 增量去重入库\n"
            "入库前计算文档 SHA-256 指纹 (content_hash)，未变更文档直接跳过，"
            "变更文档在事务内原子删旧插新。\n\n"
            "## 混合检索与精排\n"
            "采用 pgvector 向量召回 + 中英混排 BM25 召回，通过 RRF 融合排序后再做 Rerank 精排与邻接扩展。"
        ),
    },
]


class EvalService:
    def __init__(self, rag_service: RagService) -> None:
        self._rag = rag_service
        self._eval_file = Path(__file__).resolve().parent.parent.parent / "eval" / "golden_qa.json"

    def load_cases(self) -> list[dict[str, Any]]:
        if not self._eval_file.exists():
            return []
        return json.loads(self._eval_file.read_text(encoding="utf-8"))

    async def seed_sample_docs(self, user_id: UUID) -> list[dict[str, Any]]:
        results = []
        for doc in _SAMPLE_DOCS:
            res = await self._rag.ingest_document(
                user_id=user_id,
                title=doc["title"],
                source_path=doc["source_path"],
                content=doc["content"],
                category=doc["category"],
            )
            results.append({"source_path": doc["source_path"], **res})
        return results

    async def run_suite(
        self, user_id: UUID, seed_if_empty: bool = True, top_k: int = 3
    ) -> dict[str, Any]:
        if seed_if_empty:
            await self.seed_sample_docs(user_id=user_id)

        cases = self.load_cases()
        case_results: list[dict[str, Any]] = []
        hit_count = 0
        mrr_sum = 0.0
        total_ms = 0

        for case in cases:
            t0 = time.perf_counter()
            hits = await self._rag.search_structured(
                query=case["question"],
                top_k=top_k,
                category=case.get("category"),
                user_id=user_id,
            )
            cost_ms = int((time.perf_counter() - t0) * 1000)
            total_ms += cost_ms

            expected_source = case["expected_source"]
            rank = 0
            for idx, h in enumerate(hits, start=1):
                if h.get("source_path") == expected_source:
                    rank = idx
                    break

            merged_snippets = " ".join(h.get("snippet", "") for h in hits).lower()
            matched_kw = [
                kw for kw in case.get("expected_keywords", []) if kw.lower() in merged_snippets
            ]
            passed = rank > 0 and len(matched_kw) >= 1
            if rank > 0:
                hit_count += 1
                mrr_sum += 1.0 / rank

            case_results.append(
                {
                    "id": case["id"],
                    "category": case["category"],
                    "question": case["question"],
                    "expected_source": expected_source,
                    "expected_keywords": case.get("expected_keywords", []),
                    "matched_keywords": matched_kw,
                    "rank": rank,
                    "passed": passed,
                    "latency_ms": cost_ms,
                    "top_hit": hits[0] if hits else None,
                }
            )

        total = len(cases) or 1
        return {
            "summary": {
                "total": len(cases),
                "passed": sum(1 for r in case_results if r["passed"]),
                "hit_rate_at_3": round(hit_count / total, 4),
                "mrr": round(mrr_sum / total, 4),
                "avg_latency_ms": round(total_ms / total, 1),
            },
            "results": case_results,
        }
