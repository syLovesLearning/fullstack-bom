#!/usr/bin/env bash
# 放在服务器 /opt/deploy_bom.sh（一键解压、保留 .venv、同步表结构与子路由、重启服务、清理 zip）
set -euo pipefail

ZIP_PATH="${1:-/tmp/fullstack-bom-prod.zip}"
TARGET="/opt/fullstack-bom-prod"
TMP_DIR="/tmp/bom_unpack"

if [ ! -f "$ZIP_PATH" ]; then
  echo "[error] 未找到安装包: $ZIP_PATH"
  exit 1
fi

rm -rf "$TMP_DIR"
unzip -oq "$ZIP_PATH" -d "$TMP_DIR"
SRC="$TMP_DIR/fullstack-bom-prod"

mkdir -p "$TARGET/backend" "$TARGET/frontend"
rm -rf "$TARGET/frontend/dist"
cp -r "$SRC/frontend/dist" "$TARGET/frontend/dist"

for item in src scripts pyproject.toml .env.example; do
  if [ -e "$SRC/backend/$item" ]; then
    rm -rf "$TARGET/backend/$item"
    cp -r "$SRC/backend/$item" "$TARGET/backend/$item"
  fi
done
cp "$SRC/start_prod.py" "$TARGET/start_prod.py"
[ -f "$SRC/nginx.location.conf" ] && cp "$SRC/nginx.location.conf" "$TARGET/nginx.location.conf"

if [ -f "$SRC/backend/.env" ]; then
  cp "$SRC/backend/.env" "$TARGET/backend/.env"
  echo "[deploy] 已同步生产环境变量 backend/.env"
fi

VPY="$TARGET/backend/.venv/bin/python"
if [ ! -x "$VPY" ]; then
  echo "[deploy] 首次初始化生产虚拟环境 backend/.venv ..."
  python3 -m venv "$TARGET/backend/.venv"
  "$VPY" -m pip install -e "$TARGET/backend"
fi

cd "$TARGET/backend"
PYTHONPATH="$TARGET/backend" "$VPY" "$TARGET/backend/src/infra/migrate.py"

if [ -f /etc/systemd/system/fullstack-bom.service ]; then
  systemctl restart fullstack-bom
  echo "[deploy] 已重启 fullstack-bom 服务"
fi
nginx -t && systemctl reload nginx || true

rm -rf "$TMP_DIR" "$ZIP_PATH"
echo "[deploy] 主项目发布完成并已清理临时压缩包"
