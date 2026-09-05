import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from innaware_pms_emulator.phonesuite_pms_to_pbx_diagnostics import (
    analyze_phonesuite_pms_to_pbx_transactions,
)


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "diagnose-phonesuite-pms-to-pbx.py"
ENQ = b"\x05"
ACK = b"\x06"
NAK = b"\x15"


def _frame(text: str) -> bytes:
    return b"\x02" + text.encode("latin-1") + b"\x03"


def _capture(
    direction: str,
    data: bytes,
    timestamp: str | None = None,
) -> dict:
    item = {"direction": direction, "data": data}
    if timestamp is not None:
        item["timestamp"] = timestamp
    return item


def test_source_backed_chk_transaction_is_direction_and_timing_bounded():
    guest_frame = _frame("CHK1 901 SYNTHETIC-GUEST")
    report = analyze_phonesuite_pms_to_pbx_transactions(
        [
            _capture("tx", ENQ, "2026-09-04T10:00:00.000Z"),
            _capture("rx", ACK, "2026-09-04T10:00:00.010Z"),
            _capture("tx", guest_frame, "2026-09-04T10:00:00.050Z"),
            _capture("rx", ACK, "2026-09-04T10:00:00.060Z"),
        ],
        transport="serial",
        evidence_class="legacy_source_profile",
        pms_capture_direction="tx",
    )

    assert report["diagnostic_profile"] == "phonesuite_mitel1_serial_pms_to_pbx"
    assert report["reference_contract"]["direction"] == "PMS_TO_PBX"
    assert report["strict_transaction_count"] == 1
    assert report["peer_ack_count"] == 1
    assert report["peer_nak_count"] == 0
    assert report["qualified_success_count"] == 1
    assert report["timing_assessed_count"] == 1
    assert report["timing_violation_count"] == 0

    txn = report["strict_transactions"][0]
    assert txn["record"]["application_opcode"] == "CHK1"
    assert txn["record"]["wire_sha256"] == hashlib.sha256(guest_frame).hexdigest()
    assert txn["record"]["framing"] == "stx_etx"
    assert txn["ack_to_stx_observation_seconds"] == 0.04
    assert txn["within_ack_to_stx_deadline"] is True
    assert txn["qualified_success"] is True

    encoded = json.dumps(report)
    assert "SYNTHETIC-GUEST" not in encoded
    assert "CHK1 901" not in encoded
    assert report["claim_policy"]["raw_payloads_embedded"] is False
    assert report["claim_policy"]["guest_pii_allowed_in_report"] is False


def test_direct_manual_msg_is_qualified_only_after_direction_is_explicit():
    message_frame = _frame("MSG2 901")
    report = analyze_phonesuite_pms_to_pbx_transactions(
        [
            _capture("tx", ENQ),
            _capture("rx", ACK),
            _capture("tx", message_frame),
            _capture("rx", ACK),
        ],
        transport="serial",
        evidence_class="legacy_source_profile",
        pms_capture_direction="tx",
    )

    assert report["strict_transaction_count"] == 1
    txn = report["strict_transactions"][0]
    assert txn["record"]["application_family"] == "MSG"
    assert txn["record"]["application_opcode"] == "MSG2"
    assert txn["record"]["application_source_layer"] == "direct_manual_extension"
    assert txn["format_valid"] is True
    assert txn["qualified_success"] is True
    assert report["claim_policy"]["reverse_direction_inferred"] is False
    assert "MSG2 901" not in json.dumps(report)


def test_ack_to_stx_capture_timestamp_over_point_one_second_is_flagged():
    report = analyze_phonesuite_pms_to_pbx_transactions(
        [
            _capture("tx", ENQ, "2026-09-04T10:00:00.000Z"),
            _capture("rx", ACK, "2026-09-04T10:00:00.010Z"),
            _capture("tx", _frame("CHK0 901"), "2026-09-04T10:00:00.150Z"),
            _capture("rx", ACK, "2026-09-04T10:00:00.160Z"),
        ],
        transport="serial",
        evidence_class="legacy_source_profile",
        pms_capture_direction="tx",
    )

    assert report["strict_transaction_count"] == 1
    assert report["qualified_success_count"] == 0
    assert report["timing_assessed_count"] == 1
    assert report["timing_violation_count"] == 1
    txn = report["strict_transactions"][0]
    assert txn["ack_to_stx_observation_seconds"] == 0.14
    assert txn["within_ack_to_stx_deadline"] is False
    assert {
        item["code"] for item in txn["timing_diagnostics"]
    } == {"phonesuite_pms_stx_deadline_exceeded"}
    assert "phonesuite-pms-stx-deadline-exceeded" in {
        item["id"] for item in report["findings"]
    }
    assert report["between_character_timing_assessed"] is False


def test_peer_nak_is_rejection_evidence_not_checksum_inference():
    report = analyze_phonesuite_pms_to_pbx_transactions(
        [
            _capture("tx", ENQ),
            _capture("rx", ACK),
            _capture("tx", _frame("CHK0 901")),
            _capture("rx", NAK),
        ],
        transport="serial",
        evidence_class="packet_capture",
        pms_capture_direction="tx",
    )

    assert report["strict_transaction_count"] == 1
    assert report["peer_ack_count"] == 0
    assert report["peer_nak_count"] == 1
    assert report["qualified_success_count"] == 0
    assert report["strict_transactions"][0]["outcome"] == "peer_nak"
    assert "phonesuite-pms-application-nak" in {
        item["id"] for item in report["findings"]
    }
    assert report["claim_policy"]["checksum_fault_inferred_from_nak"] is False
    assert report["claim_policy"]["checksum_contract_inferred"] is False


def test_documented_optional_checksum_is_candidate_not_inferred_contract():
    checksum_variant = b"\x02CHK0 901\x03\x00"
    report = analyze_phonesuite_pms_to_pbx_transactions(
        [_capture("tx", checksum_variant)],
        transport="serial",
        evidence_class="packet_capture",
        pms_capture_direction="tx",
    )

    assert report["strict_transaction_count"] == 0
    assert report["checksum_variant_candidate_count"] == 1
    candidate = report["checksum_variant_candidates"][0]
    assert candidate["framing"] == "stx_etx_bcc"
    assert candidate["wire_sha256"] == hashlib.sha256(checksum_variant).hexdigest()
    assert report["reference_contract"]["optional_checksum_documented"] is True
    assert report["reference_contract"]["checksum_contract_qualified"] is False
    assert report["claim_policy"]["checksum_contract_inferred"] is False
    assert "CHK0 901" not in json.dumps(report)


def test_incomplete_frame_wrong_framing_and_unqualified_record_are_retained_safely():
    report = analyze_phonesuite_pms_to_pbx_transactions(
        [
            _capture("tx", b"\x02CHK0 901"),
            _capture("tx", b"CHK0 901\r\n"),
            _capture("tx", _frame("MOV 901 902")),
        ],
        transport="serial",
        evidence_class="packet_capture",
        pms_capture_direction="tx",
    )

    assert report["incomplete_stx_candidate_count"] == 1
    assert report["wrong_framing_record_count"] == 1
    assert report["wrong_framing_records"][0]["framing"] == "crlf"
    assert report["unqualified_record_count"] == 1
    ids = {item["id"] for item in report["findings"]}
    assert "phonesuite-pms-stx-frame-not-terminated" in ids
    assert "phonesuite-pms-application-framing-mismatch" in ids
    assert "phonesuite-pms-unqualified-record-observed" in ids

    encoded = json.dumps(report)
    assert "CHK0 901" not in encoded
    assert "MOV 901 902" not in encoded


def test_format_problem_is_reported_without_copying_observed_guest_or_room_text():
    bad = _frame("MW1 901")
    report = analyze_phonesuite_pms_to_pbx_transactions(
        [
            _capture("tx", ENQ),
            _capture("rx", ACK),
            _capture("tx", bad),
            _capture("rx", ACK),
        ],
        transport="serial",
        evidence_class="legacy_source_profile",
        pms_capture_direction="tx",
    )

    assert report["strict_transaction_count"] == 1
    assert report["format_error_count"] == 1
    assert report["qualified_success_count"] == 0
    txn = report["strict_transactions"][0]
    assert txn["format_valid"] is False
    assert {
        item["code"] for item in txn["format_diagnostics"]
    } == {"phonesuite_pms_mw_spacing_invalid"}
    assert "MW1 901" not in json.dumps(report)


def test_transport_direction_and_evidence_inputs_fail_closed():
    with pytest.raises(ValueError, match="transport must be serial"):
        analyze_phonesuite_pms_to_pbx_transactions(
            [],
            transport="tcp",
            evidence_class="legacy_source_profile",
            pms_capture_direction="tx",
        )

    with pytest.raises(ValueError, match="transport must be serial"):
        analyze_phonesuite_pms_to_pbx_transactions(
            [],
            transport="unknown",
            evidence_class="legacy_source_profile",
            pms_capture_direction="tx",
        )

    with pytest.raises(ValueError, match="pms_capture_direction must be rx or tx"):
        analyze_phonesuite_pms_to_pbx_transactions(
            [],
            transport="serial",
            evidence_class="legacy_source_profile",
            pms_capture_direction="unknown",
        )

    with pytest.raises(ValueError, match="evidence_class must be one of"):
        analyze_phonesuite_pms_to_pbx_transactions(
            [],
            transport="serial",
            evidence_class="assumed",
            pms_capture_direction="tx",
        )


def test_reversing_declared_pms_direction_prevents_msg_reverse_direction_promotion():
    report = analyze_phonesuite_pms_to_pbx_transactions(
        [
            _capture("tx", ENQ),
            _capture("rx", ACK),
            _capture("tx", _frame("MSG2 901")),
            _capture("rx", ACK),
        ],
        transport="serial",
        evidence_class="legacy_source_profile",
        pms_capture_direction="rx",
    )

    assert report["strict_transaction_count"] == 0
    assert report["source_qualified_frame_count"] == 0
    assert report["claim_policy"]["reverse_direction_inferred"] is False


def test_cli_output_is_deterministic_and_payload_safe(tmp_path):
    capture = tmp_path / "synthetic-phonesuite-pms.json"
    capture.write_text(
        json.dumps(
            [
                {"direction": "tx", "hex": ENQ.hex()},
                {"direction": "rx", "hex": ACK.hex()},
                {
                    "direction": "tx",
                    "hex": _frame("NAM1 SYNTHETIC-GUEST 901").hex(),
                },
                {"direction": "rx", "hex": ACK.hex()},
            ]
        ),
        encoding="utf-8",
    )
    out1 = tmp_path / "result-1.json"
    out2 = tmp_path / "result-2.json"
    command = [
        sys.executable,
        str(SCRIPT),
        str(capture),
        "--transport",
        "serial",
        "--pms-direction",
        "tx",
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

    payload = json.loads(out1.read_text(encoding="utf-8"))
    assert payload["strict_transaction_count"] == 1
    assert payload["strict_transactions"][0]["record"]["application_opcode"] == "NAM1"
    raw = out1.read_text(encoding="utf-8")
    assert "SYNTHETIC-GUEST" not in raw
    assert "NAM1 " not in raw
    assert " 901" not in raw


def test_cli_read_failure_does_not_echo_private_source_path(tmp_path):
    missing = tmp_path / "hotel-private" / "guest-capture.json"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            str(missing),
            "--transport",
            "serial",
            "--pms-direction",
            "tx",
            "--evidence-class",
            "packet_capture",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert "capture could not be read as UTF-8 JSON" in result.stdout
    assert "hotel-private" not in result.stdout
    assert "guest-capture.json" not in result.stdout
