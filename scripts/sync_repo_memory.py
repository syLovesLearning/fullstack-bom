"""Sync English repo memory docs into PostgreSQL (category='repo_memory') via SHA-256 dedup."""

import asyncio
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from src.config import settings  # noqa: E402
from src.infra.http_client import close_http_client, create_http_client  # noqa: E402
from src.infra.postgres import close_pg_pool, create_pg_pool  # noqa: E402
from src.repositories.doc_repo import DocRepo  # noqa: E402
from src.repositories.user_repo import UserRepo  # noqa: E402
from src.services.embedding_service import EmbeddingService  # noqa: E402
from src.services.rag_service import RagService  # noqa: E402

TARGET_DOCS = [
    ("Monorepo Root Memory", "CLAUDE.md"),
    ("Backend Memory Rules", "backend/CLAUDE.md"),
    ("Frontend Memory Rules", "frontend/CLAUDE.md"),
    ("System Architecture", "docs/ARCHITECTURE.md"),
    ("API & SSE Contract", "docs/API_SPEC.md"),
    ("Structural Code Index", "docs/CODE_INDEX.md"),
]


async def sync_all(username: str = "shenyang") -> None:
    pool = await create_pg_pool(settings.pg_dsn)
    http_client = create_http_client()
    try:
        user = await UserRepo(pool).get_or_create_dev_user(username=username, role="admin")
        rag = RagService(doc_repo=DocRepo(pool), embed_service=EmbeddingService(http_client))
        for title, rel_path in TARGET_DOCS:
            file_path = ROOT / rel_path
            if not file_path.exists():
                continue
            res = await rag.ingest_document(
                user_id=user["id"],
                title=title,
                source_path=rel_path,
                content=file_path.read_text(encoding="utf-8"),
                category="repo_memory",
            )
            print(f"[{res['status']}] {rel_path} (chunks={res['chunks']})")
    finally:
        await close_http_client(http_client)
        await close_pg_pool(pool)


if __name__ == "__main__":
    asyncio.run(sync_all())
