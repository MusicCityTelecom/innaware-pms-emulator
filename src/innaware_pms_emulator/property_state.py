from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from .storage import data_dir


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class RoomState(BaseModel):
    number: str = Field(min_length=1, max_length=32)
    room_type: str = "standard"
    building: str = ""
    floor: str = ""
    housekeeping: str = "clean"
    out_of_order: bool = False
    active_stay_id: str | None = None
    default_restriction: str = "guest"
    restriction: str = "guest"
    dnd: bool = False
    mwi_count: int = Field(default=0, ge=0)
    language: str = ""
    voicemail_state: str = "clear"
    call_billing_enabled: bool = True
    rate_plan: str = ""


class GuestState(BaseModel):
    id: str
    first_name: str = ""
    last_name: str = ""
    language: str = ""
    vip_code: str = ""
    created_at: str = Field(default_factory=_utcnow)


class StayState(BaseModel):
    id: str
    guest_id: str
    room: str
    status: str = "active"
    reservation_id: str = ""
    check_in_at: str = Field(default_factory=_utcnow)
    check_out_at: str | None = None


class WakeupState(BaseModel):
    id: str
    room: str
    wakeup_date: str = ""
    wakeup_time: str
    status: str = "scheduled"
    created_at: str = Field(default_factory=_utcnow)
    cancelled_at: str | None = None


class CallAccountingState(BaseModel):
    id: str
    room: str
    number: str
    duration_seconds: int = Field(ge=0)
    cost: float = Field(default=0.0, ge=0)
    call_type: str = "D"
    timestamp: str = Field(default_factory=_utcnow)
    description: str = ""


class PropertyEvent(BaseModel):
    sequence: int
    timestamp: str = Field(default_factory=_utcnow)
    event_type: str
    room: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class PropertyState(BaseModel):
    id: str
    name: str
    timezone: str = "America/Chicago"
    rooms: dict[str, RoomState] = Field(default_factory=dict)
    guests: dict[str, GuestState] = Field(default_factory=dict)
    stays: dict[str, StayState] = Field(default_factory=dict)
    wakeups: dict[str, WakeupState] = Field(default_factory=dict)
    calls: list[CallAccountingState] = Field(default_factory=list)
    events: list[PropertyEvent] = Field(default_factory=list)
    next_sequence: int = 1
    created_at: str = Field(default_factory=_utcnow)
    updated_at: str = Field(default_factory=_utcnow)


class PropertyStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (data_dir() / "properties.json")

    def load(self) -> list[PropertyState]:
        if not self.path.exists():
            return []
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        if not isinstance(raw, list):
            return []
        out: list[PropertyState] = []
        for item in raw:
            try:
                out.append(PropertyState.model_validate(item))
            except Exception:
                continue
        return out

    def save(self, properties: list[PropertyState]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(self.path.suffix + ".tmp")
        payload = [item.model_dump(mode="json") for item in properties]
        temp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temp.replace(self.path)


class PropertyManager:
    def __init__(self, store: PropertyStore | None = None) -> None:
        self.store = store or PropertyStore()
        self._properties: dict[str, PropertyState] = {}
        self._lock = threading.RLock()
        for item in self.store.load():
            self._properties[item.id.lower()] = item

    def _persist(self) -> None:
        self.store.save(list(self._properties.values()))

    @staticmethod
    def _key(value: str) -> str:
        return value.strip().lower()

    def list(self) -> list[dict[str, Any]]:
        with self._lock:
            return [self.summary(item) for item in self._properties.values()]

    def summary(self, item: PropertyState) -> dict[str, Any]:
        active = sum(1 for stay in item.stays.values() if stay.status == "active")
        return {
            "id": item.id,
            "name": item.name,
            "timezone": item.timezone,
            "rooms": len(item.rooms),
            "occupied_rooms": active,
            "scheduled_wakeups": sum(1 for w in item.wakeups.values() if w.status == "scheduled"),
            "calls": len(item.calls),
            "updated_at": item.updated_at,
        }

    def get(self, property_id: str) -> PropertyState:
        item = self._properties.get(self._key(property_id))
        if not item:
            raise KeyError(property_id)
        return item

    def create(self, property_id: str, name: str, timezone_name: str = "America/Chicago") -> PropertyState:
        key = self._key(property_id)
        if not key:
            raise ValueError("Property id is required")
        with self._lock:
            if key in self._properties:
                raise ValueError(f"Property '{property_id}' already exists")
            item = PropertyState(id=property_id.strip(), name=name.strip() or property_id.strip(), timezone=timezone_name)
            self._properties[key] = item
            self._event(item, "property.created", payload={"name": item.name})
            self._persist()
            return item

    def delete(self, property_id: str) -> None:
        with self._lock:
            if self._properties.pop(self._key(property_id), None) is None:
                raise KeyError(property_id)
            self._persist()

    def add_room(self, property_id: str, room: RoomState) -> RoomState:
        with self._lock:
            item = self.get(property_id)
            if room.number in item.rooms:
                raise ValueError(f"Room '{room.number}' already exists")
            item.rooms[room.number] = room
            self._event(item, "room.created", room=room.number, payload=room.model_dump(mode="json"))
            self._touch(item)
            return room

    def bulk_add_rooms(self, property_id: str, *, start: int, count: int, room_type: str = "standard", floor: str = "", building: str = "") -> list[RoomState]:
        if count < 1 or count > 1000:
            raise ValueError("count must be between 1 and 1000")
        rooms: list[RoomState] = []
        with self._lock:
            item = self.get(property_id)
            for offset in range(count):
                number = str(start + offset)
                if number in item.rooms:
                    continue
                room = RoomState(number=number, room_type=room_type, floor=floor, building=building)
                item.rooms[number] = room
                rooms.append(room)
            self._event(item, "rooms.bulk_created", payload={"start": start, "count": len(rooms)})
            self._touch(item)
        return rooms

    def checkin(self, property_id: str, *, room: str, first_name: str = "", last_name: str = "", guest_id: str | None = None, stay_id: str | None = None, reservation_id: str = "", language: str = "") -> tuple[GuestState, StayState]:
        with self._lock:
            item = self.get(property_id)
            room_state = self._room(item, room)
            if room_state.active_stay_id:
                raise ValueError(f"Room '{room}' is already occupied")
            gid = guest_id or f"guest-{uuid4().hex[:12]}"
            sid = stay_id or f"stay-{uuid4().hex[:12]}"
            guest = item.guests.get(gid)
            if guest:
                guest.first_name = first_name
                guest.last_name = last_name
                guest.language = language or guest.language
            else:
                guest = GuestState(id=gid, first_name=first_name, last_name=last_name, language=language)
                item.guests[gid] = guest
            stay = StayState(id=sid, guest_id=gid, room=room, reservation_id=reservation_id)
            item.stays[sid] = stay
            room_state.active_stay_id = sid
            room_state.restriction = room_state.default_restriction
            room_state.dnd = False
            room_state.mwi_count = 0
            room_state.language = language
            room_state.voicemail_state = "active"
            self._event(item, "stay.checkin", room=room, payload={"guest_id": gid, "stay_id": sid, "first_name": first_name, "last_name": last_name})
            self._touch(item)
            return guest, stay

    def checkout(self, property_id: str, *, room: str) -> StayState:
        with self._lock:
            item = self.get(property_id)
            room_state = self._room(item, room)
            if not room_state.active_stay_id:
                raise ValueError(f"Room '{room}' is vacant")
            stay = item.stays[room_state.active_stay_id]
            stay.status = "checked_out"
            stay.check_out_at = _utcnow()
            room_state.active_stay_id = None
            room_state.restriction = room_state.default_restriction
            room_state.dnd = False
            room_state.mwi_count = 0
            room_state.language = ""
            room_state.voicemail_state = "clear"
            for wakeup in item.wakeups.values():
                if wakeup.room == room and wakeup.status == "scheduled":
                    wakeup.status = "cancelled"
                    wakeup.cancelled_at = _utcnow()
            self._event(item, "stay.checkout", room=room, payload={"stay_id": stay.id, "guest_id": stay.guest_id})
            self._touch(item)
            return stay

    def move(self, property_id: str, *, room: str, new_room: str) -> StayState:
        with self._lock:
            item = self.get(property_id)
            old = self._room(item, room)
            new = self._room(item, new_room)
            if not old.active_stay_id:
                raise ValueError(f"Room '{room}' is vacant")
            if new.active_stay_id:
                raise ValueError(f"Room '{new_room}' is already occupied")
            stay = item.stays[old.active_stay_id]
            operational = {"restriction": old.restriction, "dnd": old.dnd, "mwi_count": old.mwi_count, "language": old.language, "voicemail_state": old.voicemail_state}
            old.active_stay_id = None
            old.restriction = old.default_restriction
            old.dnd = False
            old.mwi_count = 0
            old.language = ""
            old.voicemail_state = "clear"
            new.active_stay_id = stay.id
            new.restriction = operational["restriction"]
            new.dnd = operational["dnd"]
            new.mwi_count = operational["mwi_count"]
            new.language = operational["language"]
            new.voicemail_state = operational["voicemail_state"]
            stay.room = new_room
            for wakeup in item.wakeups.values():
                if wakeup.room == room and wakeup.status == "scheduled":
                    wakeup.room = new_room
            self._event(item, "stay.move", room=new_room, payload={"stay_id": stay.id, "from_room": room, "to_room": new_room})
            self._touch(item)
            return stay

    def set_room_status(self, property_id: str, *, room: str, housekeeping: str, out_of_order: bool | None = None) -> RoomState:
        allowed = {"clean", "dirty", "inspected", "pickup", "out_of_order", "unknown"}
        if housekeeping not in allowed:
            raise ValueError(f"Unsupported housekeeping state: {housekeeping}")
        with self._lock:
            item = self.get(property_id)
            state = self._room(item, room)
            state.housekeeping = housekeeping
            if out_of_order is not None:
                state.out_of_order = out_of_order
            elif housekeeping == "out_of_order":
                state.out_of_order = True
            self._event(item, "room.status", room=room, payload={"housekeeping": housekeeping, "out_of_order": state.out_of_order})
            self._touch(item)
            return state

    def set_controls(self, property_id: str, *, room: str, restriction: str | None = None, dnd: bool | None = None, mwi_count: int | None = None, language: str | None = None, voicemail_state: str | None = None) -> RoomState:
        with self._lock:
            item = self.get(property_id)
            state = self._room(item, room)
            changed: dict[str, Any] = {}
            for name, value in {"restriction": restriction, "dnd": dnd, "mwi_count": mwi_count, "language": language, "voicemail_state": voicemail_state}.items():
                if value is not None:
                    setattr(state, name, value)
                    changed[name] = value
            self._event(item, "room.controls", room=room, payload=changed)
            self._touch(item)
            return state

    def schedule_wakeup(self, property_id: str, *, room: str, wakeup_time: str, wakeup_date: str = "", wakeup_id: str | None = None) -> WakeupState:
        if len(wakeup_time) not in {4, 6} or not wakeup_time.isdigit():
            raise ValueError("wakeup_time must be HHMM or HHMMSS")
        with self._lock:
            item = self.get(property_id)
            self._room(item, room)
            wid = wakeup_id or f"wakeup-{uuid4().hex[:12]}"
            wakeup = WakeupState(id=wid, room=room, wakeup_date=wakeup_date, wakeup_time=wakeup_time)
            item.wakeups[wid] = wakeup
            self._event(item, "wakeup.scheduled", room=room, payload=wakeup.model_dump(mode="json"))
            self._touch(item)
            return wakeup

    def cancel_wakeup(self, property_id: str, *, wakeup_id: str | None = None, room: str | None = None) -> list[WakeupState]:
        with self._lock:
            item = self.get(property_id)
            matches: list[WakeupState] = []
            for wakeup in item.wakeups.values():
                if wakeup.status != "scheduled":
                    continue
                if wakeup_id and wakeup.id != wakeup_id:
                    continue
                if room and wakeup.room != room:
                    continue
                wakeup.status = "cancelled"
                wakeup.cancelled_at = _utcnow()
                matches.append(wakeup)
            if not matches:
                raise ValueError("No scheduled wakeup matched")
            self._event(item, "wakeup.cancelled", room=room, payload={"ids": [x.id for x in matches]})
            self._touch(item)
            return matches

    def record_call(self, property_id: str, record: CallAccountingState) -> CallAccountingState:
        with self._lock:
            item = self.get(property_id)
            self._room(item, record.room)
            item.calls.append(record)
            if len(item.calls) > 5000:
                del item.calls[:-5000]
            self._event(item, "call.recorded", room=record.room, payload=record.model_dump(mode="json"))
            self._touch(item)
            return record

    def active_stays(self, property_id: str) -> list[tuple[RoomState, GuestState, StayState]]:
        with self._lock:
            item = self.get(property_id)
            rows: list[tuple[RoomState, GuestState, StayState]] = []
            for room_number in sorted(item.rooms, key=lambda v: (len(v), v)):
                room = item.rooms[room_number]
                if not room.active_stay_id:
                    continue
                stay = item.stays.get(room.active_stay_id)
                if not stay or stay.status != "active":
                    continue
                guest = item.guests.get(stay.guest_id)
                if guest:
                    rows.append((room, guest, stay))
            return rows

    def fias_sync_records(self, property_id: str, protocol: str = "FIAS") -> list[bytes]:
        try:
            rows = self.active_stays(property_id)
        except KeyError:
            return []
        from .protocols.registry import REGISTRY

        adapter = REGISTRY.get(protocol.upper()) or REGISTRY["FIAS"]
        records: list[bytes] = []
        for room, guest, _stay in rows:
            payload = adapter.encode_event({"action": "checkin", "room": room.number, "last_name": guest.last_name, "first_name": guest.first_name})
            records.append(payload.rstrip(b"\r\n"))
        return records

    def seed_small_hotel(self, property_id: str = "demo-hotel") -> PropertyState:
        with self._lock:
            key = self._key(property_id)
            if key in self._properties:
                del self._properties[key]
            item = PropertyState(id=property_id, name="InnAware Demo Hotel")
            self._properties[key] = item
            for floor in range(1, 4):
                for room_index in range(1, 11):
                    number = f"{floor}{room_index:02d}"
                    item.rooms[number] = RoomState(number=number, floor=str(floor))
            self._event(item, "scenario.seed", payload={"scenario": "small-hotel", "rooms": 30})
            self._persist()
        self.checkin(property_id, room="101", first_name="John", last_name="Smith", guest_id="guest-demo-1", stay_id="stay-demo-1")
        self.checkin(property_id, room="103", first_name="Jane", last_name="Doe", guest_id="guest-demo-2", stay_id="stay-demo-2")
        self.set_room_status(property_id, room="102", housekeeping="dirty")
        self.schedule_wakeup(property_id, room="101", wakeup_time="0630", wakeup_id="wakeup-demo-1")
        return self.get(property_id)

    @staticmethod
    def _room(item: PropertyState, room: str) -> RoomState:
        state = item.rooms.get(room)
        if not state:
            raise ValueError(f"Room '{room}' does not exist")
        return state

    def _event(self, item: PropertyState, event_type: str, *, room: str | None = None, payload: dict[str, Any] | None = None) -> None:
        item.events.append(PropertyEvent(sequence=item.next_sequence, event_type=event_type, room=room, payload=payload or {}))
        item.next_sequence += 1
        if len(item.events) > 5000:
            del item.events[:-5000]

    def _touch(self, item: PropertyState) -> None:
        item.updated_at = _utcnow()
        self._persist()


property_manager = PropertyManager()
