from __future__ import annotations

import argparse
import socket
import threading
import time
import webbrowser

import uvicorn


def _port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.25):
            return True
    except OSError:
        return False


def _open_browser_when_ready(url: str, host: str, port: int, timeout: float = 15.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _port_open(host, port):
            webbrowser.open(url)
            return
        time.sleep(0.2)


def main() -> None:
    parser = argparse.ArgumentParser(description="InnAware PMS Emulator for Windows")
    parser.add_argument("--host", default="127.0.0.1", help="HTTP bind address")
    parser.add_argument("--port", type=int, default=8080, help="HTTP port")
    parser.add_argument("--no-browser", action="store_true", help="Do not open the operator console automatically")
    parser.add_argument("--log-level", default="info", choices=["critical", "error", "warning", "info", "debug", "trace"])
    args = parser.parse_args()

    if _port_open(args.host, args.port):
        raise SystemExit(f"TCP/{args.port} is already in use. Stop the existing emulator or choose another --port.")

    url_host = "127.0.0.1" if args.host in {"0.0.0.0", "::"} else args.host
    url = f"http://{url_host}:{args.port}/"

    if not args.no_browser:
        threading.Thread(
            target=_open_browser_when_ready,
            args=(url, url_host, args.port),
            daemon=True,
            name="open-emulator-browser",
        ).start()

    uvicorn.run(
        "innaware_pms_emulator.main:app",
        host=args.host,
        port=args.port,
        log_level=args.log_level,
    )


if __name__ == "__main__":
    main()
