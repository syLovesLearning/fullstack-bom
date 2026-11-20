"""动态菜单仓库：sys_menus 表读写、自动建表/种子兜底及外部微服务 URL 挂载。"""

from typing import Any
from psycopg_pool import AsyncConnectionPool

DEFAULT_MENUS: list[tuple[str, str, str, str, int, list[str], bool, str]] = [
    ("overview", "能力全景概览", "工作台", "◈", 10, ["admin", "user", "readonly", "external_guest"], True, ""),
    ("feature_guide", "功能文档说明", "工作台", "📖", 15, ["admin", "user", "readonly", "external_guest"], True, ""),
    ("bom", "BOM 算料维护", "业务中心", "❖", 20, ["admin", "user", "readonly"], True, ""),
    ("perf_3d", "3D 渲染提效", "业务中心", "🚀", 25, ["admin", "user", "readonly"], True, ""),
    ("workflow", "OA/SRM 流程", "业务中心", "⚡", 30, ["admin", "user", "external_guest"], True, ""),
    ("badminton_power", "羽毛球发力分析", "业务中心", "🏸", 35, ["admin", "user"], True, "http://127.0.0.1:8090"),
    ("chat", "AI 流程工作台", "AI 与记忆", "✦", 40, ["admin", "user", "readonly", "external_guest"], True, ""),
    ("mem", "长期记忆中心", "AI 与记忆", "◉", 50, ["admin", "user"], True, ""),
    ("kb", "知识库管理", "系统管理", "▤", 60, ["admin", "user", "readonly"], True, ""),
    ("lab", "命中透视台", "系统管理", "◎", 70, ["admin", "user", "readonly"], True, ""),
    ("eval", "黄金测试集", "系统管理", "★", 80, ["admin", "user", "readonly"], True, ""),
    ("api", "接口测试台", "系统管理", "⌘", 90, ["admin", "user"], True, ""),
    ("menu_admin", "动态菜单配置", "系统管理", "⚙", 100, ["admin"], True, ""),
    ("role_admin", "角色与能力", "系统管理", "⛨", 105, ["admin"], True, ""),
]


class MenuRepo:
    def __init__(self, pool: AsyncConnectionPool) -> None:
        self._pool = pool
        self._initialized = False

    async def ensure_initialized(self) -> None:
        if self._initialized:
            return
        ddl = """
            CREATE TABLE IF NOT EXISTS sys_menus (
                menu_key        TEXT PRIMARY KEY,
                title           TEXT NOT NULL,
                group_name      TEXT NOT NULL,
                icon            TEXT NOT NULL DEFAULT '▣',
                sort_order      INTEGER NOT NULL DEFAULT 10,
                allowed_roles   TEXT[] NOT NULL DEFAULT ARRAY['admin', 'user', 'readonly'],
                is_enabled      BOOLEAN NOT NULL DEFAULT TRUE,
                external_url    TEXT NOT NULL DEFAULT '',
                updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            ALTER TABLE sys_menus ADD COLUMN IF NOT EXISTS external_url TEXT NOT NULL DEFAULT '';
        """
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(ddl)
                for item in DEFAULT_MENUS:
                    await cur.execute(
                        """
                        INSERT INTO sys_menus (menu_key, title, group_name, icon, sort_order, allowed_roles, is_enabled, external_url)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (menu_key) DO NOTHING;
                        """,
                        item,
                    )
        self._initialized = True

    async def list_for_role(self, role: str) -> list[dict[str, Any]]:
        await self.ensure_initialized()
        sql = """
            SELECT menu_key, title, group_name, icon, sort_order, allowed_roles, is_enabled, external_url
            FROM sys_menus
            WHERE is_enabled = TRUE AND %s = ANY(allowed_roles)
            ORDER BY sort_order ASC, menu_key ASC;
        """
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, (role,))
                return [dict(r) for r in await cur.fetchall()]

    async def list_all(self) -> list[dict[str, Any]]:
        await self.ensure_initialized()
        sql = """
            SELECT menu_key, title, group_name, icon, sort_order, allowed_roles, is_enabled, external_url
            FROM sys_menus
            ORDER BY sort_order ASC, menu_key ASC;
        """
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql)
                return [dict(r) for r in await cur.fetchall()]

    async def update_menu(self, menu_key: str, data: dict[str, Any]) -> dict[str, Any] | None:
        await self.ensure_initialized()
        roles = list(data["allowed_roles"])
        enabled = bool(data["is_enabled"])
        if menu_key in ("menu_admin", "role_admin"):
            if "admin" not in roles:
                roles.append("admin")
            enabled = True
        sql = """
            UPDATE sys_menus
            SET title = %s, group_name = %s, icon = %s, sort_order = %s,
                allowed_roles = %s, is_enabled = %s, external_url = %s, updated_at = NOW()
            WHERE menu_key = %s
            RETURNING menu_key, title, group_name, icon, sort_order, allowed_roles, is_enabled, external_url;
        """
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    sql,
                    (data["title"], data["group_name"], data.get("icon", "▣"), data["sort_order"], roles, enabled, data.get("external_url", ""), menu_key),
                )
                row = await cur.fetchone()
                return dict(row) if row else None

    async def upsert_menu(
        self, menu_key: str, title: str, group_name: str, allowed_roles: list[str], external_url: str = "", icon: str = "◈"
    ) -> dict[str, Any]:
        await self.ensure_initialized()
        roles = list(dict.fromkeys(["admin", *allowed_roles]))
        sql = """
            INSERT INTO sys_menus (menu_key, title, group_name, icon, sort_order, allowed_roles, is_enabled, external_url)
            VALUES (%s, %s, %s, %s, 55, %s, TRUE, %s)
            ON CONFLICT (menu_key) DO UPDATE
              SET title = EXCLUDED.title, group_name = EXCLUDED.group_name,
                  allowed_roles = EXCLUDED.allowed_roles, is_enabled = TRUE,
                  external_url = EXCLUDED.external_url, updated_at = NOW()
            RETURNING menu_key, title, group_name, icon, sort_order, allowed_roles, is_enabled, external_url;
        """
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, (menu_key, title, group_name, icon, roles, external_url))
                row = await cur.fetchone()
                assert row is not None
                return dict(row)

    async def delete_menu(self, menu_key: str) -> bool:
        await self.ensure_initialized()
        builtin = {item[0] for item in DEFAULT_MENUS}
        if menu_key in builtin:
            return False
        sql = "DELETE FROM sys_menus WHERE menu_key = %s RETURNING menu_key;"
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, (menu_key,))
                return (await cur.fetchone()) is not None
