import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from innaware_pms_emulator.mitel_half_duplex_diagnostics import (
    analyze_mitel_half_duplex_sequence,
)


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "diagnose-mitel-half-duplex.py"
ENQ = b"\x05"
ACK = b"\x06"
NAK = b"\x15"
CHK1 = b"\x02CHK1   901\x03"
CHK0 = b"\x02CHK0   901\x03"


def _capture(*items):
    return [{"direction": direction, "data": data} for direction, data in items]


def test_identifies_strict_canonical_success_without_transport_inference():
    report = analyze_mitel_half_duplex_sequence(
        _capture(
            ("tx", ENQ),
            ("rx", ACK),
            ("tx", CHK1),
            ("rx", ACK),
        ),
        transport="tcp",
        evidence_class="packet_capture",
    )

    assert report["exact_successful_transaction_count"] == 1
    transaction = report["exact_successful_transactions"][0]
    assert transaction["enq_index"] == 0
    assert transaction["tx_index"] == 2
    assert transaction["frame_ack_index"] == 3
    assert transaction["tx_sha256"] == hashlib.sha256(CHK1).hexdigest()
    assert transaction["tx_framing"] == "stx_etx"
    assert transaction["tx_record_family"] == "legacy_hotel"
    assert transaction["tx_record_code"] == "CHK"

    assert report["reference_contract"]["ack_nak_window_seconds"] == 3
    assert report["reference_contract"]["timing_assessed_by_this_analyzer"] is False
    assert report["claim_policy"] == {
        "transport_inferred": False,
        "serial_defaults_inferred": False,
        "tcp_port_inferred": False,
        "personality_switch_authorized": False,
        "compatibility_promotion_authorized": False,
        "raw_payloads_embedded": False,
        "series2_station_programming_in_scope": False,
    }
    assert any("site port" in action for action in report["technician_actions"])
    assert "901" not in json.dumps(report)
    assert "CHK1" not in json.dumps(report)


def test_three_frame_only_retries_remain_within_reference_limit():
    report = analyze_mitel_half_duplex_sequence(
        _capture(
            ("tx", ENQ),
            ("rx", ACK),
            ("tx", CHK1),
            ("rx", NAK),
            ("tx", CHK1),
            ("rx", NAK),
            ("tx", CHK1),
            ("rx", NAK),
            ("tx", CHK1),
            ("rx", ACK),
        ),
        transport="serial",
        evidence_class="legacy_source_profile",
    )

    assert report["application_frame_nak_count"] == 3
    assert report["frame_only_retry_count"] == 3
    assert [event["retry_ordinal"] for event in report["frame_only_retries"]] == [1, 2, 3]
    assert [event["total_record_transmissions"] for event in report["frame_only_retries"]] == [2, 3, 4]
    assert all(event["within_reference_retry_limit"] for event in report["frame_only_retries"])
    assert not any(finding["id"] == "record-retry-limit-exceeded" for finding in report["findings"])
    assert any("baud" in action for action in report["technician_actions"])
    assert any("TCP reconnect" in action for action in report["technician_actions"])


def test_fifth_total_record_transmission_is_flagged_as_reference_deviation():
    report = analyze_mitel_half_duplex_sequence(
        _capture(
            ("tx", ENQ),
            ("rx", ACK),
            ("tx", CHK1),
            ("rx", NAK),
            ("tx", CHK1),
            ("rx", NAK),
            ("tx", CHK1),
            ("rx", NAK),
            ("tx", CHK1),
            ("rx", NAK),
            ("tx", CHK1),
        ),
        transport="unknown",
        evidence_class="simulator_characterization",
    )

    assert report["frame_only_retry_count"] == 4
    final_retry = report["frame_only_retries"][-1]
    assert final_retry["retry_ordinal"] == 4
    assert final_retry["total_record_transmissions"] == 5
    assert final_retry["within_reference_retry_limit"] is False
    finding = next(
        item for item in report["findings"] if item["id"] == "record-retry-limit-exceeded"
    )
    assert finding["total_record_transmissions"] == 5
    assert any("Resolve transport" in action for action in report["technician_actions"])


def test_new_enq_after_frame_nak_is_reported_without_calling_transport_wrong():
    report = analyze_mitel_half_duplex_sequence(
        _capture(
            ("tx", ENQ),
            ("rx", ACK),
            ("tx", CHK1),
            ("rx", NAK),
            ("tx", ENQ),
            ("rx", ACK),
        ),
        transport="serial",
        evidence_class="operator_confirmed",
    )

    assert report["enq_reissue_after_frame_nak_count"] == 1
    event = report["enq_reissue_after_frame_nak"][0]
    assert event["nak_index"] == 3
    assert event["enq_index"] == 4
    assert event["rejected_tx_sha256"] == hashlib.sha256(CHK1).hexdigest()
    assert any(
        finding["id"] == "enq-reissued-before-record-retry"
        for finding in report["findings"]
    )
    assert report["claim_policy"]["transport_inferred"] is False


def test_changed_frame_after_nak_fails_closed_as_ambiguous():
    report = analyze_mitel_half_duplex_sequence(
        _capture(
            ("tx", ENQ),
            ("rx", ACK),
            ("tx", CHK1),
            ("rx", NAK),
            ("tx", CHK0),
        ),
        transport="tcp",
        evidence_class="packet_capture",
    )

    assert report["changed_frame_after_nak_without_enq_count"] == 1
    event = report["changed_frame_after_nak_without_enq"][0]
    assert event["rejected_tx_sha256"] == hashlib.sha256(CHK1).hexdigest()
    assert event["replacement_tx_sha256"] == hashlib.sha256(CHK0).hexdigest()
    assert event["confidence"] == "medium"
    assert any(
        finding["id"] == "frame-changed-after-nak-without-enq"
        for finding in report["findings"]
    )
    encoded = json.dumps(report)
    assert "CHK1" not in encoded
    assert "CHK0" not in encoded
    assert "901" not in encoded


def test_handshake_nak_is_separate_from_application_frame_nak():
    report = analyze_mitel_half_duplex_sequence(
        _capture(("tx", ENQ), ("rx", NAK)),
        transport="tcp",
        evidence_class="packet_capture",
    )

    assert report["handshake_nak_count"] == 1
    assert report["application_frame_nak_count"] == 0
    assert report["frame_only_retry_count"] == 0


def test_transport_and_evidence_class_are_required_and_fail_closed():
    with pytest.raises(ValueError, match="transport must be one of"):
        analyze_mitel_half_duplex_sequence(
            [], transport="auto", evidence_class="packet_capture"
        )

    with pytest.raises(ValueError, match="evidence_class must be one of"):
        analyze_mitel_half_duplex_sequence(
            [], transport="serial", evidence_class="assumed"
        )


def test_cli_output_is_deterministic_and_payload_safe(tmp_path):
    capture = tmp_path / "synthetic-capture.json"
    capture.write_text(
        json.dumps(
            [
                {"direction": "tx", "hex": ENQ.hex()},
                {"direction": "rx", "hex": ACK.hex()},
                {"direction": "tx", "hex": CHK1.hex()},
                {"direction": "rx", "hex": NAK.hex()},
                {"direction": "tx", "hex": CHK1.hex()},
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
        "--evidence-class",
        "simulator_characterization",
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
    assert payload["frame_only_retry_count"] == 1
    assert payload["frame_only_retries"][0]["tx_sha256"] == hashlib.sha256(CHK1).hexdigest()
    raw = out1.read_text(encoding="utf-8")
    assert "901" not in raw
    assert "CHK1" not in raw


def test_cli_read_failure_does_not_echo_private_source_path(tmp_path):
    missing = tmp_path / "hotel-a" / "guest-capture.json"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            str(missing),
            "--transport",
            "unknown",
            "--evidence-class",
            "inference",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert json.loads(result.stdout) == {"error": "capture could not be read as UTF-8 JSON"}
    assert str(tmp_path) not in result.stdout
    assert "hotel-a" not in result.stdout
