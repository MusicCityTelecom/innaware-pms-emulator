from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

from innaware_pms_emulator.hitachi_evidence_admission import admit_hitachi_profile_evidence
from innaware_pms_emulator.hitachi_profile_evidence import (
    build_hitachi_profile_evidence_bundle,
    hitachi_bundle_digest,
)


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "admit-hitachi-profile-evidence.py"
EXACT_SHA = "d" * 40

EPITOME = """[pbx-protocol]\nprotocol=Epitome\nfamily=HITACHI\nenq=5\nstx=2\netx=3\nack=6\nnak=21\nchecksum=0\nCHK=CHK{status}{room}\nNAM=NAM{name}{room}\n\n[pbx-masks]\nchkroom=4 3 MASK_NUMBER\nnamroom=4 3 MASK_NUMBER\nnamname=7 20 MASK_LITERAL\n"""
EPIT_HIT = """[pbx-protocol]\nprotocol=EPIT-HIT\nfamily=HITACHI\nenq=5\nstx=2\netx=3\nack=6\nnak=21\nchecksum=0\nCHK=CHK{status}{room}\nNAM=NAM{name}{room}\n\n[pbx-masks]\nchkroom=4 3 MASK_NUMBER\nnamroom=5 3 MASK_NUMBER\nnamname=8 20 MASK_LITERAL\n"""
EPIT_HIT2 = """[pbx-protocol]\nprotocol=EPIT-HIT2\nfamily=HITACHI\nenq=5\nstx=2\netx=3\nack=6\nnak=21\nchecksum=0\nCHK=CHK{status}{room}\nNAM=NAM{name}{room}\n\n[pbx-masks]\nchkroom=4 3 MASK_NUMBER\nnamroom=8 3 MASK_NUMBER\nnamname=11 20 MASK_LITERAL\nnameindex0=2\n"""


def _write_bundle(tmp_path: Path, *, transport: str | None = None) -> tuple[Path, dict[str, object]]:
    profile_paths = []
    for name, text in (
        ("psip-pbx-protocol.Epitome", EPITOME),
        ("psip-pbx-protocol.EPIT-HIT", EPIT_HIT),
        ("psip-pbx-protocol.EPIT-HIT2", EPIT_HIT2),
    ):
        if transport is not None:
            text = text.replace("family=HITACHI\n", f"family=HITACHI\ntransport={transport}\n")
        path = tmp_path / name
        path.write_text(text, encoding="utf-8")
        profile_paths.append(path)

    bundle = build_hitachi_profile_evidence_bundle(
        epitome_path=profile_paths[0],
        epit_hit_path=profile_paths[1],
        epit_hit2_path=profile_paths[2],
        source_sha=EXACT_SHA,
    )
    bundle_path = tmp_path / "hitachi-evidence.json"
    bundle_path.write_text(json.dumps(bundle, sort_keys=True), encoding="utf-8")
    return bundle_path, bundle


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        check=False,
        capture_output=True,
        text=True,
    )


def test_cli_report_matches_library_admission_and_stays_non_promoting(tmp_path: Path) -> None:
    bundle_path, bundle = _write_bundle(tmp_path)

    result = _run(
        "--bundle",
        str(bundle_path),
        "--expected-source-sha",
        EXACT_SHA,
    )

    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["schema_version"] == 1
    assert report["sanitized"] is True
    assert report["data_only"] is True
    assert report["producer"]["source_sha"] == EXACT_SHA
    assert report["bundle_sha256"] == hitachi_bundle_digest(bundle)
    assert report["claim_policy"] == {
        "compatibility_promotion_authorized": False,
        "matrix_changes_require_separate_review": True,
        "partial_or_planned_evidence_is_not_production_support": True,
        "runtime_dependency_on_emulator": False,
    }

    for protocol in ("EPIT-HIT", "EPIT-HIT2"):
        assert report["admissions"][protocol] == admit_hitachi_profile_evidence(
            bundle,
            pms_protocol=protocol,
        ).as_dict()
        assert report["admissions"][protocol]["compatibility_promotion_authorized"] is False
        assert "checksum_contract" in report["admissions"][protocol]["remaining_gap_codes"]
        assert "reverse_direction" in report["admissions"][protocol]["remaining_gap_codes"]


def test_cli_output_is_deterministic_and_explicit_transport_requires_matrix_review(tmp_path: Path) -> None:
    bundle_path, bundle = _write_bundle(tmp_path, transport="serial")
    first = tmp_path / "admission-1.json"
    second = tmp_path / "admission-2.json"

    for destination in (first, second):
        result = _run(
            "--bundle",
            str(bundle_path),
            "--expected-source-sha",
            EXACT_SHA,
            "--output",
            str(destination),
        )
        assert result.returncode == 0, result.stderr
        assert f"bundle_sha256={hitachi_bundle_digest(bundle)}" in result.stdout

    assert first.read_bytes() == second.read_bytes()
    report = json.loads(first.read_text(encoding="utf-8"))
    for protocol in ("EPIT-HIT", "EPIT-HIT2"):
        admission = report["admissions"][protocol]
        assert admission["observed_transport"] == "serial"
        assert admission["current_matrix_transport"] == "unknown"
        assert admission["matrix_change_required"] is True
        assert admission["compatibility_promotion_authorized"] is False


def test_cli_rejects_wrong_pinned_sha_and_tampered_bundle(tmp_path: Path) -> None:
    bundle_path, bundle = _write_bundle(tmp_path)

    wrong_sha = _run(
        "--bundle",
        str(bundle_path),
        "--expected-source-sha",
        "e" * 40,
    )
    assert wrong_sha.returncode == 2
    assert json.loads(wrong_sha.stdout) == {
        "error": "producer.source_sha does not match --expected-source-sha"
    }

    tampered = deepcopy(bundle)
    tampered["comparisons"]["epit_hit_to_epit_hit2"]["candidate_sha256"] = "0" * 64
    bundle_path.write_text(json.dumps(tampered), encoding="utf-8")
    bad_digest = _run(
        "--bundle",
        str(bundle_path),
        "--expected-source-sha",
        EXACT_SHA,
    )
    assert bad_digest.returncode == 2
    assert "digest mismatch" in json.loads(bad_digest.stdout)["error"]


def test_cli_missing_bundle_fails_closed_without_exposing_private_path(tmp_path: Path) -> None:
    missing = tmp_path / "private-site" / "hitachi-evidence.json"
    result = _run(
        "--bundle",
        str(missing),
        "--expected-source-sha",
        EXACT_SHA,
    )

    assert result.returncode == 2
    assert json.loads(result.stdout) == {"error": "evidence bundle could not be read"}
    assert str(tmp_path) not in result.stdout
    assert "private-site" not in result.stdout
