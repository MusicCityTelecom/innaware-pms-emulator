import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from innaware_pms_emulator.transaction_rejection_diagnostics import analyze_peer_naks


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "diagnose-peer-naks.py"
SYNTHETIC_CHK1 = b"\x02CHK1   901\x03"


def test_correlates_immediate_peer_nak_without_embedding_payload():
    report = analyze_peer_naks(
        [
            {"direction": "tx", "data": SYNTHETIC_CHK1},
            {"direction": "rx", "data": b"\x15"},
        ],
        transport="serial",
        evidence_class="simulator_characterization",
    )

    assert report["peer_nak_count"] == 1
    assert report["correlated_rejection_count"] == 1
    assert report["uncorrelated_rejection_count"] == 0
    assert report["claim_policy"] == {
        "transport_inferred": False,
        "personality_switch_authorized": False,
        "compatibility_promotion_authorized": False,
        "raw_payloads_embedded": False,
        "series2_station_programming_in_scope": False,
    }

    rejection = report["rejections"][0]
    assert rejection["nak_index"] == 1
    assert rejection["preceding_tx_index"] == 0
    assert rejection["confidence"] == "high"
    assert rejection["tx_sha256"] == hashlib.sha256(SYNTHETIC_CHK1).hexdigest()
    assert rejection["tx_length"] == len(SYNTHETIC_CHK1)
    assert rejection["tx_framing"] == "stx_etx"
    assert rejection["tx_record_family"] == "legacy_hotel"
    assert rejection["tx_record_code"] == "CHK"
    assert rejection["tx_control"] is None
    assert any("baud" in action for action in rejection["corrective_actions"])

    encoded = json.dumps(report)
    assert "901" not in encoded
    assert "CHK1" not in encoded


def test_does_not_correlate_nak_across_new_inbound_transaction_boundary():
    report = analyze_peer_naks(
        [
            {"direction": "tx", "data": SYNTHETIC_CHK1},
            {"direction": "rx", "data": b"\x05"},
            {"direction": "rx", "data": b"\x15"},
        ],
        transport="tcp",
        evidence_class="packet_capture",
    )

    rejection = report["rejections"][0]
    assert rejection["preceding_tx_index"] is None
    assert rejection["confidence"] == "low"
    assert rejection["tx_sha256"] is None
    assert any("site port" in action for action in rejection["corrective_actions"])
    assert any("uncorrelated NAK" in action for action in rejection["corrective_actions"])


def test_transport_and_evidence_class_are_explicit_and_fail_closed():
    with pytest.raises(ValueError, match="transport must be one of"):
        analyze_peer_naks([], transport="auto", evidence_class="packet_capture")

    with pytest.raises(ValueError, match="evidence_class must be one of"):
        analyze_peer_naks([], transport="serial", evidence_class="assumed")


def test_cli_output_is_deterministic_and_payload_safe(tmp_path):
    capture = tmp_path / "synthetic-capture.json"
    capture.write_text(
        json.dumps(
            [
                {"direction": "tx", "hex": SYNTHETIC_CHK1.hex()},
                {"direction": "rx", "hex": "15"},
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
    assert payload["rejections"][0]["tx_sha256"] == hashlib.sha256(SYNTHETIC_CHK1).hexdigest()
    assert "901" not in out1.read_text(encoding="utf-8")
    assert "CHK1" not in out1.read_text(encoding="utf-8")


def test_cli_read_failure_does_not_echo_private_source_path(tmp_path):
    missing = tmp_path / "customer-a" / "guest-capture.json"
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
    assert "customer-a" not in result.stdout
