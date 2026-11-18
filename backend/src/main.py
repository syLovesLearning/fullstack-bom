"""FastAPI 应用入口：通过 lifespan 统一托管 Postgres / Redis / HTTPX 连接池。"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api import auth, bom, chat, docs, eval as eval_api, memories, menus, sessions, tools, workflows
from src.config import settings
from src.infra.http_client import close_http_client, create_http_client
from src.infra.postgres import close_pg_pool, create_pg_pool
from src.infra.redis import close_redis_client, create_redis_client
from src.repositories.bom_repo import BomRepo


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.pg_pool = await create_pg_pool(settings.pg_dsn)
    app.state.bom_pool = await create_pg_pool(settings.bom_pg_dsn)
    # 启动时一次性完成 BOM 增量迁移，避免每个请求重复执行 6 条 DDL
    bom_repo = BomRepo(app.state.bom_pool)
    await bom_repo.ensure_v3_schema()
    app.state.bom_repo = bom_repo
    app.state.redis = await create_redis_client(settings.redis_url)
    app.state.http_client = create_http_client()
    try:
        yield
    finally:
        await close_http_client(app.state.http_client)
        await close_redis_client(app.state.redis)
        await close_pg_pool(app.state.bom_pool)
        await close_pg_pool(app.state.pg_pool)


app = FastAPI(title="Transparent Agent Framework", version="0.2.0", lifespan=lifespan)

origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(sessions.router)
app.include_router(memories.router)
app.include_router(docs.router)
app.include_router(eval_api.router)
app.include_router(chat.router)
app.include_router(tools.router)
app.include_router(workflows.router)
app.include_router(bom.router)
app.include_router(menus.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
