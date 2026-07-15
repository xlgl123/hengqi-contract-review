from __future__ import annotations

import argparse
import ctypes
import json
import os
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
RUNTIME_ROOT = (
    Path("F:/Codex/temp/hengqi-contract-review")
    if Path("F:/Codex").exists()
    else PROJECT_ROOT / ".runtime"
)
PID_FILE = RUNTIME_ROOT / "server.pid"
STDOUT_FILE = RUNTIME_ROOT / "server.stdout.log"
STDERR_FILE = RUNTIME_ROOT / "server.stderr.log"


def _process_exists(pid: int) -> bool:
    if sys.platform == "win32":
        process_query_limited_information = 0x1000
        handle = ctypes.windll.kernel32.OpenProcess(
            process_query_limited_information, False, pid
        )
        if not handle:
            return False
        ctypes.windll.kernel32.CloseHandle(handle)
        return True
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _health(port: int) -> dict[str, object] | None:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=2) as response:
            return json.loads(response.read().decode("utf-8"))
    except (OSError, ValueError):
        return None


def _read_pid() -> int | None:
    if not PID_FILE.is_file():
        return None
    try:
        return int(PID_FILE.read_text(encoding="ascii").strip())
    except ValueError:
        return None


def start(port: int) -> int:
    RUNTIME_ROOT.mkdir(parents=True, exist_ok=True)
    old_pid = _read_pid()
    if old_pid and _process_exists(old_pid):
        health = _health(port)
        if health and health.get("status") == "ok":
            print(f"衡契已经在运行：http://127.0.0.1:{port}")
            return 0
        raise RuntimeError(f"PID {old_pid}仍在运行，但健康检查失败。请先执行stop。")
    PID_FILE.unlink(missing_ok=True)

    creationflags = 0
    if sys.platform == "win32":
        creationflags = (
            subprocess.CREATE_NO_WINDOW
            | subprocess.DETACHED_PROCESS
            | subprocess.CREATE_NEW_PROCESS_GROUP
        )
    with STDOUT_FILE.open("ab") as stdout, STDERR_FILE.open("ab") as stderr:
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
            ],
            cwd=BACKEND_ROOT,
            stdin=subprocess.DEVNULL,
            stdout=stdout,
            stderr=stderr,
            creationflags=creationflags,
            close_fds=True,
        )
    PID_FILE.write_text(str(process.pid), encoding="ascii")

    for _ in range(40):
        time.sleep(0.5)
        health = _health(port)
        if health and health.get("status") == "ok":
            print(f"衡契本地部署已启动：http://127.0.0.1:{port}")
            print(f"AI已配置：{health.get('ai_configured', False)}")
            return 0
        if process.poll() is not None:
            break

    PID_FILE.unlink(missing_ok=True)
    error_tail = ""
    if STDERR_FILE.is_file():
        error_tail = "\n".join(STDERR_FILE.read_text(encoding="utf-8", errors="replace").splitlines()[-20:])
    raise RuntimeError(f"本地服务启动失败。\n{error_tail}")


def stop() -> int:
    pid = _read_pid()
    if not pid or not _process_exists(pid):
        PID_FILE.unlink(missing_ok=True)
        print("衡契本地服务当前未运行。")
        return 0
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:
        os.kill(pid, signal.SIGTERM)
    PID_FILE.unlink(missing_ok=True)
    print("衡契本地服务已停止。")
    return 0


def status(port: int) -> int:
    pid = _read_pid()
    health = _health(port)
    print(json.dumps({"running": bool(pid and _process_exists(pid) and health), "pid": pid, "health": health}, ensure_ascii=False))
    return 0 if health else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="衡契本地服务启停器")
    parser.add_argument("action", choices=("start", "stop", "status"))
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    if args.action == "start":
        return start(args.port)
    if args.action == "stop":
        return stop()
    return status(args.port)


if __name__ == "__main__":
    raise SystemExit(main())
