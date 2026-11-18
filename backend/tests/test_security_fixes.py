"""安全与审批语义回归测试：注册提权拦截、dev-login 门禁、审批人规则、chat 调试参数透传。"""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from src.api.deps import create_access_token
from src.config import settings
from src.main import app
from src.schemas.models import AuthContext
from src.services.tool_setup import build_tool_registry


def test_register_rejects_admin_role() -> None:
    """匿名注册不允许自选 admin：Pydantic 白名单外直接 422，白名单内 admin 已移除。"""
    from src.schemas.models import RegisterRequest

    with pytest.raises(ValueError):
        RegisterRequest(username="attacker", password="123456", role="admin")  # type: ignore[arg-type]


def test_dev_login_blocked_outside_dev_env() -> None:
    """非 dev 环境 dev-login 必须返回 403，杜绝免密换任意角色 token。"""
    client = TestClient(app, raise_server_exceptions=False)
    original = settings.env
    try:
        settings.env = "prod"
        resp = client.post("/api/v1/auth/dev-login", json={"username": "intruder", "role": "admin"})
        assert resp.status_code == 403
    finally:
        settings.env = original


class _StubRag:
    """记录 rag_search 实际收到的参数，验证请求级默认值透传。"""

    def __init__(self) -> None:
        self.calls: list[tuple[str, int, float]] = []

    async def search(self, query: str, top_k: int = 3, min_score: float = 0.2, **_: object) -> str:
        self.calls.append((query, top_k, min_score))
        return "{}"


class _StubMemory:
    pass


def test_chat_debug_params_reach_rag_tool() -> None:
    """前端调试面板的 top_k/min_score 必须真实生效：作为 rag_search 的请求级默认值。"""

    async def _run() -> None:
        stub = _StubRag()
        registry = build_tool_registry(
            rag_service=stub,  # type: ignore[arg-type]
            memory_service=_StubMemory(),  # type: ignore[arg-type]
            default_top_k=1,
            default_min_score=0.9,
        )
        tool = registry._tools["rag_search"]
        await tool.handler(tool.args_model.model_validate({"query": "测试"}))
        await tool.handler(tool.args_model.model_validate({"query": "显式", "top_k": 5}))
        # 未显式传 top_k → 请求级默认 1；显式传 5 → 尊重 LLM 入参
        assert stub.calls[0] == ("测试", 1, 0.9)
        assert stub.calls[1] == ("显式", 5, 0.9)

    import asyncio

    asyncio.run(_run())


class FakeWorkflowRepo:
    """最小实现：仅覆盖审批链路需要的 get_instance / update_status_idempotent。"""

    def __init__(self) -> None:
        self.owner_id = uuid4()
        self.instance = {"id": uuid4(), "user_id": self.owner_id, "flow_code": "oa_approval", "title": "t", "status": "submitted"}

    async def get_instance(self, instance_id: object) -> dict | None:
        return self.instance if self.instance and self.instance["id"] == instance_id else None

    async def update_status_idempotent(self, instance_id: object, owner_user_id: object, status: str, operator: str, channel: str = "form") -> dict | None:
        if self.instance and self.instance["status"] == "submitted":
            self.instance["status"] = status
            self.instance["approved_by"] = operator
            return self.instance
        return None


def test_workflow_approval_rules() -> None:
    """审批语义：仅 admin 可审批；不得自审自批；非 admin 一律 403。"""
    from src.api.deps import get_workflow_repo

    repo = FakeWorkflowRepo()
    app.dependency_overrides[get_workflow_repo] = lambda: repo
    try:
        client = TestClient(app, raise_server_exceptions=False)
        instance_id = repo.instance["id"]

        # 1) 普通用户（发起人自己）审批 → 403
        owner_token = create_access_token(
            AuthContext(user_id=repo.owner_id, username="owner", role="user", allowed_tools=["rag_search"])
        )
        r1 = client.patch(
            f"/api/v1/workflows/{instance_id}/status",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"status": "approved"},
        )
        assert r1.status_code == 403

        # 2) admin 审批自己发起的 → 403（防自审自批）
        self_admin_token = create_access_token(
            AuthContext(user_id=repo.owner_id, username="admin_self", role="admin", allowed_tools=["*"])
        )
        r2 = client.patch(
            f"/api/v1/workflows/{instance_id}/status",
            headers={"Authorization": f"Bearer {self_admin_token}"},
            json={"status": "approved"},
        )
        assert r2.status_code == 403

        # 3) 其他 admin 审批 → 200，approved_by 记录实际审批人
        other_admin_token = create_access_token(
            AuthContext(user_id=uuid4(), username="admin_b", role="admin", allowed_tools=["*"])
        )
        r3 = client.patch(
            f"/api/v1/workflows/{instance_id}/status",
            headers={"Authorization": f"Bearer {other_admin_token}"},
            json={"status": "approved"},
        )
        assert r3.status_code == 200
        assert r3.json()["approved_by"] == "admin_b"

        # 4) 重复审批 → 409 幂等
        r4 = client.patch(
            f"/api/v1/workflows/{instance_id}/status",
            headers={"Authorization": f"Bearer {other_admin_token}"},
            json={"status": "rejected"},
        )
        assert r4.status_code == 409
    finally:
        app.dependency_overrides.clear()
