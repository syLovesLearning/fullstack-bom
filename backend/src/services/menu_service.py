"""动态菜单编排服务：按角色返回可见菜单树并保护系统配置入口不被锁死。"""

from typing import Any
from src.repositories.menu_repo import MenuRepo


class MenuService:
    def __init__(self, repo: MenuRepo) -> None:
        self._repo = repo

    async def list_visible_menus(self, role: str) -> list[dict[str, Any]]:
        return await self._repo.list_for_role(role)

    async def list_all_menus(self) -> list[dict[str, Any]]:
        return await self._repo.list_all()

    async def update_menu(self, menu_key: str, data: dict[str, Any]) -> dict[str, Any] | None:
        return await self._repo.update_menu(menu_key, data)
