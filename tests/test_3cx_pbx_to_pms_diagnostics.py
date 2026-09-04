from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from innaware_pms_emulator.compatibility_matrix import (
    Direction,
    EvidenceClass,
    SupportStatus,
    find_compatibility,
)
from innaware_pms_emulator.threecx_pbx_to_pms_diagnostics import (
    analyze_3cx_pbx_to_pms_observations,
)


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "diagnose-3cx-pbx-to-pms.py"
FIXTURE = ROOT / "tests" / "fixtures" / "pbx" / "3cx_mitel_sx2000_pbx_to_pms_source_candidate.json"
STS2 = b"\x02STS2 101\x03"
MSG_MINIMAL = b"\x02MSG\x03"
CHK1 = b"\x02CHK1   101\x03"
ACK = b"\x06"


def _capture(*items):
    return [{"direction": direction, "data": data} for direction, data in items]


def test_source_documented_maid_status_is_direction_qualified_and_payload_safe():
    report = analyze_3cx_pbx_to_pms_observations(
        _capture(("rx", STS2)),
        transport="tcp",
        evidence_class="legacy_source_profile",
        pbx_direction="rx",
    )

    assert report["schema_version"] == "1.1"
    assert report["matrix_claim"] == "candidate_only_not_registered"
    assert report["source_direction_qualified_record_count"] == 1
    assert report["exact_maid_status_record_count"] == 1
    record = report["exact_maid_status_records"][0]
    assert record["sha256"] == hashlib.sha256(STS2).hexdigest()
    assert record["record_code"] == "STS"
    assert record["framing"] == "stx_etx"
    assert record["maid_status_code"] == "STS2"
    assert record["maid_status_meaning"] == "clean"
    assert record["station_digit_count"] == 3

    contract = report["reference_contract"]
    assert contract["maid_status_station_digits_max"] == 5
    assert contract["source_bidirectional_link_control_pattern"] == "ENQ/ACK/STX-text-ETX/ACK"
    assert contract["source_bidirectional_link_control_pattern_qualified"] is True
    assert contract["pbx_to_pms_transaction_correlation_qualified"] is False
    assert contract["pbx_to_pms_timing_qualified"] is False
    assert contract["pbx_to_pms_retry_policy_qualified"] is False
    assert contract["pbx_to_pms_checksum_contract_qualified"] is False
    assert report["claim_policy"]["matrix_registration_authorized"] is False
    assert report["claim_policy"]["raw_payloads_embedded"] is False

    encoded = json.dumps(report)
    assert "STS2 101" not in encoded


def test_message_registration_direction_and_fee_width_are_source_backed_but_layout_stays_unqualified():
    report = analyze_3cx_pbx_to_pms_observations(
        _capture(("tx", MSG_MINIMAL)),
        transport="tcp",
        evidence_class="legacy_source_profile",
        pbx_direction="tx",
    )

    assert report["source_direction_qualified_record_count"] == 1
    assert report["message_registration_candidate_count"] == 1
    item = report["message_registration_candidates"][0]
    assert item["record_code"] == "MSG"
    assert item["field_layout_qualified"] is False
    assert item["fee_status_width_bytes"] == 4
    assert item["fee_status_width_source_qualified"] is True
    contract = report["reference_contract"]
    assert contract["message_registration_fee_status_width_bytes"] == 4
    assert contract["message_registration_fee_status_width_qualified"] is True
    assert contract["message_registration_field_layout_qualified"] is False
    finding = next(
        finding
        for finding in report["findings"]
        if finding["id"] == "3cx-pbx-to-pms-message-registration-layout-unqualified"
    )
    assert finding["fee_status_width_bytes"] == 4


def test_capture_endpoint_direction_is_never_inferred_from_opcode():
    wrong = analyze_3cx_pbx_to_pms_observations(
        _capture(("rx", STS2)),
        transport="tcp",
        evidence_class="operator_confirmed",
        pbx_direction="tx",
    )
    assert wrong["source_direction_qualified_record_count"] == 0

    right = analyze_3cx_pbx_to_pms_observations(
        _capture(("rx", STS2)),
        transport="tcp",
        evidence_class="operator_confirmed",
        pbx_direction="rx",
    )
    assert right["source_direction_qualified_record_count"] == 1


def test_other_legacy_record_and_peer_control_remain_evidence_candidates():
    report = analyze_3cx_pbx_to_pms_observations(
        _capture(("rx", CHK1), ("tx", ACK)),
        transport="tcp",
        evidence_class="packet_capture",
        pbx_direction="rx",
    )
    assert report["source_direction_qualified_record_count"] == 0
    assert report["other_pbx_application_candidate_count"] == 1
    assert len(report["pms_controls"]) == 1
    assert any(
        finding["id"] == "3cx-pbx-to-pms-control-bytes-not-transaction-correlated"
        for finding in report["findings"]
    )
    assert report["claim_policy"]["bidirectional_link_pattern_does_not_infer_direction_specific_timing_or_retries"] is True
    assert report["claim_policy"]["pbx_to_pms_transaction_state_machine_inferred"] is False


def test_tcp_only_and_explicit_pbx_direction_fail_closed():
    with pytest.raises(ValueError, match="transport must be one of: tcp"):
        analyze_3cx_pbx_to_pms_observations(
            [],
            transport="serial",
            evidence_class="legacy_source_profile",
            pbx_direction="rx",
        )
    with pytest.raises(ValueError, match="pbx_direction must be one of"):
        analyze_3cx_pbx_to_pms_observations(
            [],
            transport="tcp",
            evidence_class="legacy_source_profile",
            pbx_direction="auto",
        )


def test_reverse_matrix_row_remains_unregistered_until_live_exact_sha_evidence():
    entry = find_compatibility(
        pbx_family="3CX",
        pbx_dialect="Hotel Module / Mitel SX2000-compatible",
        transport="tcp",
        pms_family="legacy-hotel-pms",
        pms_protocol="mitel-hospitality",
        direction=Direction.PBX_TO_PMS,
    )
    assert entry.status is SupportStatus.UNSUPPORTED
    assert entry.evidence_class is EvidenceClass.NONE


def test_synthetic_candidate_fixture_is_explicitly_sanitized():
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert payload["candidate_only"] is True
    assert payload["sanitized"] is True
    assert payload["sanitization"] == {
        "synthetic": True,
        "guest_pii": False,
        "vendor_binary": False,
        "field_layout_scope": "maid_status_only",
    }
    report = analyze_3cx_pbx_to_pms_observations(
        payload["captures"],
        transport=payload["combination_candidate"]["transport"],
        evidence_class=payload["evidence_class"],
        pbx_direction="rx",
    )
    assert report["exact_maid_status_record_count"] == 1


def test_cli_is_deterministic_and_does_not_echo_application_payload(tmp_path):
    out1 = tmp_path / "result-1.json"
    out2 = tmp_path / "result-2.json"
    command = [
        sys.executable,
        str(SCRIPT),
        str(FIXTURE),
        "--transport",
        "tcp",
        "--pbx-direction",
        "rx",
        "--evidence-class",
        "legacy_source_profile",
    ]
    first = subprocess.run(
        command + ["--output", str(out1)],
        check=False,
        capture_output=True,
        text=True,
    )
    second = subprocess.run(
        command + ["--output", str(out2)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert first.returncode == 0, first.stdout + first.stderr
    assert second.returncode == 0, second.stdout + second.stderr
    assert out1.read_bytes() == out2.read_bytes()
    result = json.loads(out1.read_text(encoding="utf-8"))
    assert result["exact_maid_status_record_count"] == 1
    raw = out1.read_text(encoding="utf-8")
    assert "STS2 101" not in raw


def test_cli_read_failure_does_not_echo_private_source_path(tmp_path):
    missing = tmp_path / "hotel-secret" / "guest-capture.json"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            str(missing),
            "--transport",
            "tcp",
            "--pbx-direction",
            "rx",
            "--evidence-class",
            "legacy_source_profile",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert json.loads(result.stdout) == {"error": "capture could not be read as UTF-8 JSON"}
    assert str(tmp_path) not in result.stdout
    assert "hotel-secret" not in result.stdout
