"""FastAPI 依赖注入装配与 JWT 鉴权（解析 AuthContext 并写入 ContextVar）。"""

from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt

from src.config import settings
from src.core.event_context import set_auth_context
from src.repositories.doc_repo import DocRepo
from src.repositories.memory_repo import MemoryRepo
from src.repositories.session_repo import SessionRepo
from src.repositories.trace_repo import TraceRepo
from src.repositories.user_repo import UserRepo
from src.repositories.inventory_repo import InventoryRepo
from src.repositories.bom_repo import BomRepo
from src.repositories.menu_repo import MenuRepo
from src.repositories.workflow_repo import WorkflowRepo
from src.schemas.models import AuthContext
from src.services.embedding_service import EmbeddingService
from src.services.llm_service import LLMService
from src.services.memory_service import MemoryService
from src.services.bom_service import BomService
from src.services.menu_service import MenuService
from src.services.rag_service import RagService

_bearer = HTTPBearer(auto_error=False)


def create_access_token(auth: AuthContext) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {
        "sub": str(auth.user_id),
        "username": auth.username,
        "role": auth.role,
        "allowed_tools": auth.allowed_tools,
        "groups": auth.groups,
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def get_user_repo(request: Request) -> UserRepo:
    return UserRepo(request.app.state.pg_pool)


def get_session_repo(request: Request) -> SessionRepo:
    return SessionRepo(request.app.state.pg_pool)


def get_memory_repo(request: Request) -> MemoryRepo:
    return MemoryRepo(request.app.state.pg_pool)


def get_trace_repo(request: Request) -> TraceRepo:
    return TraceRepo(request.app.state.pg_pool)


def get_doc_repo(request: Request) -> DocRepo:
    return DocRepo(request.app.state.pg_pool)

def get_workflow_repo(request: Request) -> WorkflowRepo:
    return WorkflowRepo(request.app.state.pg_pool)

def get_inventory_repo(request: Request) -> InventoryRepo:
    return InventoryRepo(request.app.state.pg_pool)


def get_memory_service(
    request: Request,
    session_repo: SessionRepo = Depends(get_session_repo),
    memory_repo: MemoryRepo = Depends(get_memory_repo),
) -> MemoryService:
    return MemoryService(session_repo, memory_repo, request.app.state.redis)


def get_llm_service(request: Request) -> LLMService:
    return LLMService(request.app.state.http_client)


def get_rag_service(
    request: Request,
    doc_repo: DocRepo = Depends(get_doc_repo),
    llm_service: LLMService = Depends(get_llm_service),
) -> RagService:
    embed = EmbeddingService(request.app.state.http_client)
    return RagService(
        doc_repo=doc_repo,
        embed_service=embed,
        redis_client=request.app.state.redis,
        llm_service=llm_service,
    )


async def get_current_auth(
    cred: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> AuthContext:
    if cred is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Bearer token")
    try:
        payload = jwt.decode(cred.credentials, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        auth = AuthContext(
            user_id=UUID(payload["sub"]),
            username=payload["username"],
            role=payload.get("role", "user"),
            allowed_tools=payload.get("allowed_tools", ["rag_search"]),
            groups=payload.get("groups", ["public"]),
        )
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    set_auth_context(auth)
    return auth


def get_bom_repo(request: Request) -> BomRepo:
    # 单例复用：lifespan 已预热迁移并缓存到 app.state.bom_repo
    repo = getattr(request.app.state, "bom_repo", None)
    if repo is None:
        pool = getattr(request.app.state, "bom_pool", None) or request.app.state.pg_pool
        repo = BomRepo(pool)
        request.app.state.bom_repo = repo
    return repo


def get_bom_service(repo: BomRepo = Depends(get_bom_repo), inv_repo: InventoryRepo = Depends(get_inventory_repo)) -> BomService:
    return BomService(repo, inv_repo)


def get_menu_repo(request: Request) -> MenuRepo:
    return MenuRepo(request.app.state.pg_pool)


def get_menu_service(repo: MenuRepo = Depends(get_menu_repo)) -> MenuService:
    return MenuService(repo)
