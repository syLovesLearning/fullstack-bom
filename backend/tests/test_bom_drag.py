"""BOM 拖拽落地链路离线单测：批量挂载（单事务）与换父级（环检测）。

用 FakeRepo 替换 Postgres，验证「一次环检测 / 一次批量写入 / 只改挂载点」三条契约。
"""

import asyncio
from typing import Any
from uuid import UUID, uuid4

import pytest

from src.services.bom_service import BomService


def _row(child_item_id: UUID) -> dict[str, Any]:
    return {
        "child_item_id": child_item_id, "qty_mode": "FIXED", "base_qty": 1.0,
        "formula_expr": "", "extra_cost_expr": "", "remnant_policy": "CONTINUOUS",
        "unit_pack_size": 1.0, "min_remnant": 0.0, "loss_rate": 0.0,
        "float_factor": 1.0, "bom_group": "材料", "cost_group": "基材",
    }


class FakeBomRepo:
    """记录调用次数，不触碰数据库。A -> B -> C 作为既有结构。"""

    def __init__(self) -> None:
        self.a, self.b, self.c = uuid4(), uuid4(), uuid4()
        self.header = uuid4()
        self.all_edges = [
            {"id": uuid4(), "parent_id": self.a, "child_id": self.b},
            {"id": uuid4(), "parent_id": self.b, "child_id": self.c},
        ]
        self.moving_edge = uuid4()
        self.list_all_calls = 0
        self.batch_calls: list[list[dict[str, Any]]] = []
        self.move_calls: list[UUID] = []

    async def list_all_edges(self, user_id: UUID) -> list[dict[str, Any]]:
        self.list_all_calls += 1
        return self.all_edges

    async def get_or_create_header(self, user_id: UUID, item_id: UUID) -> UUID:
        return self.header

    async def add_edges_batch(self, user_id: UUID, header_id: UUID, rows: list[dict[str, Any]]) -> None:
        self.batch_calls.append(rows)

    async def get_edge(self, edge_id: UUID, user_id: UUID) -> dict[str, Any] | None:
        if edge_id != self.moving_edge:
            return None
        return {"id": edge_id, "parent_id": self.b, "child_id": self.c}

    async def move_edge(self, edge_id: UUID, user_id: UUID, header_id: UUID) -> bool:
        self.move_calls.append(header_id)
        return True


def _svc() -> tuple[BomService, FakeBomRepo]:
    repo = FakeBomRepo()
    return BomService(repo), repo  # type: ignore[arg-type]


def test_batch_drop_is_single_transaction() -> None:
    async def _run() -> None:
        svc, repo = _svc()
        x, y, z = uuid4(), uuid4(), uuid4()
        count = await svc.add_edges_batch(uuid4(), repo.a, [_row(x), _row(y), _row(z)])
        assert count == 3
        assert len(repo.batch_calls) == 1          # 单事务，不是 3 次 INSERT
        assert len(repo.batch_calls[0]) == 3
        assert repo.list_all_calls == 1            # 环检测只拉一次全量边
        # 规范化后字段齐全，可直接进 executemany
        assert repo.batch_calls[0][0]["remnant_policy"] == "CONTINUOUS"
        assert repo.batch_calls[0][0]["child_item_id"] == x

    asyncio.run(_run())


def test_batch_drop_rejects_cycle_without_writing() -> None:
    async def _run() -> None:
        svc, repo = _svc()
        # 把 A 挂到 C 下：A -> B -> C 已存在，必然成环
        with pytest.raises(ValueError, match="环路"):
            await svc.add_edges_batch(uuid4(), repo.c, [_row(repo.a)])
        assert repo.batch_calls == []              # 拒绝时零写入

    asyncio.run(_run())


def test_batch_drop_rejects_self_parent() -> None:
    async def _run() -> None:
        svc, repo = _svc()
        with pytest.raises(ValueError, match="自身"):
            await svc.add_edges_batch(uuid4(), repo.a, [_row(repo.a)])
        assert repo.batch_calls == []

    asyncio.run(_run())


def test_move_edge_only_changes_mount_point() -> None:
    async def _run() -> None:
        svc, repo = _svc()
        res = await svc.move_edge(uuid4(), repo.moving_edge, repo.a)
        assert res["parent_id"] == str(repo.a)
        assert res["child_id"] == str(repo.c)
        assert repo.move_calls == [repo.header]   # 只改 bom_header_id
        assert repo.list_all_calls == 1

    asyncio.run(_run())


def test_move_edge_rejects_cycle() -> None:
    async def _run() -> None:
        svc, repo = _svc()
        # C 可到达 D，把「C 这条边」挂到 D 下即从 child(C) DFS 命中 parent(D)
        d = uuid4()
        repo.all_edges = [{"id": uuid4(), "parent_id": repo.c, "child_id": d}]
        with pytest.raises(ValueError, match="环路"):
            await svc.move_edge(uuid4(), repo.moving_edge, d)
        assert repo.move_calls == []

    asyncio.run(_run())


def test_move_edge_rejects_same_parent_and_missing_edge() -> None:
    async def _run() -> None:
        svc, repo = _svc()
        with pytest.raises(ValueError, match="相同"):
            await svc.move_edge(uuid4(), repo.moving_edge, repo.b)
        with pytest.raises(ValueError, match="未找到"):
            await svc.move_edge(uuid4(), uuid4(), repo.a)
        assert repo.move_calls == []

    asyncio.run(_run())
