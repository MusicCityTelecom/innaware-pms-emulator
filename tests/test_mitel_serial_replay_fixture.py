from pathlib import Path

from innaware_pms_emulator.framing import ACK
from innaware_pms_emulator.mitel_serial_session import MitelSerialSessionStateMachine
from innaware_pms_emulator.replay import load_fixtures


FIXTURE_PATH = Path(__file__).parent / "data" / "emulation" / "mitel_serial_pms_to_pbx.json"
TCP_FIXTURE_PATH = Path(__file__).parent / "data" / "emulation" / "mitel_ipocket_tcp.json"


def test_mitel_serial_fixture_is_sanitized_and_keeps_transport_characterization_scoped():
    fixture = load_fixtures(FIXTURE_PATH)[0]

    assert fixture.fixture_id == "mitel-serial-pms-to-pbx-simulator-chk-sequence"
    assert fixture.personality == "pbx-mitel-sx200"
    assert fixture.protocol == "MITEL 1"
    assert fixture.status == "partially_characterized"
    assert fixture.sanitized is True
    assert fixture.environment["transport"] == "serial"
    assert fixture.environment["evidence_class"] == "simulator_characterization"
    assert fixture.environment["serial"] == {
        "baud_rate": 9600,
        "data_bits": 8,
        "parity": "N",
        "stop_bits": 1,
        "flow_control": "xonxoff",
    }
    assert "not a universal" in fixture.environment["scope"]
    assert "room 901 is synthetic" in fixture.evidence

    source = FIXTURE_PATH.read_text(encoding="utf-8")
    assert "COM10" not in source
    assert "C:\\Temp" not in source
    assert "192.168." not in source
    assert "TOMMY" not in source.upper()
    assert "HEGGIE" not in source.upper()


def test_replay_fixture_environment_is_backward_compatible_for_existing_fixtures():
    fixture = load_fixtures(TCP_FIXTURE_PATH)[0]
    assert fixture.environment == {}


def test_mitel_serial_fixture_replays_pms_to_pbx_enq_chk_transactions():
    fixture = load_fixtures(FIXTURE_PATH)[0]
    serial = fixture.environment["serial"]
    session = MitelSerialSessionStateMachine(
        baud_rate=serial["baud_rate"],
        data_bits=serial["data_bits"],
        parity=serial["parity"],
        stop_bits=serial["stop_bits"],
        flow_control=serial["flow_control"],
    )
    session.open()

    generated = []
    observed_records = []
    expected_tx = [step.raw for step in fixture.steps if step.direction == "tx"]

    for step in fixture.steps:
        if step.direction != "rx" or step.raw is None:
            continue
        result = session.feed(step.raw)
        generated.extend(action.data for action in result.actions)
        observed_records.extend(record.opcode for record in result.records)
        if step.expect_state is not None:
            assert session.status()["state"] == step.expect_state
        if step.expect_control == "ENQ":
            assert result.records == []
        if step.expect_record is not None:
            assert [record.opcode for record in result.records] == [step.expect_record]
            assert result.diagnostics == []

    assert observed_records == ["CHK1", "CHK0"]
    assert generated == expected_tx == [bytes((ACK,))] * 4
    assert session.status()["serial"] == serial
    assert session.status()["enq_received"] == 2
    assert session.status()["frames_received"] == 2
    assert session.status()["state"] == "idle"
