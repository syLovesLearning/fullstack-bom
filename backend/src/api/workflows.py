"""配置化企业流程中心 REST 接口（按角色过滤可用流程 + 动态新建流程类型 + 分页台账）。"""

from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from src.api.deps import get_current_auth, get_workflow_repo
from src.repositories.workflow_repo import WorkflowRepo
from src.schemas.models import AuthContext
from src.services.workflow_skills import validate_dynamic_workflow

router = APIRouter(prefix="/api/v1/workflows", tags=["workflows"])


class WorkflowSubmitRequest(BaseModel):
    flow_code: str = Field(min_length=2, max_length=64)
    form_data: dict[str, Any]


class WorkflowStatusUpdate(BaseModel):
    status: Literal["approved", "rejected"]
    channel: Literal["form", "chat_card"] = "form"


class WorkflowDefinitionUpsert(BaseModel):
    flow_code: str = Field(min_length=2, max_length=64, pattern=r"^[a-z0-9_]+$")
    name: str = Field(min_length=2, max_length=100)
    description: str = ""
    allowed_roles: list[Literal["admin", "user", "readonly", "external_guest"]] = Field(
        default_factory=lambda: ["admin", "user"]
    )
    fields: list[dict[str, Any]] = Field(min_length=1)


@router.get("/skills")
async def list_workflow_skills(
    auth: AuthContext = Depends(get_current_auth),
    repo: WorkflowRepo = Depends(get_workflow_repo),
) -> list[dict[str, Any]]:
    """按当前用户角色返回有权限调用的配置化流程定义。"""
    return await repo.list_definitions(role=auth.role)


@router.post("/definitions")
async def upsert_workflow_definition(
    body: WorkflowDefinitionUpsert,
    auth: AuthContext = Depends(get_current_auth),
    repo: WorkflowRepo = Depends(get_workflow_repo),
) -> dict[str, Any]:
    if auth.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅管理员可配置新流程类型")
    return await repo.upsert_definition(
        flow_code=body.flow_code,
        name=body.name,
        description=body.description,
        allowed_roles=body.allowed_roles,
        fields=body.fields,
    )


@router.post("")
async def submit_workflow(
    body: WorkflowSubmitRequest,
    auth: AuthContext = Depends(get_current_auth),
    repo: WorkflowRepo = Depends(get_workflow_repo),
) -> dict[str, Any]:
    if auth.role == "readonly":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="只读角色无权发起流程")
    defn = await repo.get_definition(body.flow_code)
    if defn is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"未找到流程定义: {body.flow_code}")
    if auth.role not in defn.get("allowed_roles", []):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"角色 {auth.role} 无权发起流程 {defn['name']}",
        )
    try:
        title, clean_data = validate_dynamic_workflow(defn, body.form_data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    return await repo.create_instance(
        user_id=auth.user_id, flow_code=body.flow_code, title=title, form_data=clean_data
    )


@router.get("")
async def list_workflows(
    flow_code: str | None = Query(default=None),
    scope: str = Query(default="mine", pattern="^(mine|all)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=50),
    auth: AuthContext = Depends(get_current_auth),
    repo: WorkflowRepo = Depends(get_workflow_repo),
) -> dict[str, Any]:
    # scope=all 仅 admin 可用（审批视图，可看到他人发起的流程）；普通用户固定只看自己的台账
    if scope == "all" and auth.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅管理员可查看全量流程台账")
    owner_filter = None if scope == "all" else auth.user_id
    return await repo.list_instances(
        owner_user_id=owner_filter,
        flow_code=flow_code or None,
        page=page,
        page_size=page_size,
    )


@router.patch("/{instance_id}/status")
async def update_workflow_status(
    instance_id: UUID,
    body: WorkflowStatusUpdate,
    auth: AuthContext = Depends(get_current_auth),
    repo: WorkflowRepo = Depends(get_workflow_repo),
) -> dict[str, Any]:
    # 审批规则：仅 admin 可审批，且不得审批自己发起的流程（防止自审自批）
    if auth.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅管理员可审批流程")
    instance = await repo.get_instance(instance_id)
    if instance is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="流程实例不存在")
    if instance["user_id"] == auth.user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="不得审批自己发起的流程")
    row = await repo.update_status_idempotent(
        instance_id=instance_id,
        owner_user_id=instance["user_id"],
        status=body.status,
        operator=auth.username,
        channel=body.channel,
    )
    if not row:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="流程不存在或已完成审批，请勿重复操作",
        )
    return row
