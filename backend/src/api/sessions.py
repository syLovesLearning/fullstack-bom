"""会话管理 REST 接口（严格按 user_id 隔离，支持重命名与删除）。"""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.deps import get_current_auth, get_session_repo
from src.repositories.session_repo import SessionRepo
from src.schemas.models import AuthContext, SessionCreate, SessionUpdate

router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])


@router.post("")
async def create_session(
    body: SessionCreate,
    auth: AuthContext = Depends(get_current_auth),
    repo: SessionRepo = Depends(get_session_repo),
) -> dict[str, Any]:
    return await repo.create_session(user_id=auth.user_id, agent_name=body.agent_name, title=body.title)


@router.get("")
async def list_sessions(
    auth: AuthContext = Depends(get_current_auth),
    repo: SessionRepo = Depends(get_session_repo),
) -> list[dict[str, Any]]:
    return await repo.list_sessions(user_id=auth.user_id)


@router.patch("/{session_id}")
async def rename_session(
    session_id: UUID,
    body: SessionUpdate,
    auth: AuthContext = Depends(get_current_auth),
    repo: SessionRepo = Depends(get_session_repo),
) -> dict[str, Any]:
    updated = await repo.rename_session(session_id=session_id, user_id=auth.user_id, title=body.title)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return updated


@router.delete("/{session_id}")
async def delete_session(
    session_id: UUID,
    auth: AuthContext = Depends(get_current_auth),
    repo: SessionRepo = Depends(get_session_repo),
) -> dict[str, bool]:
    deleted = await repo.delete_session(session_id=session_id, user_id=auth.user_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return {"deleted": True}


@router.get("/{session_id}/messages")
async def list_messages(
    session_id: UUID,
    auth: AuthContext = Depends(get_current_auth),
    repo: SessionRepo = Depends(get_session_repo),
) -> list[dict[str, Any]]:
    session = await repo.get_session(session_id=session_id, user_id=auth.user_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return await repo.list_messages(session_id=session_id, user_id=auth.user_id)
