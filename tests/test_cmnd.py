import asyncio
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from xml.etree import ElementTree as ET

import pytest

from innaware_pms_emulator.cmnd_transport import configured_event, post_guest_event, validate_options
from innaware_pms_emulator.profiles import build_interface_from_profile
from innaware_pms_emulator.protocols.cmnd import CmndHtngAdapter, HTNG, OTA, SOAP
from innaware_pms_emulator.protocols.registry import protocol_catalog
from innaware_pms_emulator.sessions import InterfaceManager


def event(action="checkin"):
    return {"action": action, "room": "00101", "first_name": "Zoë & <Test>", "last_name": "SYNTHETIC",
            "language": "en-US", "extra": {"hotel_code": "LAB", "guest_id": "synthetic-guest-1",
            "guest_id_type": "1", "telephone_extension": "0101", "housekeeping_status": "VACANT_CLEAN"}}


def response(action="checkin", content="<h:Success/>"):
    name = "CheckIn" if action == "checkin" else "CheckOut"
    return (f'<s:Envelope xmlns:s="{SOAP}" xmlns:h="{HTNG}"><s:Body>'
            f'<h:HTNG_Hotel{name}NotifRS Version="1.000">{content}</h:HTNG_Hotel{name}NotifRS>'
            '</s:Body></s:Envelope>').encode()


@contextmanager
def peer(body=None, status=200):
    received = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            received.append((self.path, dict(self.headers), self.rfile.read(int(self.headers["Content-Length"]))))
            self.send_response(status)
            self.send_header("Content-Type", "text/xml")
            self.end_headers()
            self.wfile.write(response() if body is None else body)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield {"endpoint_url": f"http://127.0.0.1:{server.server_port}/stay", "execute": True,
               "allowed_rooms": ["00101"], "timeout_seconds": 1}, received
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


@pytest.mark.parametrize("action", ["checkin", "checkout"])
def test_schema_shaped_requests_preserve_ids_and_names(action):
    payload = CmndHtngAdapter().encode_event(event(action))
    root = ET.fromstring(payload)
    request = root.find(f"{{{SOAP}}}Body")[0]
    assert request.attrib == {"Version": "1.001"}
    assert [node.tag.rsplit("}", 1)[-1] for node in request] == ["PropertyInfo", "AffectedGuests", "Room", "HotelReservations"]
    assert request.find(f"{{{HTNG}}}Room").get("RoomID") == "00101"
    assert request.find(f".//{{{HTNG}}}TelephoneExtention").text == "0101"
    if action == "checkin":
        assert request.find(f".//{{{OTA}}}GivenName").text == "Zoë & <Test>"
        assert request.find(f".//{{{OTA}}}Customer").get("Language") == "en-US"
    else:
        assert b"SYNTHETIC" not in payload and b"GivenName" not in payload


@pytest.mark.parametrize("key", ["hotel_code", "guest_id", "guest_id_type", "telephone_extension", "housekeeping_status"])
def test_required_site_fields_not_invented(key):
    data = event()
    del data["extra"][key]
    with pytest.raises(ValueError):
        CmndHtngAdapter().encode_event(data)


@pytest.mark.parametrize("change", [{"room": 101}, {"room": "a" * 17}, {"room": ""},
                                    {"action": "move"}, {"first_name": "test\x00"}, {"language": "bad|value"}])
def test_invalid_values_rejected(change):
    with pytest.raises(ValueError):
        CmndHtngAdapter().encode_event({**event(), **change})


@pytest.mark.parametrize("body", [b"<html>login</html>", b"<!DOCTYPE a [<!ENTITY b 'x'>]><a>&b;</a>",
                                  "<!DOCTYPE a><a/>".encode("utf-16"), b"x" * 65537],
                         ids=["html", "entity", "utf16", "oversize"])
def test_invalid_or_unsafe_response_rejected(body):
    with pytest.raises(ValueError):
        CmndHtngAdapter().decode(body)


def test_response_is_not_http_success_alone():
    assert CmndHtngAdapter().decode(response()).fields["success"]
    assert not CmndHtngAdapter().decode(response(content="<h:Errors/>")).fields["success"]
    assert not CmndHtngAdapter().decode(response(content="")).fields["success"]
    assert not CmndHtngAdapter().decode(response(content="<h:Success/><h:Errors/>")).fields["success"]


def test_http_transaction_observed_on_loopback_only():
    with peer() as (options, received):
        result = post_guest_event(options, event())
        assert result["cmnd_accepted"] and not result["tv_verified"]
        assert len(received) == 1
        path, headers, wire = received[0]
        assert path == "/stay"
        assert headers["SOAPAction"] == f'"{HTNG}/HTNG_GuestAndRoomStatusService#CheckedIn"'
        assert wire == CmndHtngAdapter().encode_event(event())


@pytest.mark.parametrize("status,body", [(302, b""), (401, b""), (500, b""),
    (200, response("checkout")), (200, response(content="<h:Errors/>")), (200, b"<html/>")])
def test_http_failure_never_retries_or_follows_redirects(status, body):
    with peer(body, status) as (options, received):
        with pytest.raises((RuntimeError, ValueError)):
            post_guest_event(options, event())
        assert len(received) == 1


def test_no_writes_without_both_guards():
    with peer() as (options, received):
        for override in ({"execute": False}, {"execute": "true"}, {"allowed_rooms": []}, {"allowed_rooms": [101]}):
            with pytest.raises(ValueError):
                post_guest_event({**options, **override}, event())
        assert not received


@pytest.mark.parametrize("url", [None, "http://tempuri.org/", "https://a/\r\n", "https://user:password@host/path",
                                     "https://host/", "http://192.0.2.1/stay", "file:///stay", "https://host/path?secret=1"])
def test_endpoint_validation(url):
    # Bare root is allowed as an explicitly configured service endpoint.
    if url == "https://host/":
        validate_options({"endpoint_url": url})
    else:
        with pytest.raises(ValueError):
            validate_options({"endpoint_url": url})


def test_catalog_profile_and_guarded_runtime():
    profile = build_interface_from_profile("philips-cmnd-htng-guest-tv", name="tv-lab", enabled=False)
    assert profile.options["execute"] is False and profile.transport.value == "http_client"
    assert next(p for p in protocol_catalog() if p["id"] == "CMND_HTNG_2011B")["maturity"] == "experimental-schema-backed"

    async def run():
        manager = InterfaceManager()
        await manager.create(profile)
        with pytest.raises(ValueError, match="endpoint_url"):
            await manager.start("tv-lab")
        with pytest.raises(RuntimeError, match="raw/control"):
            await manager.send("tv-lab", b"anything")
        with pytest.raises(RuntimeError, match="started"):
            await manager.send_cmnd_guest("tv-lab", event())
        await manager.shutdown()
    asyncio.run(run())


def test_site_defaults_preserve_per_stay_identity():
    data = event()
    result = configured_event({"htng_defaults": {"hotel_code": "SITE"},
                               "room_settings": {"00101": {"telephone_extension": "999"}}}, data)
    assert result["extra"]["guest_id"] == data["extra"]["guest_id"]
    assert result["extra"]["telephone_extension"] == "0101"


def test_property_checkin_checkout_keep_guest_identity(monkeypatch, tmp_path):
    from innaware_pms_emulator import property_api
    from innaware_pms_emulator.property_state import PropertyManager, PropertyStore, RoomState
    manager = PropertyManager(PropertyStore(tmp_path / "properties.json"))
    manager.create("cmnd-lab", "CMND Synthetic Lab")
    manager.add_room("cmnd-lab", RoomState(number="00101"))
    monkeypatch.setattr(property_api, "property_manager", manager)
    sent = []

    async def transmit(name, guest_event):
        sent.append(guest_event)
        return {"ok": True, "cmnd_accepted": True, "tv_verified": False}

    monkeypatch.setattr(property_api, "_transmit_guest", transmit)

    async def run():
        await property_api.checkin("cmnd-lab", property_api.CheckinRequest(room="00101", first_name="SYNTHETIC", interface_name="tv"))
        await property_api.checkout("cmnd-lab", property_api.CheckoutRequest(room="00101", interface_name="tv"))
    asyncio.run(run())
    assert sent[0].extra["guest_id"] == sent[1].extra["guest_id"]
    assert sent[0].extra["guest_id"]


def test_runtime_delivers_both_actions(monkeypatch):
    from innaware_pms_emulator import sessions
    async def run():
        manager = InterfaceManager()
        config = build_interface_from_profile("philips-cmnd-htng-guest-tv", name="tv", enabled=False,
                    overrides={"options": {"endpoint_url": "https://cmnd.invalid/stay"}})
        await manager.create(config)
        await manager.start("tv")
        observed = []
        def post(options, data):
            observed.append(data)
            return {"sent_to": 1, "cmnd_accepted": True, "tv_verified": False,
                    "hex": CmndHtngAdapter().encode_event(data).hex()}
        monkeypatch.setattr(sessions, "post_guest_event", post)
        for action in ("checkin", "checkout"):
            result = await manager.send_cmnd_guest("tv", event(action))
            assert result["cmnd_accepted"] and not result["tv_verified"]
        assert [x["action"] for x in observed] == ["checkin", "checkout"]
        assert len(manager.get("tv").captures) == 2
        await manager.shutdown()
    asyncio.run(run())


def test_action_housekeeping_settings_are_explicit():
    options = {"htng_defaults": event()["extra"], "action_settings": {"checkout": {"housekeeping_status": "VACANT_DIRTY"}}}
    result = configured_event(options, {"action": "checkout", "room": "00101"})
    assert result["extra"]["housekeeping_status"] == "VACANT_DIRTY"


def test_console_exposes_separate_safe_cmnd_setup():
    from innaware_pms_emulator.operator_console import html
    page = html()
    assert 'id="create-cmnd"' in page
    assert 'id="cmnd-execute" checked' not in page
    assert 'CMND runtime and TV behavior are not yet qualified' in page
    assert '/api/v1/profiles/philips-cmnd-htng-guest-tv/instantiate' in page
