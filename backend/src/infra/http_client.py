"""全局复用的异步 HTTPX 客户端（用于大模型与外部 API 调用）。"""

import httpx


def create_http_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=httpx.Timeout(connect=10.0, read=60.0, write=10.0, pool=10.0),
        limits=httpx.Limits(max_connections=50, max_keepalive_connections=20),
    )


async def close_http_client(client: httpx.AsyncClient | None) -> None:
    if client is not None:
        await client.aclose()
