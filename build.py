"""一键打包主项目生产发布包：构建前端产物 + 注入本地 .env.product + 可选一键上传部署。

用法：
  python3 build.py                   仅打包到 release/fullstack-bom-prod.zip
  python3 build.py --deploy          打包并自动上传到 aliyun3d 执行 /opt/deploy_bom.sh
  python3 build.py --host aliyun3d   指定 SSH 主机别名（默认 aliyun3d）
"""

import argparse
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FRONTEND = ROOT / "frontend"
BACKEND = ROOT / "backend"
IS_WIN = sys.platform == "win32"

START_PROD_TEMPLATE = '''"""服务器直跑入口：自动准备 .venv、同步表结构并启动 FastAPI（端口 {port}）。"""

import argparse, os, shutil, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BACKEND = HERE / "backend"
IS_WIN = sys.platform == "win32"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default={port})
    ap.add_argument("--workers", type=int, default=1)
    args = ap.parse_args()

    env_file = BACKEND / ".env"
    if not env_file.exists() and (BACKEND / ".env.example").exists():
        shutil.copyfile(BACKEND / ".env.example", env_file)
        print(f"[setup] 已生成 {{env_file}}，请确认 PG_DSN / BOM_PG_DSN / JWT_SECRET")

    vpy = BACKEND / ".venv" / ("Scripts/python.exe" if IS_WIN else "bin/python")
    if not vpy.exists():
        print("[setup] 正在创建生产虚拟环境 backend/.venv ...")
        subprocess.run([sys.executable, "-m", "venv", str(BACKEND / ".venv")], check=True)
        subprocess.run([str(vpy), "-m", "pip", "install", "-e", "."], cwd=BACKEND, check=True)

    env = os.environ.copy()
    env["PYTHONPATH"] = str(BACKEND)
    subprocess.run([str(vpy), str(BACKEND / "src" / "infra" / "migrate.py")], cwd=BACKEND, env=env, check=True)
    cmd = [str(vpy), "-m", "uvicorn", "src.main:app", "--host", args.host, "--port", str(args.port)]
    if not IS_WIN and args.workers > 1:
        cmd.extend(["--workers", str(args.workers)])
    print(f"[prod] 启动后端 http://{{args.host}}:{{args.port}} (workers={{args.workers}})")
    subprocess.run(cmd, cwd=BACKEND, env=env, check=True)


if __name__ == "__main__":
    main()
'''


def _find_pnpm() -> str:
    cmd = shutil.which("pnpm") or (shutil.which("pnpm.cmd") if IS_WIN else None)
    if not cmd:
        raise RuntimeError("未检测到 pnpm，请先安装 Node.js 与 pnpm")
    return cmd


def main() -> None:
    ap = argparse.ArgumentParser(description="打包主项目前端与配套直跑后端")
    ap.add_argument("--port", type=int, default=8000, help="后端默认监听端口，默认 8000")
    ap.add_argument("--deploy", action="store_true", help="打包后自动 scp 上传并触发服务器 /opt/deploy_bom.sh")
    ap.add_argument("--host", default="aliyun3d", help="SSH 主机别名，默认 aliyun3d")
    args = ap.parse_args()

    pnpm = _find_pnpm()
    if not (FRONTEND / "node_modules").exists():
        subprocess.run([pnpm, "install"], cwd=FRONTEND, check=True)

    print("[build] 正在构建主项目前端 ...")
    subprocess.run([pnpm, "build"], cwd=FRONTEND, check=True)

    out_dir = ROOT / "release" / "fullstack-bom-prod"
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    shutil.copytree(FRONTEND / "dist", out_dir / "frontend" / "dist")
    be_out = out_dir / "backend"
    be_out.mkdir(parents=True, exist_ok=True)
    shutil.copytree(BACKEND / "src", be_out / "src", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    shutil.copytree(BACKEND / "scripts", be_out / "scripts")
    for fname in ("pyproject.toml", ".env.example"):
        if (BACKEND / fname).exists():
            shutil.copy2(BACKEND / fname, be_out / fname)

    prod_env = BACKEND / ".env.product"
    if prod_env.exists():
        shutil.copy2(prod_env, be_out / ".env")
        print("[build] 已注入本地生产配置 backend/.env.product -> backend/.env")
    else:
        print("[warn] 未找到 backend/.env.product，发布包将沿用服务器现有 .env")

    (out_dir / "start_prod.py").write_text(START_PROD_TEMPLATE.format(port=args.port), encoding="utf-8")
    for fname in ("nginx.location.conf", "nginx.main.conf", "fullstack-bom.service", "server_deploy.sh"):
        if (ROOT / "deploy" / fname).exists():
            shutil.copy2(ROOT / "deploy" / fname, out_dir / fname)

    zip_path = ROOT / "release" / "fullstack-bom-prod.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in out_dir.rglob("*"):
            if p.is_file():
                zf.write(p, p.relative_to(ROOT / "release"))
    print(f"[done] 已生成发布压缩包: {zip_path} ({zip_path.stat().st_size // 1024} KB)")

    if args.deploy:
        remote_zip = "/tmp/fullstack-bom-prod.zip"
        print(f"[deploy] 正在上传到 {args.host}:{remote_zip} ...")
        subprocess.run(["scp", str(zip_path), f"{args.host}:{remote_zip}"], check=True)
        print(f"[deploy] 正在触发 {args.host} 自动解压与重启 ...")
        subprocess.run(["ssh", args.host, f"sudo bash /opt/deploy_bom.sh {remote_zip}"], check=True)


if __name__ == "__main__":
    main()
