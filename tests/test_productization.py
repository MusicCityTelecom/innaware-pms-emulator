from __future__ import annotations

import io
import json
import sys
import zipfile

from innaware_pms_emulator import windows_launcher
from innaware_pms_emulator.profiles import build_interface_from_profile, profile_catalog
from innaware_pms_emulator.support import build_support_bundle, capture_export


def test_builtin_profiles_cover_primary_field_workflows():
    catalog = {item["id"]: item for item in profile_catalog()}
    assert "fias-pms-tcp-server" in catalog
    assert "hilton-pep-fias-tcp-server" in catalog
    assert "operaip-fias-tcp-server" in catalog
    assert "mitel-1-serial" in catalog
    assert "mitel-2-serial" in catalog
    assert "innform-xl-tcp-server" in catalog
    assert "hobis-a-tcp-server" in catalog
    assert catalog["hilton-pep-fias-tcp-server"]["defaults"]["options"]["framing"] == "stx_etx"
    opera = catalog["operaip-fias-tcp-server"]["defaults"]["options"]
    assert opera["control_bytes"] == {"enq": 5, "ack": 6, "stx": 2, "etx": 3, "nak": 21}
    assert opera["checksum"] == "none"
    assert opera["ack_enq"] is True and opera["ack_records"] is True
    assert opera["pbx_to_pms_masks"] == ["STS", "RQINZ"]
    assert set(opera["pms_to_pbx_masks"]) == {
        "AREYUTHERE", "GRS", "END", "EDT", "DND", "CHK", "LNG", "LMT", "MOV",
        "MSG", "MW", "NAM", "RST", "SDD", "STE", "VIP", "WKP",
    }
    assert catalog["mitel-1-serial"]["name"] == "Mitel 1"
    assert catalog["mitel-2-serial"]["name"] == "Mitel 2"
    assert catalog["mitel-1-serial"]["protocol"] == "Mitel 1"
    assert catalog["mitel-2-serial"]["protocol"] == "Mitel 2"
    assert catalog["mitel-1-serial"]["defaults"]["baud_rate"] == 1200
    assert catalog["mitel-1-serial"]["defaults"]["data_bits"] == 8
    assert catalog["mitel-1-serial"]["defaults"]["parity"] == "N"
    assert catalog["mitel-1-serial"]["defaults"]["stop_bits"] == 1
    assert catalog["mitel-1-serial"]["defaults"]["flow_control"] == "xonxoff"
    assert catalog["mitel-1-serial"]["defaults"]["options"]["framing"] == "stx_etx"
    assert catalog["mitel-1-serial"]["defaults"]["options"]["transaction_framing"] == "stx_etx"
    assert catalog["mitel-1-serial"]["defaults"]["options"]["transactional_enq_ack"] is True
    assert catalog["hobis-a-tcp-server"]["defaults"]["options"]["transaction_framing"] == "stx_etx_bcc"


def test_mitel_profile_can_be_instantiated_disabled_until_port_selected():
    config = build_interface_from_profile(
        "mitel-2-serial",
        name="field-mitel",
        property_id="hotel-a",
        enabled=False,
        overrides={"serial_device": "COM7"},
    )
    assert config.name == "field-mitel"
    assert config.protocol == "Mitel 2"
    assert config.transport.value == "serial"
    assert config.serial_device == "COM7"
    assert config.options["framing"] == "stx_etx"
    assert config.options["transactional_enq_ack"] is True


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
        full_property_state=[{"id": "hotel-a", "guests": {"g1": {"last_name": "GUESTLAST"}}}],
    )
    with zipfile.ZipFile(io.BytesIO(data), "r") as archive:
        payload = json.loads(archive.read("properties/FULL_PROPERTY_STATE_CONTAINS_GUEST_DATA.json"))
        assert payload[0]["guests"]["g1"]["last_name"] == "GUESTLAST"


def test_windowed_server_uses_file_only_uvicorn_logging(monkeypatch, tmp_path):
    monkeypatch.setenv("INNAWARE_PMS_DATA_DIR", str(tmp_path))
    captured = {}

    def fake_run(app, **kwargs):
        captured["app"] = app
        captured.update(kwargs)

    monkeypatch.setattr(windows_launcher.uvicorn, "run", fake_run)
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)

    windows_launcher._run_server_only("127.0.0.1", 18081, "warning")

    assert captured["app"] == "innaware_pms_emulator.main:app"
    assert captured["host"] == "127.0.0.1"
    assert captured["port"] == 18081
    assert captured["log_level"] == "warning"
    config = captured["log_config"]
    assert config["handlers"]["file"]["class"] == "logging.FileHandler"
    assert config["handlers"]["file"]["filename"].endswith("emulator.log")
    assert all(handler["class"] != "logging.StreamHandler" for handler in config["handlers"].values())
