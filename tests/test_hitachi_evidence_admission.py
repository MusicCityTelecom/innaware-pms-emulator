from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from innaware_pms_emulator.hitachi_evidence_admission import (
    admit_hitachi_profile_evidence,
    validate_hitachi_profile_evidence_bundle,
)
from innaware_pms_emulator.hitachi_profile_evidence import (
    build_hitachi_profile_evidence_bundle,
)


EXACT_SHA = "c" * 40

EPITOME = b"""[pbx-protocol]\nprotocol=Epitome\nfamily=HITACHI\nenq=5\nstx=2\netx=3\nack=6\nnak=21\nchecksum=0\nCHK=CHK{status}{room}\nNAM=NAM{name}{room}\n\n[pbx-masks]\nchkroom=4 3 MASK_NUMBER\nnamroom=4 3 MASK_NUMBER\nnamname=7 20 MASK_LITERAL\n"""

EPIT_HIT = b"""[pbx-protocol]\nprotocol=EPIT-HIT\nfamily=HITACHI\nenq=5\nstx=2\netx=3\nack=6\nnak=21\nchecksum=0\nCHK=CHK{status}{room}\nNAM=NAM{name}{room}\n\n[pbx-masks]\nchkroom=4 3 MASK_NUMBER\nnamroom=5 3 MASK_NUMBER\nnamname=8 20 MASK_LITERAL\n"""

EPIT_HIT2 = b"""[pbx-protocol]\nprotocol=EPIT-HIT2\nfamily=HITACHI\nenq=5\nstx=2\netx=3\nack=6\nnak=21\nchecksum=0\nCHK=CHK{status}{room}\nNAM=NAM{name}{room}\n\n[pbx-masks]\nchkroom=4 3 MASK_NUMBER\nnamroom=8 3 MASK_NUMBER\nnamname=11 20 MASK_LITERAL\nnameindex0=2\n"""


def _bundle(tmp_path: Path, *, transport: str | None = None) -> dict[str, object]:
    paths = (
        tmp_path / "psip-pbx-protocol.Epitome",
        tmp_path / "psip-pbx-protocol.EPIT-HIT",
        tmp_path / "psip-pbx-protocol.EPIT-HIT2",
    )
    payloads = [EPITOME, EPIT_HIT, EPIT_HIT2]
    for path, payload in zip(paths, payloads, strict=True):
        if transport is not None:
            payload = payload.replace(
                b"family=HITACHI\n",
                f"family=HITACHI\ntransport={transport}\n".encode(),
            )
        path.write_bytes(payload)
    return build_hitachi_profile_evidence_bundle(
        epitome_path=paths[0],
        epit_hit_path=paths[1],
        epit_hit2_path=paths[2],
        source_sha=EXACT_SHA,
    )


def test_admission_closes_only_profile_proven_gaps(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    admission = admit_hitachi_profile_evidence(bundle, pms_protocol="EPIT-HIT")

    assert admission.current_matrix_status == "planned"
    assert admission.current_matrix_transport == "unknown"
    assert admission.observed_transport == "unknown"
    assert set(admission.resolved_gap_codes) == {
        "profile_body",
        "framing_control",
        "record_layout",
    }
    assert {
        "transport",
        "checksum_contract",
        "reverse_direction",
    } <= set(admission.remaining_gap_codes)
    assert admission.compatibility_promotion_authorized is False
    assert admission.matrix_change_required is False


def test_epit_hit2_admits_only_sanitized_room_name_delta(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    admission = admit_hitachi_profile_evidence(bundle, pms_protocol="EPIT-HIT2")

    assert "profile_delta" in admission.resolved_gap_codes
    assert "record_layout" in admission.resolved_gap_codes
    assert "transport" in admission.remaining_gap_codes
    assert "checksum_contract" in admission.remaining_gap_codes
    assert "reverse_direction" in admission.remaining_gap_codes


def test_explicit_profile_transport_is_evidence_not_matrix_promotion(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path, transport="serial")
    admission = admit_hitachi_profile_evidence(bundle, pms_protocol="EPIT-HIT")

    assert admission.observed_transport == "serial"
    assert "transport" in admission.resolved_gap_codes
    assert admission.current_matrix_transport == "unknown"
    assert admission.matrix_change_required is True
    assert admission.compatibility_promotion_authorized is False
    assert "checksum_contract" in admission.remaining_gap_codes


def test_checksum_scalar_does_not_claim_checksum_contract(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    assert bundle["profiles"]["epit_hit"]["profile_identity"]["checksum"] == "0"

    admission = admit_hitachi_profile_evidence(bundle, pms_protocol="EPIT-HIT")
    assert "checksum_contract" not in admission.resolved_gap_codes
    assert "checksum_contract" in admission.remaining_gap_codes


def test_tampered_profile_or_comparison_digest_is_rejected(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)

    tampered_profile = deepcopy(bundle)
    tampered_profile["profiles"]["epit_hit"]["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="digest mismatch"):
        validate_hitachi_profile_evidence_bundle(tampered_profile)

    tampered_comparison = deepcopy(bundle)
    tampered_comparison["comparisons"]["epit_hit_to_epit_hit2"][
        "candidate_sha256"
    ] = "f" * 64
    with pytest.raises(ValueError, match="digest mismatch"):
        validate_hitachi_profile_evidence_bundle(tampered_comparison)


def test_incomplete_or_wrongly_scoped_bundle_fails_closed(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)

    bad_policy = deepcopy(bundle)
    bad_policy["claim_policy"]["reverse_direction_requires_separate_evidence"] = False
    with pytest.raises(ValueError, match="claim policy"):
        validate_hitachi_profile_evidence_bundle(bad_policy)

    with pytest.raises(ValueError, match="EPIT-HIT or EPIT-HIT2"):
        admit_hitachi_profile_evidence(bundle, pms_protocol="FIAS")


def test_non_room_name_delta_does_not_close_epit_hit2_profile_delta(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    changed = deepcopy(bundle)
    delta = changed["comparisons"]["epit_hit_to_epit_hit2"]
    delta["record_layout_changes"]["CHK"] = {
        "baseline": "CHK{status}{room}",
        "candidate": "CHKX{status}{room}",
    }

    admission = admit_hitachi_profile_evidence(changed, pms_protocol="EPIT-HIT2")
    assert "profile_delta" not in admission.resolved_gap_codes
    assert "profile_delta" in admission.remaining_gap_codes
