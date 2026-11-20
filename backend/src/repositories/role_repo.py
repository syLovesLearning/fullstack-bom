"""角色与 AI 能力权限仓库：sys_roles 表读写与系统内置角色初始化。"""

from typing import Any
from psycopg_pool import AsyncConnectionPool

DEFAULT_ROLES: list[tuple[str, str, str, list[str], bool]] = [
    (
        "admin",
        "系统管理员",
        "拥有全部 AI 接口、业务流程与系统管理权限",
        [
            "rag_search",
            "memory_save",
            "submit_workflow_form",
            "query_recent_workflows",
            "analyze_tool_demand",
            "query_inventory",
            "bom_quote",
            "bom_stock_check",
            "bom_save_quote",
        ],
        True,
    ),
    (
        "user",
        "研发工程师",
        "可使用知识库检索、长期记忆、流程发起、库存查询与 BOM 试算/保存报价",
        [
            "rag_search",
            "memory_save",
            "submit_workflow_form",
            "query_recent_workflows",
            "analyze_tool_demand",
            "query_inventory",
            "bom_quote",
            "bom_stock_check",
            "bom_save_quote",
        ],
        True,
    ),
    (
        "readonly",
        "只读观察员",
        "仅可检索知识库、查询库存与 BOM 试算，不可保存报价或发起流程",
        [
            "rag_search",
            "query_recent_workflows",
            "analyze_tool_demand",
            "query_inventory",
            "bom_quote",
            "bom_stock_check",
        ],
        True,
    ),
    (
        "external_guest",
        "外部访客",
        "仅限公开知识库问答与访客类流程发起",
        [
            "rag_search",
            "submit_workflow_form",
            "query_recent_workflows",
            "analyze_tool_demand",
        ],
        True,
    ),
]


class RoleRepo:
    def __init__(self, pool: AsyncConnectionPool) -> None:
        self._pool = pool
        self._initialized = False

    async def ensure_initialized(self) -> None:
        if self._initialized:
            return
        ddl = """
            CREATE TABLE IF NOT EXISTS sys_roles (
                role_code     TEXT PRIMARY KEY,
                role_name     TEXT NOT NULL,
                description   TEXT NOT NULL DEFAULT '',
                allowed_tools TEXT[] NOT NULL DEFAULT ARRAY['rag_search'],
                is_system     BOOLEAN NOT NULL DEFAULT FALSE,
                updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
        """
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(ddl)
                for item in DEFAULT_ROLES:
                    await cur.execute(
                        """
                        INSERT INTO sys_roles (role_code, role_name, description, allowed_tools, is_system)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (role_code) DO NOTHING;
                        """,
                        item,
                    )
        self._initialized = True

    async def list_roles(self) -> list[dict[str, Any]]:
        await self.ensure_initialized()
        sql = """
            SELECT role_code, role_name, description, allowed_tools, is_system, updated_at
            FROM sys_roles
            ORDER BY is_system DESC, role_code ASC;
        """
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql)
                return [dict(r) for r in await cur.fetchall()]

    async def get_role(self, role_code: str) -> dict[str, Any] | None:
        await self.ensure_initialized()
        sql = """
            SELECT role_code, role_name, description, allowed_tools, is_system, updated_at
            FROM sys_roles
            WHERE role_code = %s;
        """
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, (role_code,))
                row = await cur.fetchone()
                return dict(row) if row else None

    async def get_allowed_tools(self, role_code: str) -> list[str] | None:
        row = await self.get_role(role_code)
        return list(row["allowed_tools"]) if row else None

    async def upsert_role(
        self,
        role_code: str,
        role_name: str,
        description: str,
        allowed_tools: list[str],
    ) -> dict[str, Any]:
        await self.ensure_initialized()
        clean_tools = list(dict.fromkeys(t.strip() for t in allowed_tools if t.strip()))
        sql = """
            INSERT INTO sys_roles (role_code, role_name, description, allowed_tools, is_system, updated_at)
            VALUES (%s, %s, %s, %s, FALSE, NOW())
            ON CONFLICT (role_code) DO UPDATE
              SET role_name = EXCLUDED.role_name,
                  description = EXCLUDED.description,
                  allowed_tools = EXCLUDED.allowed_tools,
                  updated_at = NOW()
            RETURNING role_code, role_name, description, allowed_tools, is_system, updated_at;
        """
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, (role_code, role_name, description, clean_tools))
                row = await cur.fetchone()
                assert row is not None
                return dict(row)

    async def delete_role(self, role_code: str) -> bool:
        await self.ensure_initialized()
        sql = "DELETE FROM sys_roles WHERE role_code = %s AND is_system = FALSE RETURNING role_code;"
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, (role_code,))
                row = await cur.fetchone()
                return row is not None
