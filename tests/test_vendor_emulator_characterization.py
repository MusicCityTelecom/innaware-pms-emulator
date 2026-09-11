import json
from pathlib import Path

from innaware_pms_emulator.protocols.mitel import Mitel1Adapter, Mitel2Adapter


DATA = Path(__file__).parent / "data" / "vendor_characterization"


def _load(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def test_vendor_observations_are_sanitized_and_evidence_labeled():
    fixtures = [_load("mitel_pms_tester_2_01_0002.json"), _load("cmp_serial_simulator_1_003.json")]
    assert all(item["sanitized"] is True for item in fixtures)
    assert all(item["evidence"] == "emulator-observed" for item in fixtures)


def test_mitel_observed_nam_frames_have_fixed_layout():
    fixture = _load("mitel_pms_tester_2_01_0002.json")
    for observation in fixture["observations"]:
        wire = bytes.fromhex(observation["wire_hex"])
        payload = wire[1:-1]
        assert wire[:1] == b"\x02"
        assert wire[-1:] == b"\x03"
        assert len(payload) == 31
        assert payload.startswith(b"NAM1 ")
        assert payload[-3:] == b"101"
        assert b"\r" not in payload and b"\n" not in payload
        assert payload.decode("ascii") == observation["payload_text"]


def test_his_and_hyatt_observations_use_same_nam_field_positions():
    fixture = _load("mitel_pms_tester_2_01_0002.json")
    modes = {item["mode"] for item in fixture["observations"]}
    assert modes == {"HIS", "Hyatt Encore"}
    assert all(item["payload_text"][28:] == "101" for item in fixture["observations"])


def test_current_mitel1_can_reproduce_observed_payload_when_operation_is_one():
    event = {
        "action": "name",
        "room": "101",
        "last_name": "TEST",
        "first_name": "GUEST",
        "extra": {"name_operation": "1"},
    }
    expected = next(
        item["payload_text"].encode("ascii")
        for item in _load("mitel_pms_tester_2_01_0002.json")["observations"]
        if item["id"] == "hyatt-encore-nam-add"
    )
    assert Mitel1Adapter().encode_event(event) == expected
    assert Mitel2Adapter().encode_event(event) != expected


def test_cmp_sender_claims_are_limited_to_exposed_generic_behavior():
    fixture = _load("cmp_serial_simulator_1_003.json")
    assert fixture["phonesuite_attribution"] == "unknown"
    assert fixture["modes"] == ["Ack-Nak Receiver", "PMS Sender", "HOBIS A Sender"]
    assert {"Mitel 1", "Mitel 2", "Voiceware", "OperaIP", "FIAS"} <= set(fixture["not_exposed"])
    controls, frame = fixture["pms_sender"]["wire_hex"].split(" | ")
    assert bytes.fromhex(controls) == b"\x05"
    wire = bytes.fromhex(frame)
    assert wire == b"\x02CHK1  101 LASTNAME,FIRSTNAME\x03"
