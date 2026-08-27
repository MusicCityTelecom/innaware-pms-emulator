from __future__ import annotations

from copy import deepcopy
from typing import Any

from pydantic import BaseModel, Field

from .models import InterfaceConfig
from .protocol_packs import active_pack_profiles


class InterfaceProfile(BaseModel):
    id: str
    name: str
    purpose: str
    protocol: str
    description: str
    maturity: str
    defaults: dict[str, Any] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)
    source: str = "built-in"


BUILTIN_PROFILES: dict[str, InterfaceProfile] = {
    "fias-pms-tcp-server": InterfaceProfile(
        id="fias-pms-tcp-server",
        name="Generic FIAS PMS - TCP Server",
        purpose="pms",
        protocol="FIAS",
        maturity="stateful",
        description="Generic FIAS-family PMS listener with property-backed database resynchronization.",
        defaults={
            "transport": "tcp_server",
            "bind_host": "0.0.0.0",
            "port": 5001,
            "options": {"framing": "crlf", "role": "pms"},
        },
        notes=["Use STX/ETX only when the target FIAS profile specifically requires it."],
    ),
    "hilton-pep-fias-tcp-server": InterfaceProfile(
        id="hilton-pep-fias-tcp-server",
        name="Hilton / PEP FIAS - TCP Server",
        purpose="pms",
        protocol="HILTON_PEP_FIAS",
        maturity="stateful",
        description="Hilton/PEP FIAS-family listener using combined guest-name semantics.",
        defaults={
            "transport": "tcp_server",
            "bind_host": "0.0.0.0",
            "port": 5001,
            "options": {"framing": "stx_etx", "role": "pms"},
        },
        notes=["No legacy ENQ/ACK handshake is enabled by this profile."],
    ),
    "mitel-1-serial": InterfaceProfile(
        id="mitel-1-serial",
        name="Mitel 1",
        purpose="pms",
        protocol="Mitel 1",
        maturity="fixture-backed",
        description="Classic Mitel-style serial hotel PMS interface with a fixed-width guest-name field and the room field at the end of name records.",
        defaults={
            "transport": "serial",
            "serial_device": None,
            "baud_rate": 1200,
            "data_bits": 8,
            "parity": "N",
            "stop_bits": 1,
            "flow_control": "xonxoff",
            "options": {
                "framing": "stx_etx",
                "transaction_framing": "stx_etx",
                "transactional_enq_ack": True,
                "auto_ack": True,
                "ack_enq": True,
                "ack_timeout": 3.0,
                "max_attempts": 3,
            },
        },
        notes=[
            "Select the actual COM/serial device before starting the interface.",
            "Use when the target PMS offers the classic Mitel hotel PMS format.",
        ],
    ),
    "mitel-2-serial": InterfaceProfile(
        id="mitel-2-serial",
        name="Mitel 2",
        purpose="pms",
        protocol="Mitel 2",
        maturity="fixture-backed",
        description="Mitel-style serial compatibility variant with the room field before a variable-length guest name, preventing long names from shifting the room field.",
        defaults={
            "transport": "serial",
            "serial_device": None,
            "baud_rate": 1200,
            "data_bits": 8,
            "parity": "N",
            "stop_bits": 1,
            "flow_control": "xonxoff",
            "options": {
                "framing": "stx_etx",
                "transaction_framing": "stx_etx",
                "transactional_enq_ack": True,
                "auto_ack": True,
                "ack_enq": True,
                "ack_timeout": 3.0,
                "max_attempts": 3,
            },
        },
        notes=[
            "Select the actual COM/serial device before starting the interface.",
            "Use this variant when a fixed-width name field causes room/name parsing failures.",
        ],
    ),
    "innform-xl-tcp-server": InterfaceProfile(
        id="innform-xl-tcp-server",
        name="TelElectronics InnForm XL - TCP Server",
        purpose="call_accounting",
        protocol="INNFORM_XL",
        maturity="transactional",
        description="Field-tested InnForm XL/TEL-style call-accounting listener and transaction endpoint.",
        defaults={
            "transport": "tcp_server",
            "bind_host": "0.0.0.0",
            "port": 5002,
            "options": {
                "framing": "raw",
                "transaction_framing": "raw",
                "auto_ack": True,
                "ack_enq": True,
                "ack_type": "ack",
                "ack_timeout": 5.0,
                "max_attempts": 3,
            },
        },
    ),
    "hobis-a-tcp-server": InterfaceProfile(
        id="hobis-a-tcp-server",
        name="HOBIS-A / Holidex - TCP Server",
        purpose="call_accounting",
        protocol="HOBIS_A",
        maturity="transactional",
        description="HOBIS-A fixed-field record with ENQ/ACK and STX/ETX/XOR-BCC transaction framing.",
        defaults={
            "transport": "tcp_server",
            "bind_host": "0.0.0.0",
            "port": 5002,
            "options": {
                "framing": "raw",
                "transaction_framing": "stx_etx_bcc",
                "auto_ack": True,
                "ack_enq": True,
                "ack_type": "ack",
                "ack_timeout": 5.0,
                "max_attempts": 3,
            },
        },
    ),
    "blind-smdr-tcp-server": InterfaceProfile(
        id="blind-smdr-tcp-server",
        name="Blind SMDR - TCP Server",
        purpose="call_accounting",
        protocol="BLIND_SMDR",
        maturity="encoder",
        description="Line-oriented blind-send SMDR endpoint with no acknowledgement transaction.",
        defaults={
            "transport": "tcp_server",
            "bind_host": "0.0.0.0",
            "port": 5002,
            "options": {"framing": "raw"},
        },
    ),
}


def _external_profiles() -> dict[str, InterfaceProfile]:
    result: dict[str, InterfaceProfile] = {}
    for raw in active_pack_profiles():
        try:
            profile = InterfaceProfile.model_validate({**raw, "source": "protocol-pack"})
        except Exception:
            continue
        # Downloaded data is allowed to add profiles, not replace a built-in
        # profile that shipped with the executable.
        if profile.id in BUILTIN_PROFILES:
            continue
        result[profile.id] = profile
    return result


def _all_profiles() -> dict[str, InterfaceProfile]:
    return {**BUILTIN_PROFILES, **_external_profiles()}


def profile_catalog() -> list[dict[str, Any]]:
    return [profile.model_dump(mode="json") for profile in _all_profiles().values()]


def build_interface_from_profile(
    profile_id: str,
    *,
    name: str,
    property_id: str | None = None,
    enabled: bool = True,
    overrides: dict[str, Any] | None = None,
) -> InterfaceConfig:
    profile = _all_profiles().get(profile_id)
    if not profile:
        raise KeyError(profile_id)
    data = deepcopy(profile.defaults)
    if overrides:
        for key, value in overrides.items():
            if key == "options" and isinstance(value, dict):
                data.setdefault("options", {}).update(value)
            else:
                data[key] = value
    data.update(
        {
            "name": name,
            "purpose": profile.purpose,
            "protocol": profile.protocol,
            "property_id": property_id,
            "enabled": enabled,
        }
    )
    return InterfaceConfig.model_validate(data)
