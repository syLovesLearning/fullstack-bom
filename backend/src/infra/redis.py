"""Redis 异步连接池管理（本地未启动 Redis 时允许降级运行）。"""

import logging
from redis.asyncio import Redis

logger = logging.getLogger(__name__)


async def create_redis_client(url: str) -> Redis | None:
    client = Redis.from_url(url, decode_responses=True)
    try:
        await client.ping()
        return client
    except Exception as exc:
        logger.warning("Redis 未连接 (%s)，短期缓冲将自动降级为纯 Postgres 模式", exc)
        await client.aclose()
        return None


async def close_redis_client(client: Redis | None) -> None:
    if client is not None:
        await client.aclose()
