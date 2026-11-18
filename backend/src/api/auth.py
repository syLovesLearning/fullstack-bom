"""鉴权接口：支持开发一键切换角色、个人密钥门禁、正式注册与密码登录。"""

import hmac
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.deps import create_access_token, get_current_auth, get_role_repo, get_user_repo
from src.config import settings
from src.repositories.role_repo import RoleRepo
from src.repositories.user_repo import UserRepo
from src.schemas.models import AuthContext, DevLoginRequest, LoginRequest, PasscodeLoginRequest, RegisterRequest

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def _issue_response(row: dict[str, Any], allowed_tools: list[str] | None = None) -> dict[str, Any]:
    auth = AuthContext(
        user_id=row["id"],
        username=row["username"],
        role=row["role"],
        allowed_tools=allowed_tools if allowed_tools is not None else row["allowed_tools"],
        groups=row.get("groups", ["public"]),
    )
    return {
        "access_token": create_access_token(auth),
        "token_type": "bearer",
        "user": auth.model_dump(mode="json"),
    }


@router.post("/dev-login")
async def dev_login(
    body: DevLoginRequest,
    user_repo: UserRepo = Depends(get_user_repo),
    role_repo: RoleRepo = Depends(get_role_repo),
) -> dict[str, Any]:
    if settings.env != "dev":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="dev-login 仅限开发环境使用")
    role_row = await role_repo.get_role(body.role)
    if role_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"角色 {body.role} 不存在")
    row = await user_repo.get_or_create_dev_user(
        username=body.username,
        role=body.role,
        groups=body.groups,
        allowed_tools=role_row["allowed_tools"],
    )
    return _issue_response(row, allowed_tools=role_row["allowed_tools"])


@router.post("/register")
async def register(
    body: RegisterRequest,
    user_repo: UserRepo = Depends(get_user_repo),
    role_repo: RoleRepo = Depends(get_role_repo),
) -> dict[str, Any]:
    if body.role == "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="不允许自助注册管理员角色")
    live_tools = await role_repo.get_allowed_tools(body.role)
    row = await user_repo.register_user(
        username=body.username, password=body.password, role=body.role, groups=body.groups
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="用户名已存在")
    return _issue_response(row, allowed_tools=live_tools)


@router.post("/login")
async def login(
    body: LoginRequest,
    user_repo: UserRepo = Depends(get_user_repo),
    role_repo: RoleRepo = Depends(get_role_repo),
) -> dict[str, Any]:
    row = await user_repo.verify_login(username=body.username, password=body.password)
    if row is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
    live_tools = await role_repo.get_allowed_tools(row["role"])
    return _issue_response(row, allowed_tools=live_tools)


@router.get("/me")
async def get_me(auth: AuthContext = Depends(get_current_auth)) -> AuthContext:
    return auth


@router.post("/passcode-login")
async def passcode_login(
    body: PasscodeLoginRequest,
    user_repo: UserRepo = Depends(get_user_repo),
    role_repo: RoleRepo = Depends(get_role_repo),
) -> dict[str, Any]:
    if not hmac.compare_digest(body.passcode.strip(), settings.resume_access_key):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="访问密钥错误")
    live_tools = await role_repo.get_allowed_tools("admin")
    row = await user_repo.get_or_create_dev_user(
        username="shenyang", role="admin", groups=["public", "engineering", "finance"], allowed_tools=live_tools
    )
    return _issue_response(row, allowed_tools=live_tools)


@router.get("/mode")
async def get_auth_mode() -> dict[str, Any]:
    return {"env": settings.env, "require_passcode": settings.env != "dev"}
