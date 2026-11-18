"""动态菜单仓库：sys_menus 表读写与自动建表/种子兜底。"""

from typing import Any
from psycopg_pool import AsyncConnectionPool

DEFAULT_MENUS: list[tuple[str, str, str, str, int, list[str], bool]] = [
    ("overview", "能力全景概览", "工作台", "◈", 10, ["admin", "user", "readonly", "external_guest"], True),
    ("bom", "BOM 算料维护", "业务中心", "❖", 20, ["admin", "user", "readonly"], True),
    ("workflow", "OA/SRM 流程", "业务中心", "⚡", 30, ["admin", "user", "external_guest"], True),
    ("chat", "AI 流程工作台", "AI 与记忆", "✦", 40, ["admin", "user", "readonly", "external_guest"], True),
    ("mem", "长期记忆中心", "AI 与记忆", "◉", 50, ["admin", "user"], True),
    ("kb", "知识库管理", "系统管理", "▤", 60, ["admin", "user", "readonly"], True),
    ("lab", "命中透视台", "系统管理", "◎", 70, ["admin", "user", "readonly"], True),
    ("eval", "黄金测试集", "系统管理", "★", 80, ["admin", "user", "readonly"], True),
    ("api", "接口测试台", "系统管理", "⌘", 90, ["admin", "user"], True),
    ("menu_admin", "动态菜单配置", "系统管理", "⚙", 100, ["admin"], True),
]


class MenuRepo:
    def __init__(self, pool: AsyncConnectionPool) -> None:
        self._pool = pool

    async def ensure_initialized(self) -> None:
        ddl = """
            CREATE TABLE IF NOT EXISTS sys_menus (
                menu_key        TEXT PRIMARY KEY,
                title           TEXT NOT NULL,
                group_name      TEXT NOT NULL,
                icon            TEXT NOT NULL DEFAULT '▣',
                sort_order      INTEGER NOT NULL DEFAULT 10,
                allowed_roles   TEXT[] NOT NULL DEFAULT ARRAY['admin', 'user', 'readonly'],
                is_enabled      BOOLEAN NOT NULL DEFAULT TRUE,
                updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
        """
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(ddl)
                await cur.execute("SELECT COUNT(*) AS cnt FROM sys_menus;")
                row = await cur.fetchone()
                if row and row["cnt"] == 0:
                    for item in DEFAULT_MENUS:
                        await cur.execute(
                            """
                            INSERT INTO sys_menus (menu_key, title, group_name, icon, sort_order, allowed_roles, is_enabled)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (menu_key) DO NOTHING;
                            """,
                            item,
                        )

    async def list_for_role(self, role: str) -> list[dict[str, Any]]:
        await self.ensure_initialized()
        sql = """
            SELECT menu_key, title, group_name, icon, sort_order, allowed_roles, is_enabled
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
            SELECT menu_key, title, group_name, icon, sort_order, allowed_roles, is_enabled
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
        if menu_key == "menu_admin":
            if "admin" not in roles:
                roles.append("admin")
            enabled = True

        sql = """
            UPDATE sys_menus
            SET title = %s, group_name = %s, icon = %s, sort_order = %s,
                allowed_roles = %s, is_enabled = %s, updated_at = NOW()
            WHERE menu_key = %s
            RETURNING menu_key, title, group_name, icon, sort_order, allowed_roles, is_enabled;
        """
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    sql,
                    (
                        data["title"],
                        data["group_name"],
                        data.get("icon", "▣"),
                        data["sort_order"],
                        roles,
                        enabled,
                        menu_key,
                    ),
                )
                row = await cur.fetchone()
                return dict(row) if row else None
