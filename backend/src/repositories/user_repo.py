"""用户与权限数据仓库（支持角色、分组数据权限与 PBKDF2 密码校验）。"""

import hashlib
import hmac
import os
from typing import Any
from uuid import UUID

from psycopg_pool import AsyncConnectionPool


def _hash_password(password: str, salt: bytes | None = None) -> str:
    s = salt or os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), s, 100_000)
    return f"{s.hex()}${dk.hex()}"


def _verify_password(password: str, stored: str) -> bool:
    if "$" not in stored:
        return False
    salt_hex, dk_hex = stored.split("$", 1)
    expected = _hash_password(password, bytes.fromhex(salt_hex)).split("$", 1)[1]
    return hmac.compare_digest(expected, dk_hex)


def _default_groups_for_role(role: str) -> list[str]:
    if role == "admin":
        return ["public", "engineering", "finance"]
    if role == "user":
        return ["public", "engineering"]
    return ["public"]


class UserRepo:
    def __init__(self, pool: AsyncConnectionPool) -> None:
        self._pool = pool

    async def get_or_create_dev_user(
        self, username: str, role: str = "admin", groups: list[str] | None = None, allowed_tools: list[str] | None = None
    ) -> dict[str, Any]:
        if allowed_tools is not None:
            default_tools = allowed_tools
        elif role in ("admin", "user"):
            default_tools = ["rag_search", "memory_save", "submit_workflow_form", "query_recent_workflows", "query_inventory", "bom_quote", "bom_stock_check"]
        elif role == "external_guest":
            default_tools = ["rag_search", "submit_workflow_form", "query_recent_workflows"]
        else:
            default_tools = ["rag_search", "query_recent_workflows", "query_inventory"]
        user_groups = groups if groups is not None else _default_groups_for_role(role)
        sql = """
            INSERT INTO users (username, password_hash, role, allowed_tools, groups)
            VALUES (%s, 'dev-only-no-password', %s, %s, %s)
            ON CONFLICT (username) DO UPDATE
              SET role = EXCLUDED.role,
                  allowed_tools = EXCLUDED.allowed_tools,
                  groups = EXCLUDED.groups
            RETURNING id, username, role, allowed_tools, groups, is_active;
        """
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, (username, role, default_tools, user_groups))
                row = await cur.fetchone()
                assert row is not None
                return dict(row)

    async def register_user(
        self, username: str, password: str, role: str, groups: list[str]
    ) -> dict[str, Any] | None:
        if role in ("admin", "user"):
            default_tools = ["rag_search", "memory_save", "submit_workflow_form", "query_recent_workflows", "query_inventory", "bom_quote", "bom_stock_check"]
        elif role == "external_guest":
            default_tools = ["rag_search", "submit_workflow_form", "query_recent_workflows"]
        else:
            default_tools = ["rag_search", "query_recent_workflows", "query_inventory"]
        pwd_hash = _hash_password(password)
        sql = """
            INSERT INTO users (username, password_hash, role, allowed_tools, groups)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (username) DO NOTHING
            RETURNING id, username, role, allowed_tools, groups, is_active;
        """
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, (username, pwd_hash, role, default_tools, groups))
                row = await cur.fetchone()
                return dict(row) if row else None

    async def verify_login(self, username: str, password: str) -> dict[str, Any] | None:
        sql = "SELECT id, username, password_hash, role, allowed_tools, groups, is_active FROM users WHERE username = %s;"
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, (username,))
                row = await cur.fetchone()
                if not row or not row["is_active"] or not _verify_password(password, row["password_hash"]):
                    return None
                return dict(row)

    async def get_by_id(self, user_id: UUID) -> dict[str, Any] | None:
        sql = "SELECT id, username, role, allowed_tools, groups, is_active FROM users WHERE id = %s;"
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, (user_id,))
                row = await cur.fetchone()
                return dict(row) if row else None
