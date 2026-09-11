from __future__ import annotations

import csv
import io
import json
import os
import platform
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import __version__
from .storage import data_dir


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, default=str) + "\n").encode("utf-8")


def safe_name(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in value.strip())
    return cleaned or "interface"


def captures_as_csv(captures: list[dict[str, Any]]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=["timestamp", "direction", "peer", "note", "hex", "text"])
    writer.writeheader()
    for row in captures:
        writer.writerow({key: row.get(key, "") for key in writer.fieldnames})
    return stream.getvalue().encode("utf-8-sig")


def captures_as_text(captures: list[dict[str, Any]]) -> bytes:
    lines: list[str] = []
    for row in captures:
        lines.append(
            f"{row.get('timestamp', '')} {str(row.get('direction', '')).upper()} "
            f"{row.get('peer') or '-'} {row.get('note') or ''}".rstrip()
        )
        lines.append(f"HEX  {row.get('hex', '')}")
        lines.append(f"TEXT {row.get('text', '')}")
        lines.append("")
    return "\n".join(lines).encode("utf-8", errors="replace")


def capture_export(captures: list[dict[str, Any]], export_format: str) -> tuple[bytes, str, str]:
    fmt = export_format.lower().strip()
    if fmt == "json":
        return _json_bytes(captures), "application/json", "json"
    if fmt == "csv":
        return captures_as_csv(captures), "text/csv; charset=utf-8", "csv"
    if fmt in {"txt", "text"}:
        return captures_as_text(captures), "text/plain; charset=utf-8", "txt"
    raise ValueError("Capture export format must be json, csv, or txt")


def _platform_manifest() -> dict[str, Any]:
    return {
        "product": "InnAware PMS Emulator",
        "version": __version__,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(),
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "python": sys.version,
        "frozen": bool(getattr(sys, "frozen", False)),
        "data_dir": str(data_dir()),
    }


def _read_optional_log(max_bytes: int = 2_000_000) -> bytes | None:
    candidates = [
        data_dir() / "logs" / "emulator.log",
        data_dir() / "emulator.log",
    ]
    override = os.environ.get("INNAWARE_PMS_LOG_FILE")
    if override:
        candidates.insert(0, Path(override).expanduser())
    for path in candidates:
        try:
            if not path.is_file():
                continue
            size = path.stat().st_size
            with path.open("rb") as handle:
                if size > max_bytes:
                    handle.seek(-max_bytes, os.SEEK_END)
                return handle.read()
        except OSError:
            continue
    return None


def build_support_bundle(
    *,
    interface_statuses: list[dict[str, Any]],
    interface_configs: list[dict[str, Any]],
    property_summaries: list[dict[str, Any]],
    protocol_catalog: list[dict[str, Any]],
    serial_ports: list[dict[str, Any]],
    captures_by_interface: dict[str, list[dict[str, Any]]],
    transactions_by_interface: dict[str, list[dict[str, Any]]],
    diagnostics_by_interface: dict[str, list[dict[str, Any]]] | None = None,
    full_property_state: list[dict[str, Any]] | None = None,
) -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", _json_bytes(_platform_manifest()))
        archive.writestr("interfaces/status.json", _json_bytes(interface_statuses))
        archive.writestr("interfaces/config.json", _json_bytes(interface_configs))
        archive.writestr("properties/summary.json", _json_bytes(property_summaries))
        archive.writestr("protocols/catalog.json", _json_bytes(protocol_catalog))
        archive.writestr("serial/ports.json", _json_bytes(serial_ports))

        for name, captures in captures_by_interface.items():
            base = safe_name(name)
            archive.writestr(f"captures/{base}.json", _json_bytes(captures))
            archive.writestr(f"captures/{base}.csv", captures_as_csv(captures))
        for name, transactions in transactions_by_interface.items():
            archive.writestr(f"transactions/{safe_name(name)}.json", _json_bytes(transactions))
        for name, diagnostics in (diagnostics_by_interface or {}).items():
            archive.writestr(f"diagnostics/{safe_name(name)}.json", _json_bytes(diagnostics))

        if full_property_state is not None:
            archive.writestr("properties/FULL_PROPERTY_STATE_CONTAINS_GUEST_DATA.json", _json_bytes(full_property_state))
        else:
            archive.writestr(
                "properties/PRIVACY.txt",
                "Full property/guest state was not included. Generate the bundle with include_property_state=true only when guest data is appropriate to share.\n",
            )

        log_data = _read_optional_log()
        if log_data:
            archive.writestr("logs/emulator.log", log_data)

        archive.writestr(
            "README.txt",
            (
                "InnAware PMS Emulator support bundle\n\n"
                "This archive is intended for troubleshooting. Interface addresses, serial-port identifiers, diagnostics, and wire captures may contain environment-specific data.\n"
                "Full guest/property state is excluded by default.\n"
            ),
        )
    return stream.getvalue()
