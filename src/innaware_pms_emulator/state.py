from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from .framing import ACK, ENQ, ETX, NAK, STX


def _now_fields() -> tuple[str, str]:
    now = datetime.now()
    return now.strftime("%y%m%d"), now.strftime("%H%M%S")


@dataclass(slots=True)
class EngineAction:
    payload: bytes
    note: str
    apply_framing: bool = True


@dataclass
class FiasStateMachine:
    role: str = "pms"
    state: str = "down"
    buffer: bytearray = field(default_factory=bytearray)
    current_frame: bytearray = field(default_factory=bytearray)
    in_frame: bool = False

    def status(self) -> dict[str, str]:
        return {"engine": "fias", "role": self.role, "link_state": self.state}

    def feed(self, data: bytes) -> list[EngineAction]:
        actions: list[EngineAction] = []
        for b in data:
            if b == STX and not self.in_frame:
                self.in_frame = True
                self.current_frame.clear()
                continue
            if self.in_frame:
                if b == ETX:
                    payload = bytes(self.current_frame).decode("ascii", errors="replace")
                    self.current_frame.clear()
                    self.in_frame = False
                    actions.extend(self._handle_record(payload))
                else:
                    self.current_frame.append(b)
                continue

            self.buffer.append(b)
            if b == 0x0A:
                raw = bytes(self.buffer).rstrip(b"\r\n")
                self.buffer.clear()
                if raw:
                    actions.extend(self._handle_record(raw.decode("ascii", errors="replace")))
            elif len(self.buffer) > 16384:
                self.buffer.clear()
        return actions

    def _handle_record(self, record: str) -> list[EngineAction]:
        record = record.strip("\x00\r\n")
        if not record:
            return []
        rt = record.split("|", 1)[0].upper()
        d, t = _now_fields()

        if rt == "LS":
            if self.role.lower() == "pms":
                self.state = "negotiating"
                return [EngineAction(f"LS|DA{d}|TI{t}|".encode(), "FIAS LS reply")]
            self.state = "active"
            records = [
                f"LD|DA{d}|TI{t}|",
                "LR|RTGI|RN|G#|GN|GF|GL|GV|CS|GA|GD|GS||",
                "LR|RTGO|RN|G#|GS||",
                "LR|RTGC|RN|RO|G#|GN|GF|GL|GV|CS||",
                "LR|RTRE|RN|ML|DN|RS|CS||",
                "LR|RTWR|RN|DA|TI||",
                "LR|RTWA|RN|DA|TI|AS||",
                "LR|RTWC|RN|DA|TI||",
                "LR|RTPS|RN|TA|DA|TI|DU|P#|DD|PC|CT|PT||",
                "LR|RTPA|RN|AS|P#|DA|TI||",
                "LR|RTDR|DA|TI||",
                "LR|RTDS|DA|TI||",
                "LR|RTDE|DA|TI||",
                f"LA|DA{d}|TI{t}|",
            ]
            return [EngineAction(x.encode(), "FIAS link description") for x in records]

        if rt == "LA":
            self.state = "active"
        elif rt == "LE":
            self.state = "down"
        elif rt == "LD" and self.state == "down":
            self.state = "negotiating"
        elif rt == "PS" and self.role.lower() == "pms":
            rn = self._field(record, "RN")
            pid = self._field(record, "P#") or "1"
            return [EngineAction(
                f"PA|RN{rn}|ASOK|P#{pid}|DA{d}|TI{t}|".encode(),
                "FIAS posting answer",
            )]
        elif rt == "DR" and self.role.lower() == "pms":
            return [
                EngineAction(f"DS|DA{d}|TI{t}|".encode(), "FIAS database sync start"),
                EngineAction(f"DE|DA{d}|TI{t}|".encode(), "FIAS database sync end"),
            ]
        return []

    @staticmethod
    def _field(record: str, name: str) -> str:
        needle = f"|{name}"
        idx = record.find(needle)
        if idx < 0:
            return ""
        start = idx + len(needle)
        end = record.find("|", start)
        return record[start:] if end < 0 else record[start:end]


@dataclass
class CallAccountingStateMachine:
    ack_type: str = "ack"
    auto_ack: bool = True
    ack_enq: bool = True

    def status(self) -> dict[str, str | bool]:
        return {
            "engine": "call_accounting",
            "ack_type": self.ack_type,
            "auto_ack": self.auto_ack,
            "ack_enq": self.ack_enq,
        }

    def ack_bytes(self) -> bytes:
        if self.ack_type.lower() in {"y", "ascii_y", "ascii y"}:
            return b"y"
        return bytes((ACK,))

    def feed(self, data: bytes) -> list[EngineAction]:
        actions: list[EngineAction] = []
        if self.ack_enq and self.auto_ack and bytes((ENQ,)) in data:
            actions.append(EngineAction(self.ack_bytes(), "call accounting ACK ENQ", apply_framing=False))

        if not self.auto_ack:
            return actions

        # Do not ACK bare ACK/NAK control responses. Any actual framed or line-oriented
        # payload is treated as a received call record and acknowledged.
        controls_only = all(b in {ACK, NAK, ENQ, 0x0D, 0x0A} for b in data)
        has_record = (STX in data and ETX in data) or (
            not controls_only and (b"\n" in data or b"\r" in data)
        )
        if has_record:
            actions.append(EngineAction(self.ack_bytes(), "call accounting record ACK", apply_framing=False))
        return actions
