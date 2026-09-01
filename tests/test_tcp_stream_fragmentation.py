from innaware_pms_emulator.framing import ACK, ENQ, FramingMode, encode_frame
from innaware_pms_emulator.protocols.fias import FiasAdapter
from innaware_pms_emulator.replay import TcpStreamDecoder


LS = encode_frame(b"LS|DA000101|TI000000|", FramingMode.STX_ETX)
LA = encode_frame(b"LA|DA000101|TI000030|", FramingMode.STX_ETX)


def _record_types(items):
    adapter = FiasAdapter()
    return [adapter.decode(item.payload).kind for item in items if item.kind == "frame"]


def test_one_full_stx_etx_record_in_one_read():
    items = TcpStreamDecoder("stx_etx").feed(LS)
    assert _record_types(items) == ["link_start"]


def test_one_record_split_across_several_reads():
    decoder = TcpStreamDecoder("stx_etx")
    items = []
    for chunk in (LS[:1], LS[1:5], LS[5:-1], LS[-1:]):
        items.extend(decoder.feed(chunk))
    assert _record_types(items) == ["link_start"]
    assert decoder.pending == b""


def test_two_records_in_one_read():
    items = TcpStreamDecoder("stx_etx").feed(LS + LA)
    assert _record_types(items) == ["link_start", "link_alive"]


def test_enq_and_framed_record_in_one_read():
    items = TcpStreamDecoder("stx_etx").feed(bytes((ENQ,)) + LS)
    assert [(item.kind, item.control) for item in items] == [
        ("control", "ENQ"), ("frame", None)
    ]
    assert _record_types(items) == ["link_start"]


def test_ack_and_next_frame_coalesced():
    items = TcpStreamDecoder("stx_etx").feed(bytes((ACK,)) + LA)
    assert items[0].control == "ACK"
    assert _record_types(items) == ["link_alive"]


def test_crlf_stream_records_may_split_and_coalesce_too():
    decoder = TcpStreamDecoder("crlf")
    assert decoder.feed(b"LS|DA000101|") == []
    items = decoder.feed(b"TI000000|\r\nLA|DA000101|TI000030|\r\n")
    assert _record_types(items) == ["link_start", "link_alive"]
