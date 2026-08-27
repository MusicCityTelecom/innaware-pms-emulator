from pathlib import Path

import pytest

from innaware_pms_emulator.property_state import PropertyManager, PropertyStore, RoomState


def manager(tmp_path: Path) -> PropertyManager:
    return PropertyManager(PropertyStore(tmp_path / "properties.json"))


def test_checkin_move_checkout_lifecycle(tmp_path):
    m = manager(tmp_path)
    m.create("hotel-a", "Hotel A")
    m.add_room("hotel-a", RoomState(number="101"))
    m.add_room("hotel-a", RoomState(number="102"))

    guest, stay = m.checkin("hotel-a", room="101", first_name="John", last_name="Smith")
    state = m.get("hotel-a")
    assert state.rooms["101"].active_stay_id == stay.id
    assert state.rooms["101"].voicemail_state == "active"
    assert state.guests[guest.id].last_name == "Smith"

    moved = m.move("hotel-a", room="101", new_room="102")
    assert moved.room == "102"
    assert state.rooms["101"].active_stay_id is None
    assert state.rooms["102"].active_stay_id == stay.id

    checked_out = m.checkout("hotel-a", room="102")
    assert checked_out.status == "checked_out"
    assert state.rooms["102"].active_stay_id is None
    assert state.rooms["102"].voicemail_state == "clear"


def test_wakeup_follows_room_move_and_cancels_on_checkout(tmp_path):
    m = manager(tmp_path)
    m.create("hotel-a", "Hotel A")
    m.add_room("hotel-a", RoomState(number="101"))
    m.add_room("hotel-a", RoomState(number="201"))
    m.checkin("hotel-a", room="101", first_name="Jane", last_name="Doe")
    wakeup = m.schedule_wakeup("hotel-a", room="101", wakeup_time="0630")

    m.move("hotel-a", room="101", new_room="201")
    assert m.get("hotel-a").wakeups[wakeup.id].room == "201"

    m.checkout("hotel-a", room="201")
    assert m.get("hotel-a").wakeups[wakeup.id].status == "cancelled"


def test_properties_are_isolated(tmp_path):
    m = manager(tmp_path)
    for property_id in ("hotel-a", "hotel-b"):
        m.create(property_id, property_id.upper())
        m.add_room(property_id, RoomState(number="101"))

    m.checkin("hotel-a", room="101", first_name="Only", last_name="Here")
    assert m.get("hotel-a").rooms["101"].active_stay_id is not None
    assert m.get("hotel-b").rooms["101"].active_stay_id is None
    assert not m.get("hotel-b").guests


def test_property_store_roundtrip(tmp_path):
    path = tmp_path / "properties.json"
    m = PropertyManager(PropertyStore(path))
    m.create("hotel-a", "Hotel A")
    m.add_room("hotel-a", RoomState(number="101", floor="1", rate_plan="standard"))
    m.checkin("hotel-a", room="101", first_name="John", last_name="Smith")

    restored = PropertyManager(PropertyStore(path))
    state = restored.get("hotel-a")
    assert state.rooms["101"].floor == "1"
    assert state.rooms["101"].active_stay_id is not None
    assert len(state.guests) == 1
    assert state.events[-1].event_type == "stay.checkin"


def test_fias_database_sync_contains_only_active_stays(tmp_path):
    m = manager(tmp_path)
    m.create("hotel-a", "Hotel A")
    m.add_room("hotel-a", RoomState(number="101"))
    m.add_room("hotel-a", RoomState(number="102"))
    m.checkin("hotel-a", room="101", first_name="John", last_name="Smith")

    records = m.fias_sync_records("hotel-a", "FIAS")
    assert records == [b"GI|RN101|GNSmith|GFJohn|"]

    m.checkout("hotel-a", room="101")
    assert m.fias_sync_records("hotel-a", "FIAS") == []


def test_hilton_database_sync_uses_combined_name(tmp_path):
    m = manager(tmp_path)
    m.create("hotel-a", "Hotel A")
    m.add_room("hotel-a", RoomState(number="101"))
    m.checkin("hotel-a", room="101", first_name="John", last_name="Smith")
    records = m.fias_sync_records("hotel-a", "HILTON_PEP_FIAS")
    assert records == [b"GI|RN101|GNSmith, John|"]
    assert b"GF" not in records[0]


def test_room_occupancy_and_invalid_wakeup_fail_closed(tmp_path):
    m = manager(tmp_path)
    m.create("hotel-a", "Hotel A")
    m.add_room("hotel-a", RoomState(number="101"))
    m.checkin("hotel-a", room="101", first_name="John", last_name="Smith")
    with pytest.raises(ValueError, match="already occupied"):
        m.checkin("hotel-a", room="101", first_name="Jane", last_name="Doe")
    with pytest.raises(ValueError, match="HHMM"):
        m.schedule_wakeup("hotel-a", room="101", wakeup_time="6:30")


def test_seed_scenario_is_deterministic(tmp_path):
    m = manager(tmp_path)
    state = m.seed_small_hotel("demo")
    assert len(state.rooms) == 30
    assert state.rooms["101"].active_stay_id == "stay-demo-1"
    assert state.rooms["103"].active_stay_id == "stay-demo-2"
    assert state.rooms["102"].housekeeping == "dirty"
    assert state.wakeups["wakeup-demo-1"].room == "101"
