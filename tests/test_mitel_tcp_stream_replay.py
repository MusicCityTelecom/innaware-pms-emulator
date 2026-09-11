from innaware_pms_emulator.framing import ACK, ENQ, NAK, FramingMode, encode_frame
from innaware_pms_emulator.protocols.mitel import Mitel1Adapter
from innaware_pms_emulator.replay import TcpStreamDecoder


ADAPTER = Mitel1Adapter()
KEEPALIVE = encode_frame(b"AREYUTHERE", FramingMode.STX_ETX)
CHECKIN = encode_frame(ADAPTER.encode_event({"action": "checkin", "room": "101"}), FramingMode.STX_ETX)
NAME = encode_frame(
    ADAPTER.encode_event(
        {
            "action": "name_update",
            "room": "101",
            "last_name": "TEST",
            "first_name": "GUEST",
            "extra": {"name_operation": "2"},
        }
    ),
    FramingMode.STX_ETX,
)


def _summary(items):
    return [(item.kind, item.control, item.payload) for item in items]


def test_mitel_tcp_capture_style_controls_and_frames_can_coalesce():
    # Capture-derived control/framing families, with synthetic guest/room data.
    stream = bytes((ENQ, ACK)) + KEEPALIVE + CHECKIN + NAME + bytes((NAK,))
    items = TcpStreamDecoder("stx_etx").feed(stream)

    assert [item.kind for item in items] == [
        "control",
        "control",
        "frame",
        "frame",
        "frame",
        "control",
    ]
    assert [item.control for item in items if item.kind == "control"] == ["ENQ", "ACK", "NAK"]
    assert [ADAPTER.decode(item.payload).kind for item in items if item.kind == "frame"] == [
        "heartbeat",
        "checkin",
        "name_update",
    ]
    assert ADAPTER.decode(items[3].payload).fields["status"] == "1"
    assert ADAPTER.decode(items[4].payload).fields["operation"] == "2"


def test_mitel_tcp_fragmentation_preserves_control_and_application_boundaries():
    decoder = TcpStreamDecoder("stx_etx")
    wire = bytes((ENQ,)) + KEEPALIVE + CHECKIN
    chunks = (wire[:2], wire[2:5], wire[5:13], wire[13:-2], wire[-2:])

    items = []
    for chunk in chunks:
        items.extend(decoder.feed(chunk))

    assert _summary(items)[0][:2] == ("control", "ENQ")
    assert [ADAPTER.decode(item.payload).kind for item in items if item.kind == "frame"] == [
        "heartbeat",
        "checkin",
    ]
    assert decoder.pending == b""


def test_mitel_tcp_partial_frame_is_retained_until_etx_arrives():
    decoder = TcpStreamDecoder("stx_etx")

    assert decoder.feed(CHECKIN[:-1]) == []
    assert decoder.pending == CHECKIN[:-1]

    items = decoder.feed(CHECKIN[-1:])
    assert len(items) == 1
    assert ADAPTER.decode(items[0].payload).kind == "checkin"
    assert decoder.pending == b""


def test_mitel_tcp_unexpected_unframed_byte_is_reported_without_losing_next_frame():
    decoder = TcpStreamDecoder("stx_etx")
    items = decoder.feed(b"X" + KEEPALIVE)

    assert items[0].kind == "error"
    assert items[0].raw == b"X"
    assert items[0].error == "unexpected byte outside STX/ETX frame"
    assert items[1].kind == "frame"
    assert ADAPTER.decode(items[1].payload).kind == "heartbeat"


def test_mitel_tcp_finish_reports_incomplete_frame_and_resets_buffer():
    decoder = TcpStreamDecoder("stx_etx")
    decoder.feed(NAME[:-1])

    final = decoder.finish()
    assert len(final) == 1
    assert final[0].kind == "error"
    assert final[0].error == "incomplete frame"
    assert decoder.pending == b""
