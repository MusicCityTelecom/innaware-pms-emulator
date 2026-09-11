from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

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


def _tcp_facts() -> dict[str, str]:
    return {
        "local_endpoint_role": "emulator-pms-client",
        "remote_endpoint_role": "3cx-hotel-services-server",
        "local_address_and_port": "192.0.2.10:49152",
        "remote_address_and_port": "192.0.2.20:5010",
    }


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
        "transport_facts": _tcp_facts(),
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


def test_unregistered_3cx_reverse_candidate_is_deterministic_digest_only_and_non_promoting() -> None:
    first = _candidate(
        observation_codes=[
            "wire_bytes_observed",
            "transport_opened",
            "application_record_observed",
        ],
        wire_artifact_sha256s=[WIRE_SHA, WIRE_SHA.upper()],
    )
    second = _candidate()

    assert first == second
    assert first["schema_version"] == "1.0"
    assert first["producer"]["source_sha"] == EXACT_SHA
    assert first["combination"] == {
        "pbx_family": "3CX",
        "pbx_dialect": "Hotel Module / Mitel SX2000-compatible",
        "transport": "tcp",
        "pms_family": "legacy-hotel-pms",
        "pms_protocol": "mitel-hospitality",
        "direction": Direction.PBX_TO_PMS.value,
    }
    assert first["matrix_state"]["status"] == "unsupported"
    assert first["matrix_state"]["registered_exact_or_covering_row"] is False
    assert first["matrix_state"]["nearby_registered_claims"] == [
        {
            "direction": Direction.PMS_TO_PBX.value,
            "status": "partial",
            "evidence_class": "legacy_source_profile",
        }
    ]
    assert first["result"]["status"] == "observed"
    assert first["result"]["wire_artifact_sha256s"] == [WIRE_SHA]
    assert first["result"]["diagnostic_report_sha256s"] == [DIAGNOSTIC_SHA]
    assert first["architectural_boundary"]["exchange_mode"] == "data_only"
    assert first["architectural_boundary"]["runtime_dependency_on_emulator"] is False
    assert first["claim_policy"]["matrix_registration_authorized"] is False
    assert first["claim_policy"]["compatibility_promotion_authorized"] is False
    assert first["claim_policy"]["production_support_claim_authorized"] is False
    assert first["claim_policy"]["manual_evidence_review_required"] is True
    assert first["claim_policy"]["candidate_must_not_enter_normal_interop_fixture_pack"] is True
    assert first["claim_policy"]["raw_capture_or_vendor_profile_embedded"] is False
    assert first["claim_policy"]["series2_tdmoe_pri_station_programming_in_scope"] is False
    assert first["consumer_exchange"]["ucp_runtime_dependency_allowed"] is False
    assert first["consumer_exchange"]["candidate_is_not_a_compatibility_claim"] is True


def test_registered_3cx_forward_row_must_use_registered_acceptance_workflow() -> None:
    with pytest.raises(ValueError, match="registered compatibility row already covers"):
        _candidate(direction=Direction.PMS_TO_PBX)


def test_bidirectional_registered_row_also_blocks_directional_candidate_duplicate() -> None:
    with pytest.raises(ValueError, match="registered compatibility row already covers"):
        _candidate(
            pbx_family="Mitel",
            pbx_dialect="MITEL 1 / iPocket-characterized",
            pms_protocol="mitel-hospitality",
            direction=Direction.PBX_TO_PMS,
        )


def test_unknown_transport_is_rejected_instead_of_inferred() -> None:
    with pytest.raises(ValueError, match="explicit evidence-qualified tcp or serial transport"):
        _candidate(
            transport="unknown",
            transport_facts={"transport_evidence_source": "capture"},
        )


def test_tcp_candidate_requires_exact_endpoint_role_and_address_facts() -> None:
    facts = _tcp_facts()
    facts.pop("remote_address_and_port")
    with pytest.raises(ValueError, match="transport facts must match"):
        _candidate(transport_facts=facts)

    facts = _tcp_facts()
    facts["serial_device_or_adapter"] = "not-applicable"
    with pytest.raises(ValueError, match="transport facts must match"):
        _candidate(transport_facts=facts)


def test_serial_candidate_has_separate_fact_contract() -> None:
    result = _candidate(
        pbx_family="Hitachi",
        pbx_dialect="EPIT-HIT / Epitome Hitachi emulation",
        transport="serial",
        pms_family="Epitome",
        pms_protocol="EPIT-HIT",
        direction=Direction.PMS_TO_PBX,
        transport_facts={
            "serial_device_or_adapter": "authorized-lab-adapter",
            "baud_rate": "9600",
            "data_bits": "8",
            "parity": "none",
            "stop_bits": "1",
            "flow_control": "none",
        },
        endpoint_provenance={
            "evidence_origin": EvidenceOrigin.REAL_PBX_AND_PMS_LAB.value,
            "pbx_model": "Hitachi-compatible lab endpoint",
            "pbx_firmware": "lab-1",
            "pms_product": "Epitome lab endpoint",
            "pms_version": "lab-1",
        },
    )
    assert result["combination"]["transport"] == "serial"
    assert set(result["result"]["transport_facts"]) == {
        "serial_device_or_adapter",
        "baud_rate",
        "data_bits",
        "parity",
        "stop_bits",
        "flow_control",
    }
    assert result["matrix_state"]["status"] == "unsupported"


def test_real_endpoint_provenance_is_required_and_simulator_cannot_claim_hardware() -> None:
    with pytest.raises(ValueError, match="explicit endpoint provenance"):
        _candidate(endpoint_provenance=None)
    with pytest.raises(ValueError, match="pbx_firmware"):
        _candidate(
            endpoint_provenance={
                "evidence_origin": EvidenceOrigin.REAL_PBX_LAB.value,
                "pbx_model": "3CX Hotel Services",
            }
        )
    with pytest.raises(ValueError, match="must not claim real endpoint provenance"):
        _candidate(
            endpoint_provenance={
                "evidence_origin": EvidenceOrigin.SYNTHETIC_REPLAY.value,
                "pbx_model": "not-real",
            }
        )


def test_candidate_requires_green_exact_head_safe_wire_evidence_and_no_pii() -> None:
    with pytest.raises(ValueError, match="deterministic diagnostics tests"):
        _candidate(candidate_diagnostics_tests_passed=False)
    with pytest.raises(ValueError, match="green exact-head"):
        _candidate(exact_head_windows_build_green=False)
    with pytest.raises(ValueError, match="operator_authorized"):
        _candidate(operator_authorized=False)
    with pytest.raises(ValueError, match="synthetic_or_redacted"):
        _candidate(synthetic_or_redacted_wire_bytes=False)
    with pytest.raises(ValueError, match="guest PII"):
        _candidate(guest_pii_present=True)


def test_candidate_statuses_require_matching_observation_shape() -> None:
    with pytest.raises(ValueError, match="affirmative wire observation"):
        _candidate(observation_codes=["transport_opened"])
    with pytest.raises(ValueError, match="rejection/failure observation"):
        _candidate(
            result_status=CandidateObservationStatus.REJECTED,
            observation_codes=["wire_bytes_observed"],
        )

    rejected = _candidate(
        result_status=CandidateObservationStatus.REJECTED,
        observation_codes=["transport_opened", "frame_rejected"],
    )
    assert rejected["result"]["status"] == "rejected"
    assert any("not why" in item for item in rejected["technician_diagnostics"])


def test_candidate_rejects_weak_evidence_abbreviated_sha_and_invalid_digests() -> None:
    with pytest.raises(ValueError, match="40-character"):
        _candidate(source_sha="abc123")
    with pytest.raises(ValueError, match="stronger than inference"):
        _candidate(evidence_class=EvidenceClass.INFERENCE)
    with pytest.raises(ValueError, match="64-character"):
        _candidate(wire_artifact_sha256s=["bad"])


def test_cli_records_same_payload_without_raw_wire_input(tmp_path: Path) -> None:
    output = tmp_path / "candidate.json"
    command = [
        sys.executable,
        str(REPO_ROOT / "scripts" / "record-candidate-observation.py"),
        "--source-sha",
        EXACT_SHA,
        "--pbx-family",
        "3CX",
        "--pbx-dialect",
        "Hotel Module / Mitel SX2000-compatible",
        "--transport",
        "tcp",
        "--pms-family",
        "legacy-hotel-pms",
        "--pms-protocol",
        "mitel-hospitality",
        "--direction",
        "pbx_to_pms",
        "--result",
        "observed",
        "--evidence-class",
        "packet_capture",
        "--transport-fact",
        "local_endpoint_role=emulator-pms-client",
        "--transport-fact",
        "remote_endpoint_role=3cx-hotel-services-server",
        "--transport-fact",
        "local_address_and_port=192.0.2.10:49152",
        "--transport-fact",
        "remote_address_and_port=192.0.2.20:5010",
        "--evidence-origin",
        "real_pbx_lab",
        "--pbx-model",
        "3CX Hotel Services",
        "--pbx-firmware",
        "lab-build-1",
        "--observation",
        "application_record_observed",
        "--observation",
        "wire_bytes_observed",
        "--observation",
        "transport_opened",
        "--wire-artifact-sha256",
        WIRE_SHA,
        "--diagnostic-report-sha256",
        DIAGNOSTIC_SHA,
        "--candidate-diagnostics-tests-passed",
        "--exact-head-test-matrix-green",
        "--exact-head-windows-build-green",
        "--operator-authorized",
        "--synthetic-or-redacted-wire-bytes",
        "--no-guest-pii",
        "--output",
        str(output),
    ]
    completed = subprocess.run(
        command,
        cwd=tmp_path,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert json.loads(output.read_text(encoding="utf-8")) == _candidate()


def test_cli_fails_closed_for_registered_row(tmp_path: Path) -> None:
    command = [
        sys.executable,
        str(REPO_ROOT / "scripts" / "record-candidate-observation.py"),
        "--source-sha",
        EXACT_SHA,
        "--pbx-family",
        "3CX",
        "--pbx-dialect",
        "Hotel Module / Mitel SX2000-compatible",
        "--transport",
        "tcp",
        "--pms-family",
        "legacy-hotel-pms",
        "--pms-protocol",
        "mitel-hospitality",
        "--direction",
        "pms_to_pbx",
        "--result",
        "observed",
        "--evidence-class",
        "packet_capture",
        "--transport-fact",
        "local_endpoint_role=emulator-pms-client",
        "--transport-fact",
        "remote_endpoint_role=3cx-hotel-services-server",
        "--transport-fact",
        "local_address_and_port=192.0.2.10:49152",
        "--transport-fact",
        "remote_address_and_port=192.0.2.20:5010",
        "--evidence-origin",
        "synthetic_replay",
        "--observation",
        "wire_bytes_observed",
        "--wire-artifact-sha256",
        WIRE_SHA,
        "--candidate-diagnostics-tests-passed",
        "--exact-head-test-matrix-green",
        "--exact-head-windows-build-green",
        "--operator-authorized",
        "--synthetic-or-redacted-wire-bytes",
        "--no-guest-pii",
    ]
    completed = subprocess.run(
        command,
        cwd=tmp_path,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert completed.returncode == 2
    assert "registered compatibility row already covers" in completed.stderr
