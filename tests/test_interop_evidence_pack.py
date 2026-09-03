from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

from innaware_pms_emulator.compatibility_matrix import (
    COMPATIBILITY_MATRIX,
    EvidenceClass,
    SupportStatus,
)
from innaware_pms_emulator.interop_evidence_pack import (
    EVIDENCE_RANK,
    SHAREABLE_FIXTURES,
    build_interop_evidence_pack,
    validate_fixture_registry,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
EXACT_SHA = "a" * 40


def test_shareable_fixture_registry_is_exact_and_sanitized() -> None:
    assert validate_fixture_registry(REPO_ROOT) == []

    matrix_by_key = {entry.key: entry for entry in COMPATIBILITY_MATRIX}
    assert SHAREABLE_FIXTURES
    for fixture in SHAREABLE_FIXTURES:
        assert fixture.path.endswith(".json")
        assert ".exe" not in fixture.path.casefold()
        entry = matrix_by_key[fixture.matrix_key]
        assert entry.evidence_class is fixture.evidence_class
        assert entry.status in {SupportStatus.PARTIAL, SupportStatus.SUPPORTED}


def test_pack_is_deterministic_data_only_and_sha_pinned() -> None:
    first = build_interop_evidence_pack(repo_root=REPO_ROOT, source_sha=EXACT_SHA)
    second = build_interop_evidence_pack(repo_root=REPO_ROOT, source_sha=EXACT_SHA)

    assert first == second
    assert first["producer"] == {
        "project": "InnAware PMS-PBX Emulator",
        "repository": "MusicCityTelecom/innaware-pms-emulator",
        "source_sha": EXACT_SHA,
    }
    boundary = first["architectural_boundary"]
    assert boundary["exchange_mode"] == "data_only"
    assert boundary["runtime_dependency_on_emulator"] is False
    assert "separate production hospitality PMS gateway/runtime" in boundary["ucp_role"]
    assert any("Do not import" in rule for rule in boundary["rules"])

    assert first["evidence_rank"] == [item.value for item in EVIDENCE_RANK]
    assert first["evidence_rank"][:5] == [
        EvidenceClass.PACKET_CAPTURE.value,
        EvidenceClass.OPERATOR_CONFIRMED.value,
        EvidenceClass.LEGACY_SOURCE_PROFILE.value,
        EvidenceClass.SIMULATOR_CHARACTERIZATION.value,
        EvidenceClass.INFERENCE.value,
    ]
    assert len(first["compatibility_rows"]) == len(COMPATIBILITY_MATRIX)


def test_pack_embeds_only_registered_sanitized_fixture_documents() -> None:
    pack = build_interop_evidence_pack(repo_root=REPO_ROOT, source_sha=EXACT_SHA)
    expected_paths = {fixture.path for fixture in SHAREABLE_FIXTURES}
    exported_paths = {fixture["path"] for fixture in pack["fixtures"]}
    assert exported_paths == expected_paths

    for fixture in pack["fixtures"]:
        assert len(fixture["sha256"]) == 64
        assert fixture["path"].endswith(".json")
        document = fixture["document"]
        if "sanitized" in document:
            assert document["sanitized"] is True
        else:
            assert document["fixtures"]
            assert all(item["sanitized"] is True for item in document["fixtures"])


def test_supported_rows_cannot_lack_a_shareable_fixture() -> None:
    exported_keys = {fixture.matrix_key for fixture in SHAREABLE_FIXTURES}
    for entry in COMPATIBILITY_MATRIX:
        if entry.status is SupportStatus.SUPPORTED:
            assert entry.key in exported_keys


def test_pack_rejects_unpinned_or_abbreviated_source_sha() -> None:
    for source_sha in ("", "abc1234", "not-a-sha", "a" * 39, "a" * 41):
        with pytest.raises(ValueError, match="exact 40-character Git commit SHA"):
            build_interop_evidence_pack(repo_root=REPO_ROOT, source_sha=source_sha)


def test_cli_builds_same_cross_project_data_contract(tmp_path: Path) -> None:
    output = tmp_path / "interop-evidence-pack.json"
    script = REPO_ROOT / "scripts" / "build-interop-evidence-pack.py"
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--source-sha",
            EXACT_SHA,
            "--output",
            str(output),
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr

    cli_pack = json.loads(output.read_text(encoding="utf-8"))
    direct_pack = build_interop_evidence_pack(repo_root=REPO_ROOT, source_sha=EXACT_SHA)
    assert cli_pack == direct_pack
