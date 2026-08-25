from typing import Any
from .base import DecodedRecord


def _fields(record: str) -> tuple[str, dict[str, str]]:
    record = record.strip("\r\n")
    parts = record.split("|")
    code = parts[0][:2]
    out: dict[str, str] = {}
    for token in parts[1:]:
        if len(token) >= 2:
            out[token[:2]] = token[2:]
    return code, out


class FiasAdapter:
    name = "FIAS"
    purpose = "pms"

    def __init__(self, hilton: bool = False):
        self.hilton = hilton

    @staticmethod
    def _line(code: str, *fields: tuple[str, Any]) -> bytes:
        body = "|".join([code] + [f"{key}{value}" for key, value in fields if value not in (None, "")])
        return (body + "|\r\n").encode("latin-1")

    def encode_event(self, event: dict[str, Any]) -> bytes:
        action = event["action"].lower()
        room = event.get("room", "")
        last = event.get("last_name", "")
        first = event.get("first_name", "")
        if action == "checkin":
            fields = [("RN", room), ("GN", last)]
            if first and not self.hilton:
                fields.append(("GF", first))
            return self._line("GI", *fields)
        if action == "checkout":
            return self._line("GO", ("RN", room))
        if action in ("name", "name_update"):
            fields = [("RN", room), ("GN", last)]
            if first and not self.hilton:
                fields.append(("GF", first))
            return self._line("GC", *fields)
        if action == "wakeup_set":
            return self._line("WR", ("RN", room), ("DA", event.get("wakeup_date")), ("TI", event.get("wakeup_time")))
        if action == "wakeup_cancel":
            return self._line("WC", ("RN", room))
        if action == "link_start":
            return self._line("LS")
        if action == "link_description":
            return self._line("LD", ("IF", event.get("interface_id", "InnAware PMS Emulator")))
        if action == "link_alive":
            return self._line("LA")
        raise ValueError(f"Unsupported FIAS action: {action}")

    def decode(self, payload: bytes) -> DecodedRecord:
        text = payload.decode("latin-1", errors="replace")
        code, fields = _fields(text)
        room = fields.get("RN")
        mapping = {
            "GI": "checkin", "GO": "checkout", "GC": "name_update",
            "WR": "wakeup_set", "WU": "wakeup_set", "WC": "wakeup_cancel",
            "LS": "link_start", "LD": "link_description", "LR": "link_result",
            "LA": "link_alive", "LE": "link_end",
            "PS": "posting", "PR": "posting_response",
        }
        return DecodedRecord(mapping.get(code, "unknown"), room, {"code": code, **fields}, payload)


class HiltonPepFiasAdapter(FiasAdapter):
    name = "HILTON_PEP_FIAS"

    def __init__(self):
        super().__init__(hilton=True)
