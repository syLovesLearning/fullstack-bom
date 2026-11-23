"""跨平台数据库自动建库与建表脚本：依次初始化 PG_DSN (init_db.sql) 与 BOM_PG_DSN (init_bom_db.sql)。"""

import sys
from pathlib import Path
from urllib.parse import urlparse, urlunparse

BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import psycopg  # noqa: E402
from src.config import settings  # noqa: E402


def _ensure_db_and_sql(dsn: str, sql_file: Path, label: str) -> None:
    if not dsn:
        print(f"[migrate] 跳过 {label}（未配置 DSN）")
        return
    parsed = urlparse(dsn)
    db_name = parsed.path.lstrip("/") or label
    admin_dsn = urlunparse(parsed._replace(path="/postgres"))
    with psycopg.connect(admin_dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s;", (db_name,))
            if cur.fetchone() is None:
                safe_name = db_name.replace('"', '""')
                cur.execute(f'CREATE DATABASE "{safe_name}";')
                print(f"[migrate] 已自动创建数据库: {db_name}")

    raw_lines = [ln for ln in sql_file.read_text(encoding="utf-8").splitlines() if not ln.lstrip().startswith("--")]
    stmts = [s.strip() for s in "\n".join(raw_lines).split(";") if s.strip()]
    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            for stmt in stmts:
                cur.execute(stmt + ";")
    print(f"[migrate] 已完成表结构同步: {db_name} ({sql_file.name})")


def run_migrate() -> None:
    _ensure_db_and_sql(settings.pg_dsn, BACKEND_DIR / "scripts" / "init_db.sql", "rag_db")
    _ensure_db_and_sql(settings.bom_pg_dsn, BACKEND_DIR / "scripts" / "init_bom_db.sql", "bom_db")


if __name__ == "__main__":
    run_migrate()
