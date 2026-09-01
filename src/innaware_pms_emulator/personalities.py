from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .models import EmulationRole, InterfacePurpose


@dataclass(frozen=True, slots=True)
class EndpointPersonality:
    id: str
    name: str
    purpose: InterfacePurpose
    role: EmulationRole
    maturity: str
    description: str
    protocols: tuple[str, ...]
    recommended_profile: str | None = None
    defaults: dict[str, Any] = field(default_factory=dict)
    notes: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "purpose": self.purpose.value,
            "role": self.role.value,
            "maturity": self.maturity,
            "description": self.description,
            "protocols": list(self.protocols),
            "recommended_profile": self.recommended_profile,
            "defaults": self.defaults,
            "notes": list(self.notes),
        }


PERSONALITIES: dict[str, EndpointPersonality] = {
    "pms-generic-fias": EndpointPersonality(
        id="pms-generic-fias",
        name="Generic FIAS PMS",
        purpose=InterfacePurpose.PMS,
        role=EmulationRole.PMS,
        maturity="stateful",
        description="Generic PMS-side FIAS personality for standards-oriented interoperability testing.",
        protocols=("FIAS",),
        recommended_profile="fias-pms-tcp-server",
    ),
    "pms-opera-fias": EndpointPersonality(
        id="pms-opera-fias",
        name="Oracle / MICROS Opera PMS",
        purpose=InterfacePurpose.PMS,
        role=EmulationRole.PMS,
        maturity="compatibility",
        description="Opera/MICROS PMS personality using FIAS-family hotel integration records.",
        protocols=("FIAS",),
        recommended_profile="fias-pms-tcp-server",
        notes=("Select the PBX-specific framing/session profile when known; Opera/FIAS deployments vary by integration partner.",),
    ),
    "pms-hilton-pep-fias": EndpointPersonality(
        id="pms-hilton-pep-fias",
        name="Hilton / PEP FIAS PMS",
        purpose=InterfacePurpose.PMS,
        role=EmulationRole.PMS,
        maturity="stateful",
        description="Hilton/PEP PMS personality with combined guest-name FIAS semantics.",
        protocols=("HILTON_PEP_FIAS",),
        recommended_profile="hilton-pep-fias-tcp-server",
    ),
    "pms-onq": EndpointPersonality(
        id="pms-onq",
        name="Hilton OnQ PMS",
        purpose=InterfacePurpose.PMS,
        role=EmulationRole.PMS,
        maturity="encoder",
        description="OnQ-compatible PMS personality using the existing legacy hotel adapter foundation.",
        protocols=("ONQ",),
    ),
    "pms-choice-advantage": EndpointPersonality(
        id="pms-choice-advantage",
        name="Choice Advantage PMS",
        purpose=InterfacePurpose.PMS,
        role=EmulationRole.PMS,
        maturity="encoder",
        description="Choice Advantage-compatible PMS personality using the existing legacy hotel adapter foundation.",
        protocols=("CHOICE_ADVANTAGE",),
    ),
    "pbx-generic-fias": EndpointPersonality(
        id="pbx-generic-fias",
        name="Generic FIAS PBX",
        purpose=InterfacePurpose.PMS,
        role=EmulationRole.PBX,
        maturity="planned",
        description="Generic PBX-side FIAS personality for testing a PMS implementation from the PBX side.",
        protocols=("FIAS",),
    ),
    "pbx-matrix-sarvam-opera": EndpointPersonality(
        id="pbx-matrix-sarvam-opera",
        name="Matrix SARVAM UCS - MICROS Opera",
        purpose=InterfacePurpose.PMS,
        role=EmulationRole.PBX,
        maturity="field-observed",
        description="Matrix SARVAM UCS PBX personality observed using FIAS records inside STX/ETX framing over TCP in MICROS Opera mode.",
        protocols=("FIAS",),
        defaults={
            "framing": "stx_etx",
            "role": "pbx",
            "link_initiator": "pbx",
            "transport_preference": "tcp_client",
        },
        notes=("Observed on a live SARVAM UCS deployment; preserve firmware/model qualifiers in future fixtures.",),
    ),
    "pbx-matrix-type1": EndpointPersonality(
        id="pbx-matrix-type1",
        name="Matrix SARVAM UCS - Type 1",
        purpose=InterfacePurpose.PMS,
        role=EmulationRole.PBX,
        maturity="capture",
        description="Matrix Type 1 PBX personality reserved for capture-driven characterization.",
        protocols=("MATRIX_TYPE1",),
    ),
    "pbx-matrix-type2": EndpointPersonality(
        id="pbx-matrix-type2",
        name="Matrix SARVAM UCS - Type 2",
        purpose=InterfacePurpose.PMS,
        role=EmulationRole.PBX,
        maturity="compatibility",
        description="Matrix Type 2 PBX personality intended for Mitel-compatible hotel PMS testing.",
        protocols=("MITEL 1", "MITEL 2"),
        notes=("Do not mark a specific Mitel layout field-observed until a sanitized Matrix Type 2 capture proves it.",),
    ),
    "pbx-matrix-extended-starlight": EndpointPersonality(
        id="pbx-matrix-extended-starlight",
        name="Matrix SARVAM UCS - Extended Starlight",
        purpose=InterfacePurpose.PMS,
        role=EmulationRole.PBX,
        maturity="capture",
        description="Matrix Extended Starlight PBX personality reserved for capture-driven characterization.",
        protocols=("MATRIX_EXTENDED_STARLIGHT",),
    ),
    "pbx-mitel-1": EndpointPersonality(
        id="pbx-mitel-1",
        name="Mitel PBX - Type 1",
        purpose=InterfacePurpose.PMS,
        role=EmulationRole.PBX,
        maturity="fixture-backed",
        description="PBX-side Mitel 1 hotel PMS personality using the existing fixed-width Mitel record layout.",
        protocols=("MITEL 1",),
        recommended_profile="mitel-1-serial",
    ),
    "pbx-mitel-2": EndpointPersonality(
        id="pbx-mitel-2",
        name="Mitel PBX - Type 2",
        purpose=InterfacePurpose.PMS,
        role=EmulationRole.PBX,
        maturity="fixture-backed",
        description="PBX-side Mitel 2 hotel PMS personality using the variable-length guest-name compatibility layout.",
        protocols=("MITEL 2",),
        recommended_profile="mitel-2-serial",
    ),
    "pbx-voiceware-operaip": EndpointPersonality(
        id="pbx-voiceware-operaip",
        name="Voiceware PBX - OperaIP",
        purpose=InterfacePurpose.PMS,
        role=EmulationRole.PBX,
        maturity="field-observed",
        description="Voiceware-era PBX personality for the observed OperaIP ENQ/ACK plus STX/ETX command family.",
        protocols=("OPERAIP_FIAS",),
        recommended_profile="operaip-fias-tcp-server",
    ),
    "pbx-innaware-ucp": EndpointPersonality(
        id="pbx-innaware-ucp",
        name="InnAware UCP PBX",
        purpose=InterfacePurpose.PMS,
        role=EmulationRole.PBX,
        maturity="planned",
        description="InnAware UCP hospitality PBX personality used to validate UCP PMS interoperability from the opposite endpoint.",
        protocols=("FIAS", "HILTON_PEP_FIAS", "OPERAIP_FIAS", "MITEL 1", "MITEL 2"),
    ),
}


def personality_catalog() -> list[dict[str, Any]]:
    return [item.as_dict() for item in PERSONALITIES.values()]


def get_personality(personality_id: str) -> EndpointPersonality | None:
    return PERSONALITIES.get(personality_id.strip().lower())
