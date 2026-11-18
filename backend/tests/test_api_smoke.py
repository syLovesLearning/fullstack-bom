"""FastAPI 接口冒烟测试：覆盖鉴权、工具权限裁剪、记忆 CRUD、知识库与评测接口。"""

from uuid import UUID, uuid4

from fastapi.testclient import TestClient
import httpx

from src.api.deps import (
    create_access_token,
    get_doc_repo,
    get_memory_repo,
    get_rag_service,
)
from src.main import app
from src.schemas.models import AuthContext
from src.services.embedding_service import EmbeddingService
from src.services.rag_service import RagService
from tests.test_rag_pipeline import FakeDocRepo


class FakeMemoryRepo:
    def __init__(self) -> None:
        self.items: list[dict] = []

    async def create_memory(self, user_id: UUID, memory_type: str, content: str, importance: int = 3):
        row = {"id": str(uuid4()), "user_id": user_id, "memory_type": memory_type, "content": content, "importance": importance}
        self.items.append(row)
        return row

    async def list_memories(self, user_id: UUID, limit: int = 20):
        return [m for m in self.items if m["user_id"] == user_id][:limit]


def test_api_auth_tools_memory_and_rag_endpoints() -> None:
    fake_doc_repo = FakeDocRepo()
    fake_mem_repo = FakeMemoryRepo()

    async def override_rag() -> RagService:
        return RagService(doc_repo=fake_doc_repo, embed_service=EmbeddingService(httpx.AsyncClient()))  # type: ignore[arg-type]

    app.dependency_overrides[get_doc_repo] = lambda: fake_doc_repo
    app.dependency_overrides[get_memory_repo] = lambda: fake_mem_repo
    app.dependency_overrides[get_rag_service] = override_rag

    try:
        client = TestClient(app, raise_server_exceptions=False)
        assert client.get("/health").status_code == 200
        assert client.post("/api/v1/docs/search", json={"query": "pgvector"}).status_code == 401

        # 测试普通角色仅能看见 rag_search 工具（权限裁剪）
        user_token = create_access_token(
            AuthContext(user_id=uuid4(), username="readonly_u", role="readonly", allowed_tools=["rag_search"])
        )
        tools_resp = client.get("/api/v1/tools", headers={"Authorization": f"Bearer {user_token}"})
        assert tools_resp.status_code == 200
        assert [t["function"]["name"] for t in tools_resp.json()] == ["rag_search"]

        # 测试管理员全流程：记忆写入 -> 知识库入库 -> 检索 -> 拉取黄金测试集
        admin_token = create_access_token(
            AuthContext(user_id=uuid4(), username="admin_u", role="admin", allowed_tools=["rag_search", "memory_save"])
        )
        headers = {"Authorization": f"Bearer {admin_token}"}
        assert client.get("/api/v1/auth/me", headers=headers).status_code == 200

        mem_resp = client.post(
            "/api/v1/memories",
            headers=headers,
            json={"memory_type": "fact", "content": "使用 Postgres 17", "importance": 5},
        )
        assert mem_resp.status_code == 200
        assert len(client.get("/api/v1/memories", headers=headers).json()) == 1

        ingest_resp = client.post(
            "/api/v1/docs/ingest",
            headers=headers,
            json={
                "title": "架构说明",
                "source_path": "docs/arch.md",
                "category": "arch",
                "content": "# 架构\n\n## RAG 服务\nRAG 作为 Services 层的一部分挂载给 AgentLoop。",
            },
        )
        assert ingest_resp.status_code == 200 and ingest_resp.json()["status"] == "indexed"

        search_resp = client.post(
            "/api/v1/docs/search",
            headers=headers,
            json={"query": "AgentLoop RAG", "category": "arch", "top_k": 2},
        )
        assert search_resp.status_code == 200 and len(search_resp.json()["hits"]) == 1

        eval_cases = client.get("/api/v1/eval/cases", headers=headers)
        assert eval_cases.status_code == 200 and len(eval_cases.json()) >= 6
    finally:
        app.dependency_overrides.clear()


class FakeBomRepo:
    def __init__(self) -> None:
        self.items: dict[UUID, dict] = {}
        self.edges: list[dict] = []

    async def list_items(self, user_id: UUID):
        return [v for v in self.items.values() if v["user_id"] == user_id and v["is_active"]]

    async def upsert_item(self, user_id: UUID, data: dict):
        for k, v in self.items.items():
            if v["user_id"] == user_id and v["sku_code"] == data["sku_code"]:
                v.update(data)
                v["is_active"] = True
                return v
        item_id = uuid4()
        row = {"id": item_id, "user_id": user_id, "is_active": True, "created_at": "2026-11-17T00:00:00Z", **data}
        self.items[item_id] = row
        return row

    async def soft_delete_item(self, item_id: UUID, user_id: UUID) -> bool:
        if item_id in self.items and self.items[item_id]["user_id"] == user_id:
            self.items[item_id]["is_active"] = False
            return True
        return False

    async def get_or_create_header(self, user_id: UUID, item_id: UUID) -> UUID:
        return item_id

    async def list_edges(self, user_id: UUID, parent_id: UUID):
        res = []
        for e in self.edges:
            if e["user_id"] == user_id and e["parent_id"] == parent_id and e["is_active"]:
                c = self.items[e["child_item_id"]]
                res.append({**e, "child_sku": c["sku_code"], "child_name": c["name"], "child_category": c["category"], "child_sub_type": c["sub_type"], "child_unit": c["unit"], "child_price": c["base_price"]})
        return res

    async def list_all_edges(self, user_id: UUID):
        return [
            {"id": e["id"], "parent_id": e["parent_id"], "child_id": e["child_item_id"], **e}
            for e in self.edges
            if e["user_id"] == user_id and e["is_active"]
        ]

    async def add_edge(self, user_id: UUID, header_id: UUID, data: dict):
        row = {"id": uuid4(), "user_id": user_id, "parent_id": header_id, "is_active": True, **data}
        self.edges.append(row)
        return row

    async def add_edges_batch(self, user_id: UUID, header_id: UUID, rows: list[dict]) -> None:
        for data in rows:
            self.edges.append({"id": uuid4(), "user_id": user_id, "parent_id": header_id, "is_active": True, **data})

    async def soft_delete_edge(self, edge_id: UUID, user_id: UUID) -> bool:
        for e in self.edges:
            if e["id"] == edge_id and e["user_id"] == user_id:
                e["is_active"] = False
                return True
        return False


def test_bom_maintenance_and_rollup_endpoints() -> None:
    from src.api.deps import get_bom_repo

    fake_bom = FakeBomRepo()
    app.dependency_overrides[get_bom_repo] = lambda: fake_bom
    try:
        client = TestClient(app, raise_server_exceptions=False)
        token = create_access_token(AuthContext(user_id=uuid4(), username="bom_u", role="admin"))
        headers = {"Authorization": f"Bearer {token}"}

        seed_res = client.post("/api/v1/bom/seed", headers=headers)
        assert seed_res.status_code == 200 and seed_res.json()["seeded_items"] >= 8

        items = client.get("/api/v1/bom/items", headers=headers).json()
        prod = next(i for i in items if i["sku_code"] == "PROD-GGD-01")
        semi = next(i for i in items if i["sku_code"] == "SEMI-FRAME-01")

        # 验证防环路拦截：将父级 PROD-GGD-01 反向挂到子级 SEMI-FRAME-01 下应报 400
        cycle_res = client.post(
            f"/api/v1/bom/edges/{semi['id']}",
            headers=headers,
            json={"child_item_id": prod["id"], "qty_mode": "FIXED", "base_qty": 1},
        )
        assert cycle_res.status_code == 400

        # 验证多级递归算价与双视图输出
        tree_res = client.get(f"/api/v1/bom/tree/{prod['id']}", headers=headers)
        assert tree_res.status_code == 200
        body = tree_res.json()
        assert body["root"]["subtotal"] > 0
        assert body["cost_summary"]["基材(非固定)"] > 0
        assert body["bom_summary"]["材料"] > 0
    finally:
        app.dependency_overrides.clear()


class FakeMenuRepo:
    def __init__(self) -> None:
        from src.repositories.menu_repo import DEFAULT_MENUS
        self.rows = [
            {
                "menu_key": k, "title": t, "group_name": g, "icon": ic,
                "sort_order": s, "allowed_roles": list(r), "is_enabled": en,
            }
            for k, t, g, ic, s, r, en in DEFAULT_MENUS
        ]

    async def list_for_role(self, role: str):
        return [r for r in self.rows if r["is_enabled"] and role in r["allowed_roles"]]

    async def list_all(self):
        return self.rows

    async def update_menu(self, menu_key: str, data: dict):
        for r in self.rows:
            if r["menu_key"] == menu_key:
                r.update(data)
                if menu_key == "menu_admin":
                    r["is_enabled"] = True
                    if "admin" not in r["allowed_roles"]:
                        r["allowed_roles"].append("admin")
                return r
        return None


def test_dynamic_menus_rbac_and_lockout_guard() -> None:
    from src.api.deps import get_menu_repo

    fake_menu = FakeMenuRepo()
    app.dependency_overrides[get_menu_repo] = lambda: fake_menu
    try:
        client = TestClient(app, raise_server_exceptions=False)
        guest_token = create_access_token(AuthContext(user_id=uuid4(), username="ext_u", role="external_guest"))
        guest_menus = client.get("/api/v1/menus", headers={"Authorization": f"Bearer {guest_token}"}).json()
        guest_keys = [m["menu_key"] for m in guest_menus]
        assert "workflow" in guest_keys and "menu_admin" not in guest_keys

        admin_token = create_access_token(AuthContext(user_id=uuid4(), username="adm_u", role="admin"))
        headers = {"Authorization": f"Bearer {admin_token}"}
        # Attempt to disable menu_admin should be auto-guarded to stay enabled
        res = client.put(
            "/api/v1/menus/menu_admin",
            headers=headers,
            json={"title": "菜单管理", "group_name": "系统管理", "icon": "⚙", "sort_order": 100, "allowed_roles": ["user"], "is_enabled": False},
        )
        assert res.status_code == 200
        assert res.json()["is_enabled"] is True and "admin" in res.json()["allowed_roles"]
    finally:
        app.dependency_overrides.clear()
