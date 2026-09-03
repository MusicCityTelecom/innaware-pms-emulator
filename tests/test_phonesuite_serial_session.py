from innaware_pms_emulator.framing import ACK, ENQ, ETX, NAK, STX
from innaware_pms_emulator.phonesuite_serial_session import PhoneSuiteSerialSessionStateMachine


def framed(payload: bytes) -> bytes:
    return bytes((STX,)) + payload + bytes((ETX,))


def test_phonesuite_serial_characterized_chk_sequence() -> None:
    session = PhoneSuiteSerialSessionStateMachine()
    session.open()

    grant = session.feed(bytes((ENQ,)))
    assert [action.payload for action in grant.actions] == [bytes((ACK,))]
    assert session.status()["state"] == "peer_granted"

    record = session.feed(framed(b"CHK1ROOM101"))
    assert [item.opcode for item in record.records] == ["CHK1"]
    assert [action.payload for action in record.actions] == [bytes((ACK,))]
    assert not record.diagnostics
    assert session.status()["state"] == "idle"


def test_phonesuite_serial_fragmented_nam2_sequence() -> None:
    session = PhoneSuiteSerialSessionStateMachine()
    session.open()
    session.feed(bytes((ENQ,)))

    first = session.feed(bytes((STX,)) + b"NAM2TEST,")
    assert not first.records
    assert not first.actions
    assert session.status()["pending_bytes"] > 0

    second = session.feed(b"GUESTROOM101" + bytes((ETX,)))
    assert [item.opcode for item in second.records] == ["NAM2"]
    assert second.records[0].payload == b"NAM2TEST,GUESTROOM101"
    assert [action.payload for action in second.actions] == [bytes((ACK,))]


def test_phonesuite_serial_chk0_is_characterized() -> None:
    session = PhoneSuiteSerialSessionStateMachine()
    session.open()
    session.feed(bytes((ENQ,)))

    result = session.feed(framed(b"CHK0ROOM101"))
    assert [item.opcode for item in result.records] == ["CHK0"]
    assert [action.payload for action in result.actions] == [bytes((ACK,))]


def test_phonesuite_serial_does_not_promote_other_mitel_family_records() -> None:
    session = PhoneSuiteSerialSessionStateMachine()
    session.open()
    session.feed(bytes((ENQ,)))

    result = session.feed(framed(b"WKP0715ROOM101"))
    assert not result.records
    assert not result.actions
    assert [item.code for item in result.diagnostics] == ["phonesuite_serial_uncharacterized_record"]
    assert "another PBX family" in result.diagnostics[0].corrective_action


def test_phonesuite_serial_requires_characterized_enq_grant() -> None:
    session = PhoneSuiteSerialSessionStateMachine()
    session.open()

    result = session.feed(framed(b"CHK1ROOM101"))
    assert not result.records
    assert not result.actions
    assert [item.code for item in result.diagnostics] == ["phonesuite_serial_frame_without_enq"]
    assert "Series2 D-channel" in result.diagnostics[0].corrective_action


def test_phonesuite_serial_routes_peer_ack_and_nak_without_treating_them_as_frames() -> None:
    session = PhoneSuiteSerialSessionStateMachine()
    session.open()

    result = session.feed(bytes((ACK, NAK)))
    assert result.response_controls == [ACK, NAK]
    assert not result.records
    assert not result.actions


def test_phonesuite_serial_close_reports_and_resets_incomplete_frame() -> None:
    session = PhoneSuiteSerialSessionStateMachine()
    session.open()
    session.feed(bytes((ENQ, STX)) + b"CHK1ROOM")

    diagnostics = session.close()
    assert [item.code for item in diagnostics] == ["phonesuite_serial_close_incomplete_frame"]
    assert session.status()["state"] == "closed"
    assert session.status()["pending_bytes"] == 0

    session.open()
    result = session.feed(bytes((ENQ,)) + framed(b"CHK1ROOM101"))
    assert [item.opcode for item in result.records] == ["CHK1"]


def test_phonesuite_serial_status_does_not_claim_unverified_serial_defaults() -> None:
    session = PhoneSuiteSerialSessionStateMachine()
    session.open()

    status = session.status()
    assert status["pbx_family"] == "PhoneSuite"
    assert status["serial_defaults"] == "unqualified_configurable"
    assert status["evidence_class"] == "simulator_characterization"
    assert "baud_rate" not in status
    assert "parity" not in status
