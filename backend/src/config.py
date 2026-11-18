"""全局配置：使用 find_dotenv 向上查找 .env，杜绝硬编码 .parent 层级。"""

from dotenv import find_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    pg_dsn: str = "postgresql://shenyang@localhost:5432/rag_db"
    bom_pg_dsn: str = "postgresql://shenyang@localhost:5432/bom_db"
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
        env_file=find_dotenv(usecwd=True) or ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
