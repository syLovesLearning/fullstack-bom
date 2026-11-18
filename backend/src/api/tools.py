"""能力发现与轨迹审计接口（按用户权限裁剪工具列表）。"""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.deps import (
    get_bom_service,
    get_current_auth,
    get_inventory_repo,
    get_memory_service,
    get_rag_service,
    get_trace_repo,
    get_workflow_repo,
)
from src.repositories.inventory_repo import InventoryRepo
from src.repositories.trace_repo import TraceRepo
from src.repositories.workflow_repo import WorkflowRepo
from src.schemas.models import AuthContext
from src.services.bom_service import BomService
from src.services.memory_service import MemoryService
from src.services.rag_service import RagService
from src.services.tool_setup import build_tool_registry

router = APIRouter(prefix="/api/v1", tags=["tools-and-trace"])


@router.get("/tools")
async def list_available_tools(
    auth: AuthContext = Depends(get_current_auth),
    rag_service: RagService = Depends(get_rag_service),
    memory_service: MemoryService = Depends(get_memory_service),
    bom_service: BomService = Depends(get_bom_service),
    workflow_repo: WorkflowRepo = Depends(get_workflow_repo),
    inventory_repo: InventoryRepo = Depends(get_inventory_repo),
) -> list[dict[str, Any]]:
    # 与 chat_stream 的 registry 构建保持一致：workflow/inventory 工具也要出现在能力发现中
    registry = build_tool_registry(
        rag_service=rag_service,
        memory_service=memory_service,
        workflow_repo=workflow_repo,
        inventory_repo=inventory_repo,
        bom_service=bom_service,
    )
    return registry.list_schemas(allowed_tools=auth.allowed_tools)


@router.get("/runs/{run_id}/trace")
async def get_run_trace(
    run_id: UUID,
    auth: AuthContext = Depends(get_current_auth),
    trace_repo: TraceRepo = Depends(get_trace_repo),
) -> dict[str, Any]:
    trace = await trace_repo.get_run_trace(run_id=run_id, user_id=auth.user_id)
    if not trace:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run trace not found")
    return trace
