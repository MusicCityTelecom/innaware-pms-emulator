from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

import pytest

from innaware_pms_emulator.candidate_admission_review import (
    build_candidate_admission_review,
)
from innaware_pms_emulator.candidate_observation_result import (
    CandidateObservationStatus,
    build_candidate_observation_result,
)
from innaware_pms_emulator.compatibility_matrix import Direction, EvidenceClass
from innaware_pms_emulator.technician_evidence_result import EvidenceOrigin


REPO_ROOT = Path(__file__).resolve().parents[1]
EXACT_SHA = "a" * 40
WIRE_SHA = "b" * 64
DIAGNOSTIC_SHA = "c" * 64


def _candidate(**overrides) -> dict:
    kwargs = {
        "source_sha": EXACT_SHA,
        "pbx_family": "3CX",
        "pbx_dialect": "Hotel Module / Mitel SX2000-compatible",
        "transport": "tcp",
        "pms_family": "legacy-hotel-pms",
        "pms_protocol": "mitel-hospitality",
        "direction": Direction.PBX_TO_PMS,
        "result_status": CandidateObservationStatus.OBSERVED,
        "evidence_class": EvidenceClass.PACKET_CAPTURE,
        "transport_facts": {
            "local_endpoint_role": "emulator-pms-client",
            "remote_endpoint_role": "3cx-hotel-services-server",
            "local_address_and_port": "192.0.2.10:49152",
            "remote_address_and_port": "192.0.2.20:5010",
        },
        "endpoint_provenance": {
            "evidence_origin": EvidenceOrigin.REAL_PBX_LAB.value,
            "pbx_model": "3CX Hotel Services",
            "pbx_firmware": "lab-build-1",
        },
        "observation_codes": [
            "transport_opened",
            "wire_bytes_observed",
            "application_record_observed",
        ],
        "wire_artifact_sha256s": [WIRE_SHA],
        "diagnostic_report_sha256s": [DIAGNOSTIC_SHA],
        "candidate_diagnostics_tests_passed": True,
        "exact_head_test_matrix_green": True,
        "exact_head_windows_build_green": True,
        "operator_authorized": True,
        "synthetic_or_redacted_wire_bytes": True,
        "guest_pii_present": False,
    }
    kwargs.update(overrides)
    return build_candidate_observation_result(**kwargs)


def test_packet_capture_candidate_can_be_review_ready_without_authorizing_promotion() -> None:
    review = build_candidate_admission_review(
        _candidate(), expected_source_sha=EXACT_SHA
    )

    assert review["schema_version"] == "1.0"
    assert review["producer"]["reviewed_source_sha"] == EXACT_SHA
    assert review["current_matrix_state"] == {
        "status": "unsupported",
        "registered_exact_or_covering_row": False,
    }
    assert review["review_gate"]["manual_review_ready"] is True
    assert review["review_gate"]["blocking_requirements"] == []
    assert review["candidate"]["evidence_class"] == "packet_capture"
    assert review["candidate"]["evidence_rank"] == 5
    assert review["candidate"]["evidence_origin"] == "real_pbx_lab"
    assert review["claim_policy"]["matrix_registration_authorized"] is False
    assert review["claim_policy"]["compatibility_promotion_authorized"] is False
    assert review["claim_policy"]["production_support_claim_authorized"] is False
    assert review["claim_policy"]["automated_matrix_mutation_allowed"] is False
    assert review["claim_policy"]["human_protocol_review_required"] is True
    assert review["claim_policy"]["review_ready_does_not_equal_supported"] is True
    assert review["architectural_boundary"]["exchange_mode"] == "data_only"
    assert review["architectural_boundary"]["ucp_runtime_dependency_allowed"] is False


def test_source_or_simulator_candidate_reports_specific_admission_blockers() -> None:
    candidate = _candidate(
        evidence_class=EvidenceClass.LEGACY_SOURCE_PROFILE,
        endpoint_provenance={
            "evidence_origin": EvidenceOrigin.SYNTHETIC_REPLAY.value,
        },
        diagnostic_report_sha256s=[],
    )
    review = build_candidate_admission_review(
        candidate, expected_source_sha=EXACT_SHA
    )

    assert review["review_gate"]["manual_review_ready"] is False
    assert [
        item["code"] for item in review["review_gate"]["blocking_requirements"]
    ] == [
        "packet_capture_missing",
        "real_endpoint_provenance_missing",
        "payload_safe_diagnostic_missing",
    ]
    assert review["candidate"]["evidence_rank"] == 3


def test_transport_only_observation_does_not_qualify_application_review() -> None:
    candidate = _candidate(
        observation_codes=["transport_opened", "wire_bytes_observed"],
    )
    review = build_candidate_admission_review(
        candidate, expected_source_sha=EXACT_SHA
    )
    assert review["review_gate"]["manual_review_ready"] is False
    assert any(
        item["code"] == "application_record_observation_missing"
        for item in review["review_gate"]["blocking_requirements"]
    )


def test_rejected_candidate_remains_diagnostic_evidence_not_admission_ready() -> None:
    candidate = _candidate(
        result_status=CandidateObservationStatus.REJECTED,
        observation_codes=["transport_opened", "wire_bytes_observed", "frame_rejected"],
    )
    review = build_candidate_admission_review(
        candidate, expected_source_sha=EXACT_SHA
    )
    codes = [item["code"] for item in review["review_gate"]["blocking_requirements"]]
    assert "affirmative_observation_missing" in codes
    assert "application_record_observation_missing" in codes
    assert review["claim_policy"]["matrix_registration_authorized"] is False


def test_review_refuses_stale_source_sha() -> None:
    with pytest.raises(ValueError, match="does not match the exact Emulator SHA"):
        build_candidate_admission_review(
            _candidate(), expected_source_sha="d" * 40
        )


def test_review_rechecks_current_matrix_instead_of_trusting_stale_candidate_state() -> None:
    candidate = deepcopy(_candidate())
    candidate["combination"]["direction"] = Direction.PMS_TO_PBX.value

    with pytest.raises(ValueError, match="now covered by a registered compatibility row"):
        build_candidate_admission_review(
            candidate, expected_source_sha=EXACT_SHA
        )


def test_review_rejects_candidate_that_relaxes_non_promoting_or_ucp_boundary() -> None:
    candidate = deepcopy(_candidate())
    candidate["claim_policy"]["compatibility_promotion_authorized"] = True
    with pytest.raises(ValueError, match="compatibility_promotion_authorized must remain false"):
        build_candidate_admission_review(
            candidate, expected_source_sha=EXACT_SHA
        )

    candidate = deepcopy(_candidate())
    candidate["consumer_exchange"]["ucp_runtime_dependency_allowed"] = True
    with pytest.raises(ValueError, match="must not allow a UCP runtime dependency"):
        build_candidate_admission_review(
            candidate, expected_source_sha=EXACT_SHA
        )


def test_cli_is_deterministic_payload_safe_and_exact_sha_pinned(tmp_path: Path) -> None:
    candidate_path = tmp_path / "candidate.json"
    first_path = tmp_path / "review-1.json"
    second_path = tmp_path / "review-2.json"
    candidate_path.write_text(
        json.dumps(_candidate(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    command = [
        sys.executable,
        str(REPO_ROOT / "scripts" / "review-candidate-admission.py"),
        str(candidate_path),
        "--expected-source-sha",
        EXACT_SHA,
    ]
    first = subprocess.run(
        command + ["--output", str(first_path)],
        cwd=tmp_path,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    second = subprocess.run(
        command + ["--output", str(second_path)],
        cwd=tmp_path,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    assert first_path.read_bytes() == second_path.read_bytes()

    report = json.loads(first_path.read_text(encoding="utf-8"))
    assert report["review_gate"]["manual_review_ready"] is True
    raw = first_path.read_text(encoding="utf-8")
    assert "192.0.2.10" not in raw
    assert "192.0.2.20" not in raw
    assert "lab-build-1" not in raw
    assert WIRE_SHA in raw
    assert DIAGNOSTIC_SHA in raw

    stale = subprocess.run(
        command[:-1] + ["d" * 40],
        cwd=tmp_path,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert stale.returncode == 2
    assert "does not match the exact Emulator SHA" in stale.stderr
