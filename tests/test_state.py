from innaware_pms_emulator.framing import ACK, ENQ, ETX, STX
from innaware_pms_emulator.state import CallAccountingStateMachine, FiasStateMachine


def test_fias_pms_replies_to_ls_and_tracks_state():
    sm = FiasStateMachine(role="pms")
    actions = sm.feed(b"LS|DA250825|TI001500|\r\n")
    assert sm.state == "negotiating"
    assert len(actions) == 1
    assert actions[0].payload.startswith(b"LS|DA")


def test_fias_pbx_sends_link_description_after_peer_ls():
    sm = FiasStateMachine(role="pbx")
    actions = sm.feed(bytes((STX,)) + b"LS|DA250825|TI001500|" + bytes((ETX,)))
    assert sm.state == "active"
    payloads = [x.payload for x in actions]
    assert any(x.startswith(b"LD|") for x in payloads)
    assert any(x.startswith(b"LR|RTGI|") for x in payloads)
    assert any(x.startswith(b"LA|") for x in payloads)


def test_fias_pms_answers_posting_request():
    sm = FiasStateMachine(role="pms")
    actions = sm.feed(b"PS|RN101|P#77|CTD|\r\n")
    assert len(actions) == 1
    assert b"PA|RN101|ASOK|P#77|" in actions[0].payload


def test_operaip_fias_acknowledges_enq_and_each_complete_frame():
    sm = FiasStateMachine(role="pms", ack_enq=True, ack_records=True)
    actions = sm.feed(
        bytes((ENQ, STX)) + b"LA|DA260827|TI220000|" + bytes((ETX, STX))
        + b"GI|RN101|GNTEST, GUEST|" + bytes((ETX,))
    )
    assert [action.payload for action in actions] == [bytes((ACK,)), bytes((ACK,)), bytes((ACK,))]
    assert all(action.apply_framing is False for action in actions)
    assert sm.state == "active"


def test_standard_fias_profiles_do_not_enable_legacy_control_ack_by_default():
    sm = FiasStateMachine(role="pms")
    assert sm.feed(bytes((ENQ,))) == []


def test_fias_database_sync_includes_property_guest_records():
    sm = FiasStateMachine(
        role="pms",
        sync_records_provider=lambda: [
            b"GI|RN101|GNSmith|GFJohn|",
            b"GI|RN103|GNDoe|GFJane|",
        ],
    )
    actions = sm.feed(b"DR|DA250825|TI001500|\r\n")
    payloads = [action.payload for action in actions]
    assert payloads[0].startswith(b"DS|")
    assert payloads[1] == b"GI|RN101|GNSmith|GFJohn|"
    assert payloads[2] == b"GI|RN103|GNDoe|GFJane|"
    assert payloads[-1].startswith(b"DE|")
    assert sm.last_sync_count == 2


def test_call_accounting_acknowledges_enq():
    sm = CallAccountingStateMachine()
    actions = sm.feed(bytes((ENQ,)))
    assert len(actions) == 1
    assert actions[0].payload == bytes((ACK,))
    assert actions[0].apply_framing is False


def test_call_accounting_acknowledges_line_record():
    sm = CallAccountingStateMachine()
    actions = sm.feed(b"001A TEL 08/25   101 00:13 0004 $002.75 16155551212 D\r\n")
    assert len(actions) == 1
    assert actions[0].payload == bytes((ACK,))


def test_call_accounting_ascii_y_ack_mode():
    sm = CallAccountingStateMachine(ack_type="ascii_y")
    actions = sm.feed(bytes((ENQ,)))
    assert actions[0].payload == b"y"
