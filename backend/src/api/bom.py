"""BOM 维护、余料试算、报价快照与跨库库存齐套 REST 接口。"""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.api.deps import get_bom_service, get_current_auth
from src.schemas.models import AuthContext, BomCloneRequest, BomEdgeCreate, BomEdgeUpdate, BomItemCreate, QuoteSaveRequest, StockCheckRequest
from src.services.bom_service import BomService

router = APIRouter(prefix="/api/v1/bom", tags=["bom"])


@router.get("/items")
async def list_bom_items(auth: AuthContext = Depends(get_current_auth), svc: BomService = Depends(get_bom_service)) -> list[dict[str, Any]]:
    return await svc.list_items(user_id=auth.user_id)


@router.post("/items")
async def upsert_bom_item(body: BomItemCreate, auth: AuthContext = Depends(get_current_auth), svc: BomService = Depends(get_bom_service)) -> dict[str, Any]:
    return await svc.upsert_item(user_id=auth.user_id, data=body.model_dump())


@router.delete("/items/{item_id}")
async def delete_bom_item(item_id: UUID, auth: AuthContext = Depends(get_current_auth), svc: BomService = Depends(get_bom_service)) -> dict[str, bool]:
    try:
        if not await svc.delete_item(item_id=item_id, user_id=auth.user_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="BOM item not found")
        return {"deleted": True}
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/edges/{parent_id}")
async def list_bom_edges(parent_id: UUID, auth: AuthContext = Depends(get_current_auth), svc: BomService = Depends(get_bom_service)) -> list[dict[str, Any]]:
    return await svc.list_edges(user_id=auth.user_id, parent_id=parent_id)


@router.post("/edges/{parent_id}")
async def create_bom_edge(parent_id: UUID, body: BomEdgeCreate, auth: AuthContext = Depends(get_current_auth), svc: BomService = Depends(get_bom_service)) -> dict[str, Any]:
    try:
        return await svc.add_edge(user_id=auth.user_id, parent_id=parent_id, data=body.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.patch("/edges/{edge_id}")
async def update_bom_edge(edge_id: UUID, body: BomEdgeUpdate, auth: AuthContext = Depends(get_current_auth), svc: BomService = Depends(get_bom_service)) -> dict[str, Any]:
    updated = await svc.update_edge(user_id=auth.user_id, edge_id=edge_id, data=body.model_dump())
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="BOM edge not found")
    return updated


@router.delete("/edges/{edge_id}")
async def delete_bom_edge(edge_id: UUID, auth: AuthContext = Depends(get_current_auth), svc: BomService = Depends(get_bom_service)) -> dict[str, bool]:
    if not await svc.delete_edge(edge_id=edge_id, user_id=auth.user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="BOM edge not found")
    return {"deleted": True}


@router.post("/clone")
async def clone_bom_edges(body: BomCloneRequest, auth: AuthContext = Depends(get_current_auth), svc: BomService = Depends(get_bom_service)) -> dict[str, int]:
    try:
        return {"cloned_count": await svc.clone_bom(user_id=auth.user_id, source_id=body.source_parent_id, target_id=body.target_parent_id)}
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/seed")
async def seed_bom_data(auth: AuthContext = Depends(get_current_auth), svc: BomService = Depends(get_bom_service)) -> dict[str, int]:
    return await svc.seed_demo_bom(user_id=auth.user_id)


@router.get("/tree/{root_id}")
async def get_bom_rollup_tree(
    root_id: UUID, h: float = Query(2200.0), w: float = Query(800.0), d: float = Query(600.0), t: float = Query(2.0),
    auth: AuthContext = Depends(get_current_auth), svc: BomService = Depends(get_bom_service),
) -> dict[str, Any]:
    try:
        return await svc.build_rollup_tree(user_id=auth.user_id, root_id=root_id, params_3d={"H": h, "W": w, "D": d, "T": t})
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/quotes")
async def save_bom_quote(body: QuoteSaveRequest, auth: AuthContext = Depends(get_current_auth), svc: BomService = Depends(get_bom_service)) -> dict[str, Any]:
    return await svc.save_quote(user_id=auth.user_id, req=body.model_dump())


@router.get("/quotes")
async def list_bom_quotes(auth: AuthContext = Depends(get_current_auth), svc: BomService = Depends(get_bom_service)) -> list[dict[str, Any]]:
    return await svc.list_quotes(user_id=auth.user_id)


@router.post("/stock-check")
async def check_bom_stock(body: StockCheckRequest, auth: AuthContext = Depends(get_current_auth), svc: BomService = Depends(get_bom_service)) -> list[dict[str, Any]]:
    return await svc.check_stock(user_id=auth.user_id, root_id=body.root_id, env={"H": body.h, "W": body.w, "D": body.d, "T": body.t})
