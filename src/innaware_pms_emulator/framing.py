from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

NUL = 0x00
ENQ = 0x05
ACK = 0x06
NAK = 0x15
STX = 0x02
ETX = 0x03
CR = 0x0D
LF = 0x0A


class FramingMode(str, Enum):
    RAW = "raw"
    CR = "cr"
    LF = "lf"
    CRLF = "crlf"
    STX_ETX = "stx_etx"
    STX_ETX_BCC = "stx_etx_bcc"


@dataclass(slots=True)
class Frame:
    raw: bytes
    payload: bytes
    framing: FramingMode
    bcc_valid: bool | None = None


def xor_bcc(data: bytes) -> int:
    value = 0
    for byte in data:
        value ^= byte
    return value


def encode_frame(payload: bytes, mode: FramingMode | str) -> bytes:
    mode = FramingMode(mode)
    if mode is FramingMode.RAW:
        return payload
    if mode is FramingMode.CR:
        return payload.rstrip(b"\r\n") + b"\r"
    if mode is FramingMode.LF:
        return payload.rstrip(b"\r\n") + b"\n"
    if mode is FramingMode.CRLF:
        return payload.rstrip(b"\r\n") + b"\r\n"
    if mode is FramingMode.STX_ETX:
        return bytes((STX,)) + payload + bytes((ETX,))
    if mode is FramingMode.STX_ETX_BCC:
        body = payload + bytes((ETX,))
        return bytes((STX,)) + body + bytes((xor_bcc(body),))
    raise ValueError(f"Unsupported framing mode: {mode}")


def decode_frame(raw: bytes, mode: FramingMode | str) -> Frame:
    mode = FramingMode(mode)
    if mode is FramingMode.RAW:
        return Frame(raw=raw, payload=raw, framing=mode)
    if mode is FramingMode.CR:
        return Frame(raw=raw, payload=raw.rstrip(b"\r"), framing=mode)
    if mode is FramingMode.LF:
        return Frame(raw=raw, payload=raw.rstrip(b"\n"), framing=mode)
    if mode is FramingMode.CRLF:
        return Frame(raw=raw, payload=raw.rstrip(b"\r\n"), framing=mode)
    if mode is FramingMode.STX_ETX:
        if len(raw) < 2 or raw[0] != STX or raw[-1] != ETX:
            raise ValueError("Invalid STX/ETX frame")
        return Frame(raw=raw, payload=raw[1:-1], framing=mode)
    if mode is FramingMode.STX_ETX_BCC:
        if len(raw) < 3 or raw[0] != STX or raw[-2] != ETX:
            raise ValueError("Invalid STX/ETX/BCC frame")
        body = raw[1:-1]
        expected = xor_bcc(body)
        return Frame(
            raw=raw,
            payload=raw[1:-2],
            framing=mode,
            bcc_valid=(expected == raw[-1]),
        )
    raise ValueError(f"Unsupported framing mode: {mode}")


def control_name(value: int) -> str | None:
    return {
        ENQ: "ENQ",
        ACK: "ACK",
        NAK: "NAK",
        STX: "STX",
        ETX: "ETX",
        CR: "CR",
        LF: "LF",
    }.get(value)
