# ARCHITECTURE.md — 分层架构与记忆系统设计

> 本文档定义智能体开发框架的模块边界、跨层数据穿透机制、连接池生命周期以及四级记忆体系。所有核心模块开发需严格对齐本架构。

## 1. 总体分层与依赖规则

系统采用“垂直五层解耦 + 横向事件穿透”的微内核架构，前端可类比为 `路由层 → 状态与调度内核 → 业务 Service → 数据仓库 → 底层客户端`。

| 层级 | 目录 | 核心职责 | 允许依赖 | 严禁依赖 | 
| ----- | ----- | ----- | ----- | ----- | 
| Controller | `src/api/` | FastAPI 路由、参数校验、SSE 流输出 | `services`, `core`, `schemas` | `repositories`, `infra`（直接 SQL） | 
| Agent Kernel | `src/core/` | `AgentLoop` 调度、Tool 注册、Hook 钩子 | `schemas`, 标准库 | `fastapi`, `infra`, `services` 具体实现 | 
| Services | `src/services/` | LLM 调用、Memory 编排、RAG 检索、Session | `repositories`, `schemas`, `core` | `api` | 
| Repositories | `src/repositories/` | 显式异步 SQL（`psycopg3`）与 Redis 操作 | `infra`, `schemas` | `api`, `core`, `services` | 
| Infra | `src/infra/` | Postgres/Redis 连接池、`httpx` 客户端 | `config` | 任何上层业务模块 | 

## 2. 跨层数据穿透机制（EventContext）

传统 MVC 分层中，底层 `RAG Service` 或 `AgentLoop` 的中间状态难以直接推给最外层的 SSE `Controller`。本框架通过 `src/core/event_context.py` 解决该痛点：

1. **原理**：使用 Python 标准库 `contextvars.ContextVar` 绑定当前异步请求的 `asyncio.Queue`（类比 Vue 的 `provide / inject`）。

2. **写入端（任意内层）**：`AgentLoop`、`ToolRegistry` 或 `RagService` 在执行关键节点时，直接调用 `await emit_event("tool_start", {...})`，无需修改中间层函数签名。

3. **消费端（API 层）**：`api/chat.py` 启动后台协程运行 Agent 任务，同时持续 `await queue.get()` 并格式化为标准 SSE 帧推送给 Vue 3 / App 客户端，收到 `done` 哨兵事件后关闭流。

## 3. 连接池托管与注入（Infra）

* **生命周期托管**：`src/main.py` 的 `lifespan` 上下文管理器在应用启动时初始化 `AsyncConnectionPool`（PostgreSQL）与 `redis.asyncio.ConnectionPool`（Redis），挂载至 `app.state`，并在停机时优雅释放。

* **依赖注入**：`src/api/deps.py` 封装 FastAPI `Depends` 工厂函数，组装 `Repository → Service → Controller` 依赖链，杜绝全局裸连接与连接泄漏。

## 4. 四级记忆系统架构（Postgres + Redis）

为了兼顾毫秒级响应与长期可追溯性，记忆引擎（`services/memory_service.py`）按生命周期分为四层：

| 记忆层级 | 载体 | 存储内容 | 读写时机 | 
| ----- | ----- | ----- | ----- | 
| 工作记忆 (Working) | 内存 `AgentState` | 当前单次循环的临时上下文、待执行工具队列 | 单次 Run 开始创建，结束销毁 | 
| 短期缓冲 (Short-Term) | Redis | 最近 N 轮对话窗口缓存、SSE 断线重连缓冲、限流计数 | 每次对话高频读写，设置 TTL | 
| 情景记忆 (Episodic) | PostgreSQL | `sessions` 与 `messages` 完整对话历史与 `tool_call` 记录 | 每轮对话结束异步落盘 | 
| 语义记忆 (Semantic) | PostgreSQL (`pgvector`) | 跨会话提炼的用户偏好、长期事实（Fact）及知识库向量 | 检索前置注入 + 对话后异步提炼 | 
| 轨迹审计 (Trace) | PostgreSQL | `agent_runs` 与 `run_steps`（每步耗时、Token、报错现场） | 挂载于 Hook 钩子，全程透明记录 | 

## 5. 完整 API 接口体系规划

所有接口遵循 `/api/v1` 前缀，统一返回结构化 JSON 或 `text/event-stream`：

* **对话与流式执行**：`POST /api/v1/sessions/{session_id}/chat/stream`（SSE 流式输出 `thought` / `tool_start` / `tool_result` / `citations` / `token` / `done`）。

* **会话管理**：`POST /api/v1/sessions`、`GET /api/v1/sessions`、`GET /api/v1/sessions/{session_id}/messages`、`DELETE /api/v1/sessions/{session_id}`。

* **记忆管理**：`GET /api/v1/memories`、`POST /api/v1/memories`、`DELETE /api/v1/memories/{memory_id}`（支持前端可视化查看与人工纠偏记忆）。

* **能力与轨迹审计**：`GET /api/v1/tools`（返回已注册工具 Schema）、`GET /api/v1/runs/{run_id}/trace`（回放单次智能体执行全链路）。

## 6. 权限与安全隔离体系（双层鉴权 + 上下文穿透）

智能体框架的权限不仅管“人能不能调接口”，更要管“智能体能不能调工具、能查哪些数据”。采用**外层鉴权 + ContextVar 穿透**设计：

1. **接入层鉴权（FastAPI `Depends`）**：

   * **多端凭证**：Vue 3 / App 走 JWT Bearer Token（存 Redis 黑名单/刷新态）；外部脚本走 `X-API-Key`。

   * **接口路由**：新增 `/api/v1/auth/login`、`/api/v1/auth/refresh`、`GET /api/v1/auth/me`。

2. **数据与上下文穿透（`AuthContext`）**：

   * 鉴权中间件解析出 `AuthContext(user_id, role, allowed_tools)` 后写入 `contextvars`。

   * **数据隔离**：`SessionRepo`、`MemoryRepo` 与 `RagRepo` 从上下文读取 `user_id` / `role`，所有 SQL 查询（含 `pgvector` 检索）强制拼接归属条件，杜绝越权读取他人记忆或文档。

3. **智能体工具权限与高危拦截（`core/hooks.py`）**：

   * **工具白名单**：`AgentLoop` 在组装给大模型的 `tools` Schema 列表前，按当前用户角色动态裁剪，模型根本“看不见”无权调用的工具。

   * **高危操作确认（Human-in-the-Loop）**：对标记 `requires_approval=True` 的写操作工具，`pre_tool` 钩子暂停循环并通过 SSE 发射 `approval_required` 事件，等待前端确认接口放行。