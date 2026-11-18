# Agent Framework (透明可控智能体开发框架)

基于 **FastAPI + SSE + PostgreSQL (`pgvector`) + Redis** 的透明微内核智能体后端。

## 快速启动

```bash
# 1. 创建虚拟环境并安装依赖
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# 2. 配置环境变量（默认已适配本地 Postgres.app）
cp .env.example .env

# 3. 初始化 PostgreSQL 表结构
make migrate

# 4. 启动服务（自带 Swagger 文档：http://localhost:8000/docs）
make dev
```

## 快速验证接口

1. 调用 `POST /api/v1/auth/dev-login`（传 `{"username": "shenyang"}`）获取 JWT Token。
2. 调用 `POST /api/v1/sessions` 创建会话，拿到 `session_id`。
3. 调用 `POST /api/v1/sessions/{session_id}/chat/stream` 体验实时 SSE 流式事件（`thought` / `tool_start` / `tool_result` / `token` / `done`）。
   - 若 `.env` 中 `LLM_API_KEY` 仍为默认值 `your_api_key`，系统会自动进入本地 Mock 模式，方便零成本验证全链路。
