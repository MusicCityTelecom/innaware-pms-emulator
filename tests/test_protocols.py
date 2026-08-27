from innaware_pms_emulator.protocols.call_accounting import (
    BlindSmdrAdapter,
    HobisAAdapter,
    HobisAdapter,
    HolidexAdapter,
    InnFormXLAdapter,
)
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
    assert decoded.kind == "room_move"
    assert decoded.room == "204"
    assert decoded.fields["RO"] == "101"


def test_onq_checkout():
    p = OnQAdapter().encode_event({"action": "checkout", "room": "204", "last_name": "Smith", "first_name": "John"})
    assert p.startswith(b"CHK0 ")
    assert b"204" in p


def test_innform_xl_core_fields_and_field_tested_prefix():
    p = InnFormXLAdapter().encode_call({
        "room": "101", "number": "16155551212", "duration_seconds": 125, "cost": 1.25,
        "call_type": "D", "timestamp": "2026-08-24T20:30:00",
    })
    s = p.decode()
    assert s.startswith("001A TEL 08/24")
    assert "20:30" in s and "16155551212" in s


def test_hobis_a_verified_fixed_positions():
    p = HobisAdapter().encode_call({
        "room": "101", "number": "16155551212", "duration_seconds": 125, "cost": 1.25,
        "call_type": "D", "timestamp": "2026-08-24T20:30:00",
    })
    s = p.decode("ascii")
    assert len(s) == 54
    assert s[0:4] == "0001"
    assert s[5:8] == "PST"
    assert s[9:14] == "08/24"
    assert s[16:20] == " 101"
    assert s[21:26] == "20:30"
    assert s[27:31] == "0003"
    assert s[32:39] == "$001.25"
    assert s[40:52] == "16155551212 "
    assert s[53] == "D"


def test_hobis_a_and_holidex_aliases_use_same_verified_layout():
    call = {
        "room": "204", "number": "5551212", "duration_seconds": 60, "cost": 0,
        "call_type": "D", "timestamp": "2026-08-24T20:30:00",
    }
    outputs = [HobisAAdapter().encode_call(call), HolidexAdapter().encode_call(call)]
    assert outputs[0] == outputs[1]
    assert outputs[0][5:8] == b"PST"
    assert len(outputs[0]) == 54


def test_hobis_money_rounds_instead_of_truncating():
    p = HobisAdapter().encode_call({
        "room": "101", "number": "5551212", "duration_seconds": 60, "cost": "1.155",
        "call_type": "D", "timestamp": "2026-08-24T20:30:00",
    })
    assert p[32:39] == b"$001.16"


def test_blind_is_crlf_terminated():
    p = BlindSmdrAdapter().encode_call({"room": "101", "number": "5551212", "duration_seconds": 60, "cost": 0})
    assert p.endswith(b"\r\n")
