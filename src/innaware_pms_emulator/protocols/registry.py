from .call_accounting import (
    BlindSmdrAdapter,
    HobisAAdapter,
    HobisAdapter,
    HolidexAdapter,
    InnFormXLAdapter,
)
from .fias import FiasAdapter, HiltonPepFiasAdapter
from .legacy import ChoiceAdvantageAdapter, OnQAdapter, OperaLegacyAdapter
from .mitel import Mitel1Adapter, Mitel2Adapter


def build_registry():
    mitel_1 = Mitel1Adapter()
    mitel_2 = Mitel2Adapter()
    return {
        "FIAS": FiasAdapter(),
        "HILTON_PEP_FIAS": HiltonPepFiasAdapter(),
        "MITEL 1": mitel_1,
        "MITEL 2": mitel_2,
        # Historical/internal aliases are retained only so old saved emulator
        # configurations can be restored. They are hidden from the public
        # catalog so technicians see only Mitel 1 and Mitel 2.
        "MITEL_1": mitel_1,
        "MITEL_2": mitel_2,
        "DEFAULT": mitel_1,
        "DEFAULT2": mitel_2,
        "ONQ": OnQAdapter(),
        "CHOICE_ADVANTAGE": ChoiceAdvantageAdapter(),
        "OPERA_LEGACY": OperaLegacyAdapter(),
        "INNFORM_XL": InnFormXLAdapter(),
        "HOBIS": HobisAdapter(),
        "HOBIS_A": HobisAAdapter(),
        "HOLIDEX": HolidexAdapter(),
        "BLIND_SMDR": BlindSmdrAdapter(),
    }


REGISTRY = build_registry()


_HOBIS_RECOMMENDED = {
    "framing": "raw",
    "transaction_framing": "stx_etx_bcc",
    "ack_timeout": 5.0,
    "max_attempts": 3,
}

_MITEL_RECOMMENDED = {
    "transport": "serial",
    "baud_rate": 1200,
    "data_bits": 8,
    "parity": "N",
    "stop_bits": 1,
    "flow_control": "xonxoff",
    "framing": "stx_etx",
    "transaction_framing": "stx_etx",
    "transactional_enq_ack": True,
    "auto_ack": True,
    "ack_enq": True,
    "ack_timeout": 3.0,
    "max_attempts": 3,
}


PROTOCOL_METADATA = {
    "FIAS": {
        "maturity": "stateful",
        "description": "Generic FIAS-family PMS adapter with link negotiation, posting acknowledgement and property database resync.",
        "recommended": {"framing": "crlf", "role": "pms"},
    },
    "HILTON_PEP_FIAS": {
        "maturity": "stateful",
        "description": "Hilton/PEP FIAS-family adapter using combined guest-name semantics and no separate GF field.",
        "recommended": {"framing": "stx_etx", "role": "pms"},
    },
    "MITEL 1": {
        "maturity": "fixture-backed",
        "public_id": "Mitel 1",
        "description": "Classic Mitel-style serial hotel PMS layout: fixed-width name field followed by the five-character room field, with ENQ/ACK and STX/ETX transactions.",
        "recommended": _MITEL_RECOMMENDED,
    },
    "MITEL 2": {
        "maturity": "fixture-backed",
        "public_id": "Mitel 2",
        "description": "Mitel-style serial compatibility layout: five-character room field before a variable-length guest name so long names cannot shift the room field.",
        "recommended": _MITEL_RECOMMENDED,
    },
    "MITEL_1": {"hidden": True},
    "MITEL_2": {"hidden": True},
    "DEFAULT": {"hidden": True},
    "DEFAULT2": {"hidden": True},
    "ONQ": {
        "maturity": "encoder",
        "description": "OnQ-style legacy PMS message encoding foundation; additional session behavior remains under development.",
        "recommended": {"framing": "raw"},
    },
    "CHOICE_ADVANTAGE": {
        "maturity": "encoder",
        "description": "Choice Advantage-style legacy PMS encoding foundation; profile-specific session behavior remains under development.",
        "recommended": {"framing": "raw"},
    },
    "OPERA_LEGACY": {
        "maturity": "encoder",
        "description": "Legacy Opera-style PMS encoding foundation; use FIAS for Oracle/MICROS FIAS-family testing.",
        "recommended": {"framing": "raw"},
    },
    "INNFORM_XL": {
        "maturity": "transactional",
        "description": "TelElectronics InnForm XL/TEL fixed-field call-accounting records with optional ENQ/ACK transaction mode.",
        "recommended": {"framing": "raw", "transaction_framing": "raw", "ack_timeout": 5.0, "max_attempts": 3},
    },
    "HOBIS": {
        "maturity": "transactional",
        "description": "Verified HOBIS-A fixed-field call record with ENQ/ACK then STX record ETX XOR-BCC and ACK.",
        "recommended": _HOBIS_RECOMMENDED,
    },
    "HOBIS_A": {
        "maturity": "transactional",
        "description": "Explicit HOBIS-A compatibility name using the verified HOBIS-A fixed-field layout.",
        "recommended": _HOBIS_RECOMMENDED,
    },
    "HOLIDEX": {
        "maturity": "transactional",
        "description": "Holidex compatibility alias for the verified HOBIS/Holidex HOBIS-A transaction family.",
        "recommended": _HOBIS_RECOMMENDED,
    },
    "BLIND_SMDR": {
        "maturity": "encoder",
        "description": "Blind-send line-oriented SMDR/call-accounting output with no acknowledgement transaction.",
        "recommended": {"framing": "raw"},
    },
}


def protocol_catalog():
    catalog = []
    for key, adapter in REGISTRY.items():
        metadata = PROTOCOL_METADATA.get(key, {})
        if metadata.get("hidden"):
            continue
        public_id = metadata.get("public_id", key)
        item = {
            "id": public_id,
            "purpose": adapter.purpose,
            "implemented": True,
            **metadata,
        }
        item.pop("hidden", None)
        item.pop("public_id", None)
        catalog.append(item)
    catalog.extend([
        {"id": "HOTELKEY", "purpose": "pms", "implemented": False, "transport": "http_server", "maturity": "planned"},
        {"id": "HOBIC", "purpose": "call_accounting", "implemented": False, "maturity": "planned"},
        {"id": "HOBIS2", "purpose": "call_accounting", "implemented": False, "maturity": "planned", "description": "Five-digit-extension HOBIS variant; exact fixture work pending."},
        {"id": "HOBIS_B", "purpose": "call_accounting", "implemented": False, "maturity": "planned"},
        {"id": "MICROS_CA", "purpose": "call_accounting", "implemented": False, "maturity": "planned"},
        {"id": "ROOMKEY", "purpose": "call_accounting", "implemented": False, "maturity": "planned"},
        {"id": "PROFITWATCH", "purpose": "call_accounting", "implemented": False, "maturity": "planned"},
        {"id": "RAW_SMDR", "purpose": "call_accounting", "implemented": False, "maturity": "planned"},
    ])
    return catalog
