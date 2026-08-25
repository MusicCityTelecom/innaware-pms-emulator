from datetime import datetime
from typing import Any
from .base import DecodedRecord


def _duration_minutes(seconds: int) -> int:
    return max(0, (int(seconds) + 59) // 60)


class InnFormXLAdapter:
    name = "INNFORM_XL"
    purpose = "call_accounting"

    def __init__(self, pcode: str = "TEL"):
        self.pcode = pcode[:3].ljust(3)
        self.counter = 0

    def encode_call(self, call: dict[str, Any]) -> bytes:
        self.counter = (self.counter + 1) % 1000
        dt = datetime.fromisoformat(call["timestamp"]) if call.get("timestamp") else datetime.now()
        ext = str(call.get("room", ""))[-4:].rjust(4)
        dur = str(_duration_minutes(call.get("duration_seconds", 0))).rjust(4)
        cost = f"${float(call.get('cost',0)):.2f}".rjust(7)
        number = str(call.get("number", ""))[:12].ljust(12)
        ctype = str(call.get("call_type", "D"))[:1]
        return f"{self.counter:03d}A {self.pcode} {dt:%m/%d}  {ext} {dt:%H:%M} {dur} {cost} {number}  {ctype}".encode("ascii", "replace")

    def decode(self, payload: bytes) -> DecodedRecord:
        s = payload.decode("latin-1", errors="replace").strip("\r\n")
        room = s[16:20].strip() if len(s) >= 20 else None
        fields = {
            "counter": s[0:3].strip(),
            "pcode": s[5:8].strip() if len(s) >= 8 else "",
            "date": s[9:14].strip() if len(s) >= 14 else "",
            "time": s[21:26].strip() if len(s) >= 26 else "",
            "duration": s[27:31].strip() if len(s) >= 31 else "",
            "cost": s[32:39].strip() if len(s) >= 39 else "",
            "number": s[40:52].strip() if len(s) >= 52 else "",
        }
        return DecodedRecord("call_record", room, fields, payload)


class HobisAdapter(InnFormXLAdapter):
    name = "HOBIS"
    def __init__(self): super().__init__(pcode="PST")


class BlindSmdrAdapter:
    name = "BLIND_SMDR"
    purpose = "call_accounting"
    def __init__(self):
        self.counter = 0

    def encode_call(self, call: dict[str, Any]) -> bytes:
        self.counter = (self.counter + 1) % 10000
        dt = datetime.fromisoformat(call["timestamp"]) if call.get("timestamp") else datetime.now()
        room = str(call.get("room", ""))[-4:].rjust(4)
        number = str(call.get("number", ""))[:12].ljust(12)
        desc = str(call.get("description", ""))[:16].ljust(16)
        dur = str(_duration_minutes(call.get("duration_seconds", 0))).zfill(4)
        cost = f"${float(call.get('cost',0)):.2f}".rjust(7)
        line = f"{self.counter:04d} PST{room} {dt:%m/%d} {dt:%H:%M}{number}{desc}{dur}  {cost}"
        return (line + "\r\n").encode("ascii", "replace")

    def decode(self, payload: bytes) -> DecodedRecord:
        return DecodedRecord("call_record_raw", fields={"text": payload.decode("latin-1", errors="replace").rstrip()}, raw=payload)
