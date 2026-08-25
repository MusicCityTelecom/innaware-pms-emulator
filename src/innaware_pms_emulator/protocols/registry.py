from .fias import FiasAdapter, HiltonPepFiasAdapter
from .legacy import OnQAdapter, ChoiceAdvantageAdapter, OperaLegacyAdapter
from .call_accounting import InnFormXLAdapter, HobisAdapter, BlindSmdrAdapter


def build_registry():
    return {
        "FIAS": FiasAdapter(),
        "HILTON_PEP_FIAS": HiltonPepFiasAdapter(),
        "ONQ": OnQAdapter(),
        "CHOICE_ADVANTAGE": ChoiceAdvantageAdapter(),
        "OPERA_LEGACY": OperaLegacyAdapter(),
        "INNFORM_XL": InnFormXLAdapter(),
        "HOBIS": HobisAdapter(),
        "BLIND_SMDR": BlindSmdrAdapter(),
    }


REGISTRY = build_registry()


def protocol_catalog():
    return [
        {"id": key, "purpose": adapter.purpose, "implemented": True}
        for key, adapter in REGISTRY.items()
    ] + [
        {"id": "HOTELKEY", "purpose": "pms", "implemented": False, "transport": "http_server"},
        {"id": "HOBIC", "purpose": "call_accounting", "implemented": False},
        {"id": "HOBIS_A", "purpose": "call_accounting", "implemented": False},
        {"id": "HOBIS_B", "purpose": "call_accounting", "implemented": False},
        {"id": "HOLIDEX", "purpose": "call_accounting", "implemented": False},
        {"id": "RAW_SMDR", "purpose": "call_accounting", "implemented": False},
    ]
