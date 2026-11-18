"""动态菜单 REST 接口：支持按角色拉取左侧菜单与管理员在线配置。"""

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status

from src.api.deps import get_current_auth, get_menu_service
from src.schemas.models import AuthContext, SysMenuUpdate
from src.services.menu_service import MenuService

router = APIRouter(prefix="/api/v1/menus", tags=["menus"])


@router.get("")
async def get_my_menus(
    auth: AuthContext = Depends(get_current_auth),
    svc: MenuService = Depends(get_menu_service),
) -> list[dict[str, Any]]:
    return await svc.list_visible_menus(role=auth.role)


@router.get("/all")
async def get_all_menus(
    auth: AuthContext = Depends(get_current_auth),
    svc: MenuService = Depends(get_menu_service),
) -> list[dict[str, Any]]:
    return await svc.list_all_menus()


@router.put("/{menu_key}")
async def update_menu_config(
    menu_key: str,
    body: SysMenuUpdate,
    auth: AuthContext = Depends(get_current_auth),
    svc: MenuService = Depends(get_menu_service),
) -> dict[str, Any]:
    if auth.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admin can modify menus")
    updated = await svc.update_menu(menu_key, body.model_dump())
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Menu key not found")
    return updated
