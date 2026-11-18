"""知识库文档管理、分组权限上传与 RAG 透视接口。"""

import asyncio
from pathlib import Path
import time
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from src.api.deps import get_current_auth, get_doc_repo, get_rag_service
from src.repositories.doc_repo import DocRepo
from src.schemas.models import AuthContext
from src.services.file_parser import expand_uploaded_archive, parse_uploaded_file
from src.services.rag_service import RagService

router = APIRouter(prefix="/api/v1/docs", tags=["rag-docs"])


class DocIngestRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    source_path: str = Field(min_length=1, max_length=500)
    category: str = Field(default="general", max_length=64)
    allowed_groups: list[str] = Field(default_factory=lambda: ["private"])
    content: str = Field(min_length=1)


class DocSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    category: str | None = None
    top_k: int = Field(default=3, ge=1, le=10)


class DocDebugSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    category: str | None = None
    top_k: int = Field(default=5, ge=1, le=10)
    min_score: float = Field(default=0.2, ge=0.0, le=1.0)


@router.post("/ingest")
async def ingest_document(
    body: DocIngestRequest,
    auth: AuthContext = Depends(get_current_auth),
    rag_service: RagService = Depends(get_rag_service),
) -> dict[str, Any]:
    return await rag_service.ingest_document(
        user_id=auth.user_id,
        title=body.title,
        source_path=body.source_path,
        content=body.content,
        category=body.category,
        allowed_groups=body.allowed_groups,
    )


@router.post("/upload")
async def upload_documents(
    files: list[UploadFile] = File(...),
    category: str = Form("general"),
    allowed_groups: str = Form("private"),
    auth: AuthContext = Depends(get_current_auth),
    rag_service: RagService = Depends(get_rag_service),
) -> dict[str, Any]:
    groups = [g.strip() for g in allowed_groups.split(",") if g.strip()] or ["private"]
    pending: list[tuple[str, bytes]] = []
    results: list[dict[str, Any]] = []

    for f in files:
        fname = f.filename or "upload.txt"
        raw = await f.read()
        if Path(fname).suffix.lower() == ".zip":
            try:
                pending.extend(expand_uploaded_archive(raw))
            except Exception as exc:
                results.append({"filename": fname, "status": "failed", "chunks": 0, "error": str(exc)})
        else:
            pending.append((fname, raw))

    sem = asyncio.Semaphore(3)

    async def process_one(name: str, data: bytes) -> dict[str, Any]:
        async with sem:
            try:
                title, text = await parse_uploaded_file(name, data)
                res = await rag_service.ingest_document(
                    user_id=auth.user_id,
                    title=title,
                    source_path=f"uploads/{name}",
                    content=text,
                    category=category,
                    allowed_groups=groups,
                )
                return {"filename": name, **res}
            except Exception as exc:
                return {"filename": name, "status": "failed", "chunks": 0, "error": str(exc)}

    batch_out = await asyncio.gather(*(process_one(n, b) for n, b in pending))
    results.extend(batch_out)
    return {
        "total": len(results),
        "indexed": sum(1 for r in results if r["status"] == "indexed"),
        "skipped": sum(1 for r in results if r["status"] == "skipped"),
        "failed": sum(1 for r in results if r["status"] == "failed"),
        "results": results,
    }


@router.get("")
async def list_documents(
    auth: AuthContext = Depends(get_current_auth),
    doc_repo: DocRepo = Depends(get_doc_repo),
) -> list[dict[str, Any]]:
    return await doc_repo.list_documents(user_id=auth.user_id, user_groups=auth.groups)


@router.delete("/{doc_id}")
async def delete_document(
    doc_id: UUID,
    auth: AuthContext = Depends(get_current_auth),
    doc_repo: DocRepo = Depends(get_doc_repo),
) -> dict[str, bool]:
    ok = await doc_repo.delete_document(doc_id=doc_id, user_id=auth.user_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found or no ownership")
    return {"deleted": True}


@router.post("/search")
async def debug_rag_search(
    body: DocSearchRequest,
    auth: AuthContext = Depends(get_current_auth),
    rag_service: RagService = Depends(get_rag_service),
) -> dict[str, Any]:
    t0 = time.perf_counter()
    hits = await rag_service.search_structured(
        query=body.query,
        top_k=body.top_k,
        category=body.category,
        user_id=auth.user_id,
        user_groups=auth.groups,
    )
    return {"query": body.query, "latency_ms": int((time.perf_counter() - t0) * 1000), "hits": hits}


@router.post("/search-debug")
async def debug_rag_pipeline(
    body: DocDebugSearchRequest,
    auth: AuthContext = Depends(get_current_auth),
    rag_service: RagService = Depends(get_rag_service),
) -> dict[str, Any]:
    t0 = time.perf_counter()
    data = await rag_service.search_debug(
        query=body.query,
        user_id=auth.user_id,
        user_groups=auth.groups,
        top_k=body.top_k,
        category=body.category or None,
        min_score=body.min_score,
    )
    data["latency_ms"] = int((time.perf_counter() - t0) * 1000)
    return data
