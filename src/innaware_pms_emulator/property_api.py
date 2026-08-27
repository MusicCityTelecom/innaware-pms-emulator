from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .models import CallRecord, GuestEvent
from .property_state import CallAccountingState, RoomState, property_manager
from .protocols.registry import REGISTRY
from .sessions import manager

router = APIRouter(prefix="/api/v1", tags=["property-state"])


class PropertyCreateRequest(BaseModel):
    id: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=160)
    timezone: str = "America/Chicago"


class BulkRoomRequest(BaseModel):
    start: int = Field(ge=1)
    count: int = Field(ge=1, le=1000)
    room_type: str = "standard"
    floor: str = ""
    building: str = ""


class CheckinRequest(BaseModel):
    room: str
    first_name: str = ""
    last_name: str = ""
    guest_id: str | None = None
    stay_id: str | None = None
    reservation_id: str = ""
    language: str = ""
    interface_name: str | None = None


class CheckoutRequest(BaseModel):
    room: str
    interface_name: str | None = None


class MoveRequest(BaseModel):
    room: str
    new_room: str
    interface_name: str | None = None


class RoomStatusRequest(BaseModel):
    housekeeping: str
    out_of_order: bool | None = None


class RoomControlsRequest(BaseModel):
    restriction: str | None = None
    dnd: bool | None = None
    mwi_count: int | None = Field(default=None, ge=0)
    language: str | None = None
    voicemail_state: str | None = None


class WakeupRequest(BaseModel):
    room: str
    wakeup_time: str
    wakeup_date: str = ""
    wakeup_id: str | None = None
    interface_name: str | None = None


class WakeupCancelRequest(BaseModel):
    wakeup_id: str | None = None
    room: str | None = None
    interface_name: str | None = None


class PropertyCallRequest(CallRecord):
    interface_name: str | None = None
    transactional: bool = False


def _property_or_404(property_id: str):
    try:
        return property_manager.get(property_id)
    except KeyError:
        raise HTTPException(404, f"Property '{property_id}' not found")


async def _transmit_guest(interface_name: str | None, event: GuestEvent) -> dict | None:
    if not interface_name:
        return None
    try:
        runtime = manager.get(interface_name)
    except KeyError:
        return {"ok": False, "error": f"Interface '{interface_name}' not found"}
    if runtime.config.purpose.value != "pms":
        return {"ok": False, "error": "Selected interface is not a PMS interface"}
    adapter = REGISTRY[runtime.config.protocol]
    try:
        payload = adapter.encode_event(event.model_dump())
        sent = await manager.send(interface_name, payload, note=f"property operation: {event.action}")
        return {"ok": True, "sent_to": sent, "hex": payload.hex(" ")}
    except (ValueError, RuntimeError) as exc:
        return {"ok": False, "error": str(exc)}


@router.get("/properties")
def list_properties():
    return {"properties": property_manager.list()}


@router.post("/properties", status_code=201)
def create_property(request: PropertyCreateRequest):
    try:
        item = property_manager.create(request.id, request.name, request.timezone)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return item.model_dump(mode="json")


@router.get("/properties/{property_id}")
def get_property(property_id: str):
    return _property_or_404(property_id).model_dump(mode="json")


@router.delete("/properties/{property_id}", status_code=204)
def delete_property(property_id: str):
    _property_or_404(property_id)
    bound = [item["name"] for item in manager.list() if item.get("property_id", "").lower() == property_id.lower()]
    if bound:
        raise HTTPException(409, f"Property is still bound to interface(s): {', '.join(bound)}")
    property_manager.delete(property_id)


@router.post("/properties/{property_id}/rooms", status_code=201)
def create_room(property_id: str, room: RoomState):
    _property_or_404(property_id)
    try:
        return property_manager.add_room(property_id, room).model_dump(mode="json")
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@router.post("/properties/{property_id}/rooms/bulk")
def bulk_rooms(property_id: str, request: BulkRoomRequest):
    _property_or_404(property_id)
    try:
        rooms = property_manager.bulk_add_rooms(
            property_id,
            start=request.start,
            count=request.count,
            room_type=request.room_type,
            floor=request.floor,
            building=request.building,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return {"created": len(rooms), "rooms": [room.model_dump(mode="json") for room in rooms]}


@router.post("/properties/{property_id}/checkin")
async def checkin(property_id: str, request: CheckinRequest):
    _property_or_404(property_id)
    try:
        guest, stay = property_manager.checkin(
            property_id,
            room=request.room,
            first_name=request.first_name,
            last_name=request.last_name,
            guest_id=request.guest_id,
            stay_id=request.stay_id,
            reservation_id=request.reservation_id,
            language=request.language,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    transmission = await _transmit_guest(
        request.interface_name,
        GuestEvent(action="checkin", room=request.room, first_name=request.first_name, last_name=request.last_name, language=request.language or None),
    )
    return {"guest": guest.model_dump(mode="json"), "stay": stay.model_dump(mode="json"), "transmission": transmission}


@router.post("/properties/{property_id}/checkout")
async def checkout(property_id: str, request: CheckoutRequest):
    _property_or_404(property_id)
    try:
        stay = property_manager.checkout(property_id, room=request.room)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    transmission = await _transmit_guest(request.interface_name, GuestEvent(action="checkout", room=request.room))
    return {"stay": stay.model_dump(mode="json"), "transmission": transmission}


@router.post("/properties/{property_id}/move")
async def move(property_id: str, request: MoveRequest):
    item = _property_or_404(property_id)
    old_room = item.rooms.get(request.room)
    guest_first = ""
    guest_last = ""
    if old_room and old_room.active_stay_id:
        stay_before = item.stays.get(old_room.active_stay_id)
        guest = item.guests.get(stay_before.guest_id) if stay_before else None
        if guest:
            guest_first, guest_last = guest.first_name, guest.last_name
    try:
        stay = property_manager.move(property_id, room=request.room, new_room=request.new_room)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    transmission = await _transmit_guest(
        request.interface_name,
        GuestEvent(action="move", room=request.room, new_room=request.new_room, first_name=guest_first, last_name=guest_last),
    )
    return {"stay": stay.model_dump(mode="json"), "transmission": transmission}


@router.post("/properties/{property_id}/rooms/{room}/status")
def set_room_status(property_id: str, room: str, request: RoomStatusRequest):
    _property_or_404(property_id)
    try:
        state = property_manager.set_room_status(property_id, room=room, housekeeping=request.housekeeping, out_of_order=request.out_of_order)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return state.model_dump(mode="json")


@router.post("/properties/{property_id}/rooms/{room}/controls")
def set_room_controls(property_id: str, room: str, request: RoomControlsRequest):
    _property_or_404(property_id)
    try:
        state = property_manager.set_controls(
            property_id,
            room=room,
            restriction=request.restriction,
            dnd=request.dnd,
            mwi_count=request.mwi_count,
            language=request.language,
            voicemail_state=request.voicemail_state,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return state.model_dump(mode="json")


@router.post("/properties/{property_id}/wakeups")
async def schedule_wakeup(property_id: str, request: WakeupRequest):
    _property_or_404(property_id)
    try:
        wakeup = property_manager.schedule_wakeup(
            property_id,
            room=request.room,
            wakeup_time=request.wakeup_time,
            wakeup_date=request.wakeup_date,
            wakeup_id=request.wakeup_id,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    transmission = await _transmit_guest(
        request.interface_name,
        GuestEvent(action="wakeup_set", room=request.room, wakeup_time=request.wakeup_time, wakeup_date=request.wakeup_date or None),
    )
    return {"wakeup": wakeup.model_dump(mode="json"), "transmission": transmission}


@router.post("/properties/{property_id}/wakeups/cancel")
async def cancel_wakeup(property_id: str, request: WakeupCancelRequest):
    _property_or_404(property_id)
    try:
        wakeups = property_manager.cancel_wakeup(property_id, wakeup_id=request.wakeup_id, room=request.room)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    room = request.room or wakeups[0].room
    transmission = await _transmit_guest(request.interface_name, GuestEvent(action="wakeup_cancel", room=room))
    return {"wakeups": [w.model_dump(mode="json") for w in wakeups], "transmission": transmission}


@router.post("/properties/{property_id}/calls")
async def record_property_call(property_id: str, request: PropertyCallRequest):
    _property_or_404(property_id)
    timestamp = request.timestamp or datetime.now(timezone.utc).isoformat()
    record = CallAccountingState(
        id=f"call-{uuid4().hex[:12]}",
        room=request.room,
        number=request.number,
        duration_seconds=request.duration_seconds,
        cost=request.cost,
        call_type=request.call_type,
        timestamp=timestamp,
        description=request.description,
    )
    try:
        property_manager.record_call(property_id, record)
    except ValueError as exc:
        raise HTTPException(400, str(exc))

    transmission = None
    if request.interface_name:
        try:
            runtime = manager.get(request.interface_name)
            if runtime.config.purpose.value != "call_accounting":
                raise ValueError("Selected interface is not a call-accounting interface")
            adapter = REGISTRY[runtime.config.protocol]
            call_payload = CallRecord(
                room=request.room,
                number=request.number,
                duration_seconds=request.duration_seconds,
                cost=request.cost,
                call_type=request.call_type,
                timestamp=timestamp,
                description=request.description,
            )
            payload = adapter.encode_call(call_payload.model_dump())
            if request.transactional:
                transaction = await manager.send_call_transaction(request.interface_name, payload)
                transmission = {"ok": bool(transaction.get("success")), "transaction": transaction, "hex": payload.hex(" ")}
            else:
                sent = await manager.send(request.interface_name, payload, note="property call record")
                transmission = {"ok": True, "sent_to": sent, "hex": payload.hex(" ")}
        except (KeyError, ValueError, RuntimeError) as exc:
            transmission = {"ok": False, "error": str(exc)}
    return {"call": record.model_dump(mode="json"), "transmission": transmission}


@router.get("/properties/{property_id}/events")
def property_events(property_id: str, limit: int = 200):
    item = _property_or_404(property_id)
    size = max(1, min(limit, 5000))
    return {"events": [event.model_dump(mode="json") for event in item.events[-size:]]}


@router.post("/scenarios/small-hotel")
def seed_small_hotel(property_id: str = "demo-hotel"):
    item = property_manager.seed_small_hotel(property_id)
    return item.model_dump(mode="json")
