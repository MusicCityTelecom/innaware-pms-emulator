import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from innaware_pms_emulator.phonesuite_serial_diagnostics import (
    analyze_phonesuite_serial_transactions,
)


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "diagnose-phonesuite-serial.py"
FIXTURE = ROOT / "tests" / "fixtures" / "pbx" / "phonesuite_serial_characterization.json"
ENQ = b"\x05"
ACK = b"\x06"
NAK = b"\x15"
CHK1 = b"\x02CHK1ROOM901\x03"
NAM2 = b"\x02NAM2SYNTHETIC,GUESTROOM901\x03"


def _capture(*items):
    return [{"direction": direction, "data": data} for direction, data in items]


def test_existing_sanitized_fixture_produces_three_exact_accepted_transactions():
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    report = analyze_phonesuite_serial_transactions(
        fixture["sequence"],
        transport="serial",
        evidence_class="simulator_characterization",
    )

    assert report["diagnostic_profile"] == "phonesuite_mitel1_serial_pbx_to_pms"
    assert report["transport"] == "serial"
    assert report["exact_transaction_count"] == 3
    assert report["accepted_transaction_count"] == 3
    assert report["rejected_transaction_count"] == 0
    assert [item["record_opcode"] for item in report["exact_transactions"]] == [
        "CHK1",
        "NAM2",
        "CHK0",
    ]
    first = report["exact_transactions"][0]
    expected_wire = bytes.fromhex(fixture["sequence"][2]["hex"])
    assert first["record"]["wire_sha256"] == hashlib.sha256(expected_wire).hexdigest()
    assert first["record"]["framing"] == "stx_etx"
    assert first["response"]["control"] == "ACK"
    assert report["reference_contract"]["serial_defaults_qualified"] is False
    assert report["reference_contract"]["checksum_contract_qualified"] is False
    assert report["reference_contract"]["retry_policy_qualified"] is False
    assert report["claim_policy"]["compatibility_promotion_authorized"] is False
    assert report["claim_policy"]["series2_station_programming_in_scope"] is False

    encoded = json.dumps(report)
    assert "ROOM101" not in encoded
    assert "TEST,GUEST" not in encoded


def test_application_nak_is_rejection_evidence_not_checksum_inference():
    report = analyze_phonesuite_serial_transactions(
        _capture(
            ("pbx_to_emulator", ENQ),
            ("emulator_to_pbx", ACK),
            ("pbx_to_emulator", CHK1),
            ("emulator_to_pbx", NAK),
        ),
        transport="serial",
        evidence_class="simulator_characterization",
    )

    assert report["exact_transaction_count"] == 1
    assert report["accepted_transaction_count"] == 0
    assert report["rejected_transaction_count"] == 1
    assert report["exact_transactions"][0]["outcome"] == "rejected"
    finding_ids = {item["id"] for item in report["findings"]}
    assert "phonesuite-serial-application-nak" in finding_ids
    assert report["claim_policy"]["checksum_fault_inferred_from_nak"] is False
    assert "ROOM901" not in json.dumps(report)


def test_qualified_frame_outside_exact_handshake_is_retained_without_guessing():
    report = analyze_phonesuite_serial_transactions(
        _capture(("pbx_to_emulator", CHK1), ("emulator_to_pbx", ACK)),
        transport="serial",
        evidence_class="packet_capture",
    )

    assert report["exact_transaction_count"] == 0
    assert report["unmatched_qualified_frame_count"] == 1
    finding_ids = {item["id"] for item in report["findings"]}
    assert "phonesuite-serial-qualified-record-outside-exact-handshake" in finding_ids
    assert report["claim_policy"]["retry_policy_inferred"] is False
    assert report["claim_policy"]["reverse_direction_inferred"] is False


def test_wrong_application_framing_is_actionable_and_does_not_infer_tcp():
    wrong = b"CHK1ROOM901\r\n"
    report = analyze_phonesuite_serial_transactions(
        _capture(
            ("pbx_to_emulator", ENQ),
            ("emulator_to_pbx", ACK),
            ("pbx_to_emulator", wrong),
            ("emulator_to_pbx", ACK),
        ),
        transport="serial",
        evidence_class="packet_capture",
    )

    assert report["exact_transaction_count"] == 0
    assert report["framing_mismatch_count"] == 1
    assert report["framing_mismatches"][0]["framing"] == "crlf"
    finding_ids = {item["id"] for item in report["findings"]}
    assert "phonesuite-serial-application-framing-mismatch" in finding_ids
    assert report["claim_policy"]["transport_inferred"] is False
    assert "ROOM901" not in json.dumps(report)


def test_additional_legacy_record_is_evidence_candidate_not_support_promotion():
    extra = b"\x02WKP0600  901\x03"
    report = analyze_phonesuite_serial_transactions(
        _capture(
            ("pbx_to_emulator", ENQ),
            ("emulator_to_pbx", ACK),
            ("pbx_to_emulator", extra),
            ("emulator_to_pbx", ACK),
        ),
        transport="serial",
        evidence_class="packet_capture",
    )

    assert report["exact_transaction_count"] == 0
    assert report["uncharacterized_record_count"] == 1
    assert report["uncharacterized_records"][0]["record_opcode"] == "WKP0600"
    assert report["claim_policy"]["broader_opcode_support_inferred"] is False
    assert "WKP0600  901" not in json.dumps(report)


def test_non_serial_transport_and_unknown_evidence_class_fail_closed():
    with pytest.raises(ValueError, match="transport must be serial"):
        analyze_phonesuite_serial_transactions(
            [], transport="tcp", evidence_class="simulator_characterization"
        )

    with pytest.raises(ValueError, match="transport must be serial"):
        analyze_phonesuite_serial_transactions(
            [], transport="unknown", evidence_class="simulator_characterization"
        )

    with pytest.raises(ValueError, match="evidence_class must be one of"):
        analyze_phonesuite_serial_transactions(
            [], transport="serial", evidence_class="assumed"
        )


def test_cli_output_is_deterministic_and_payload_safe(tmp_path):
    capture = tmp_path / "synthetic-phonesuite.json"
    capture.write_text(
        json.dumps(
            [
                {"direction": "rx", "hex": ENQ.hex()},
                {"direction": "tx", "hex": ACK.hex()},
                {"direction": "rx", "hex": NAM2.hex()},
                {"direction": "tx", "hex": ACK.hex()},
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
    assert payload["exact_transaction_count"] == 1
    assert payload["exact_transactions"][0]["record_opcode"] == "NAM2"
    raw = out1.read_text(encoding="utf-8")
    assert "SYNTHETIC" not in raw
    assert "ROOM901" not in raw


def test_cli_read_failure_does_not_echo_private_source_path(tmp_path):
    missing = tmp_path / "hotel-private" / "guest-capture.json"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            str(missing),
            "--transport",
            "serial",
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
