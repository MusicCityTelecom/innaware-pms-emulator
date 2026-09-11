import json
from pathlib import Path

from innaware_pms_emulator.framing import ACK, ENQ, ETX, STX


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "pbx" / "phonesuite_serial_characterization.json"


def _fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _payload(step: dict) -> bytes:
    return bytes.fromhex(step["hex"])


def test_phonesuite_serial_fixture_is_sanitized_and_evidence_qualified():
    fixture = _fixture()

    assert fixture["pbx_family"] == "PhoneSuite"
    assert fixture["transport"] == "serial"
    assert fixture["status"] == "partially_characterized"
    assert fixture["sanitized"] is True
    assert fixture["evidence_class"] == "simulator_characterization"
    assert "baud_rate" not in fixture
    assert "parity" not in fixture

    joined = " ".join(step["meaning"] for step in fixture["sequence"])
    assert "TEST,GUEST" in joined
    assert "192.168." not in joined


def test_phonesuite_serial_fixture_preserves_characterized_control_and_framing():
    fixture = _fixture()
    sequence = fixture["sequence"]

    controls = [_payload(step) for step in sequence if len(_payload(step)) == 1]
    assert controls.count(bytes((ENQ,))) == 3
    assert controls.count(bytes((ACK,))) == 6

    frames = [_payload(step) for step in sequence if len(_payload(step)) > 1]
    assert len(frames) == 3
    assert all(frame[0] == STX and frame[-1] == ETX for frame in frames)
    assert frames[0][1:-1].startswith(b"CHK1")
    assert frames[1][1:-1].startswith(b"NAM2")
    assert frames[2][1:-1].startswith(b"CHK0")


def test_phonesuite_serial_fixture_keeps_series2_station_programming_out_of_wire_claims():
    fixture = _fixture()
    wire_meanings = " ".join(step["meaning"] for step in fixture["sequence"])

    assert "TDMoE" not in wire_meanings
    assert "Q.921" not in wire_meanings
    assert "Q.931" not in wire_meanings
    assert "0x0E" not in wire_meanings
