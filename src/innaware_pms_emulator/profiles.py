from __future__ import annotations

from copy import deepcopy
from typing import Any

from pydantic import BaseModel, Field

from .models import InterfaceConfig


class InterfaceProfile(BaseModel):
    id: str
    name: str
    purpose: str
    protocol: str
    description: str
    maturity: str
    defaults: dict[str, Any] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


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


def profile_catalog() -> list[dict[str, Any]]:
    return [profile.model_dump(mode="json") for profile in BUILTIN_PROFILES.values()]


def build_interface_from_profile(
    profile_id: str,
    *,
    name: str,
    property_id: str | None = None,
    enabled: bool = True,
    overrides: dict[str, Any] | None = None,
) -> InterfaceConfig:
    profile = BUILTIN_PROFILES.get(profile_id)
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
