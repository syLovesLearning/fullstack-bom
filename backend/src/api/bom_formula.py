"""公式 AI 录入接口：口述编译、模板下载、测试数据解析、批量校验。"""

from typing import Any, Literal
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import Response

from src.api.deps import get_current_auth, get_llm_service
from src.schemas.bom_formula import BomFormulaBatchCheckRequest, BomFormulaDraftRequest
from src.schemas.models import AuthContext, BomFormulaCheckRequest
from src.services.bom_formula import eval_formula_with_error, verify_rows
from src.services.bom_formula_ai import draft_formula
from src.services.bom_formula_sheet import build_template, parse_sheet
from src.services.llm_service import LLMService

router = APIRouter(prefix="/api/v1/bom/formula", tags=["bom-formula"])
_XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.post("/check")
async def check_formula(body: BomFormulaCheckRequest, auth: AuthContext = Depends(get_current_auth)) -> dict[str, Any]:
    """公式试算校验：前端编辑 FORMULA_3D/附加成本表达式时实时反馈错误。"""
    value, error = eval_formula_with_error(body.expr, body.env)
    return {"ok": error == "", "value": value, "error": error}


@router.post("/draft")
async def draft_formula_expr(
    body: BomFormulaDraftRequest,
    auth: AuthContext = Depends(get_current_auth),
    llm: LLMService = Depends(get_llm_service),
) -> dict[str, Any]:
    """第 1 步：口述逻辑 → 公式草稿（含步骤拆解与三组样例求值）。"""
    return await draft_formula(llm=llm, intent=body.intent, target=body.target, env=body.env, base_qty=body.base_qty, qty=body.qty)


@router.get("/template")
async def download_template(
    target: Literal["qty", "extra"] = "qty",
    expr: str = "",
    auth: AuthContext = Depends(get_current_auth),
) -> Response:
    """第 2 步：下载 xlsx 测试数据模板（自动带入当前表达式说明）。"""
    payload = build_template(expr=expr[:400], target=target)
    suffix = "用量" if target == "qty" else "附加成本"
    filename = quote(f"BOM公式测试数据_{suffix}.xlsx")
    return Response(
        content=payload,
        media_type=_XLSX_MIME,
        headers={"Content-Disposition": f"attachment; filename=formula_test.xlsx; filename*=UTF-8''{filename}"},
    )


@router.post("/parse-sheet")
async def parse_uploaded_sheet(file: UploadFile = File(...), auth: AuthContext = Depends(get_current_auth)) -> dict[str, Any]:
    """上传填写好的 xlsx/csv，解析为结构化测试行供前端预览与编辑。"""
    chunks: list[bytes] = []
    total = 0
    while chunk := await file.read(65536):
        total += len(chunk)
        if total > 2 * 1024 * 1024:
            raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="文件超过 2MB 上限")
        chunks.append(chunk)
    content = b"".join(chunks)
    try:
        return parse_sheet(file.filename or "", content)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/batch-check")
async def batch_check_formula(body: BomFormulaBatchCheckRequest, auth: AuthContext = Depends(get_current_auth)) -> dict[str, Any]:
    """第 3 步：用测试数据批量核对公式，全部通过方可录入。"""
    return verify_rows(body.expr, [r.model_dump() for r in body.rows])
