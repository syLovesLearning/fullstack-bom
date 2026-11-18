"""企业流程定义与实例数据仓库（配置化流程 + 分页台账 + 幂等审批）。"""

import json
from typing import Any
from uuid import UUID

from psycopg_pool import AsyncConnectionPool


class WorkflowRepo:
    def __init__(self, pool: AsyncConnectionPool) -> None:
        self._pool = pool

    async def list_definitions(self, role: str | None = None) -> list[dict[str, Any]]:
        if role:
            sql = """
                SELECT flow_code, name, description, allowed_roles, fields
                FROM workflow_definitions
                WHERE is_active = TRUE AND %s = ANY(allowed_roles)
                ORDER BY created_at ASC;
            """
            params: tuple[Any, ...] = (role,)
        else:
            sql = """
                SELECT flow_code, name, description, allowed_roles, fields
                FROM workflow_definitions
                WHERE is_active = TRUE
                ORDER BY created_at ASC;
            """
            params = ()
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, params)
                return [dict(r) for r in await cur.fetchall()]

    async def get_definition(self, flow_code: str) -> dict[str, Any] | None:
        sql = """
            SELECT flow_code, name, description, allowed_roles, fields
            FROM workflow_definitions
            WHERE flow_code = %s AND is_active = TRUE;
        """
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, (flow_code,))
                row = await cur.fetchone()
                return dict(row) if row else None

    async def upsert_definition(
        self,
        flow_code: str,
        name: str,
        description: str,
        allowed_roles: list[str],
        fields: list[dict[str, Any]],
    ) -> dict[str, Any]:
        sql = """
            INSERT INTO workflow_definitions (flow_code, name, description, allowed_roles, fields)
            VALUES (%s, %s, %s, %s, %s::jsonb)
            ON CONFLICT (flow_code) DO UPDATE
              SET name = EXCLUDED.name,
                  description = EXCLUDED.description,
                  allowed_roles = EXCLUDED.allowed_roles,
                  fields = EXCLUDED.fields,
                  is_active = TRUE
            RETURNING flow_code, name, description, allowed_roles, fields;
        """
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    sql, (flow_code, name, description, allowed_roles, json.dumps(fields, ensure_ascii=False))
                )
                row = await cur.fetchone()
                assert row is not None
                return dict(row)

    async def get_instance(self, instance_id: UUID) -> dict[str, Any] | None:
        """取流程实例归属（审批前校验 owner，防止自审自批）。"""
        sql = "SELECT id, user_id, flow_code, title, status FROM workflow_instances WHERE id = %s;"
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, (instance_id,))
                row = await cur.fetchone()
                return dict(row) if row else None

    async def create_instance(
        self, user_id: UUID, flow_code: str, title: str, form_data: dict[str, Any]
    ) -> dict[str, Any]:
        sql = """
            INSERT INTO workflow_instances (user_id, flow_code, title, form_data)
            VALUES (%s, %s, %s, %s::jsonb)
            RETURNING id, user_id, flow_code, title, form_data, status, created_at;
        """
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    sql, (user_id, flow_code, title, json.dumps(form_data, ensure_ascii=False))
                )
                row = await cur.fetchone()
                assert row is not None
                return dict(row)

    async def list_instances(
        self,
        owner_user_id: UUID | None,
        flow_code: str | None = None,
        page: int = 1,
        page_size: int = 10,
    ) -> dict[str, Any]:
        """owner_user_id=None 视为全量台账（仅供 admin 审批视图使用，权限在 API 层裁定）。"""
        offset = (page - 1) * page_size
        count_sql = """
            SELECT COUNT(*) AS cnt
            FROM workflow_instances
            WHERE (%s::uuid IS NULL OR user_id = %s) AND (%s::text IS NULL OR flow_code = %s);
        """
        list_sql = """
            SELECT w.id, w.user_id, u.username AS owner_name, w.flow_code, w.title, w.form_data,
                   w.status, w.approved_by, w.action_channel, w.approved_at, w.created_at
            FROM workflow_instances w JOIN users u ON u.id = w.user_id
            WHERE (%s::uuid IS NULL OR w.user_id = %s) AND (%s::text IS NULL OR w.flow_code = %s)
            ORDER BY w.created_at DESC
            LIMIT %s OFFSET %s;
        """
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(count_sql, (owner_user_id, owner_user_id, flow_code, flow_code))
                cnt_row = await cur.fetchone()
                total = int(cnt_row["cnt"]) if cnt_row else 0
                await cur.execute(
                    list_sql, (owner_user_id, owner_user_id, flow_code, flow_code, page_size, offset)
                )
                items = [dict(r) for r in await cur.fetchall()]
                return {"items": items, "total": total, "page": page, "page_size": page_size}

    async def update_status_idempotent(
        self,
        instance_id: UUID,
        owner_user_id: UUID,
        status: str,
        operator: str,
        channel: str = "form",
    ) -> dict[str, Any] | None:
        """审批落库：owner_user_id 用于兜底约束（API 层已校验审批人非发起人）。"""
        sql = """
            UPDATE workflow_instances
            SET status = %s, approved_by = %s, action_channel = %s, approved_at = NOW()
            WHERE id = %s AND user_id = %s AND status = 'submitted'
            RETURNING id, flow_code, title, status, approved_by, action_channel, approved_at;
        """
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, (status, operator, channel, instance_id, owner_user_id))
                row = await cur.fetchone()
                return dict(row) if row else None
