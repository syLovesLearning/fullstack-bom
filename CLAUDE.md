# CLAUDE.md — Monorepo 全局记忆入口（唯一真相源）

> **所有 AI 编程助手必读**：动手改代码前，先读本文件与 `docs/CODE_INDEX.md` 精准定位目标文件，禁止全仓盲目扫描源码。人与 AI 共用同一份文档（简练中文业务语义 + 英文代码标识），不再维护双语副本。

## 1. 仓库拓扑

- `backend/`：Python 3.12 + FastAPI + SSE + PostgreSQL 17 (`pgvector`) + Redis。
- `frontend/`：Vue 3.5 + TypeScript + Vite + pnpm（`fetch + ReadableStream` 消费 SSE）。
- `docs/`：`ARCHITECTURE.md`（分层与穿透）、`API_SPEC.md`（前后端唯一契约）、`CODE_INDEX.md`（AST 自动代码地图）。
- `scripts/`：`gen_code_index.py`、`sync_repo_memory.py`、`translate_requirement.py`（仅大需求可选生成 XMind）。

## 2. 全局工程铁律

1. **先定位、后读码**：先查 `docs/CODE_INDEX.md` 找到导出符号与文件路径，只打开需要修改的 1~2 个文件。
2. **契约先行**：任何 REST 路由或 SSE 事件变更，必须先更新 `docs/API_SPEC.md`，再改 `backend/src/api/` 与 `frontend/src/api/`。
3. **禁止黑盒封装**：严禁引入 LangChain、LlamaIndex 或 ORM；保持显式异步 SQL（`psycopg3`）与单文件 < 200 行。
4. **改后刷新索引**：新增或重命名文件/函数后，执行 `python3 scripts/gen_code_index.py` 刷新 `docs/CODE_INDEX.md`。
5. **大需求可选导图**：日常小需求直接写进 `docs/backlog/`；仅在大型模块立项或复杂拆分时，才调用 `scripts/translate_requirement.py` 生成 `.xmind` 梳理层级关系。

## 3. 常用命令

- 后端启动：`cd backend && make dev`
- 后端测试：`cd backend && make test`
- 前端启动：`cd frontend && pnpm dev`
- 刷新代码地图：`python3 scripts/gen_code_index.py`
- 同步记忆到 Postgres：`python3 scripts/sync_repo_memory.py`
