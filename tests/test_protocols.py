from innaware_pms_emulator.protocols.call_accounting import BlindSmdrAdapter, HobisAdapter, InnFormXLAdapter
from innaware_pms_emulator.protocols.fias import FiasAdapter, HiltonPepFiasAdapter
from innaware_pms_emulator.protocols.legacy import OnQAdapter


def test_generic_fias_checkin():
    p = FiasAdapter().encode_event({"action": "checkin", "room": "101", "last_name": "Smith", "first_name": "John"})
    assert p == b"GI|RN101|GNSmith|GFJohn|\r\n"


def test_hilton_fias_uses_combined_name_and_omits_gf():
    p = HiltonPepFiasAdapter().encode_event({"action": "checkin", "room": "101", "last_name": "Smith", "first_name": "John"})
    assert p == b"GI|RN101|GNSmith, John|\r\n"
    assert b"GFJohn" not in p


def test_fias_room_move_uses_old_and_new_room_fields():
    p = FiasAdapter().encode_event({
        "action": "move",
        "room": "101",
        "new_room": "204",
        "last_name": "Smith",
        "first_name": "John",
    })
    assert p == b"GC|RN204|RO101|GNSmith|GFJohn|\r\n"
    decoded = FiasAdapter().decode(p)
    assert decoded.event_type == "room_move"
    assert decoded.room == "204"
    assert decoded.fields["RO"] == "101"


def test_onq_checkout():
    p = OnQAdapter().encode_event({"action": "checkout", "room": "204", "last_name": "Smith", "first_name": "John"})
    assert p.startswith(b"CHK0 ")
    assert b"204" in p


def test_innform_xl_core_fields():
    p = InnFormXLAdapter().encode_call({
        "room": "101", "number": "16155551212", "duration_seconds": 125, "cost": 1.25,
        "call_type": "D", "timestamp": "2026-08-24T20:30:00",
    })
    s = p.decode()
    assert "TEL" in s and "08/24" in s and "20:30" in s and "16155551212" in s


def test_hobis_uses_pst_code():
    p = HobisAdapter().encode_call({"room": "101", "number": "5551212", "duration_seconds": 60, "cost": 0})
    assert b"PST" in p


def test_blind_is_crlf_terminated():
    p = BlindSmdrAdapter().encode_call({"room": "101", "number": "5551212", "duration_seconds": 60, "cost": 0})
    assert p.endswith(b"\r\n")
