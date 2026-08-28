from __future__ import annotations

import json
import logging
import platform
import ssl
import threading
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .protocol_packs import current_protocol_pack_version
from .storage import data_dir


TELEMETRY_ENDPOINT = "https://telemetry.innawareucp.com/pms-telemetry-ingest.php"
TELEMETRY_TIMEOUT_SECONDS = 2.5
_ALLOWED_PAYLOAD_FIELDS = {
    "event",
    "version",
    "platform",
    "architecture",
    "protocol_pack_version",
    "install_id",
}
_LOG = logging.getLogger("innaware_pms_emulator.telemetry")


def runtime_platform() -> str:
    value = platform.system().strip().lower()
    return {
        "windows": "windows",
        "linux": "linux",
        "darwin": "macos",
    }.get(value, value or "unknown")


def runtime_architecture() -> str:
    value = platform.machine().strip().lower()
    if value in {"amd64", "x86_64", "x64"}:
        return "x64"
    if value in {"x86", "i386", "i486", "i586", "i686"}:
        return "x86"
    if value in {"arm64", "aarch64"}:
        return "arm64"
    return value or "unknown"


class TelemetryService:
    """Small, auditable, best-effort anonymous usage telemetry service."""

    def __init__(
        self,
        root: Path | None = None,
        *,
        endpoint: str = TELEMETRY_ENDPOINT,
        timeout: float = TELEMETRY_TIMEOUT_SECONDS,
        pack_version_provider: Callable[[], str] = current_protocol_pack_version,
        post_func: Callable[[dict[str, str]], bool] | None = None,
    ) -> None:
        self.root = root or data_dir()
        self.root.mkdir(parents=True, exist_ok=True)
        self.state_path = self.root / "telemetry.json"
        self.endpoint = endpoint
        self.timeout = timeout
        self.pack_version_provider = pack_version_provider
        self.post_func = post_func
        self._lock = threading.Lock()

    @staticmethod
    def _valid_uuid4(value: Any) -> str | None:
        try:
            parsed = uuid.UUID(str(value))
        except (ValueError, AttributeError, TypeError):
            return None
        if parsed.version != 4:
            return None
        return str(parsed)

    def _new_state(self) -> dict[str, Any]:
        return {
            "install_id": str(uuid.uuid4()),
            "install_event_sent": False,
            "last_attempt_at": None,
            "last_success_at": None,
            "last_error": None,
        }

    def _write_state(self, state: dict[str, Any]) -> None:
        temp = self.state_path.with_suffix(self.state_path.suffix + ".tmp")
        temp.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temp.replace(self.state_path)

    def load_or_create_state(self) -> dict[str, Any]:
        with self._lock:
            state: dict[str, Any] | None = None
            if self.state_path.exists():
                try:
                    raw = json.loads(self.state_path.read_text(encoding="utf-8"))
                    install_id = self._valid_uuid4(raw.get("install_id")) if isinstance(raw, dict) else None
                    if install_id:
                        # 0.3.6 recorded an attempt before network I/O. It could
                        # not distinguish a delivered event from a rejected one,
                        # so migrate those installations as unsent and retry.
                        install_sent = bool(raw.get("install_event_sent", False))
                        state = {
                            "install_id": install_id,
                            "install_event_sent": install_sent,
                            "last_attempt_at": raw.get("last_attempt_at"),
                            "last_success_at": raw.get("last_success_at"),
                            "last_error": raw.get("last_error"),
                        }
                except (OSError, json.JSONDecodeError):
                    state = None
            if state is None:
                state = self._new_state()
                try:
                    self._write_state(state)
                except OSError:
                    # Telemetry must never prevent the emulator from running.
                    pass
            return dict(state)

    def _payload(self, event: str, app_version: str, install_id: str) -> dict[str, str]:
        if event not in {"install", "run"}:
            raise ValueError("Unsupported telemetry event")
        payload = {
            "event": event,
            "version": str(app_version),
            "platform": runtime_platform(),
            "architecture": runtime_architecture(),
            "protocol_pack_version": str(self.pack_version_provider()),
            "install_id": install_id,
        }
        if set(payload) != _ALLOWED_PAYLOAD_FIELDS:
            raise RuntimeError("Telemetry payload contains unexpected fields")
        return payload

    def _post(self, payload: dict[str, str]) -> bool:
        if self.post_func is not None:
            return bool(self.post_func(dict(payload)))
        body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        request = urllib.request.Request(
            self.endpoint,
            data=body,
            method="POST",
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": f"InnAware-PMS-Emulator/{payload['version']}",
            },
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            if not 200 <= int(getattr(response, "status", 200)) < 300:
                return False
            raw = response.read(4096)
        try:
            result = json.loads(raw.decode("utf-8")) if raw else {}
        except (UnicodeDecodeError, json.JSONDecodeError):
            return False
        return isinstance(result, dict) and result.get("ok") is True

    def _send_safely(self, payload: dict[str, str]) -> tuple[bool, str | None]:
        try:
            delivered = self._post(payload)
            return delivered, None if delivered else "endpoint rejected the event"
        except urllib.error.HTTPError as exc:
            message = f"HTTP {exc.code}"
            _LOG.warning("Telemetry %s event failed: %s", payload.get("event"), message)
            return False, message
        except (urllib.error.URLError, TimeoutError, ssl.SSLError, OSError, ValueError) as exc:
            message = str(getattr(exc, "reason", exc))[:200]
            _LOG.warning("Telemetry %s event failed: %s", payload.get("event"), message)
            return False, message
        except Exception as exc:
            message = str(exc)[:200] or type(exc).__name__
            _LOG.warning("Telemetry %s event failed: %s", payload.get("event"), message)
            return False, message

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def run_once(self, app_version: str, *, enabled: bool) -> dict[str, Any]:
        state = self.load_or_create_state()
        install_id = state["install_id"]
        attempted: list[str] = []
        delivered: list[str] = []
        if not enabled:
            return {
                "enabled": False,
                "install_id": install_id,
                "attempted": attempted,
            }

        errors: list[str] = []
        state["last_attempt_at"] = self._utc_now()

        if not state.get("install_event_sent", False):
            attempted.append("install")
            ok, error = self._send_safely(self._payload("install", app_version, install_id))
            if ok:
                delivered.append("install")
                state["install_event_sent"] = True
                state["last_success_at"] = self._utc_now()
            elif error:
                errors.append(f"install: {error}")

        attempted.append("run")
        ok, error = self._send_safely(self._payload("run", app_version, install_id))
        if ok:
            delivered.append("run")
            state["last_success_at"] = self._utc_now()
        elif error:
            errors.append(f"run: {error}")
        state["last_error"] = "; ".join(errors) if errors else None
        try:
            with self._lock:
                self._write_state(state)
        except OSError:
            pass
        return {
            "enabled": True,
            "install_id": install_id,
            "attempted": attempted,
            "delivered": delivered,
            "error": state["last_error"],
        }

    def start_background(self, app_version: str, *, enabled: bool) -> None:
        # UUID creation is local and fast; do it synchronously so the Update Center
        # can display the identifier immediately. Network work stays off the startup path.
        self.load_or_create_state()
        if not enabled:
            return

        def worker() -> None:
            self.run_once(app_version, enabled=True)

        threading.Thread(target=worker, name="innaware-telemetry", daemon=True).start()

    def public_status(self, app_version: str, *, enabled: bool) -> dict[str, Any]:
        state = self.load_or_create_state()
        return {
            "enabled": bool(enabled),
            "install_id": state["install_id"],
            "install_event_sent": bool(state.get("install_event_sent", False)),
            "last_attempt_at": state.get("last_attempt_at"),
            "last_success_at": state.get("last_success_at"),
            "last_error": state.get("last_error"),
            "version": str(app_version),
            "platform": runtime_platform(),
            "architecture": runtime_architecture(),
            "protocol_pack_version": str(self.pack_version_provider()),
            "endpoint": self.endpoint,
        }


telemetry_service = TelemetryService()
