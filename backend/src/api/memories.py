"""长期记忆管理 REST 接口：支持前端可视化查看、新增与人工纠偏删除。"""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.deps import get_current_auth, get_memory_repo
from src.repositories.memory_repo import MemoryRepo
from src.schemas.models import AuthContext, MemoryCreate

router = APIRouter(prefix="/api/v1/memories", tags=["memories"])


@router.get("")
async def list_memories(
    auth: AuthContext = Depends(get_current_auth),
    repo: MemoryRepo = Depends(get_memory_repo),
) -> list[dict[str, Any]]:
    return await repo.list_memories(user_id=auth.user_id)


@router.post("")
async def create_memory(
    body: MemoryCreate,
    auth: AuthContext = Depends(get_current_auth),
    repo: MemoryRepo = Depends(get_memory_repo),
) -> dict[str, Any]:
    return await repo.create_memory(
        user_id=auth.user_id,
        memory_type=body.memory_type,
        content=body.content,
        importance=body.importance,
    )


@router.delete("/{memory_id}")
async def delete_memory(
    memory_id: UUID,
    auth: AuthContext = Depends(get_current_auth),
    repo: MemoryRepo = Depends(get_memory_repo),
) -> dict[str, bool]:
    deleted = await repo.soft_delete(memory_id=memory_id, user_id=auth.user_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory not found")
    return {"deleted": True}
