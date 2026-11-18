# ARCHITECTURE.md — 系统架构与记忆设计（唯一真相源）

## 1. 后端五层单向解耦

| 层级 | 目录 | 核心职责 | 允许依赖 | 严禁依赖 |
| :--- | :--- | :--- | :--- | :--- |
| Controller | `backend/src/api/` | FastAPI 路由、JWT 鉴权、SSE 输出 | `services`, `core`, `schemas` | `repositories`, `infra` |
| Agent Kernel | `backend/src/core/` | `AgentLoop`、`ToolRegistry`、`AgentHooks`、`EventContext` | `schemas`, 标准库 | `fastapi`, `infra`, `services` |
| Services | `backend/src/services/` | LLM 适配、Memory 编排、RAG、Eval | `repositories`, `schemas`, `core` | `api` |
| Repositories | `backend/src/repositories/` | 显式异步 SQL（`psycopg3`）与 Redis 读写 | `infra`, `schemas` | `api`, `core`, `services` |
| Infra | `backend/src/infra/` | Postgres/Redis 连接池、`httpx` 客户端 | `config` | 任何上层模块 |

## 2. 跨层穿透通道 (`core/event_context.py`)

- **SSE 事件穿透 (`_event_queue_var`)**：`api/chat.py` 为每次请求绑定 `asyncio.Queue`，内层（`AgentLoop`、`RagService`）直接调用 `await emit_event(event, data)` 冒泡到外层 SSE。
- **权限上下文穿透 (`_auth_ctx_var`)**：`api/deps.py` 解析 JWT 为 `AuthContext(user_id, role, allowed_tools)` 写入 `ContextVar`；`AgentLoop` 按 `allowed_tools` 裁剪可见工具，`repositories/` 强制按 `user_id` 过滤数据。

## 3. 四级运行时记忆 (PostgreSQL 17 + Redis)

1. **工作记忆 (Working)**：内存 `AgentState`，单次 Run 期间有效。
2. **短期缓冲 (Short-Term)**：Redis（`session:{user_id}:{session_id}:recent`、`rag:cache:{user_id}:*`），未启动 Redis 时自动降级。
3. **情景记忆 (Episodic)**：Postgres `sessions` + `messages` 表。
4. **语义记忆 (Semantic)**：Postgres `memories` + `documents` + `doc_chunks`（`vector(1024)` HNSW 索引）。
5. **轨迹审计 (Trace)**：Postgres `agent_runs` + `run_steps`，通过 `AgentHooks.after_tool` 自动落盘。

## 4. 商业化 RAG 管线 (`services/rag_service.py`)

- **入库**：`SHA-256` 去重 -> Markdown 结构感知切片（保留 `heading_path` 与代码块）-> `EmbeddingService`（带重试与本地降级）-> 事务原子落库。
- **检索**：Redis 缓存 -> `pgvector` Top-15 + 中英混排 `BM25` Top-15 -> `RRF (k=60)` -> `Rerank` -> 邻接切片扩展（`window=1`）-> `emit_event("citations")`。
