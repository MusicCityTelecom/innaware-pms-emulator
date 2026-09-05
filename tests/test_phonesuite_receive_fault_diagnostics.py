import json
import subprocess
import sys
from pathlib import Path

import pytest

from innaware_pms_emulator.phonesuite_receive_fault_diagnostics import (
    analyze_phonesuite_receive_faults,
)


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "diagnose-phonesuite-receive-faults.py"
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


def test_late_non_enq_data_followed_by_nak_matches_documented_timeout_behavior():
    report = analyze_phonesuite_receive_faults(
        [
            _capture("tx", ENQ, "2026-09-04T10:00:00.000Z"),
            _capture("rx", ACK, "2026-09-04T10:00:00.010Z"),
            _capture("tx", _frame("CHK0 901"), "2026-09-04T10:00:00.150Z"),
            _capture("rx", NAK, "2026-09-04T10:00:00.160Z"),
        ],
        transport="serial",
        evidence_class="packet_capture",
        pms_capture_direction="tx",
    )

    assert report["enq_grant_handshake_count"] == 1
    assert report["late_data_event_count"] == 1
    event = report["late_data_events"][0]
    assert event["ack_to_late_data_seconds"] == 0.14
    assert event["expected_response"] == "NAK"
    assert event["response_consistent_with_source"] is True
    assert event["observed_response"]["control"] == "NAK"
    assert "phonesuite-late-data-nak-source-consistent" in {
        item["id"] for item in report["findings"]
    }
    assert report["claim_policy"]["checksum_fault_inferred_from_nak"] is False


def test_late_data_ack_is_flagged_as_source_deviation_not_promoted_behavior():
    report = analyze_phonesuite_receive_faults(
        [
            _capture("tx", ENQ, "2026-09-04T10:00:00.000Z"),
            _capture("rx", ACK, "2026-09-04T10:00:00.010Z"),
            _capture("tx", _frame("CHK0 901"), "2026-09-04T10:00:00.150Z"),
            _capture("rx", ACK, "2026-09-04T10:00:00.160Z"),
        ],
        transport="serial",
        evidence_class="packet_capture",
        pms_capture_direction="tx",
    )

    assert report["late_data_event_count"] == 1
    assert report["late_data_events"][0]["response_consistent_with_source"] is False
    assert "phonesuite-late-data-ack-source-deviation" in {
        item["id"] for item in report["findings"]
    }
    assert report["claim_policy"]["compatibility_promotion_authorized"] is False


def test_new_enq_after_grant_is_not_misclassified_as_late_data():
    report = analyze_phonesuite_receive_faults(
        [
            _capture("tx", ENQ, "2026-09-04T10:00:00.000Z"),
            _capture("rx", ACK, "2026-09-04T10:00:00.010Z"),
            _capture("tx", ENQ, "2026-09-04T10:00:00.250Z"),
        ],
        transport="serial",
        evidence_class="legacy_source_profile",
        pms_capture_direction="tx",
    )

    assert report["late_data_event_count"] == 0
    assert report["enq_grant_handshakes"][0]["state"] == "new_enq_started"


def test_incomplete_stx_followed_by_nak_is_only_medium_confidence_without_byte_timing():
    report = analyze_phonesuite_receive_faults(
        [
            _capture("tx", b"\x02CHK0 901"),
            _capture("rx", NAK),
        ],
        transport="serial",
        evidence_class="packet_capture",
        pms_capture_direction="tx",
    )

    assert report["incomplete_frame_event_count"] == 1
    event = report["incomplete_frame_events"][0]
    assert event["peer_nak_observed"] is True
    assert event["missing_etx_timing_assessed"] is False
    assert event["source_consistency"] == "consistent_with_documented_missing_etx_nak"
    finding = next(
        item
        for item in report["findings"]
        if item["id"] == "phonesuite-incomplete-frame-nak-source-consistent"
    )
    assert finding["confidence"] == "medium"
    assert report["claim_policy"]["between_character_timing_inferred"] is False


@pytest.mark.parametrize("family,payload", [
    ("CHK", "CHK1 ROOM"),
    ("DND", "DND1 ROOM"),
    ("MW", "MW 1 ROOM"),
])
def test_documented_invalid_extension_nak_is_correlated_without_payload_leak(
    family: str,
    payload: str,
):
    report = analyze_phonesuite_receive_faults(
        [
            _capture("tx", _frame(payload)),
            _capture("rx", NAK),
        ],
        transport="serial",
        evidence_class="legacy_source_profile",
        pms_capture_direction="tx",
    )

    assert report["invalid_extension_nak_event_count"] == 1
    event = report["invalid_extension_nak_events"][0]
    assert event["record_family"] == family
    assert {
        item["code"] for item in event["safe_format_diagnostics"]
    } == {"phonesuite_pms_extension_format_invalid"}
    encoded = json.dumps(report)
    assert payload not in encoded
    assert "ROOM" not in encoded
    assert report["claim_policy"]["raw_payloads_embedded"] is False


def test_transport_direction_and_evidence_fail_closed():
    with pytest.raises(ValueError, match="transport must be serial"):
        analyze_phonesuite_receive_faults(
            [],
            transport="tcp",
            evidence_class="packet_capture",
            pms_capture_direction="tx",
        )

    with pytest.raises(ValueError, match="pms_capture_direction must be rx or tx"):
        analyze_phonesuite_receive_faults(
            [],
            transport="serial",
            evidence_class="packet_capture",
            pms_capture_direction="unknown",
        )

    with pytest.raises(ValueError, match="evidence_class must be one of"):
        analyze_phonesuite_receive_faults(
            [],
            transport="serial",
            evidence_class="assumed",
            pms_capture_direction="tx",
        )


def test_cli_output_is_deterministic_and_payload_safe(tmp_path):
    guest_frame = _frame("CHK1 901 SYNTHETIC-GUEST")
    capture = tmp_path / "phonesuite-timeout-capture.json"
    capture.write_text(
        json.dumps(
            [
                {
                    "direction": "tx",
                    "hex": ENQ.hex(),
                    "timestamp": "2026-09-04T10:00:00.000Z",
                },
                {
                    "direction": "rx",
                    "hex": ACK.hex(),
                    "timestamp": "2026-09-04T10:00:00.010Z",
                },
                {
                    "direction": "tx",
                    "hex": guest_frame.hex(),
                    "timestamp": "2026-09-04T10:00:00.150Z",
                },
                {
                    "direction": "rx",
                    "hex": NAK.hex(),
                    "timestamp": "2026-09-04T10:00:00.160Z",
                },
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
        "packet_capture",
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
    assert payload["late_data_event_count"] == 1
    raw = out1.read_text(encoding="utf-8")
    assert "SYNTHETIC-GUEST" not in raw
    assert "CHK1 901" not in raw


def test_cli_read_failure_does_not_echo_private_input_path(tmp_path):
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
