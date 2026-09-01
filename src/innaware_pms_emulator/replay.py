from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from .framing import ACK, ENQ, ETX, NAK, STX, FramingMode, decode_frame


CONTROL_NAMES = {ENQ: "ENQ", ACK: "ACK", NAK: "NAK"}
MATURITY_VALUES = {"supported", "partially_characterized", "capture_only", "incompatible"}


@dataclass(frozen=True, slots=True)
class StreamItem:
    kind: str
    raw: bytes
    payload: bytes = b""
    framing: FramingMode | None = None
    control: str | None = None
    bcc_valid: bool | None = None
    error: str | None = None


class TcpStreamDecoder:
    """Incrementally split controls and application frames from a TCP byte stream.

    TCP reads are deliberately treated as arbitrary chunks. The decoder retains
    incomplete records between calls and emits every complete item in order.
    """

    def __init__(self, framing: FramingMode | str) -> None:
        self.framing = FramingMode(framing)
        self._buffer = bytearray()

    @property
    def pending(self) -> bytes:
        return bytes(self._buffer)

    def feed(self, chunk: bytes) -> list[StreamItem]:
        self._buffer.extend(chunk)
        items: list[StreamItem] = []
        while self._buffer:
            first = self._buffer[0]
            if first in CONTROL_NAMES:
                del self._buffer[0]
                items.append(StreamItem("control", bytes((first,)), control=CONTROL_NAMES[first]))
                continue
            if self.framing in {FramingMode.STX_ETX, FramingMode.STX_ETX_BCC}:
                item = self._next_stx_item()
            elif self.framing in {FramingMode.CR, FramingMode.LF, FramingMode.CRLF}:
                item = self._next_line_item()
            else:
                raw = bytes(self._buffer)
                self._buffer.clear()
                item = StreamItem("frame", raw, raw, FramingMode.RAW)
            if item is None:
                break
            items.append(item)
        return items

    def finish(self) -> list[StreamItem]:
        if not self._buffer:
            return []
        raw = bytes(self._buffer)
        self._buffer.clear()
        return [StreamItem("error", raw, error="incomplete frame")]

    def _next_stx_item(self) -> StreamItem | None:
        if self._buffer[0] != STX:
            raw = bytes((self._buffer.pop(0),))
            return StreamItem("error", raw, error="unexpected byte outside STX/ETX frame")
        nested = self._buffer.find(bytes((STX,)), 1)
        end = self._buffer.find(bytes((ETX,)), 1)
        if nested != -1 and (end == -1 or nested < end):
            raw = bytes(self._buffer[:nested])
            del self._buffer[:nested]
            return StreamItem("error", raw, error="nested STX before ETX")
        if end == -1:
            return None
        length = end + (2 if self.framing is FramingMode.STX_ETX_BCC else 1)
        if len(self._buffer) < length:
            return None
        raw = bytes(self._buffer[:length])
        del self._buffer[:length]
        frame = decode_frame(raw, self.framing)
        return StreamItem("frame", raw, frame.payload, frame.framing, bcc_valid=frame.bcc_valid)

    def _next_line_item(self) -> StreamItem | None:
        delimiter = {
            FramingMode.CR: b"\r",
            FramingMode.LF: b"\n",
            FramingMode.CRLF: b"\r\n",
        }[self.framing]
        end = self._buffer.find(delimiter)
        if end == -1:
            return None
        length = end + len(delimiter)
        raw = bytes(self._buffer[:length])
        del self._buffer[:length]
        frame = decode_frame(raw, self.framing)
        return StreamItem("frame", raw, frame.payload, frame.framing)


@dataclass(frozen=True, slots=True)
class ReplayStep:
    direction: str
    raw: bytes | None = None
    expect_framing: str | None = None
    expect_record: str | None = None
    expect_control: str | None = None
    expect_state: str | None = None
    timing: dict[str, Any] = field(default_factory=dict)
    fault: str | None = None


@dataclass(frozen=True, slots=True)
class ReplayFixture:
    fixture_id: str
    personality: str
    protocol: str
    framing: str
    status: str
    sanitized: bool
    evidence: str
    steps: tuple[ReplayStep, ...]


def bytes_from_step(value: dict[str, Any]) -> bytes | None:
    if "hex" in value and "text" in value:
        raise ValueError("fixture step cannot define both hex and text")
    if "hex" in value:
        return bytes.fromhex(value["hex"])
    if "text" in value:
        return value["text"].encode(value.get("encoding", "latin-1"))
    return None


def fixture_from_dict(value: dict[str, Any]) -> ReplayFixture:
    status = value["status"]
    if status not in MATURITY_VALUES:
        raise ValueError(f"invalid fixture status: {status}")
    if value.get("sanitized") is not True:
        raise ValueError("all permanent interoperability fixtures must be explicitly sanitized")
    steps = tuple(
        ReplayStep(
            direction=step["direction"],
            raw=bytes_from_step(step),
            expect_framing=step.get("expect_framing"),
            expect_record=step.get("expect_record"),
            expect_control=step.get("expect_control"),
            expect_state=step.get("expect_state"),
            timing=dict(step.get("timing", {})),
            fault=step.get("fault"),
        )
        for step in value.get("steps", [])
    )
    if any(step.direction not in {"rx", "tx", "disconnect", "time"} for step in steps):
        raise ValueError("invalid fixture step direction")
    return ReplayFixture(
        fixture_id=value["id"],
        personality=value["personality"],
        protocol=value["protocol"],
        framing=value["framing"],
        status=status,
        sanitized=True,
        evidence=value["evidence"],
        steps=steps,
    )


def load_fixtures(path: str | Path) -> tuple[ReplayFixture, ...]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    values: Iterable[dict[str, Any]] = data if isinstance(data, list) else data["fixtures"]
    fixtures = tuple(fixture_from_dict(value) for value in values)
    ids = [fixture.fixture_id for fixture in fixtures]
    if len(ids) != len(set(ids)):
        raise ValueError("fixture ids must be unique")
    return fixtures
