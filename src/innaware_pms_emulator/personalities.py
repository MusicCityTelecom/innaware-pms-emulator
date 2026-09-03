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
    compatibility_family: str | None = None
    brand: str | None = None

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
            "compatibility_family": self.compatibility_family,
            "brand": self.brand,
        }


# PBX personalities are technician-facing systems/brands. Wire layouts such as
# Mitel 1 and Mitel 2 are protocol/profile choices underneath a PBX personality,
# not PBX brands themselves.
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
        compatibility_family="fias",
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
        compatibility_family="fias",
        brand="Oracle / MICROS",
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
        compatibility_family="fias",
        brand="Hilton",
    ),
    "pms-onq": EndpointPersonality(
        id="pms-onq",
        name="Hilton OnQ PMS",
        purpose=InterfacePurpose.PMS,
        role=EmulationRole.PMS,
        maturity="encoder",
        description="OnQ-compatible PMS personality using the existing legacy hotel adapter foundation.",
        protocols=("ONQ",),
        compatibility_family="mitel_hospitality",
        brand="Hilton",
    ),
    "pms-choice-advantage": EndpointPersonality(
        id="pms-choice-advantage",
        name="Choice Advantage PMS",
        purpose=InterfacePurpose.PMS,
        role=EmulationRole.PMS,
        maturity="encoder",
        description="Choice Advantage-compatible PMS personality using the existing legacy hotel adapter foundation.",
        protocols=("CHOICE_ADVANTAGE",),
        brand="Choice Hotels",
    ),
    "pbx-generic-fias": EndpointPersonality(
        id="pbx-generic-fias",
        name="Generic / Unknown FIAS PBX",
        purpose=InterfacePurpose.PMS,
        role=EmulationRole.PBX,
        maturity="planned",
        description="Generic PBX-side FIAS personality for testing a PMS implementation when the PBX brand/profile is unknown.",
        protocols=("FIAS",),
        compatibility_family="fias",
        brand="Generic",
    ),

    # Canonical technician-facing PBX brand catalog.
    "pbx-mitel-sx200": EndpointPersonality(
        id="pbx-mitel-sx200",
        name="Mitel SX-200",
        purpose=InterfacePurpose.PMS,
        role=EmulationRole.PBX,
        maturity="fixture-backed",
        description="Mitel SX-200 hospitality PBX personality. Mitel 1 and Mitel 2 are selectable wire/profile variants underneath this PBX brand.",
        protocols=("MITEL 1", "MITEL 2"),
        recommended_profile="mitel-1-serial",
        notes=("Transport may be Serial or TCP when testing the same Mitel-family application behavior through a transport wrapper.",),
        compatibility_family="mitel_hospitality",
        brand="Mitel",
    ),
    "pbx-mitel-mivoice": EndpointPersonality(
        id="pbx-mitel-mivoice",
        name="Mitel MiVoice",
        purpose=InterfacePurpose.PMS,
        role=EmulationRole.PBX,
        maturity="compatibility",
        description="Mitel MiVoice hospitality PBX personality using the Mitel-derived hotel PMS compatibility family; exact model/version quirks remain profile-qualified.",
        protocols=("MITEL 1", "MITEL 2"),
        recommended_profile="mitel-2-serial",
        notes=("Do not assume every MiVoice model/firmware uses the same field layout; keep Mitel 1 and Mitel 2 independently selectable.",),
        compatibility_family="mitel_hospitality",
        brand="Mitel",
    ),
    "pbx-phonesuite": EndpointPersonality(
        id="pbx-phonesuite",
        name="PhoneSuite",
        purpose=InterfacePurpose.PMS,
        role=EmulationRole.PBX,
        maturity="field-observed",
        description="PhoneSuite hospitality PBX personality. Treat Mitel-family compatibility as the baseline while retaining the field-observed Voiceware/OperaIP session variant as an optional profile.",
        protocols=("MITEL 1", "MITEL 2", "OPERAIP_FIAS"),
        recommended_profile="mitel-1-serial",
        notes=(
            "Voiceware-era OperaIP behavior belongs under the PhoneSuite brand as a compatibility/profile variant, not as a separate PBX manufacturer.",
            "The observed OperaIP variant uses ENQ/ACK plus STX/ETX fixed-command traffic and should remain independently selectable.",
        ),
        compatibility_family="mitel_hospitality",
        brand="PhoneSuite",
    ),
    "pbx-matrix": EndpointPersonality(
        id="pbx-matrix",
        name="Matrix",
        purpose=InterfacePurpose.PMS,
        role=EmulationRole.PBX,
        maturity="field-observed",
        description="Matrix hospitality PBX personality. Use Mitel-family compatibility for the Mitel-derived modes and preserve Matrix-specific protocol modes as separately selectable profiles.",
        protocols=("FIAS", "MITEL 1", "MITEL 2", "MATRIX_TYPE1", "MATRIX_EXTENDED_STARLIGHT"),
        defaults={"role": "pbx"},
        notes=(
            "A live Matrix SARVAM UCS in MICROS Opera mode was observed initiating FIAS LS over TCP using STX/ETX framing.",
            "Matrix Type 1, Type 2, MICROS Opera and Extended Starlight must remain mode/profile choices beneath the Matrix brand.",
        ),
        compatibility_family="mitel_hospitality",
        brand="Matrix",
    ),
    "pbx-hitachi": EndpointPersonality(
        id="pbx-hitachi",
        name="Hitachi",
        purpose=InterfacePurpose.PMS,
        role=EmulationRole.PBX,
        maturity="evidence-indexed",
        description="Hitachi hospitality PBX personality with a legacy PhoneSuite/Voiceware Epitome integration lineage. EPIT-HIT and EPIT-HIT2 are evidence-backed profile names, but their byte-level wire behavior is not yet qualified.",
        protocols=("EPIT-HIT", "EPIT-HIT2"),
        notes=(
            "Legacy profile documentation identifies EPIT-HIT as an Epitome Hitachi-emulation interface used for Navy NGIS/Navy Lodge deployments.",
            "EPIT-HIT2 is documented as a room/name field-layout correction for check-ins; do not infer framing, transport, serial defaults, or reverse-direction behavior from that description.",
            "Do not map Hitachi traffic onto a Mitel adapter unless stronger wire evidence proves a specific compatibility mode.",
        ),
        compatibility_family="hitachi",
        brand="Hitachi",
    ),
    "pbx-innaware-ucp": EndpointPersonality(
        id="pbx-innaware-ucp",
        name="InnAware UCP",
        purpose=InterfacePurpose.PMS,
        role=EmulationRole.PBX,
        maturity="planned",
        description="InnAware UCP hospitality PBX personality. It should emulate/test the Mitel-derived compatibility family plus InnAware-supported FIAS compatibility profiles.",
        protocols=("MITEL 1", "MITEL 2", "FIAS", "HILTON_PEP_FIAS", "OPERAIP_FIAS"),
        notes=("InnAware should be able to impersonate both legacy Mitel-style hotel interfaces and modern FIAS-family integrations for interoperability testing.",),
        compatibility_family="mitel_hospitality",
        brand="InnAware",
    ),
}


# Feature-branch aliases keep earlier v0.4 development references working while
# the public catalog exposes the normalized PBX brands above.
PERSONALITY_ALIASES: dict[str, str] = {
    "pbx-mitel-1": "pbx-mitel-sx200",
    "pbx-mitel-2": "pbx-mitel-mivoice",
    "pbx-voiceware-operaip": "pbx-phonesuite",
    "pbx-matrix-sarvam-opera": "pbx-matrix",
    "pbx-matrix-type1": "pbx-matrix",
    "pbx-matrix-type2": "pbx-matrix",
    "pbx-matrix-extended-starlight": "pbx-matrix",
}


def personality_catalog() -> list[dict[str, Any]]:
    return [item.as_dict() for item in PERSONALITIES.values()]


def get_personality(personality_id: str) -> EndpointPersonality | None:
    key = personality_id.strip().lower()
    key = PERSONALITY_ALIASES.get(key, key)
    return PERSONALITIES.get(key)
