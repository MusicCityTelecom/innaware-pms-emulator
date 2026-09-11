from __future__ import annotations

import re
from typing import Any

from .compatibility_matrix import Direction, find_compatibility


SCHEMA_VERSION = "1.0"
PRODUCER_PROJECT = "InnAware PMS-PBX Emulator"
PRODUCER_REPOSITORY = "MusicCityTelecom/innaware-pms-emulator"
EVIDENCE_CLASS = "legacy_source_profile"

_SHA40_RE = re.compile(r"^[0-9a-fA-F]{40}$")

_TARGETS: dict[str, dict[str, str]] = {
    "EPIT-HIT": {
        "pbx_dialect": "EPIT-HIT / Epitome Hitachi emulation",
        "source_purpose": (
            "Epitome Hitachi-emulation interface; the source identifies this as the "
            "normal EPIT-HIT profile lineage."
        ),
    },
    "EPIT-HIT2": {
        "pbx_dialect": "EPIT-HIT2 / Epitome Hitachi room-name layout variant",
        "source_purpose": (
            "Corrective Epitome Hitachi variant for cases where normal check-in fails "
            "because room-number and guest-name placement is not what the peer expects."
        ),
    },
}

_ALLOWED_SYMPTOMS = {
    "unknown",
    "baseline",
    "checkin_failure",
    "room_name_mismatch",
}

_CONCRETE_TRANSPORTS = {"serial", "tcp", "tcp_client", "tcp_server"}


def _require_source_sha(value: str) -> str:
    normalized = str(value).strip()
    if not _SHA40_RE.fullmatch(normalized):
        raise ValueError("source_sha must be an exact 40-character Git commit SHA")
    return normalized.casefold()


def _normalize_protocol(value: str) -> str:
    normalized = str(value).strip().upper()
    if normalized not in _TARGETS:
        raise ValueError("pms_protocol must be EPIT-HIT or EPIT-HIT2")
    return normalized


def _normalize_symptom(value: str) -> str:
    normalized = str(value).strip().lower().replace("-", "_")
    if normalized not in _ALLOWED_SYMPTOMS:
        raise ValueError(
            "symptom must be one of: "
            + ", ".join(sorted(_ALLOWED_SYMPTOMS))
        )
    return normalized


def _normalize_requested_transport(value: str | None) -> str:
    if value is None:
        return "unknown"
    normalized = str(value).strip().lower().replace("-", "_")
    if normalized not in _CONCRETE_TRANSPORTS | {"unknown"}:
        raise ValueError(
            "requested_transport must be serial, tcp, tcp_client, tcp_server, or unknown"
        )
    return normalized


def _source_profile_hint(symptom: str) -> tuple[str | None, str]:
    if symptom == "baseline":
        return (
            "EPIT-HIT",
            "The legacy setup source identifies EPIT-HIT as the normal Epitome Hitachi-emulation profile.",
        )
    if symptom in {"checkin_failure", "room_name_mismatch"}:
        return (
            "EPIT-HIT2",
            "The legacy setup source identifies EPIT-HIT2 as the corrective room/name-placement variant when normal check-in fails.",
        )
    return (
        None,
        "No source-backed profile-selection hint is available without a qualifying symptom.",
    )


def build_hitachi_source_guidance(
    *,
    source_sha: str,
    pms_protocol: str,
    symptom: str = "unknown",
    requested_transport: str | None = None,
) -> dict[str, Any]:
    """Return a fail-closed source-lineage diagnostic for Hitachi/Epitome.

    This is technician guidance derived from legacy setup documentation, not a
    wire-protocol implementation. The source establishes the EPIT-HIT lineage
    and the purpose of EPIT-HIT2, but it does not state the Hitachi transport.
    Adjacent serial/TCP profile descriptions therefore cannot be inherited.
    """

    pinned_sha = _require_source_sha(source_sha)
    protocol = _normalize_protocol(pms_protocol)
    normalized_symptom = _normalize_symptom(symptom)
    transport = _normalize_requested_transport(requested_transport)
    target = _TARGETS[protocol]

    entry = find_compatibility(
        pbx_family="Hitachi",
        pbx_dialect=target["pbx_dialect"],
        transport="unknown",
        pms_family="Epitome",
        pms_protocol=protocol,
        direction=Direction.PMS_TO_PBX,
    )
    profile_hint, profile_hint_reason = _source_profile_hint(normalized_symptom)

    transport_requested = transport in _CONCRETE_TRANSPORTS
    transport_action = (
        "Treat the requested transport as unqualified. Obtain an explicit profile "
        "transport declaration or sanitized real wire capture before creating a "
        "transport-specific matrix row."
        if transport_requested
        else
        "Determine the actual transport from the exact legacy profile body or a "
        "sanitized real endpoint/wire observation; do not infer it from neighboring profiles."
    )

    actions = [
        (
            "Acquire psip-pbx-protocol.Epitome, psip-pbx-protocol.EPIT-HIT, and "
            "psip-pbx-protocol.EPIT-HIT2 read-only; SHA-256 the originals and use "
            "the existing sanitized Hitachi profile-evidence bundle/admission workflow."
        ),
        transport_action,
        (
            "If EPIT-HIT2 is being investigated, compare the sanitized EPIT-HIT -> "
            "EPIT-HIT2 record-layout delta before changing a live profile; the source "
            "hint is not authorization to auto-switch a production interface."
        ),
        (
            "Keep any future Hitachi transport/framing/timing claim separate from "
            "generic Voiceware, PhoneSuite, FIAS, Mitel, or call-accounting behavior."
        ),
    ]

    return {
        "schema_version": SCHEMA_VERSION,
        "producer": {
            "project": PRODUCER_PROJECT,
            "repository": PRODUCER_REPOSITORY,
            "source_sha": pinned_sha,
        },
        "purpose": (
            "Technician-facing source-lineage guidance for the Hitachi/Epitome "
            "fifth-family evidence surface without inventing wire behavior."
        ),
        "evidence_class": EVIDENCE_CLASS,
        "combination": {
            "pbx_family": "Hitachi",
            "pbx_dialect": target["pbx_dialect"],
            "transport": "unknown",
            "pms_family": "Epitome",
            "pms_protocol": protocol,
            "direction": "pms_to_pbx",
        },
        "current_matrix": {
            "status": entry.status.value,
            "evidence_class": entry.evidence_class.value,
            "transport": entry.transport,
        },
        "source_contract": {
            "profile": protocol,
            "purpose": target["source_purpose"],
            "hitachi_transport_stated_by_source": False,
            "hitachi_framing_stated_by_source": False,
            "hitachi_control_sequence_stated_by_source": False,
            "hitachi_serial_parameters_stated_by_source": False,
            "exact_record_offsets_stated_by_source": False,
            "reverse_direction_stated_by_source": False,
            "neighboring_profile_transport_must_not_be_inherited": True,
        },
        "symptom": normalized_symptom,
        "source_profile_hint": {
            "profile": profile_hint,
            "reason": profile_hint_reason,
            "auto_profile_change_authorized": False,
        },
        "requested_transport": {
            "value": transport,
            "concrete_transport_requested": transport_requested,
            "evidence_qualified": False,
        },
        "technician_actions": actions,
        "claim_policy": {
            "transport_inferred": False,
            "framing_inferred": False,
            "control_sequence_inferred": False,
            "serial_defaults_inferred": False,
            "record_offsets_inferred": False,
            "reverse_direction_inferred": False,
            "source_profile_hint_is_compatibility_claim": False,
            "compatibility_promotion_authorized": False,
            "runtime_profile_auto_change_authorized": False,
            "ucp_runtime_dependency_allowed": False,
            "series2_station_programming_in_scope": False,
        },
        "architectural_boundary": {
            "exchange_mode": "data_only",
            "runtime_dependency_on_emulator": False,
            "ucp_runtime_dependency_allowed": False,
        },
    }
