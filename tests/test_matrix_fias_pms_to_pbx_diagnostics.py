import json
from pathlib import Path

import pytest

from innaware_pms_emulator.matrix_fias_pms_to_pbx_diagnostics import (
    analyze_matrix_fias_pms_to_pbx_candidate,
)


FIXTURE_PATH = (
    Path(__file__).parent
    / "fixtures"
    / "pbx"
    / "matrix_sarvam_fias_pms_to_pbx_gi_sanitized.json"
)


def _captures():
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    assert payload["sanitized"] is True
    assert payload["synthetic"] is True
    return payload["captures"]


def test_matrix_fias_pms_to_pbx_gi_candidate_is_payload_safe_and_non_promoting():
    report = analyze_matrix_fias_pms_to_pbx_candidate(
        _captures(),
        transport="tcp",
        pms_direction="tx",
        evidence_class="operator_confirmed",
    )

    assert report["combination"] == {
        "pbx_family": "Matrix",
        "pbx_dialect": "MICROS Opera / FIAS",
        "transport": "tcp",
        "pms_family": "Oracle / MICROS Opera",
        "pms_protocol": "FIAS",
        "direction": "pms_to_pbx",
    }
    assert report["matrix_claim"] == "candidate_only_not_registered"
    assert report["gi_event_count"] == 1
    assert report["exact_gi_ack_count"] == 1
    assert report["gi_nak_count"] == 0
    assert report["gi_events"][0]["response"] == "ACK"
    assert report["gi_events"][0]["source_shape_match"] is True
    assert report["observed_historical_field_identifier_shape"] == [
        "RN",
        "G#",
        "GN",
        "GL",
        "GV",
        "CS",
        "GA",
        "GD",
        "GS",
    ]

    finding_ids = {item["id"] for item in report["findings"]}
    assert "matrix-fias-gi-ack-observed" in finding_ids

    contract = report["source_contract"]
    assert contract["historical_runtime_evidence_current_sha_qualified"] is False
    assert contract["current_exact_sha_live_validation_required"] is True
    assert contract["field_values_qualified"] is False
    assert contract["site_port_qualified"] is False
    assert contract["ack_timing_qualified"] is False
    assert contract["checksum_lrc_qualified"] is False
    assert contract["other_application_records_qualified"] is False

    policy = report["claim_policy"]
    assert policy["matrix_registration_authorized"] is False
    assert policy["supported_promotion_authorized"] is False
    assert policy["production_support_claim_authorized"] is False
    assert policy["other_fias_events_inferred"] is False
    assert policy["serial_behavior_inferred"] is False
    assert policy["raw_payloads_embedded"] is False
    assert policy["guest_pii_embedded"] is False
    assert policy["series2_station_programming_in_scope"] is False

    boundary = report["architectural_boundary"]
    assert boundary["exchange_mode"] == "data_only"
    assert boundary["runtime_dependency_on_ucp"] is False
    assert boundary["ucp_runtime_dependency_allowed"] is False

    raw = json.dumps(report, sort_keys=True)
    for secret in ("RN900", "REDACTED", "0001", "GA000101"):
        assert secret not in raw


def test_matrix_fias_pms_to_pbx_candidate_fails_closed_on_transport():
    with pytest.raises(ValueError, match="qualified only for TCP"):
        analyze_matrix_fias_pms_to_pbx_candidate(
            _captures(),
            transport="serial",
            pms_direction="tx",
            evidence_class="operator_confirmed",
        )


def test_matrix_fias_pms_to_pbx_candidate_is_direction_explicit():
    reversed_captures = []
    for item in _captures():
        changed = dict(item)
        changed["direction"] = "rx" if item["direction"] == "tx" else "tx"
        reversed_captures.append(changed)

    report = analyze_matrix_fias_pms_to_pbx_candidate(
        reversed_captures,
        transport="tcp",
        pms_direction="rx",
        evidence_class="operator_confirmed",
    )
    assert report["exact_gi_ack_count"] == 1
    assert report["pms_capture_direction"] == "rx"
    assert report["pbx_capture_direction"] == "tx"


def test_matrix_fias_pms_to_pbx_candidate_reports_nak_without_guessing_cause():
    captures = _captures()
    captures[1] = {"direction": "rx", "hex": "15"}
    report = analyze_matrix_fias_pms_to_pbx_candidate(
        captures,
        transport="tcp",
        pms_direction="tx",
        evidence_class="operator_confirmed",
    )

    assert report["exact_gi_ack_count"] == 0
    assert report["gi_nak_count"] == 1
    finding_ids = {item["id"] for item in report["findings"]}
    assert "matrix-fias-gi-nak-observed" in finding_ids
    assert report["claim_policy"]["checksum_lrc_inferred"] is False


def test_matrix_fias_pms_to_pbx_candidate_does_not_pair_ack_across_application_boundary():
    captures = _captures()
    captures.insert(
        1,
        {
            "direction": "tx",
            "hex": "02 47 4f 7c 52 4e 39 30 30 7c 03",
        },
    )
    report = analyze_matrix_fias_pms_to_pbx_candidate(
        captures,
        transport="tcp",
        pms_direction="tx",
        evidence_class="operator_confirmed",
    )

    assert report["exact_gi_ack_count"] == 0
    assert report["gi_missing_response_count"] == 1
    assert report["gi_events"][0]["response"] is None
    finding_ids = {item["id"] for item in report["findings"]}
    assert "matrix-fias-gi-response-missing" in finding_ids


def test_matrix_fias_pms_to_pbx_candidate_reports_wrong_framing():
    captures = _captures()
    captures[0] = {
        "direction": "tx",
        "text": "GI|RN900|G#0001|GNREDACTED|\r\n",
    }
    report = analyze_matrix_fias_pms_to_pbx_candidate(
        captures,
        transport="tcp",
        pms_direction="tx",
        evidence_class="operator_confirmed",
    )

    assert report["exact_gi_ack_count"] == 0
    assert report["gi_wrong_framing_count"] == 1
    finding_ids = {item["id"] for item in report["findings"]}
    assert "matrix-fias-gi-framing-mismatch" in finding_ids
