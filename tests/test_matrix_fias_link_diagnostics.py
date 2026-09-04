import json
from pathlib import Path

import pytest

from innaware_pms_emulator.matrix_fias_link_diagnostics import (
    analyze_matrix_fias_link_progression,
)


FIXTURE_PATH = (
    Path(__file__).parent
    / "fixtures"
    / "pbx"
    / "matrix_sarvam_fias_link_progression_sanitized.json"
)


def _captures():
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    assert payload["sanitized"] is True
    assert payload["synthetic"] is True
    return payload["captures"]


def test_matrix_fias_link_progression_is_bounded_and_payload_safe():
    report = analyze_matrix_fias_link_progression(
        _captures(),
        transport="tcp",
        pbx_direction="rx",
        evidence_class="operator_confirmed",
    )

    assert report["combination"] == {
        "pbx_family": "Matrix",
        "pbx_dialect": "MICROS Opera / FIAS",
        "transport": "tcp",
        "pms_family": "Oracle / MICROS Opera",
        "pms_protocol": "FIAS",
        "direction": "pbx_to_pms",
    }
    assert report["exact_progression_observed"] is True
    assert report["pbx_ls_count"] == 1
    assert report["pms_ls_reply_count"] == 1
    assert report["pbx_ld_count"] == 1
    assert report["pbx_lr_count"] == 3
    assert report["pbx_la_count"] == 1
    assert report["lr_record_types"] == ["GI", "GO", "RE"]

    finding_ids = {item["id"] for item in report["findings"]}
    assert "matrix-fias-link-progression-observed" in finding_ids

    assert report["qualified_scope"]["guest_event_semantics"] is False
    assert report["qualified_scope"]["site_port"] is False
    assert report["qualified_scope"]["enq_ack"] is False
    assert report["qualified_scope"]["retry_timing"] is False

    assert report["claim_policy"]["matrix_status_changed"] is False
    assert report["claim_policy"]["compatibility_promotion_authorized"] is False
    assert report["claim_policy"]["raw_payloads_embedded"] is False
    assert report["claim_policy"]["series2_station_programming_in_scope"] is False

    raw = json.dumps(report, sort_keys=True)
    assert "RN101" not in raw
    assert "guest_name" not in raw


def test_matrix_fias_link_diagnostics_fail_closed_on_transport():
    with pytest.raises(ValueError, match="qualified only for TCP"):
        analyze_matrix_fias_link_progression(
            _captures(),
            transport="serial",
            pbx_direction="rx",
            evidence_class="operator_confirmed",
        )


def test_matrix_fias_link_diagnostics_report_incomplete_negotiation():
    captures = _captures()[:-1]
    report = analyze_matrix_fias_link_progression(
        captures,
        transport="tcp",
        pbx_direction="rx",
        evidence_class="operator_confirmed",
    )

    assert report["exact_progression_observed"] is False
    finding_ids = {item["id"] for item in report["findings"]}
    assert "matrix-fias-link-negotiation-incomplete" in finding_ids
    assert "matrix-fias-link-progression-observed" not in finding_ids


def test_matrix_fias_link_diagnostics_detect_wrong_ls_reply_framing():
    captures = _captures()
    captures[1] = {
        "direction": "tx",
        "text": "LS|DA000101|TI000001|\r\n",
    }
    report = analyze_matrix_fias_link_progression(
        captures,
        transport="tcp",
        pbx_direction="rx",
        evidence_class="operator_confirmed",
    )

    assert report["exact_progression_observed"] is False
    finding_ids = {item["id"] for item in report["findings"]}
    assert "matrix-fias-ls-reply-framing-mismatch" in finding_ids


def test_matrix_fias_link_diagnostics_are_direction_explicit():
    reversed_captures = []
    for item in _captures():
        changed = dict(item)
        changed["direction"] = "tx" if item["direction"] == "rx" else "rx"
        reversed_captures.append(changed)

    report = analyze_matrix_fias_link_progression(
        reversed_captures,
        transport="tcp",
        pbx_direction="tx",
        evidence_class="operator_confirmed",
    )
    assert report["exact_progression_observed"] is True
    assert report["pbx_capture_direction"] == "tx"
    assert report["pms_capture_direction"] == "rx"
