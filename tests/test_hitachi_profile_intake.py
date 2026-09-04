from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

from innaware_pms_emulator.hitachi_profile_intake import build_hitachi_profile_intake


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "inspect-hitachi-profile-set.py"
EXACT_SHA = "c" * 40


def _profile(protocol: str, *, transport: str | None = None, room_offset: int = 5) -> bytes:
    transport_line = f"transport={transport}\n" if transport else ""
    return (
        "[pbx-protocol]\n"
        f"protocol={protocol}\n"
        "family=HITACHI\n"
        f"{transport_line}"
        "enq=5\n"
        "stx=2\n"
        "etx=3\n"
        "ack=6\n"
        "nak=21\n"
        "checksum=0\n"
        "CHK=CHK{status}{room}\n"
        "NAM=NAM{name}{room}\n"
        "site_secret=do-not-export-this-value\n"
        "\n[pbx-masks]\n"
        "chkroom=4 3 MASK_NUMBER\n"
        f"namroom={room_offset} 3 MASK_NUMBER\n"
        f"namname={room_offset + 3} 20 MASK_LITERAL\n"
        "private_site_key=also-do-not-export\n"
    ).encode("utf-8")


def _write_profile_set(tmp_path: Path, *, transport: str | None = None) -> Path:
    source = tmp_path / "voiceware-profiles"
    source.mkdir(parents=True)
    (source / "psip-pbx-protocol.Epitome").write_bytes(
        _profile("Epitome", transport=transport, room_offset=5)
    )
    (source / "psip-pbx-protocol.EPIT-HIT").write_bytes(
        _profile("EPIT-HIT", transport=transport, room_offset=5)
    )
    (source / "psip-pbx-protocol.EPIT-HIT2").write_bytes(
        _profile("EPIT-HIT2", transport=transport, room_offset=8)
    )
    return source


def test_intake_is_deterministic_read_only_and_payload_safe(tmp_path: Path) -> None:
    source = _write_profile_set(tmp_path)

    first = build_hitachi_profile_intake(profile_dir=source, source_sha=EXACT_SHA)
    second = build_hitachi_profile_intake(profile_dir=source, source_sha=EXACT_SHA)

    assert first == second
    assert first["sanitized"] is True
    assert first["read_only"] is True
    assert first["raw_profiles_embedded"] is False
    assert first["source_directory_path_embedded"] is False
    assert first["producer"]["source_sha"] == EXACT_SHA
    assert set(first["admissions"]) == {"EPIT-HIT", "EPIT-HIT2"}
    assert first["observed_concrete_transports"] == []
    assert first["matrix_change_candidates"] == []

    serialized = json.dumps(first, sort_keys=True)
    assert "do-not-export-this-value" not in serialized
    assert "also-do-not-export" not in serialized
    assert str(source) not in serialized
    assert first["claim_policy"]["raw_profile_bodies_must_remain_outside_git"] is True
    assert first["architectural_boundary"]["exchange_mode"] == "data_only"
    assert first["architectural_boundary"]["ucp_runtime_dependency_allowed"] is False


def test_intake_preserves_unknown_transport_until_exact_profile_declares_it(tmp_path: Path) -> None:
    source = _write_profile_set(tmp_path)
    report = build_hitachi_profile_intake(profile_dir=source, source_sha=EXACT_SHA)

    for profile in report["source_set"]["profiles"].values():
        assert profile["transport"] == "unknown"
        assert profile["transport_source"] == "none"

    for admission in report["admissions"].values():
        assert admission["observed_transport"] == "unknown"
        assert admission["matrix_change_required"] is False
        assert admission["compatibility_promotion_authorized"] is False


def test_explicit_profile_transport_is_reported_but_never_auto_registered(tmp_path: Path) -> None:
    source = _write_profile_set(tmp_path, transport="serial")
    report = build_hitachi_profile_intake(profile_dir=source, source_sha=EXACT_SHA)

    assert report["observed_concrete_transports"] == ["serial"]
    assert report["matrix_change_candidates"] == ["EPIT-HIT", "EPIT-HIT2"]
    for profile in report["source_set"]["profiles"].values():
        assert profile["transport"] == "serial"
        assert profile["transport_source"] == "explicit_profile_key"
    for admission in report["admissions"].values():
        assert admission["observed_transport"] == "serial"
        assert admission["matrix_change_required"] is True
        assert admission["compatibility_promotion_authorized"] is False
        assert "transport" in admission["resolved_gap_codes"]

    assert report["claim_policy"]["matrix_mutation_is_automatic"] is False
    assert report["claim_policy"]["compatibility_promotion_authorized"] is False


def test_missing_profile_or_unpinned_sha_fails_closed(tmp_path: Path) -> None:
    source = _write_profile_set(tmp_path)
    (source / "psip-pbx-protocol.EPIT-HIT2").unlink()

    with pytest.raises(ValueError, match="missing required Hitachi source profiles"):
        build_hitachi_profile_intake(profile_dir=source, source_sha=EXACT_SHA)

    complete = _write_profile_set(tmp_path / "second")
    with pytest.raises(ValueError, match="40-character"):
        build_hitachi_profile_intake(profile_dir=complete, source_sha="abc")


def test_cli_matches_direct_report_and_does_not_modify_source_files(tmp_path: Path) -> None:
    source = _write_profile_set(tmp_path)
    before = {
        path.name: path.read_bytes()
        for path in source.iterdir()
        if path.is_file()
    }
    output = tmp_path / "hitachi-profile-intake.json"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--source-sha",
            EXACT_SHA,
            "--profile-dir",
            str(source),
            "--output",
            str(output),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "evidence_bundle_sha256=" in result.stdout
    assert "EPIT-HIT: observed_transport=unknown" in result.stdout

    cli_report = json.loads(output.read_text(encoding="utf-8"))
    direct_report = build_hitachi_profile_intake(profile_dir=source, source_sha=EXACT_SHA)
    assert cli_report == direct_report
    after = {
        path.name: path.read_bytes()
        for path in source.iterdir()
        if path.is_file()
    }
    assert after == before
