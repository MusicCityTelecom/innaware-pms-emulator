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
