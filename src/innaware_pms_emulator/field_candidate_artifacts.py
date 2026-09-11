from __future__ import annotations

import hashlib
import json
import re
import zipfile
from pathlib import Path
from typing import Any

_GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


class ArtifactManifestError(ValueError):
    """Raised when a hosted candidate artifact cannot be admitted fail-closed."""


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_object(payload: bytes, *, label: str) -> dict[str, Any]:
    try:
        parsed = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ArtifactManifestError(f"{label} must be valid UTF-8 JSON") from exc
    if not isinstance(parsed, dict):
        raise ArtifactManifestError(f"{label} must contain a JSON object")
    return parsed


def _artifact_entry(*, name: str, payload: bytes) -> dict[str, Any]:
    return {
        "name": name,
        "size_bytes": len(payload),
        "sha256": _sha256_bytes(payload),
    }


def build_field_artifact_manifest(*, source_sha: str, artifact_zip: Path) -> dict[str, Any]:
    """Build a deterministic manifest from one exact hosted Windows artifact ZIP.

    The function is intentionally fail-closed. It verifies candidate release identity,
    exact-SHA interoperability evidence, and the files required for Windows field
    acceptance without executing any vendor/field binary.
    """

    exact_sha = source_sha.lower() if isinstance(source_sha, str) else ""
    if not _GIT_SHA_RE.fullmatch(exact_sha):
        raise ArtifactManifestError("source_sha must be exactly 40 lowercase hexadecimal characters")

    artifact_zip = Path(artifact_zip)
    if not artifact_zip.is_file():
        raise ArtifactManifestError(f"artifact ZIP does not exist: {artifact_zip}")
    if not zipfile.is_zipfile(artifact_zip):
        raise ArtifactManifestError(f"artifact is not a ZIP archive: {artifact_zip}")

    with zipfile.ZipFile(artifact_zip, "r") as archive:
        file_infos = [item for item in archive.infolist() if not item.is_dir()]
        names = [item.filename for item in file_infos]
        duplicates = sorted({name for name in names if names.count(name) > 1})
        if duplicates:
            raise ArtifactManifestError(f"artifact ZIP contains duplicate member names: {', '.join(duplicates)}")

        by_name = {item.filename: item for item in file_infos}

        def read_required(name: str) -> bytes:
            if name not in by_name:
                raise ArtifactManifestError(f"required artifact member is missing: {name}")
            return archive.read(by_name[name])

        release_name = "release-manifest.json"
        release_bytes = read_required(release_name)
        release = _json_object(release_bytes, label=release_name)

        application_version = str(release.get("application_version", "")).strip()
        release_tag = str(release.get("release_tag", "")).strip()
        protocol_pack_version = str(release.get("protocol_pack_version", "")).strip()
        if not application_version:
            raise ArtifactManifestError("release-manifest.json is missing application_version")
        if release_tag != f"v{application_version}":
            raise ArtifactManifestError("release tag does not match application_version")
        if not protocol_pack_version:
            raise ArtifactManifestError("release-manifest.json is missing protocol_pack_version")
        if release.get("publish") is not False:
            raise ArtifactManifestError("field candidate artifact must keep automatic publication disabled")
        if release.get("prerelease") is not True:
            raise ArtifactManifestError("field candidate artifact must remain marked prerelease")
        if release.get("make_latest") is not False:
            raise ArtifactManifestError("field candidate artifact must not be marked latest before closure")

        exe_name = "dist-windows/InnAware-PMS-Emulator.exe"
        installer_name = "dist-windows/InnAware-PMS-Emulator-Setup.exe"
        windows_zip_name = f"InnAware-PMS-Emulator-Windows-{application_version}.zip"
        source_zip_name = f"InnAware-PMS-Emulator-Source-{application_version}.zip"
        evidence_name = f"InnAware-PMS-Interop-Evidence-{exact_sha}.json"
        protocol_pack_name = f"InnAware-PMS-Protocol-Pack-{protocol_pack_version}.zip"

        payloads = {
            "field_executable": (exe_name, read_required(exe_name)),
            "installer": (installer_name, read_required(installer_name)),
            "windows_zip": (windows_zip_name, read_required(windows_zip_name)),
            "source_zip": (source_zip_name, read_required(source_zip_name)),
            "interop_evidence_pack": (evidence_name, read_required(evidence_name)),
            "protocol_pack": (protocol_pack_name, read_required(protocol_pack_name)),
            "release_manifest": (release_name, release_bytes),
        }

        evidence = _json_object(payloads["interop_evidence_pack"][1], label=evidence_name)
        producer = evidence.get("producer")
        producer_sha = str(producer.get("source_sha", "")).lower() if isinstance(producer, dict) else ""
        if producer_sha != exact_sha:
            raise ArtifactManifestError(
                f"interop evidence producer SHA {producer_sha or '<missing>'} does not match exact source SHA {exact_sha}"
            )
        producer_repo = str(producer.get("repository", "")) if isinstance(producer, dict) else ""
        if producer_repo and producer_repo != "MusicCityTelecom/innaware-pms-emulator":
            raise ArtifactManifestError("interop evidence repository identity is not the standalone PMS Emulator repository")

    artifacts = {
        "artifact_bundle": {
            "name": artifact_zip.name,
            "size_bytes": artifact_zip.stat().st_size,
            "sha256": _sha256_file(artifact_zip),
        }
    }
    for key, (name, payload) in payloads.items():
        artifacts[key] = _artifact_entry(name=name, payload=payload)

    return {
        "schema": "innaware-pms-emulator-field-artifact-manifest/v1",
        "source_sha": exact_sha,
        "application_version": application_version,
        "release_tag": release_tag,
        "protocol_pack_version": protocol_pack_version,
        "release_policy": {
            "publish": False,
            "prerelease": True,
            "make_latest": False,
        },
        "artifacts": artifacts,
        "claim_policy": {
            "artifact_manifest_is_not_gui_acceptance": True,
            "artifact_manifest_is_not_protocol_promotion": True,
            "artifact_manifest_authorizes_production_release": False,
            "executes_field_binary": False,
        },
        "architectural_boundary": {
            "project": "InnAware PMS-PBX Emulator",
            "repository": "MusicCityTelecom/innaware-pms-emulator",
            "runtime_dependency_on_ucp": False,
            "ucp_runtime_dependency_on_emulator_allowed": False,
        },
    }
