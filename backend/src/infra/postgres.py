"""PostgreSQL 异步连接池生命周期管理（psycopg3）。"""

from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool


async def create_pg_pool(dsn: str) -> AsyncConnectionPool:
    pool = AsyncConnectionPool(
        conninfo=dsn,
        min_size=2,
        max_size=10,
        open=False,
        kwargs={"row_factory": dict_row},
    )
    await pool.open()
    return pool


async def close_pg_pool(pool: AsyncConnectionPool | None) -> None:
    if pool is not None:
        await pool.close()
