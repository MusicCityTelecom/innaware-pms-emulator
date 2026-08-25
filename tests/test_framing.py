from innaware_pms_emulator.framing import (
    ACK,
    ENQ,
    ETX,
    STX,
    FramingMode,
    control_name,
    decode_frame,
    encode_frame,
    xor_bcc,
)


def test_crlf_frame():
    wire = encode_frame(b"GI|RN101|", FramingMode.CRLF)
    assert wire == b"GI|RN101|\r\n"
    decoded = decode_frame(wire, FramingMode.CRLF)
    assert decoded.payload == b"GI|RN101|"


def test_stx_etx_frame():
    wire = encode_frame(b"TEST", FramingMode.STX_ETX)
    assert wire == bytes((STX,)) + b"TEST" + bytes((ETX,))
    assert decode_frame(wire, FramingMode.STX_ETX).payload == b"TEST"


def test_stx_etx_bcc_frame():
    wire = encode_frame(b"CALL", FramingMode.STX_ETX_BCC)
    assert wire[0] == STX
    assert wire[-2] == ETX
    assert wire[-1] == xor_bcc(b"CALL" + bytes((ETX,)))
    decoded = decode_frame(wire, FramingMode.STX_ETX_BCC)
    assert decoded.payload == b"CALL"
    assert decoded.bcc_valid is True


def test_bad_bcc_detected():
    wire = bytearray(encode_frame(b"CALL", FramingMode.STX_ETX_BCC))
    wire[-1] ^= 0xFF
    decoded = decode_frame(bytes(wire), FramingMode.STX_ETX_BCC)
    assert decoded.bcc_valid is False


def test_control_names():
    assert control_name(ENQ) == "ENQ"
    assert control_name(ACK) == "ACK"
    assert control_name(0x7F) is None
