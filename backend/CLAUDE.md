# backend/CLAUDE.md — 后端记忆规范 (FastAPI + Agent Kernel)

> 先读顶层 `../CLAUDE.md` 与 `../docs/ARCHITECTURE.md`。

## 1. 单向依赖白名单

`src/api/` -> `src/services/` & `src/core/` -> `src/repositories/` -> `src/infra/`

- `src/core/`（Agent Kernel）严禁 `import` `fastapi`、`psycopg`、`redis` 或具体 `services/` 实现。
- `src/services/rag_service.py` 只是业务服务之一，通过 Tool 注册给 `AgentLoop` 调用，不得反向耦合进内核。

## 2. 跨层穿透与隔离铁律

- **事件流穿透**：任意内层通过 `core/event_context.py` 的 `emit_event()` 向 SSE 推状态，严禁层层传 `callback`。
- **多租户行级隔离**：通过 `get_auth_context()` 读取 `AuthContext`，所有 `repositories/` SQL 必须带 `WHERE user_id = $1`。
- **路径锚定**：禁止猜测 `Path(__file__).resolve().parent` 层级，统一使用 `find_dotenv()` 或显式锚定项目根目录。
