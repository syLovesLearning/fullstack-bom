"""本地一键拉取服务器主项目 (fullstack-bom) 与 Nginx 错误日志。

用法：
  python3 getLogs.py                  拉取最近 150 行日志并保存到 logs/
  python3 getLogs.py --lines 300      指定拉取行数
  python3 getLogs.py --host aliyun3d  指定 SSH 主机别名（默认 aliyun3d）
"""

import argparse
from datetime import datetime
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent


def main() -> None:
    ap = argparse.ArgumentParser(description="拉取服务器 fullstack-bom 与 Nginx 日志")
    ap.add_argument("--host", default="aliyun3d", help="SSH 主机别名，默认 aliyun3d")
    ap.add_argument("--lines", type=int, default=150, help="每个日志拉取末尾行数，默认 150")
    args = ap.parse_args()

    remote_cmd = (
        f"echo '=== [1] Python 后端日志 (fullstack-bom) ===' && "
        f"sudo journalctl -u fullstack-bom -n {args.lines} --no-pager && "
        f"echo '\n=== [2] Nginx 错误日志 (/var/log/nginx/error.log) ===' && "
        f"sudo tail -n {args.lines} /var/log/nginx/error.log"
    )
    print(f"[logs] 正在从 {args.host} 拉取最近 {args.lines} 行日志 ...")
    res = subprocess.run(["ssh", args.host, remote_cmd], capture_output=True, text=True)
    output = (res.stdout or "") + ("\n[STDERR]\n" + res.stderr if res.stderr else "")

    logs_dir = ROOT / "logs"
    logs_dir.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_file = logs_dir / f"server_bom_{ts}.log"
    out_file.write_text(output, encoding="utf-8")

    print(f"[logs] 已保存完整日志到: {out_file}")
    print("-" * 60)
    key_lines = [ln for ln in output.splitlines() if any(k in ln for k in ("ERROR", "Traceback", "Exception", "500", "crit", "emerg", "==="))]
    print("\n".join(key_lines[-60:]) if key_lines else "\n".join(output.splitlines()[-40:]))


if __name__ == "__main__":
    main()
