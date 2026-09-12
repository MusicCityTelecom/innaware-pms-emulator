"""Original HTNG 2011B codec using the schemas distributed with CMND.

Schema evidence is not CMND runtime or physical-TV qualification. No vendor
implementation or schema files are redistributed by this module.
"""
from __future__ import annotations

import re
from typing import Any
from xml.etree import ElementTree as ET

from .base import DecodedRecord

SOAP = "http://schemas.xmlsoap.org/soap/envelope/"
HTNG = "http://htng.org/2011B"
OTA = "http://www.opentravel.org/OTA/2003/05"
ACTIONS = {"checkin": "CheckedIn", "checkout": "CheckedOut"}
RECORDS = {"checkin": "HTNG_HotelCheckInNotif", "checkout": "HTNG_HotelCheckOutNotif"}
HOUSEKEEPING = {
    "NEEDS_INSPECTION", "OCCUPIED_CLEAN", "OCCUPIED_DIRTY", "OFF_MARKET",
    "OUT_OF_ORDER", "PICKUP", "VACANT_CLEAN", "VACANT_DIRTY",
}


def _text(value: Any, label: str, maximum: int = 128, *, required: bool = True) -> str:
    if not isinstance(value, str) or (required and not value.strip()) or len(value) > maximum:
        raise ValueError(f"CMND {label} must be a {'nonempty ' if required else ''}string of at most {maximum} characters")
    if any(not (c in "\t\n\r" or 0x20 <= ord(c) <= 0xD7FF or
                0xE000 <= ord(c) <= 0xFFFD or 0x10000 <= ord(c) <= 0x10FFFF) for c in value):
        raise ValueError(f"CMND {label} contains an invalid XML character")
    return value


def parse_xml(payload: bytes) -> ET.Element:
    # UTF-8/ASCII only: reject alternate encodings before checking declarations.
    if len(payload) > 65536:
        raise ValueError("CMND SOAP document exceeds 64 KiB")
    try:
        text = payload.decode("utf-8-sig")
        if "\x00" in text or re.search(r"<!\s*(DOCTYPE|ENTITY)", text, re.I):
            raise ValueError("CMND XML declarations/entities are not permitted")
        if re.search(r'encoding\s*=\s*[\"\'](?!utf-8|us-ascii|ascii)', text, re.I):
            raise ValueError("CMND XML must use UTF-8 or ASCII")
        return ET.fromstring(text)
    except (UnicodeError, ET.ParseError) as exc:
        raise ValueError("Invalid CMND SOAP XML") from exc


class CmndHtngAdapter:
    name = "CMND_HTNG_2011B"
    purpose = "pms"

    @staticmethod
    def soap_action(action: str) -> str:
        if action not in ACTIONS:
            raise ValueError("CMND supports checkin and checkout only")
        return f"{HTNG}/HTNG_GuestAndRoomStatusService#{ACTIONS[action]}"

    def encode_event(self, event: dict[str, Any]) -> bytes:
        action = str(event.get("action", "")).lower()
        self.soap_action(action)
        extra = event.get("extra") or {}
        if not isinstance(extra, dict):
            raise ValueError("CMND extra must be an object")
        room = _text(event.get("room"), "room", 16)
        hotel = _text(extra.get("hotel_code"), "extra.hotel_code", 64)
        guest = _text(extra.get("guest_id"), "extra.guest_id", 64)
        # Do not assume a room number is a telephone extension or infer the
        # hotel's housekeeping status from a TV check-in/out operation.
        extension = _text(extra.get("telephone_extension"), "extra.telephone_extension", 8)
        status = extra.get("housekeeping_status")
        if not isinstance(status, str) or status not in HOUSEKEEPING:
            raise ValueError("CMND extra.housekeeping_status must be an HTNG housekeeping value")
        uid_type = _text(extra.get("guest_id_type"), "extra.guest_id_type", 16)
        if not re.fullmatch(r"[0-9]+", uid_type):
            raise ValueError("CMND guest_id_type must be an operator-qualified OTA numeric code")
        envelope = ET.Element(f"{{{SOAP}}}Envelope")
        body = ET.SubElement(envelope, f"{{{SOAP}}}Body")
        request = ET.SubElement(body, f"{{{HTNG}}}{RECORDS[action]}RQ", Version="1.001")
        ET.SubElement(request, f"{{{HTNG}}}PropertyInfo", HotelCode=hotel)
        affected = ET.SubElement(request, f"{{{HTNG}}}AffectedGuests")
        ET.SubElement(affected, f"{{{HTNG}}}UniqueID", ID=guest, Type=uid_type)
        room_node = ET.SubElement(request, f"{{{HTNG}}}Room", RoomID=room)
        ET.SubElement(room_node, f"{{{HTNG}}}RoomType")
        phones = ET.SubElement(room_node, f"{{{HTNG}}}TelephoneExtensions")
        # The source XSD spells this element "Extention" (without the s).
        ET.SubElement(phones, f"{{{HTNG}}}TelephoneExtention").text = extension
        ET.SubElement(room_node, f"{{{HTNG}}}HKStatus").text = status
        reservations = ET.SubElement(request, f"{{{HTNG}}}HotelReservations")
        reservation = ET.SubElement(reservations, f"{{{OTA}}}HotelReservation")
        guests = ET.SubElement(reservation, f"{{{OTA}}}ResGuests")
        res_guest = ET.SubElement(guests, f"{{{OTA}}}ResGuest")
        profiles = ET.SubElement(res_guest, f"{{{OTA}}}Profiles")
        info = ET.SubElement(profiles, f"{{{OTA}}}ProfileInfo")
        ET.SubElement(info, f"{{{OTA}}}UniqueID", ID=guest, Type=uid_type)
        profile = ET.SubElement(info, f"{{{OTA}}}Profile")
        customer = ET.SubElement(profile, f"{{{OTA}}}Customer")
        if action == "checkin":
            language = event.get("language")
            if language:
                language = _text(language, "language", 32)
                if not re.fullmatch(r"[A-Za-z]{1,8}(?:-[A-Za-z0-9]{1,8})*", language):
                    raise ValueError("CMND language must be an XML language tag")
                customer.set("Language", language)
            name = ET.SubElement(customer, f"{{{OTA}}}PersonName")
            first = _text(event.get("first_name", ""), "first_name", required=False)
            last = _text(event.get("last_name", ""), "last_name", required=False)
            if first:
                ET.SubElement(name, f"{{{OTA}}}GivenName").text = first
            ET.SubElement(name, f"{{{OTA}}}Surname").text = last
        # ASCII with XML character references survives the existing wire viewer
        # without corrupting Unicode names. XML consumers recover exact Unicode.
        return ET.tostring(envelope, encoding="us-ascii", xml_declaration=True)

    def decode(self, payload: bytes) -> DecodedRecord:
        root = parse_xml(payload)
        body = root.find(f"{{{SOAP}}}Body") if root.tag == f"{{{SOAP}}}Envelope" else None
        if body is None or len(body) != 1:
            raise ValueError("CMND requires one SOAP 1.1 body record")
        record = body[0]
        if record.tag == f"{{{SOAP}}}Fault":
            return DecodedRecord("cmnd_fault", fields={"success": False}, raw=payload)
        for action, name in RECORDS.items():
            if record.tag == f"{{{HTNG}}}{name}RS":
                success = record.find(f"{{{HTNG}}}Success") is not None
                errors = record.find(f"{{{HTNG}}}Errors") is not None
                return DecodedRecord("cmnd_response", fields={"action": action, "success": success and not errors}, raw=payload)
        raise ValueError("Unexpected CMND HTNG response type or namespace")
