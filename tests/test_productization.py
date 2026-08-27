from __future__ import annotations

import io
import json
import zipfile

from innaware_pms_emulator.profiles import build_interface_from_profile, profile_catalog
from innaware_pms_emulator.support import build_support_bundle, capture_export


def test_builtin_profiles_cover_primary_field_workflows():
    catalog = {item["id"]: item for item in profile_catalog()}
    assert "fias-pms-tcp-server" in catalog
    assert "hilton-pep-fias-tcp-server" in catalog
    assert "innform-xl-tcp-server" in catalog
    assert "hobis-a-tcp-server" in catalog
    assert catalog["hilton-pep-fias-tcp-server"]["defaults"]["options"]["framing"] == "stx_etx"
    assert catalog["hobis-a-tcp-server"]["defaults"]["options"]["transaction_framing"] == "stx_etx_bcc"


def test_profile_instantiation_allows_safe_overrides():
    config = build_interface_from_profile(
        "fias-pms-tcp-server",
        name="field-fias",
        property_id="hotel-a",
        overrides={"port": 6501, "options": {"role": "pbx"}},
    )
    assert config.name == "field-fias"
    assert config.property_id == "hotel-a"
    assert config.protocol == "FIAS"
    assert config.port == 6501
    assert config.options["framing"] == "crlf"
    assert config.options["role"] == "pbx"


def test_capture_exports_json_csv_and_text():
    captures = [
        {
            "timestamp": "2026-08-27T00:00:00+00:00",
            "direction": "rx",
            "peer": "127.0.0.1:1234",
            "note": "test",
            "hex": "05",
            "text": "\x05",
        }
    ]
    json_data, json_type, json_ext = capture_export(captures, "json")
    assert json.loads(json_data)[0]["hex"] == "05"
    assert json_type == "application/json"
    assert json_ext == "json"

    csv_data, _, csv_ext = capture_export(captures, "csv")
    assert b"timestamp,direction,peer,note,hex,text" in csv_data
    assert csv_ext == "csv"

    text_data, _, text_ext = capture_export(captures, "txt")
    assert b"RX" in text_data and b"HEX  05" in text_data
    assert text_ext == "txt"


def test_support_bundle_excludes_full_property_state_by_default():
    data = build_support_bundle(
        interface_statuses=[{"name": "fias"}],
        interface_configs=[{"name": "fias", "protocol": "FIAS"}],
        property_summaries=[{"id": "hotel-a", "rooms": 10}],
        protocol_catalog=[{"id": "FIAS"}],
        serial_ports=[],
        captures_by_interface={"fias": []},
        transactions_by_interface={"fias": []},
        full_property_state=None,
    )
    with zipfile.ZipFile(io.BytesIO(data), "r") as archive:
        names = set(archive.namelist())
        assert "manifest.json" in names
        assert "properties/summary.json" in names
        assert "properties/PRIVACY.txt" in names
        assert "properties/FULL_PROPERTY_STATE_CONTAINS_GUEST_DATA.json" not in names


def test_support_bundle_can_explicitly_include_full_property_state():
    data = build_support_bundle(
        interface_statuses=[],
        interface_configs=[],
        property_summaries=[{"id": "hotel-a"}],
        protocol_catalog=[],
        serial_ports=[],
        captures_by_interface={},
        transactions_by_interface={},
        full_property_state=[{"id": "hotel-a", "guests": {"g1": {"last_name": "Smith"}}}],
    )
    with zipfile.ZipFile(io.BytesIO(data), "r") as archive:
        payload = json.loads(archive.read("properties/FULL_PROPERTY_STATE_CONTAINS_GUEST_DATA.json"))
        assert payload[0]["guests"]["g1"]["last_name"] == "Smith"
