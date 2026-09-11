from __future__ import annotations

import json
from pathlib import Path

import pytest

from innaware_pms_emulator.matrix_fias_live_acceptance import build_matrix_fias_live_acceptance


FIXTURE = Path(__file__).parent / "fixtures" / "pbx" / "matrix_sarvam_fias_link_progression_sanitized.json"
SHA = "a" * 40


def _captures():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))["captures"]


def _build(**overrides):
    values = {
        "source_sha": SHA,
        "transport": "tcp",
        "pbx_direction": "rx",
        "evidence_class": "operator_confirmed",
        "evidence_origin": "synthetic_replay",
        "matrix_model": "SARVAM UCS",
        "matrix_version": "synthetic-test-version",
        "local_endpoint": "192.0.2.10:50000",
        "remote_endpoint": "192.0.2.20:5010",
        "tcp_initiator": "pbx",
        "operator_authorized": True,
        "synthetic_or_redacted": True,
        "no_guest_pii": True,
        "source_material_synthetic": True,
    }
    values.update(overrides)
    return build_matrix_fias_live_acceptance(_captures(), **values)


def test_synthetic_matrix_progression_is_useful_but_not_live_admission():
    report = _build()
    assert report["bounded_observation"]["exact_progression_observed"] is True
    assert report["bounded_observation"]["lr_record_types"] == ["GI", "GO", "RE"]
    assert report["manual_review_ready"] is False
    codes = {item["code"] for item in report["blockers"]}
    assert "packet-capture-evidence-required" in codes
    assert "real-endpoint-provenance-required" in codes
    assert "synthetic-source-material" in codes
    assert report["claim_policy"]["compatibility_promotion_authorized"] is False
    assert report["claim_policy"]["manual_review_ready_does_not_equal_supported"] is True


def test_exact_sha_is_required():
    with pytest.raises(ValueError, match="exact 40-character"):
        _build(source_sha="abc123")


def test_live_packet_review_can_be_ready_without_promoting_support():
    report = _build(
        evidence_class="packet_capture",
        evidence_origin="real_pbx_lab",
        source_material_synthetic=False,
    )
    assert report["manual_review_ready"] is True
    assert report["blockers"] == []
    assert report["claim_policy"]["matrix_status_changed"] is False
    assert report["claim_policy"]["production_support_claim_authorized"] is False
    assert report["architectural_boundary"]["ucp_runtime_dependency_allowed"] is False
    assert len(report["evidence"]["diagnostic_report_sha256"]) == 64
    assert len(report["artifact_sha256"]) == 64


def test_missing_progression_blocks_live_review():
    report = build_matrix_fias_live_acceptance(
        _captures()[:-1],
        source_sha=SHA,
        transport="tcp",
        pbx_direction="rx",
        evidence_class="packet_capture",
        evidence_origin="authorized_field_capture",
        matrix_model="SARVAM UCS",
        matrix_version="test",
        local_endpoint="192.0.2.10:50000",
        remote_endpoint="192.0.2.20:5010",
        tcp_initiator="pbx",
        operator_authorized=True,
        synthetic_or_redacted=True,
        no_guest_pii=True,
        source_material_synthetic=False,
    )
    assert report["manual_review_ready"] is False
    assert "bounded-link-progression-not-observed" in {item["code"] for item in report["blockers"]}


def test_transport_stays_fail_closed():
    with pytest.raises(ValueError, match="qualified only for TCP"):
        _build(transport="serial")
