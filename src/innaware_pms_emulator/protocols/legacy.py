from typing import Any
from .base import DecodedRecord


class LegacyHotelAdapter:
    """OnQ/Choice/legacy Opera family used by Voiceware-era interfaces.

    Records are fixed-position ASCII with ENQ/ACK and STX/ETX framing handled by
    the transport/session layer. This adapter generates the application payload.
    """
    purpose = "pms"

    def __init__(self, name: str):
        self.name = name

    @staticmethod
    def _room(room: str) -> str:
        return str(room)[:5].ljust(5)

    def encode_event(self, event: dict[str, Any]) -> bytes:
        action = event["action"].lower()
        room = self._room(event.get("room", ""))
        if action == "checkin":
            name = f'{event.get("last_name","")},{event.get("first_name","")}'[:20].ljust(20)
            return f"CHK1 {room}{name}".encode("ascii", "replace")
        if action == "checkout":
            name = f'{event.get("last_name","")},{event.get("first_name","")}'[:20].ljust(20)
            return f"CHK0 {room}{name}".encode("ascii", "replace")
        if action in ("name", "name_update"):
            name = f'{event.get("last_name","")},{event.get("first_name","")}'[:20].ljust(20)
            return f"NAM3 {name}{room}".encode("ascii", "replace")
        if action in ("move", "room_move"):
            return f"MOV4 {room} {self._room(event.get('new_room',''))}".encode("ascii")
        if action == "wakeup_set":
            return f"WKP{event.get('wakeup_time','0000')[:4]} {room}".encode("ascii")
        if action == "wakeup_cancel":
            return f"WKP9999 {room}".encode("ascii")
        if action == "restriction":
            return f"RST{event.get('restriction','0')[:1]} {room}".encode("ascii")
        if action == "dnd":
            return f"DND{'1' if event.get('enabled') else '0'} {room}".encode("ascii")
        if action == "language":
            return f"LNG{event.get('language','EN')[:2]} {room}".encode("ascii")
        if action == "sync_start":
            return b"GRS"
        if action == "sync_end":
            return b"END"
        if action == "heartbeat":
            return b"AREYUTHERE"
        raise ValueError(f"Unsupported {self.name} action: {action}")

    def decode(self, payload: bytes) -> DecodedRecord:
        s = payload.decode("latin-1", errors="replace").strip("\r\n\x00")
        if s.startswith("AREYUTHERE"):
            return DecodedRecord("heartbeat", fields={"command": "AREYUTHERE"}, raw=payload)
        if s.startswith("RQINZ"):
            return DecodedRecord("sync_request", fields={"command": "RQINZ"}, raw=payload)
        if s.startswith("STS"):
            return DecodedRecord("room_status", s[5:].strip(), {"status": s[3:4]}, payload)
        if s.startswith("MSG"):
            return DecodedRecord("message_status", fields={"text": s[3:].strip()}, raw=payload)
        return DecodedRecord("raw", fields={"text": s}, raw=payload)


class OnQAdapter(LegacyHotelAdapter):
    def __init__(self): super().__init__("ONQ")


class ChoiceAdvantageAdapter(LegacyHotelAdapter):
    def __init__(self): super().__init__("CHOICE_ADVANTAGE")


class OperaLegacyAdapter(LegacyHotelAdapter):
    def __init__(self): super().__init__("OPERA_LEGACY")


class OperaIpAdapter(LegacyHotelAdapter):
    """Voiceware-era OperaIP command payloads over ENQ/ACK + STX/ETX."""

    def __init__(self): super().__init__("OPERAIP_FIAS")
