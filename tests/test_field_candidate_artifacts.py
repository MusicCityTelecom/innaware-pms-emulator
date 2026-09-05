import json
import zipfile
from pathlib import Path

import pytest

from innaware_pms_emulator.field_candidate_artifacts import ArtifactManifestError, build_field_artifact_manifest

EMU_SHA = "d" * 40
VERSION = "0.4.0"
PACK = "2026.08.27.1"


def write_candidate(path: Path, *, producer_sha=EMU_SHA, publish=False, prerelease=True, make_latest=False, omit=None):
    release = {
        "schema_version": 1,
        "application_version": VERSION,
        "release_tag": f"v{VERSION}",
        "release_channel": "field-beta",
        "publish": publish,
        "prerelease": prerelease,
        "make_latest": make_latest,
        "protocol_pack_version": PACK,
        "repository": "MusicCityTelecom/innaware-pms-emulator",
        "update_source": "https://github.com/MusicCityTelecom/innaware-pms-emulator/releases",
    }
    evidence = {
        "producer": {
            "project": "InnAware PMS-PBX Emulator",
            "repository": "MusicCityTelecom/innaware-pms-emulator",
            "source_sha": producer_sha,
        }
    }
    members = {
        "release-manifest.json": json.dumps(release).encode(),
        "dist-windows/InnAware-PMS-Emulator.exe": b"synthetic-exe",
        "dist-windows/InnAware-PMS-Emulator-Setup.exe": b"synthetic-installer",
        f"InnAware-PMS-Emulator-Windows-{VERSION}.zip": b"synthetic-windows-zip",
        f"InnAware-PMS-Emulator-Source-{VERSION}.zip": b"synthetic-source-zip",
        f"InnAware-PMS-Interop-Evidence-{EMU_SHA}.json": json.dumps(evidence).encode(),
        f"InnAware-PMS-Protocol-Pack-{PACK}.zip": b"synthetic-protocol-pack",
    }
    if omit:
        members.pop(omit)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, payload in members.items():
            archive.writestr(name, payload)


def test_builds_exact_sha_candidate_manifest_without_executing_binary(tmp_path):
    artifact = tmp_path / "candidate.zip"
    write_candidate(artifact)

    result = build_field_artifact_manifest(source_sha=EMU_SHA, artifact_zip=artifact)

    assert result["source_sha"] == EMU_SHA
    assert result["application_version"] == VERSION
    assert result["release_tag"] == f"v{VERSION}"
    assert result["protocol_pack_version"] == PACK
    assert result["release_policy"] == {"publish": False, "prerelease": True, "make_latest": False}
    assert result["artifacts"]["artifact_bundle"]["name"] == "candidate.zip"
    assert result["artifacts"]["field_executable"]["name"] == "dist-windows/InnAware-PMS-Emulator.exe"
    assert len(result["artifacts"]["field_executable"]["sha256"]) == 64
    assert result["artifacts"]["interop_evidence_pack"]["name"] == f"InnAware-PMS-Interop-Evidence-{EMU_SHA}.json"
    assert result["claim_policy"]["executes_field_binary"] is False
    assert result["architectural_boundary"]["runtime_dependency_on_ucp"] is False


def test_rejects_interop_evidence_from_a_different_source_sha(tmp_path):
    artifact = tmp_path / "candidate.zip"
    write_candidate(artifact, producer_sha="e" * 40)

    with pytest.raises(ArtifactManifestError, match="does not match exact source SHA"):
        build_field_artifact_manifest(source_sha=EMU_SHA, artifact_zip=artifact)


def test_rejects_release_enabled_candidate_artifact(tmp_path):
    artifact = tmp_path / "candidate.zip"
    write_candidate(artifact, publish=True)

    with pytest.raises(ArtifactManifestError, match="automatic publication disabled"):
        build_field_artifact_manifest(source_sha=EMU_SHA, artifact_zip=artifact)


def test_rejects_missing_windows_field_executable(tmp_path):
    artifact = tmp_path / "candidate.zip"
    write_candidate(artifact, omit="dist-windows/InnAware-PMS-Emulator.exe")

    with pytest.raises(ArtifactManifestError, match="field executable|InnAware-PMS-Emulator.exe"):
        build_field_artifact_manifest(source_sha=EMU_SHA, artifact_zip=artifact)
