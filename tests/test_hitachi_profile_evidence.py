from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from innaware_pms_emulator.hitachi_profile_evidence import (
    build_hitachi_profile_evidence_bundle,
    hitachi_bundle_digest,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
EXACT_SHA = "b" * 40


EPITOME = b"""[pbx-protocol]\nprotocol=Epitome\nfamily=HITACHI\nenq=5\nstx=2\netx=3\nack=6\nnak=21\nchecksum=0\nCHK=CHK{status}{room}\nNAM=NAM{name}{room}\nsite_secret=do-not-export-epitome\n\n[pbx-masks]\nchkroom=4 3 MASK_NUMBER\nnamroom=4 3 MASK_NUMBER\nnamname=7 20 MASK_LITERAL\nprivate_site_key=do-not-export-mask\n"""

EPIT_HIT = b"""[pbx-protocol]\nprotocol=EPIT-HIT\nfamily=HITACHI\nenq=5\nstx=2\netx=3\nack=6\nnak=21\nchecksum=0\nCHK=CHK{status}{room}\nNAM=NAM{name}{room}\nsite_secret=do-not-export-hit\n\n[pbx-masks]\nchkroom=4 3 MASK_NUMBER\nnamroom=5 3 MASK_NUMBER\nnamname=8 20 MASK_LITERAL\n"""

EPIT_HIT2 = b"""[pbx-protocol]\nprotocol=EPIT-HIT2\nfamily=HITACHI\nenq=5\nstx=2\netx=3\nack=6\nnak=21\nchecksum=0\nCHK=CHK{status}{room}\nNAM=NAM{name}{room}\nsite_secret=do-not-export-hit2\n\n[pbx-masks]\nchkroom=4 3 MASK_NUMBER\nnamroom=8 3 MASK_NUMBER\nnamname=11 20 MASK_LITERAL\nnameindex0=2\n"""


def _write_profiles(tmp_path: Path) -> tuple[Path, Path, Path]:
    paths = (
        tmp_path / "psip-pbx-protocol.Epitome",
        tmp_path / "psip-pbx-protocol.EPIT-HIT",
        tmp_path / "psip-pbx-protocol.EPIT-HIT2",
    )
    for path, data in zip(paths, (EPITOME, EPIT_HIT, EPIT_HIT2), strict=True):
        path.write_bytes(data)
    return paths


def test_hitachi_bundle_is_deterministic_sha_pinned_and_sanitized(tmp_path: Path) -> None:
    epitome, epit_hit, epit_hit2 = _write_profiles(tmp_path)

    first = build_hitachi_profile_evidence_bundle(
        epitome_path=epitome,
        epit_hit_path=epit_hit,
        epit_hit2_path=epit_hit2,
        source_sha=EXACT_SHA,
    )
    second = build_hitachi_profile_evidence_bundle(
        epitome_path=epitome,
        epit_hit_path=epit_hit,
        epit_hit2_path=epit_hit2,
        source_sha=EXACT_SHA,
    )

    assert first == second
    assert hitachi_bundle_digest(first) == hitachi_bundle_digest(second)
    assert len(hitachi_bundle_digest(first)) == 64
    assert first["sanitized"] is True
    assert first["raw_profiles_embedded"] is False
    assert first["producer"]["source_sha"] == EXACT_SHA
    assert first["profile_order"] == ["epitome", "epit_hit", "epit_hit2"]

    serialized = json.dumps(first, sort_keys=True)
    assert "do-not-export-epitome" not in serialized
    assert "do-not-export-hit" not in serialized
    assert "do-not-export-hit2" not in serialized
    assert "do-not-export-mask" not in serialized


def test_hitachi_bundle_preserves_hashes_and_fails_closed_on_transport(tmp_path: Path) -> None:
    epitome, epit_hit, epit_hit2 = _write_profiles(tmp_path)
    bundle = build_hitachi_profile_evidence_bundle(
        epitome_path=epitome,
        epit_hit_path=epit_hit,
        epit_hit2_path=epit_hit2,
        source_sha=EXACT_SHA,
    )

    assert bundle["profiles"]["epitome"]["sha256"] == hashlib.sha256(EPITOME).hexdigest()
    assert bundle["profiles"]["epit_hit"]["sha256"] == hashlib.sha256(EPIT_HIT).hexdigest()
    assert bundle["profiles"]["epit_hit2"]["sha256"] == hashlib.sha256(EPIT_HIT2).hexdigest()

    for profile in bundle["profiles"].values():
        assert profile["transport"] == "unknown"
        assert profile["transport_source"] == "none"
        assert profile["raw_profile_embedded"] is False

    policy = bundle["claim_policy"]
    assert policy["transport_requires_explicit_profile_or_wire_evidence"] is True
    assert policy["layout_delta_does_not_qualify_transport"] is True
    assert policy["compatibility_status_is_not_promoted_by_bundle_generation"] is True


def test_hitachi_bundle_isolates_epit_hit2_room_name_layout_delta(tmp_path: Path) -> None:
    epitome, epit_hit, epit_hit2 = _write_profiles(tmp_path)
    bundle = build_hitachi_profile_evidence_bundle(
        epitome_path=epitome,
        epit_hit_path=epit_hit,
        epit_hit2_path=epit_hit2,
        source_sha=EXACT_SHA,
    )

    delta = bundle["comparisons"]["epit_hit_to_epit_hit2"]
    assert delta["transport_change"] is None
    assert delta["control_byte_changes"] == {}
    assert delta["record_keys_added"] == []
    assert delta["record_keys_removed"] == []
    assert delta["record_mask_layout_changes"]["NAMROOM"] == {
        "baseline": "5 3 MASK_NUMBER",
        "candidate": "8 3 MASK_NUMBER",
    }
    assert delta["record_mask_layout_changes"]["NAMNAME"] == {
        "baseline": "8 20 MASK_LITERAL",
        "candidate": "11 20 MASK_LITERAL",
    }
    assert delta["record_mask_layout_changes"]["NAMEINDEX0"] == {
        "baseline": None,
        "candidate": "2",
    }


def test_hitachi_bundle_rejects_relabelled_profiles_and_unpinned_sha(tmp_path: Path) -> None:
    epitome, epit_hit, epit_hit2 = _write_profiles(tmp_path)

    with pytest.raises(ValueError, match="refusing to relabel evidence"):
        build_hitachi_profile_evidence_bundle(
            epitome_path=epit_hit,
            epit_hit_path=epitome,
            epit_hit2_path=epit_hit2,
            source_sha=EXACT_SHA,
        )

    with pytest.raises(ValueError, match="exact 40-character"):
        build_hitachi_profile_evidence_bundle(
            epitome_path=epitome,
            epit_hit_path=epit_hit,
            epit_hit2_path=epit_hit2,
            source_sha="abc1234",
        )


def test_hitachi_bundle_cli_matches_library_output(tmp_path: Path) -> None:
    epitome, epit_hit, epit_hit2 = _write_profiles(tmp_path)
    output = tmp_path / "hitachi-evidence.json"
    script = REPO_ROOT / "scripts" / "build-hitachi-profile-evidence.py"

    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--source-sha",
            EXACT_SHA,
            "--epitome",
            str(epitome),
            "--epit-hit",
            str(epit_hit),
            "--epit-hit2",
            str(epit_hit2),
            "--output",
            str(output),
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "bundle_sha256=" in result.stdout

    cli_bundle = json.loads(output.read_text(encoding="utf-8"))
    direct_bundle = build_hitachi_profile_evidence_bundle(
        epitome_path=epitome,
        epit_hit_path=epit_hit,
        epit_hit2_path=epit_hit2,
        source_sha=EXACT_SHA,
    )
    assert cli_bundle == direct_bundle
