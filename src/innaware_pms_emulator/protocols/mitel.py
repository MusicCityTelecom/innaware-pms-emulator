from __future__ import annotations

from typing import Any

from .base import DecodedRecord


class MitelSerialAdapter:
    """Clean-room Mitel-style hotel PMS payload adapter.

    The transport/session layer owns ENQ/ACK/NAK and STX/ETX framing. This
    adapter only creates and decodes application payloads.

    Mitel 1 models the classic fixed-width layout: the guest-name field is
    fixed before the five-character room field. Mitel 2 models the historical
    compatibility variant in which the room field occurs first and the guest
    name follows it, allowing a longer name without shifting the room field.
    """

    purpose = "pms"

    def __init__(self, name: str, *, room_first_name: bool = False) -> None:
        self.name = name
        self.room_first_name = room_first_name

    @staticmethod
    def _room(room: str) -> str:
        value = str(room).strip()[:5]
        return value.rjust(5)

    @staticmethod
    def _combined_name(event: dict[str, Any]) -> str:
        last = str(event.get("last_name", "")).strip()
        first = str(event.get("first_name", "")).strip()
        return f"{last},{first}" if first else last

    def _name_record(self, operation: str, room: str, name: str) -> bytes:
        if self.room_first_name:
            # Historical compatibility form: NAMx + room(5) + SP + variable name.
            return f"NAM{operation}{room} {name[:40]}".encode("ascii", "replace")
        # Classic form: NAMx + SP + fixed name(20) + SP + room(5).
        return f"NAM{operation} {name[:20].ljust(20)} {room}".encode("ascii", "replace")

    def encode_event(self, event: dict[str, Any]) -> bytes:
        action = str(event["action"]).lower()
        room = self._room(event.get("room", ""))
        name = self._combined_name(event)

        if action == "checkin":
            suffix = f" {name[:40]}" if self.room_first_name and name else ""
            return f"CHK1{room}{suffix}".encode("ascii", "replace")
        if action == "checkout":
            suffix = f" {name[:40]}" if self.room_first_name and name else ""
            return f"CHK0{room}{suffix}".encode("ascii", "replace")
        if action in {"name", "name_update"}:
            operation = str(event.get("extra", {}).get("name_operation", "2"))[:1]
            if operation not in {"0", "1", "2", "3"}:
                raise ValueError("Mitel name_operation must be 0, 1, 2, or 3")
            return self._name_record(operation, room, name)
        if action == "wakeup_set":
            wakeup = str(event.get("wakeup_time") or "").replace(":", "")[:4]
            if len(wakeup) != 4 or not wakeup.isdigit():
                raise ValueError("Mitel wakeup_time must resolve to four HHMM digits")
            return f"WKP{wakeup}{room}".encode("ascii")
        if action == "wakeup_cancel":
            return f"WKP9999{room}".encode("ascii")
        if action == "restriction":
            level = str(event.get("restriction") or "0")[:1]
            if level not in {"0", "1", "2", "3", "4", "5"}:
                raise ValueError("Mitel restriction must be 0 through 5")
            return f"RST{level}{room}".encode("ascii")
        if action == "heartbeat":
            return b"AREYUTHERE"

        raise ValueError(f"Unsupported {self.name} action: {action}")

    def decode(self, payload: bytes) -> DecodedRecord:
        text = payload.decode("latin-1", errors="replace").strip("\x00\r\n")
        if text == "AREYUTHERE":
            return DecodedRecord("heartbeat", fields={"command": "AREYUTHERE"}, raw=payload)
        if text.startswith("CHK") and len(text) >= 9:
            status = text[3:4]
            room = text[4:9].strip()
            fields: dict[str, str] = {"command": "CHK", "status": status}
            if len(text) > 10:
                last, sep, first = text[10:].strip().partition(",")
                fields["last_name"] = last.strip()
                fields["first_name"] = first.strip() if sep else ""
            return DecodedRecord(
                "checkin" if status == "1" else "checkout" if status == "0" else "raw",
                room,
                fields,
                payload,
            )
        if text.startswith("WKP") and len(text) >= 12:
            wakeup = text[3:7]
            return DecodedRecord(
                "wakeup_cancel" if wakeup == "9999" else "wakeup_set",
                text[7:12].strip(),
                {"command": "WKP", "time": wakeup},
                payload,
            )
        if text.startswith("RST") and len(text) >= 9:
            return DecodedRecord(
                "restriction",
                text[4:9].strip(),
                {"command": "RST", "level": text[3:4]},
                payload,
            )
        if text.startswith("NAM") and len(text) >= 5:
            operation = text[3:4]
            if self.room_first_name:
                room = text[4:9].strip()
                name = text[10:].strip() if len(text) > 10 else ""
            else:
                room = text[-5:].strip() if len(text) >= 10 else ""
                name = text[5:-6].rstrip() if len(text) >= 11 else ""
            last, sep, first = name.partition(",")
            return DecodedRecord(
                "name_update",
                room,
                {
                    "command": "NAM",
                    "operation": operation,
                    "last_name": last.strip(),
                    "first_name": first.strip() if sep else "",
                },
                payload,
            )
        return DecodedRecord("raw", fields={"text": text}, raw=payload)


class Mitel1Adapter(MitelSerialAdapter):
    def __init__(self) -> None:
        super().__init__("Mitel 1", room_first_name=False)


class Mitel2Adapter(MitelSerialAdapter):
    def __init__(self) -> None:
        super().__init__("Mitel 2", room_first_name=True)
