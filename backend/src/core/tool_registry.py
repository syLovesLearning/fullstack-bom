"""声明式工具注册表：基于 Pydantic Schema 自动生成描述并校验入参。"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import json
from typing import Any

from pydantic import BaseModel, ValidationError


@dataclass
class RegisteredTool:
    name: str
    description: str
    args_model: type[BaseModel]
    handler: Callable[[BaseModel], Awaitable[str]]


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, RegisteredTool] = {}

    def register(
        self,
        name: str,
        description: str,
        args_model: type[BaseModel],
    ) -> Callable[[Callable[[Any], Awaitable[str]]], Callable[[Any], Awaitable[str]]]:
        def decorator(fn: Callable[[Any], Awaitable[str]]) -> Callable[[Any], Awaitable[str]]:
            self._tools[name] = RegisteredTool(
                name=name,
                description=description,
                args_model=args_model,
                handler=fn,
            )
            return fn

        return decorator

    def list_schemas(self, allowed_tools: list[str] | None = None) -> list[dict[str, Any]]:
        """按用户权限裁剪工具列表：无权工具对大模型不可见。"""
        schemas: list[dict[str, Any]] = []
        for tool in self._tools.values():
            if allowed_tools is not None and "*" not in allowed_tools and tool.name not in allowed_tools:
                continue
            schemas.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.args_model.model_json_schema(),
                    },
                }
            )
        return schemas

    async def execute(self, name: str, raw_args: dict[str, Any]) -> str:
        tool = self._tools.get(name)
        if tool is None:
            return json.dumps({"error": f"Tool '{name}' is not registered"}, ensure_ascii=False)
        try:
            validated = tool.args_model.model_validate(raw_args)
        except ValidationError as exc:
            return json.dumps({"error": f"Invalid arguments: {exc.errors()}"}, ensure_ascii=False)
        return await tool.handler(validated)
