from innaware_pms_emulator.framing import ACK, ENQ, ETX, NAK, STX
from innaware_pms_emulator.mitel_serial_session import MitelSerialSessionStateMachine


def test_mitel_serial_session_models_legacy_profile_settings_and_handshake():
    session = MitelSerialSessionStateMachine()
    session.open()

    status = session.status()
    assert status["transport"] == "serial"
    assert status["framing"] == "stx_etx"
    assert status["serial"] == {
        "baud_rate": 1200,
        "data_bits": 8,
        "parity": "N",
        "stop_bits": 1.0,
        "flow_control": "xonxoff",
    }
    assert status["evidence_class"] == "legacy_source_profile_verified"

    result = session.feed(bytes((ENQ, STX)) + b"CHK1ROOM101" + bytes((ETX,)))
    assert [action.payload for action in result.actions] == [bytes((ACK,)), bytes((ACK,))]
    assert [record.opcode for record in result.records] == ["CHK1"]
    assert result.records[0].family == "CHK"
    assert result.diagnostics == []
    assert session.status()["state"] == "idle"


def test_mitel_serial_session_handles_fragmented_and_coalesced_driver_reads():
    session = MitelSerialSessionStateMachine()
    session.open()

    first = session.feed(bytes((ENQ, STX)) + b"NAM2TEST,G")
    assert [action.payload for action in first.actions] == [bytes((ACK,))]
    assert first.records == []
    assert session.status()["pending_bytes"] > 0

    second = session.feed(b"UEST101" + bytes((ETX, ACK, NAK)))
    assert [record.opcode for record in second.records] == ["NAM2"]
    assert second.records[0].evidence_class == "legacy_simulator_characterized"
    assert [action.payload for action in second.actions] == [bytes((ACK,))]
    assert second.response_controls == [ACK, NAK]
    assert session.status()["pending_bytes"] == 0


def test_mitel_serial_session_rejects_frame_without_enq():
    session = MitelSerialSessionStateMachine()
    session.open()

    result = session.feed(bytes((STX,)) + b"CHK0ROOM101" + bytes((ETX,)))
    assert result.records == []
    assert [action.payload for action in result.actions] == [bytes((NAK,))]
    assert result.diagnostics[-1].code == "mitel_serial_frame_without_enq"
    assert result.diagnostics[-1].evidence_class == "legacy_source_profile_verified"
    assert "ENQ" in result.diagnostics[-1].expected


def test_mitel_serial_session_preserves_normal_chk_and_nam_statuses():
    session = MitelSerialSessionStateMachine()
    session.open()

    for payload in (b"CHK0ROOM101", b"CHK1ROOM101", b"NAM1TEST101", b"NAM2TEST101", b"NAM3TEST101", b"NAM4TEST101"):
        result = session.feed(bytes((ENQ, STX)) + payload + bytes((ETX,)))
        assert len(result.records) == 1
        assert not any("invalid" in diagnostic.code for diagnostic in result.diagnostics)


def test_mitel_serial_session_rejects_invalid_status_and_keeps_retry_window():
    session = MitelSerialSessionStateMachine()
    session.open()

    result = session.feed(bytes((ENQ, STX)) + b"CHK3ROOM101" + bytes((ETX,)))
    assert result.records == []
    assert [action.payload for action in result.actions] == [bytes((ACK,)), bytes((NAK,))]
    assert result.diagnostics[-1].code == "mitel_serial_invalid_chk_status"
    assert result.diagnostics[-1].evidence_class == "operator_confirmed_behavior"
    assert session.status()["state"] == "peer_retry_window"


def test_mitel_serial_session_close_discards_partial_frame():
    session = MitelSerialSessionStateMachine()
    session.open()
    session.feed(bytes((ENQ, STX)) + b"CHK1PARTIAL")

    diagnostics = session.close()
    assert diagnostics[-1].code == "mitel_serial_close_incomplete_frame"
    assert session.status()["state"] == "closed"
    assert session.status()["pending_bytes"] == 0

    session.open()
    result = session.feed(bytes((ENQ, STX)) + b"CHK1ROOM102" + bytes((ETX,)))
    assert [record.opcode for record in result.records] == ["CHK1"]


def test_mitel_serial_session_diagnostic_calls_out_serial_parameter_mismatch():
    session = MitelSerialSessionStateMachine()
    session.open()

    result = session.feed(b"X")
    diagnostic = result.diagnostics[-1]
    assert diagnostic.code == "mitel_serial_framing_error"
    assert diagnostic.confidence == "high"
    assert "baud/data/parity/stop" in diagnostic.corrective_action
