"""测试集接口：供前端页面直接展示黄金测试集并一键运行评测。"""

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from src.api.deps import get_current_auth, get_rag_service
from src.schemas.models import AuthContext
from src.services.eval_service import EvalService
from src.services.rag_service import RagService

router = APIRouter(prefix="/api/v1/eval", tags=["eval"])


class EvalRunRequest(BaseModel):
    seed_if_empty: bool = True
    top_k: int = 3


def get_eval_service(rag_service: RagService = Depends(get_rag_service)) -> EvalService:
    return EvalService(rag_service=rag_service)


@router.get("/cases")
async def list_eval_cases(
    _auth: AuthContext = Depends(get_current_auth),
    eval_service: EvalService = Depends(get_eval_service),
) -> list[dict[str, Any]]:
    return eval_service.load_cases()


@router.post("/seed")
async def seed_eval_docs(
    auth: AuthContext = Depends(get_current_auth),
    eval_service: EvalService = Depends(get_eval_service),
) -> dict[str, Any]:
    results = await eval_service.seed_sample_docs(user_id=auth.user_id)
    return {"seeded": results}


@router.post("/run")
async def run_eval_suite(
    body: EvalRunRequest,
    auth: AuthContext = Depends(get_current_auth),
    eval_service: EvalService = Depends(get_eval_service),
) -> dict[str, Any]:
    return await eval_service.run_suite(
        user_id=auth.user_id,
        seed_if_empty=body.seed_if_empty,
        top_k=body.top_k,
    )
