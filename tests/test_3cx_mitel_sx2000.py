import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from innaware_pms_emulator.personalities import PERSONALITIES
from innaware_pms_emulator.profiles import BUILTIN_PROFILES, build_interface_from_profile
from innaware_pms_emulator.threecx_mitel_diagnostics import analyze_3cx_mitel_sx2000


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "diagnose-3cx-mitel-sx2000.py"
FIXTURE = ROOT / "tests" / "fixtures" / "pbx" / "3cx_mitel_sx2000_pms_to_pbx.json"
ENQ = b"\x05"
ACK = b"\x06"
CHK1 = b"\x02CHK1   101\x03"
MOV = b"\x02MOV1   101   102\x03"


def _capture(*items):
    return [{"direction": direction, "data": data} for direction, data in items]


def test_3cx_is_a_distinct_pbx_identity_with_mitel_compatibility_profile():
    personality = PERSONALITIES["pbx-3cx"]
    assert personality.name == "3CX Hotel Module"
    assert personality.brand == "3CX"
    assert personality.compatibility_family == "mitel_hospitality"
    assert personality.protocols == ("MITEL SX2000",)
    assert personality.recommended_profile == "3cx-mitel-sx2000-tcp-client"
    assert "3CX is modeled as its own PBX family" in personality.description


def test_3cx_profile_is_pms_side_tcp_client_and_has_no_guessed_port():
    profile = BUILTIN_PROFILES["3cx-mitel-sx2000-tcp-client"]
    assert profile.protocol == "Mitel 1"
    assert profile.defaults["transport"] == "tcp_client"
    assert profile.defaults["host"] is None
    assert profile.defaults["port"] is None
    assert profile.defaults["peer_personality_id"] == "pbx-3cx"
    assert profile.defaults["emulation_role"] == "pms"
    assert profile.defaults["options"]["ack_timeout"] == 3.0
    assert profile.defaults["options"]["max_attempts"] == 1
    assert profile.defaults["options"]["max_record_retries"] == 3
    assert profile.defaults["options"]["auto_ack"] is False

    config = build_interface_from_profile(
        "3cx-mitel-sx2000-tcp-client",
        name="3cx-lab",
        enabled=False,
        overrides={"host": "192.0.2.10", "port": 41000},
    )
    assert config.transport.value == "tcp_client"
    assert config.host == "192.0.2.10"
    assert config.port == 41000
    assert config.peer_personality_id == "pbx-3cx"
    assert config.effective_emulation_role().value == "pms"


def test_source_qualified_pms_transaction_is_bounded_and_payload_safe():
    report = analyze_3cx_mitel_sx2000(
        _capture(("tx", ENQ), ("rx", ACK), ("tx", CHK1), ("rx", ACK)),
        transport="tcp",
        evidence_class="legacy_source_profile",
        pms_direction="tx",
    )

    assert report["source_qualified_success_count"] == 1
    transaction = report["source_qualified_successes"][0]
    assert transaction["tx_sha256"] == hashlib.sha256(CHK1).hexdigest()
    assert transaction["tx_framing"] == "stx_etx"
    assert transaction["tx_record_family"] == "legacy_hotel"
    assert transaction["tx_record_code"] == "CHK"
    assert report["reference_contract"]["response_window_seconds"] == 3
    assert report["reference_contract"]["max_frame_only_retries_after_initial"] == 3
    assert report["reference_contract"]["site_port_is_configured_not_universal"] is True
    assert report["claim_policy"]["3cx_identity_preserved"] is True
    assert report["claim_policy"]["site_port_inferred"] is False
    assert report["claim_policy"]["pbx_to_pms_support_inferred"] is False
    assert report["claim_policy"]["compatibility_promotion_authorized"] is False
    encoded = json.dumps(report)
    assert "CHK1   101" not in encoded


def test_capture_direction_can_be_reversed_only_when_explicitly_declared():
    report = analyze_3cx_mitel_sx2000(
        _capture(("rx", ENQ), ("tx", ACK), ("rx", CHK1), ("tx", ACK)),
        transport="tcp",
        evidence_class="operator_confirmed",
        pms_direction="rx",
    )
    assert report["source_qualified_success_count"] == 1
    assert report["capture_pms_direction"] == "rx"


def test_acknowledged_unqualified_legacy_opcode_does_not_widen_3cx_record_claim():
    report = analyze_3cx_mitel_sx2000(
        _capture(("tx", ENQ), ("rx", ACK), ("tx", MOV), ("rx", ACK)),
        transport="tcp",
        evidence_class="legacy_source_profile",
        pms_direction="tx",
    )
    assert report["source_qualified_success_count"] == 0
    assert report["unqualified_mitel_record_success_count"] == 1
    assert any(
        item["id"] == "3cx-mitel-record-outside-source-qualified-pms-set"
        for item in report["findings"]
    )


def test_non_tcp_transport_and_unknown_capture_role_fail_closed():
    with pytest.raises(ValueError, match="transport must be one of: tcp"):
        analyze_3cx_mitel_sx2000(
            [],
            transport="serial",
            evidence_class="legacy_source_profile",
            pms_direction="tx",
        )
    with pytest.raises(ValueError, match="pms_direction must be one of"):
        analyze_3cx_mitel_sx2000(
            [],
            transport="tcp",
            evidence_class="legacy_source_profile",
            pms_direction="auto",
        )


def test_synthetic_fixture_is_explicitly_redacted_and_deterministic():
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert payload["sanitization"] == {
        "synthetic": True,
        "guest_pii": False,
        "vendor_binary": False,
    }
    report = analyze_3cx_mitel_sx2000(
        payload["captures"],
        transport=payload["combination"]["transport"],
        evidence_class=payload["evidence_class"],
        pms_direction="tx",
    )
    assert report["source_qualified_success_count"] == 1


def test_cli_is_deterministic_and_does_not_echo_payload(tmp_path):
    out1 = tmp_path / "result-1.json"
    out2 = tmp_path / "result-2.json"
    command = [
        sys.executable,
        str(SCRIPT),
        str(FIXTURE),
        "--transport",
        "tcp",
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
    result = json.loads(out1.read_text(encoding="utf-8"))
    assert result["source_qualified_success_count"] == 1
    raw = out1.read_text(encoding="utf-8")
    assert "CHK1   101" not in raw


def test_cli_read_failure_does_not_echo_private_source_path(tmp_path):
    missing = tmp_path / "hotel-secret" / "guest-capture.json"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            str(missing),
            "--transport",
            "tcp",
            "--pms-direction",
            "tx",
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
