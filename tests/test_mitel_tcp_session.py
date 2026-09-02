from innaware_pms_emulator.framing import ACK, ENQ, ETX, NAK, STX
from innaware_pms_emulator.mitel_session import MitelTcpSessionStateMachine


def frame(text: bytes) -> bytes:
    return bytes((STX,)) + text + bytes((ETX,))


def test_fragmented_chk1_session_acknowledges_enq_then_completed_frame():
    session = MitelTcpSessionStateMachine()
    session.connect()

    first = session.feed(bytes((ENQ,)) + frame(b"CHK1   101")[:6])
    assert [action.payload for action in first.actions] == [bytes((ACK,))]
    assert first.records == []
    assert session.peer_granted is True
    assert session.pending.startswith(bytes((STX,)))

    second = session.feed(frame(b"CHK1   101")[6:])
    assert [record.opcode for record in second.records] == ["CHK1"]
    assert [record.family for record in second.records] == ["CHK"]
    assert [action.payload for action in second.actions] == [bytes((ACK,))]
    assert second.diagnostics == []
    assert session.status()["state"] == "idle"


def test_coalesced_nam2_is_normal_capture_verified_protocol_element():
    session = MitelTcpSessionStateMachine()
    session.connect()

    result = session.feed(bytes((ENQ,)) + frame(b"NAM2 ALEX SMITH  101"))

    assert [action.payload for action in result.actions] == [bytes((ACK,)), bytes((ACK,))]
    assert len(result.records) == 1
    assert result.records[0].opcode == "NAM2"
    assert result.records[0].family == "NAM"
    assert result.records[0].evidence_class == "packet_capture_verified"
    assert result.diagnostics == []


def test_areyouthere_keepalive_is_acknowledged_and_counted():
    session = MitelTcpSessionStateMachine()
    session.connect()

    result = session.feed(bytes((ENQ,)) + frame(b"AREYUTHERE"))

    assert [record.opcode for record in result.records] == ["AREYUTHERE"]
    assert [action.payload for action in result.actions] == [bytes((ACK,)), bytes((ACK,))]
    assert session.status()["keepalives_received"] == 1


def test_bare_ack_nak_controls_are_outbound_transaction_responses_only():
    session = MitelTcpSessionStateMachine()
    session.connect()

    result = session.feed(bytes((ACK, NAK)))

    assert result.response_controls == [ACK, NAK]
    assert result.actions == []
    assert result.records == []
    assert session.status()["state"] == "idle"


def test_control_byte_values_inside_application_frame_are_not_misclassified():
    session = MitelTcpSessionStateMachine()
    session.connect()

    payload = b"NAM2 AL" + bytes((ACK, NAK)) + b"ICE 101"
    result = session.feed(bytes((ENQ,)) + frame(payload))

    assert result.response_controls == []
    assert [record.opcode for record in result.records] == ["NAM2"]
    assert [action.payload for action in result.actions] == [bytes((ACK,)), bytes((ACK,))]


def test_frame_without_enq_fails_half_duplex_gate_with_structured_diagnostic():
    session = MitelTcpSessionStateMachine()
    session.connect()

    result = session.feed(frame(b"CHK1   101"))

    assert result.records == []
    assert [action.payload for action in result.actions] == [bytes((NAK,))]
    assert result.diagnostics[0].code == "mitel_tcp_frame_without_enq"
    assert result.diagnostics[0].confidence == "high"
    assert "ENQ -> ACK" in result.diagnostics[0].expected


def test_invalid_chk_status_opens_message_only_retry_window_without_second_enq():
    session = MitelTcpSessionStateMachine()
    session.connect()

    first = session.feed(bytes((ENQ,)) + frame(b"CHK3   101"))
    assert [action.payload for action in first.actions] == [bytes((ACK,)), bytes((NAK,))]
    assert first.diagnostics[-1].code == "mitel_tcp_invalid_chk_status"
    assert session.status()["state"] == "peer_retry_window"
    assert session.status()["peer_record_attempts"] == 1

    retry = session.feed(frame(b"CHK1   101"))
    assert [record.opcode for record in retry.records] == ["CHK1"]
    assert [action.payload for action in retry.actions] == [bytes((ACK,))]
    assert retry.diagnostics == []
    assert session.status()["state"] == "idle"
    assert session.status()["peer_record_attempts"] == 2


def test_application_retry_window_closes_after_initial_plus_three_retries():
    session = MitelTcpSessionStateMachine()
    session.connect()

    first = session.feed(bytes((ENQ,)) + frame(b"CHK3   101"))
    assert session.peer_retry_window is True
    assert first.diagnostics[-1].code == "mitel_tcp_invalid_chk_status"

    third_retry = None
    for _ in range(3):
        third_retry = session.feed(frame(b"CHK3   101"))

    assert third_retry is not None
    codes = [item.code for item in third_retry.diagnostics]
    assert "mitel_tcp_record_retry_budget_exhausted" in codes
    assert session.peer_retry_window is False
    assert session.status()["peer_record_attempts"] == 4

    extra = session.feed(frame(b"CHK3   101"))
    assert extra.diagnostics[0].code == "mitel_tcp_frame_without_enq"
    assert [action.payload for action in extra.actions] == [bytes((NAK,))]


def test_disconnect_discards_partial_frame_and_reconnect_starts_clean_session():
    session = MitelTcpSessionStateMachine()
    session.connect()
    session.feed(bytes((ENQ,)) + bytes((STX,)) + b"NAM2 PART")

    diagnostics = session.disconnect()
    assert diagnostics[0].code == "mitel_tcp_disconnect_incomplete_frame"
    assert session.status()["state"] == "disconnected"
    assert session.pending == b""

    session.connect()
    result = session.feed(bytes((ENQ,)) + frame(b"CHK0   101"))
    assert [record.opcode for record in result.records] == ["CHK0"]
    assert session.status()["connection_generation"] == 2


def test_uncharacterized_message_is_nakd_without_silent_profile_switch():
    session = MitelTcpSessionStateMachine()
    session.connect()

    result = session.feed(bytes((ENQ,)) + frame(b"SHELL_EXEC whatever"))

    assert result.records == []
    assert [action.payload for action in result.actions] == [bytes((ACK,)), bytes((NAK,))]
    finding = result.diagnostics[-1]
    assert finding.code == "mitel_tcp_uncharacterized_message"
    assert "selected PBX/PMS dialect" in finding.corrective_action


def test_feed_requires_explicit_connection_boundary():
    session = MitelTcpSessionStateMachine()

    try:
        session.feed(bytes((ENQ,)))
    except RuntimeError as exc:
        assert "must be connected" in str(exc)
    else:
        raise AssertionError("disconnected Mitel TCP session accepted bytes")
