from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

from .base import DecodedRecord


def _duration_minutes(seconds: int) -> int:
    return max(0, (int(seconds) + 59) // 60)


def _money(value: Any) -> Decimal:
    try:
        amount = Decimal(str(value or 0))
    except (InvalidOperation, ValueError):
        amount = Decimal("0")
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _datetime(call: dict[str, Any]) -> datetime:
    return datetime.fromisoformat(call["timestamp"]) if call.get("timestamp") else datetime.now()


class InnFormXLAdapter:
    """TelElectronics InnForm XL/TEL compatibility formatter.

    This intentionally preserves the field-tested `001A TEL ...` family used by
    existing InnForm XL installations rather than conflating it with HOBIS-A.
    """

    name = "INNFORM_XL"
    purpose = "call_accounting"

    def __init__(self, pcode: str = "TEL"):
        self.pcode = pcode[:3].ljust(3)
        self.counter = 0

    def encode_call(self, call: dict[str, Any]) -> bytes:
        self.counter = (self.counter + 1) % 1000
        dt = _datetime(call)
        ext = str(call.get("room", ""))[-4:].rjust(4)
        dur = str(_duration_minutes(call.get("duration_seconds", 0))).rjust(4)
        cost = f"${_money(call.get('cost', 0)):.2f}".rjust(7)
        number = str(call.get("number", ""))[:12].ljust(12)
        ctype = str(call.get("call_type", "D"))[:1] or " "
        return f"{self.counter:03d}A {self.pcode} {dt:%m/%d}  {ext} {dt:%H:%M} {dur} {cost} {number}  {ctype}".encode("ascii", "replace")

    def decode(self, payload: bytes) -> DecodedRecord:
        s = payload.decode("latin-1", errors="replace").strip("\r\n")
        room = s[16:20].strip() if len(s) >= 20 else None
        fields = {
            "counter": s[0:4].strip(),
            "pcode": s[5:8].strip() if len(s) >= 8 else "",
            "date": s[9:14].strip() if len(s) >= 14 else "",
            "time": s[21:26].strip() if len(s) >= 26 else "",
            "duration": s[27:31].strip() if len(s) >= 31 else "",
            "cost": s[32:39].strip() if len(s) >= 39 else "",
            "number": s[40:52].strip() if len(s) >= 52 else "",
        }
        return DecodedRecord("call_record", room, fields, payload)


class HobisAdapter:
    """HOBIS-A fixed-field costed-call record.

    Verified layout (1-based positions):
      01-04 CCCC counter
      06-08 PPP  property code
      10-14 MM/DD
      17-20 EEEE extension
      22-26 HH:MM
      28-31 MMMM duration in whole minutes
      33-39 $DDD.CC
      41-52 NNNNNNNNNNNN number dialed
      54    D description/type
    """

    name = "HOBIS"
    purpose = "call_accounting"

    def __init__(self, pcode: str = "PST"):
        self.pcode = pcode[:3].ljust(3)
        self.counter = 0

    def encode_call(self, call: dict[str, Any]) -> bytes:
        self.counter = (self.counter % 9999) + 1
        dt = _datetime(call)
        room = str(call.get("room", ""))[-4:].rjust(4)
        duration = f"{min(_duration_minutes(call.get('duration_seconds', 0)), 9999):04d}"
        cost_value = max(Decimal("0"), min(_money(call.get("cost", 0)), Decimal("999.99")))
        cost = f"${cost_value:06.2f}"
        number = str(call.get("number", ""))[:12].ljust(12)
        description = str(call.get("call_type", "D"))[:1] or " "
        record = (
            f"{self.counter:04d} {self.pcode} {dt:%m/%d}  {room} {dt:%H:%M} "
            f"{duration} {cost} {number} {description}"
        )
        return record.encode("ascii", "replace")

    def decode(self, payload: bytes) -> DecodedRecord:
        s = payload.decode("latin-1", errors="replace").strip("\r\n")
        room = s[16:20].strip() if len(s) >= 20 else None
        fields = {
            "counter": s[0:4].strip() if len(s) >= 4 else "",
            "pcode": s[5:8].strip() if len(s) >= 8 else "",
            "date": s[9:14].strip() if len(s) >= 14 else "",
            "extension": room or "",
            "time": s[21:26].strip() if len(s) >= 26 else "",
            "duration": s[27:31].strip() if len(s) >= 31 else "",
            "cost": s[32:39].strip() if len(s) >= 39 else "",
            "number": s[40:52].strip() if len(s) >= 52 else "",
            "description": s[53:54] if len(s) >= 54 else "",
        }
        return DecodedRecord("call_record", room, fields, payload)


class HobisAAdapter(HobisAdapter):
    name = "HOBIS_A"


class HolidexAdapter(HobisAdapter):
    name = "HOLIDEX"


class BlindSmdrAdapter:
    name = "BLIND_SMDR"
    purpose = "call_accounting"

    def __init__(self):
        self.counter = 0

    def encode_call(self, call: dict[str, Any]) -> bytes:
        self.counter = (self.counter + 1) % 10000
        dt = _datetime(call)
        room = str(call.get("room", ""))[-4:].rjust(4)
        number = str(call.get("number", ""))[:12].ljust(12)
        desc = str(call.get("description", ""))[:16].ljust(16)
        dur = str(_duration_minutes(call.get("duration_seconds", 0))).zfill(4)
        cost = f"${_money(call.get('cost', 0)):.2f}".rjust(7)
        line = f"{self.counter:04d} PST{room} {dt:%m/%d} {dt:%H:%M}{number}{desc}{dur}  {cost}"
        return (line + "\r\n").encode("ascii", "replace")

    def decode(self, payload: bytes) -> DecodedRecord:
        return DecodedRecord("call_record_raw", fields={"text": payload.decode("latin-1", errors="replace").rstrip()}, raw=payload)
