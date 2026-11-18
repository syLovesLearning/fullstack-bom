"""角色与 AI 聊天框能力目录管理接口（动态配置每个角色可发起的工具接口）。"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.deps import (
    get_bom_service,
    get_current_auth,
    get_inventory_repo,
    get_memory_service,
    get_rag_service,
    get_role_repo,
    get_workflow_repo,
)
from src.repositories.inventory_repo import InventoryRepo
from src.repositories.role_repo import RoleRepo
from src.repositories.workflow_repo import WorkflowRepo
from src.schemas.models import AuthContext, SysRoleUpsert
from src.services.bom_service import BomService
from src.services.memory_service import MemoryService
from src.services.rag_service import RagService
from src.services.tool_setup import build_tool_registry

router = APIRouter(prefix="/api/v1/roles", tags=["roles"])


@router.get("")
async def list_roles(
    _auth: AuthContext = Depends(get_current_auth),
    repo: RoleRepo = Depends(get_role_repo),
) -> list[dict[str, Any]]:
    return await repo.list_roles()


@router.get("/tools-catalog")
async def list_tools_catalog(
    _auth: AuthContext = Depends(get_current_auth),
    rag_service: RagService = Depends(get_rag_service),
    memory_service: MemoryService = Depends(get_memory_service),
    bom_service: BomService = Depends(get_bom_service),
    workflow_repo: WorkflowRepo = Depends(get_workflow_repo),
    inventory_repo: InventoryRepo = Depends(get_inventory_repo),
) -> list[dict[str, Any]]:
    """返回系统注册的全部 AI 工具目录（不按当前用户裁剪，供角色管理页勾选）。"""
    registry = build_tool_registry(
        rag_service=rag_service,
        memory_service=memory_service,
        workflow_repo=workflow_repo,
        inventory_repo=inventory_repo,
        bom_service=bom_service,
    )
    schemas = registry.list_schemas(allowed_tools=["*"])
    return [
        {
            "name": s["function"]["name"],
            "description": s["function"]["description"],
            "parameters": s["function"]["parameters"],
        }
        for s in schemas
    ]


@router.put("/{role_code}")
async def upsert_role(
    role_code: str,
    body: SysRoleUpsert,
    auth: AuthContext = Depends(get_current_auth),
    repo: RoleRepo = Depends(get_role_repo),
) -> dict[str, Any]:
    if auth.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅管理员可配置角色能力")
    if body.role_code != role_code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="路径 role_code 与请求体不一致")
    return await repo.upsert_role(
        role_code=role_code,
        role_name=body.role_name,
        description=body.description,
        allowed_tools=body.allowed_tools,
    )


@router.delete("/{role_code}")
async def delete_role(
    role_code: str,
    auth: AuthContext = Depends(get_current_auth),
    repo: RoleRepo = Depends(get_role_repo),
) -> dict[str, Any]:
    if auth.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅管理员可删除角色")
    deleted = await repo.delete_role(role_code)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="系统内置角色不可删除或角色不存在",
        )
    return {"deleted": True, "role_code": role_code}
