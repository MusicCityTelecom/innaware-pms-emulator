from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path
from typing import Any

import uvicorn

from innaware_pms_emulator import __version__
from innaware_pms_emulator.telemetry import telemetry_service
from innaware_pms_emulator.updates import update_manager

APP_TITLE = "InnAware PMS Emulator"
TELEMETRY_SUPPRESS_ENV = "INNAWARE_PMS_TELEMETRY_SUPPRESS_STARTUP"


def _data_dir() -> Path:
    override = os.environ.get("INNAWARE_PMS_DATA_DIR")
    if override:
        path = Path(override).expanduser()
    else:
        base = Path(os.environ.get("LOCALAPPDATA", Path.home()))
        path = base / "InnAware" / "PMS Emulator"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _log_path() -> Path:
    path = _data_dir() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path / "emulator.log"


def _server_log_config(log_level: str) -> dict[str, Any]:
    """Return a file-only logging configuration safe for pythonw/PyInstaller."""
    levels = {
        "trace": 5,
        "debug": 10,
        "info": 20,
        "warning": 30,
        "error": 40,
        "critical": 50,
    }
    level = levels.get(log_level.lower(), 20)
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "file": {
                "format": "%(asctime)s %(levelname)s %(name)s: %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            }
        },
        "handlers": {
            "file": {
                "class": "logging.FileHandler",
                "formatter": "file",
                "filename": str(_log_path()),
                "encoding": "utf-8",
            }
        },
        "loggers": {
            "uvicorn": {
                "handlers": ["file"],
                "level": level,
                "propagate": False,
            },
            "uvicorn.error": {"level": level},
            "uvicorn.access": {
                "handlers": ["file"],
                "level": level,
                "propagate": False,
            },
        },
        "root": {"handlers": ["file"], "level": level},
    }


def _port_open(host: str, port: int) -> bool:
    probe_host = "127.0.0.1" if host in {"0.0.0.0", "::"} else host
    try:
        with socket.create_connection((probe_host, port), timeout=0.25):
            return True
    except OSError:
        return False


def _health(host: str, port: int) -> dict[str, Any] | None:
    probe_host = "127.0.0.1" if host in {"0.0.0.0", "::"} else host
    try:
        with urllib.request.urlopen(f"http://{probe_host}:{port}/api/v1/health", timeout=0.5) as response:
            if response.status != 200:
                return None
            payload = json.loads(response.read().decode("utf-8"))
            if payload.get("status") == "ok" and "version" in payload:
                return payload
    except (OSError, urllib.error.URLError, json.JSONDecodeError):
        return None
    return None


def _show_error(message: str) -> None:
    if os.name == "nt":
        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(0, message, APP_TITLE, 0x10)
            return
        except Exception:
            pass
    if sys.stderr is not None:
        print(message, file=sys.stderr)


def _server_command(host: str, port: int, log_level: str) -> list[str]:
    arguments = [
        "--server-only",
        "--host",
        host,
        "--port",
        str(port),
        "--log-level",
        log_level,
    ]
    if getattr(sys, "frozen", False):
        return [sys.executable, *arguments]
    return [sys.executable, "-m", "innaware_pms_emulator.windows_launcher", *arguments]


def _spawn_server(host: str, port: int, log_level: str) -> tuple[subprocess.Popen, Any]:
    log_handle = _log_path().open("a", encoding="utf-8", buffering=1)
    log_handle.write(f"\n===== {APP_TITLE} {__version__} startup {time.strftime('%Y-%m-%d %H:%M:%S')} =====\n")
    creationflags = 0
    if os.name == "nt":
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    process = subprocess.Popen(
        _server_command(host, port, log_level),
        stdin=subprocess.DEVNULL,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        creationflags=creationflags,
        close_fds=os.name != "nt",
    )
    return process, log_handle


def _wait_for_health(host: str, port: int, process: subprocess.Popen, timeout: float = 20.0) -> dict[str, Any] | None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            return None
        health = _health(host, port)
        if health:
            return health
        time.sleep(0.2)
    return None


def _stop_child(process: subprocess.Popen | None, log_handle: Any = None) -> None:
    if process and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            process.kill()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                pass
    if log_handle:
        try:
            log_handle.flush()
            log_handle.close()
        except Exception:
            pass


def _open_browser_when_ready(url: str, host: str, port: int, timeout: float = 20.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _health(host, port):
            webbrowser.open(url)
            return
        time.sleep(0.2)


def _run_server_only(host: str, port: int, log_level: str) -> None:
    uvicorn.run(
        "innaware_pms_emulator.main:app",
        host=host,
        port=port,
        log_level=log_level,
        log_config=_server_log_config(log_level),
    )


def _run_browser_foreground(host: str, port: int, log_level: str, open_browser: bool = True) -> None:
    url_host = "127.0.0.1" if host in {"0.0.0.0", "::"} else host
    url = f"http://{url_host}:{port}/"
    if open_browser:
        threading.Thread(
            target=_open_browser_when_ready,
            args=(url, host, port),
            daemon=True,
            name="open-emulator-browser",
        ).start()
    _run_server_only(host, port, log_level)


def _run_native_window(url: str, child: subprocess.Popen | None, log_handle: Any = None) -> None:
    try:
        import webview
    except Exception as exc:
        _stop_child(child, log_handle)
        raise RuntimeError(f"The Windows desktop component could not be loaded: {exc}") from exc

    try:
        webview.create_window(
            APP_TITLE,
            url=url,
            width=1440,
            height=940,
            min_size=(1024, 700),
            resizable=True,
            text_select=True,
        )
        webview.start(debug=False)
    finally:
        _stop_child(child, log_handle)


def _start_user_launch_telemetry() -> None:
    """Count one user-facing Windows launch and suppress the service duplicate."""
    settings = update_manager.load_settings()
    telemetry_service.start_background(
        __version__,
        enabled=bool(settings.get("send_anonymous_usage_statistics", True)),
    )
    # The local FastAPI service may run in this process or a child. In either
    # case it inherits this flag and must not emit a second run event.
    os.environ[TELEMETRY_SUPPRESS_ENV] = "1"


def main() -> None:
    parser = argparse.ArgumentParser(description="InnAware PMS Emulator Windows field application")
    parser.add_argument("--host", default="127.0.0.1", help="HTTP management bind address")
    parser.add_argument("--port", type=int, default=8080, help="HTTP management port")
    parser.add_argument("--browser", action="store_true", help="Use the default web browser instead of the native desktop window")
    parser.add_argument("--no-browser", action="store_true", help="Run only the local service in the foreground")
    parser.add_argument("--server-only", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--log-level", default="info", choices=["critical", "error", "warning", "info", "debug", "trace"])
    args = parser.parse_args()

    if not 1 <= args.port <= 65535:
        _show_error("The management port must be between 1 and 65535.")
        return

    if args.server_only:
        # A direct service invocation has no parent launcher to count it; the
        # FastAPI lifespan owns telemetry in this mode.
        _run_server_only(args.host, args.port, args.log_level)
        return

    _start_user_launch_telemetry()

    existing = _health(args.host, args.port)
    port_used = _port_open(args.host, args.port)
    url_host = "127.0.0.1" if args.host in {"0.0.0.0", "::"} else args.host
    url = f"http://{url_host}:{args.port}/"

    if port_used and not existing:
        _show_error(
            f"TCP/{args.port} is already in use by another application.\n\n"
            f"Close that application or start {APP_TITLE} with a different --port."
        )
        return

    if args.no_browser:
        if existing:
            return
        _run_server_only(args.host, args.port, args.log_level)
        return

    if args.browser:
        if existing:
            webbrowser.open(url)
            return
        _run_browser_foreground(args.host, args.port, args.log_level, open_browser=True)
        return

    if existing:
        try:
            _run_native_window(url, None)
        except RuntimeError:
            webbrowser.open(url)
        return

    child: subprocess.Popen | None = None
    log_handle = None
    try:
        child, log_handle = _spawn_server(args.host, args.port, args.log_level)
        health = _wait_for_health(args.host, args.port, child)
        if not health:
            _stop_child(child, log_handle)
            child = None
            log_handle = None
            _show_error(
                f"{APP_TITLE} could not start its local service.\n\n"
                f"Diagnostic log:\n{_log_path()}"
            )
            return
        _run_native_window(url, child, log_handle)
        child = None
        log_handle = None
    except Exception as exc:
        _stop_child(child, log_handle)
        _show_error(
            f"{APP_TITLE} could not open the desktop application.\n\n"
            f"{exc}\n\nDiagnostic log:\n{_log_path()}"
        )


if __name__ == "__main__":
    main()
