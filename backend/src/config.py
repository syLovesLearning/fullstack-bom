"""全局配置：优先向上查找 .env；找不到时回落到 backend/.env，保证启动目录无关。"""

from pathlib import Path

from dotenv import find_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# config.py 位于 backend/src/ 下，向上两级即 backend/.env
_FALLBACK_ENV = Path(__file__).resolve().parent.parent / ".env"


def _locate_env() -> str:
    """先按进程 cwd 向上找（兼容 backend/ 内启动），失败则回落到文件定位，避免从仓库根目录启动时丢配置。"""
    found = find_dotenv(usecwd=True)
    return found if found else str(_FALLBACK_ENV)


class Settings(BaseSettings):
    # 运行环境标识：dev 允许 /dev-login 与默认 JWT secret；非 dev 启动时强制校验
    env: str = "dev"
    pg_dsn: str = ""
    bom_pg_dsn: str = ""
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: str = "dev-secret-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440

    llm_base_url: str = "https://open.bigmodel.cn/api/paas/v4"
    llm_api_key: str = "your_api_key"
    llm_model: str = "glm-5.3-flash"
    embed_base_url: str = ""
    embed_api_key: str = ""
    embed_model: str = "embedding-3"

    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    model_config = SettingsConfigDict(
        env_file=_locate_env(),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
