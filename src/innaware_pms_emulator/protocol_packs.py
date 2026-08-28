from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from .storage import data_dir


PACK_SCHEMA_VERSION = 1


def protocol_packs_dir() -> Path:
    path = data_dir() / "protocol-packs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def active_pointer_path() -> Path:
    return protocol_packs_dir() / "active.json"


def _safe_version(value: str) -> str:
    cleaned = "".join(ch for ch in str(value) if ch.isalnum() or ch in {".", "-", "_"}).strip("._-")
    if not cleaned:
        raise ValueError("Invalid protocol-pack version")
    return cleaned[:80]


def active_pack_info() -> dict[str, Any] | None:
    pointer = active_pointer_path()
    if not pointer.exists():
        return None
    try:
        raw = json.loads(pointer.read_text(encoding="utf-8"))
        version = _safe_version(str(raw["pack_version"]))
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None
    pack_dir = protocol_packs_dir() / version
    manifest_path = pack_dir / "protocol-pack.json"
    if not manifest_path.exists():
        return None
    return {
        **raw,
        "pack_version": version,
        "path": str(pack_dir),
        "manifest_path": str(manifest_path),
    }


def active_pack_manifest() -> dict[str, Any] | None:
    info = active_pack_info()
    if not info:
        return None
    try:
        manifest = json.loads(Path(info["manifest_path"]).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if manifest.get("schema_version") != PACK_SCHEMA_VERSION:
        return None
    if _safe_version(str(manifest.get("pack_version", ""))) != info["pack_version"]:
        return None
    return manifest


def _bundled_manifest_candidates() -> list[Path]:
    candidates: list[Path] = []
    override = os.environ.get("INNAWARE_PMS_PROTOCOL_PACK_MANIFEST")
    if override:
        candidates.append(Path(override).expanduser())
    frozen_root = getattr(sys, "_MEIPASS", None)
    if frozen_root:
        candidates.append(Path(frozen_root) / "protocol-pack.json")
    try:
        candidates.append(Path(__file__).resolve().parents[2] / "protocol-pack.json")
    except (IndexError, OSError):
        pass
    try:
        candidates.append(Path(sys.executable).resolve().parent / "protocol-pack.json")
    except OSError:
        pass
    return candidates


def bundled_pack_manifest() -> dict[str, Any] | None:
    for path in _bundled_manifest_candidates():
        try:
            manifest = json.loads(path.read_text(encoding="utf-8"))
            if manifest.get("schema_version") != PACK_SCHEMA_VERSION:
                continue
            manifest["pack_version"] = _safe_version(str(manifest.get("pack_version", "")))
            return manifest
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            continue
    return None


def current_protocol_pack_version() -> str:
    """Return the version of the pack the running application is actually using."""
    active = active_pack_manifest()
    if active:
        return str(active["pack_version"])
    bundled = bundled_pack_manifest()
    if bundled:
        return str(bundled["pack_version"])
    return "unknown"


def active_pack_profiles() -> list[dict[str, Any]]:
    manifest = active_pack_manifest()
    if not manifest:
        return []
    profiles = manifest.get("profiles", [])
    if not isinstance(profiles, list):
        return []
    return [dict(item) for item in profiles if isinstance(item, dict)]


def active_pack_stubs() -> list[dict[str, Any]]:
    info = active_pack_info()
    if not info:
        return []
    stub_dir = Path(info["path"]) / "stubs"
    if not stub_dir.is_dir():
        return []
    result: list[dict[str, Any]] = []
    for path in sorted(stub_dir.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        result.append({"file": path.name, "data": payload})
    return result
