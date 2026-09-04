import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from innaware_pms_emulator.matrix_fias_link_diagnostics import (
    analyze_matrix_fias_link_start,
)


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "diagnose-matrix-fias-link.py"
LS_RX = b"\x02LS|DA000101|TI000000|\x03"
LS_TX = b"\x02LS|DA000101|TI000001|\x03"
GI_RX = b"\x02GI|RN0901|G#SYNTHETIC|\x03"
ACK = b"\x06"


def _capture(*items):
    return [{"direction": direction, "data": data} for direction, data in items]


def test_exact_adjacent_stx_etx_ls_pair_is_preserved_without_payload_leakage():
    report = analyze_matrix_fias_link_start(
        _capture(("rx", LS_RX), ("tx", LS_TX)),
        transport="tcp",
        evidence_class="operator_confirmed",
    )

    assert report["diagnostic_profile"] == "matrix_micros_opera_fias_link_start"
    assert report["transport"] == "tcp"
    assert report["inbound_ls_count"] == 1
    assert report["outbound_ls_count"] == 1
    assert report["exact_link_start_pair_count"] == 1
    pair = report["exact_link_start_pairs"][0]
    assert pair["request"]["wire_sha256"] == hashlib.sha256(LS_RX).hexdigest()
    assert pair["reply"]["wire_sha256"] == hashlib.sha256(LS_TX).hexdigest()
    assert pair["request"]["framing"] == "stx_etx"
    assert pair["request"]["record_code"] == "LS"
    assert pair["confidence"] == "high"
    assert report["reference_contract"]["post_ls_progression_qualified"] is False
    assert report["reference_contract"]["site_port_is_protocol_constant"] is False
    assert report["claim_policy"]["compatibility_promotion_authorized"] is False
    assert report["claim_policy"]["series2_station_programming_in_scope"] is False

    encoded = json.dumps(report)
    assert "DA000101" not in encoded
    assert "TI000000" not in encoded
    assert "TI000001" not in encoded


def test_wrong_ls_reply_framing_is_actionable_without_transport_inference():
    wrong_reply = b"LS|DA000101|TI000001|\r\n"
    report = analyze_matrix_fias_link_start(
        _capture(("rx", LS_RX), ("tx", wrong_reply)),
        transport="tcp",
        evidence_class="packet_capture",
    )

    assert report["exact_link_start_pair_count"] == 0
    assert report["framing_mismatch_count"] == 1
    assert report["framing_mismatches"][0]["framing"] == "crlf"
    finding_ids = {item["id"] for item in report["findings"]}
    assert "matrix-outbound-ls-framing-mismatch" in finding_ids
    assert "matrix-ls-reply-not-observed-adjacent" in finding_ids
    assert report["claim_policy"]["transport_inferred"] is False
    assert report["claim_policy"]["serial_variant_inferred"] is False


def test_post_ls_records_and_control_bytes_are_retained_only_as_evidence_candidates():
    report = analyze_matrix_fias_link_start(
        _capture(
            ("rx", LS_RX),
            ("tx", LS_TX),
            ("rx", ACK),
            ("rx", GI_RX),
        ),
        transport="tcp",
        evidence_class="packet_capture",
    )

    assert report["control_handshake_observation_count"] == 1
    assert report["control_handshake_observations"][0]["record_code"] is None
    assert report["post_ls_progression_count"] == 1
    assert report["post_ls_progression"][0]["record_code"] == "GI"
    assert report["guest_event_candidate_count"] == 1
    finding_ids = {item["id"] for item in report["findings"]}
    assert "matrix-unqualified-control-handshake-observed" in finding_ids
    assert "matrix-post-ls-progression-observed" in finding_ids
    assert report["reference_contract"]["control_handshake_qualified"] is False
    assert report["reference_contract"]["guest_events_qualified"] is False
    assert report["claim_policy"]["guest_event_support_inferred"] is False
    assert "SYNTHETIC" not in json.dumps(report)
    assert "0901" not in json.dumps(report)


def test_non_tcp_transport_fails_closed_for_current_matrix_row():
    with pytest.raises(ValueError, match="transport must be tcp"):
        analyze_matrix_fias_link_start(
            [], transport="serial", evidence_class="operator_confirmed"
        )

    with pytest.raises(ValueError, match="transport must be tcp"):
        analyze_matrix_fias_link_start(
            [], transport="unknown", evidence_class="operator_confirmed"
        )

    with pytest.raises(ValueError, match="evidence_class must be one of"):
        analyze_matrix_fias_link_start(
            [], transport="tcp", evidence_class="assumed"
        )


def test_cli_output_is_deterministic_and_payload_safe(tmp_path):
    capture = tmp_path / "synthetic-matrix.json"
    capture.write_text(
        json.dumps(
            [
                {"direction": "rx", "hex": LS_RX.hex()},
                {"direction": "tx", "hex": LS_TX.hex()},
                {"direction": "rx", "hex": GI_RX.hex()},
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
        "tcp",
        "--evidence-class",
        "operator_confirmed",
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
    assert payload["exact_link_start_pair_count"] == 1
    assert payload["post_ls_progression_count"] == 1
    raw = out1.read_text(encoding="utf-8")
    assert "DA000101" not in raw
    assert "SYNTHETIC" not in raw
    assert "0901" not in raw


def test_cli_rejects_guessed_serial_matrix_row(tmp_path):
    capture = tmp_path / "matrix.json"
    capture.write_text(json.dumps([{"direction": "rx", "hex": LS_RX.hex()}]), encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            str(capture),
            "--transport",
            "serial",
            "--evidence-class",
            "operator_confirmed",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert "transport must be tcp" in result.stdout


def test_cli_read_failure_does_not_echo_private_source_path(tmp_path):
    missing = tmp_path / "hotel-a" / "guest-capture.json"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            str(missing),
            "--transport",
            "tcp",
            "--evidence-class",
            "packet_capture",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert "capture could not be read as UTF-8 JSON" in result.stdout
    assert "hotel-a" not in result.stdout
    assert "guest-capture.json" not in result.stdout
