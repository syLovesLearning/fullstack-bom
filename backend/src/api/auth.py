"""鉴权接口：支持开发一键切换账号、正式注册与密码登录。"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.deps import create_access_token, get_current_auth, get_user_repo
from src.repositories.user_repo import UserRepo
from src.schemas.models import AuthContext, DevLoginRequest, LoginRequest, RegisterRequest

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def _issue_response(row: dict[str, Any]) -> dict[str, Any]:
    auth = AuthContext(
        user_id=row["id"],
        username=row["username"],
        role=row["role"],
        allowed_tools=row["allowed_tools"],
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
) -> dict[str, Any]:
    row = await user_repo.get_or_create_dev_user(
        username=body.username, role=body.role, groups=body.groups
    )
    return _issue_response(row)


@router.post("/register")
async def register(
    body: RegisterRequest,
    user_repo: UserRepo = Depends(get_user_repo),
) -> dict[str, Any]:
    row = await user_repo.register_user(
        username=body.username, password=body.password, role=body.role, groups=body.groups
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="用户名已存在")
    return _issue_response(row)


@router.post("/login")
async def login(
    body: LoginRequest,
    user_repo: UserRepo = Depends(get_user_repo),
) -> dict[str, Any]:
    row = await user_repo.verify_login(username=body.username, password=body.password)
    if row is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
    return _issue_response(row)


@router.get("/me")
async def get_me(auth: AuthContext = Depends(get_current_auth)) -> AuthContext:
    return auth
