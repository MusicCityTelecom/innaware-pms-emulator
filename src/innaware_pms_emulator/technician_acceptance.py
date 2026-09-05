from __future__ import annotations

import re
from typing import Any, Iterable

from .compatibility_matrix import (
    COMPATIBILITY_MATRIX,
    CompatibilityEntry,
    Direction,
    SupportStatus,
)
from .compatibility_readiness import readiness_for, validate_readiness_registry
from .interop_evidence_pack import EVIDENCE_RANK


SCHEMA_VERSION = "1.0"
PRODUCER_PROJECT = "InnAware PMS-PBX Emulator"
PRODUCER_REPOSITORY = "MusicCityTelecom/innaware-pms-emulator"
_SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")

_SERIAL_FACTS = (
    "serial_device_or_adapter",
    "baud_rate",
    "data_bits",
    "parity",
    "stop_bits",
    "flow_control",
)
_TCP_FACTS = (
    "local_endpoint_role",
    "remote_endpoint_role",
    "local_address_and_port",
    "remote_address_and_port",
)


def _normalize_statuses(
    statuses: Iterable[SupportStatus | str] | None,
) -> set[SupportStatus] | None:
    if statuses is None:
        return None
    normalized = {
        status if isinstance(status, SupportStatus) else SupportStatus(status)
        for status in statuses
    }
    if not normalized:
        raise ValueError("statuses must be omitted or contain at least one support status")
    return normalized


def _matches(
    entry: CompatibilityEntry,
    *,
    pbx_family: str | None,
    transport: str | None,
    pms_protocol: str | None,
    direction: Direction | str | None,
    statuses: set[SupportStatus] | None,
) -> bool:
    if pbx_family is not None and entry.pbx_family.casefold() != pbx_family.casefold():
        return False
    if transport is not None and entry.transport.casefold() != transport.casefold():
        return False
    if pms_protocol is not None and entry.pms_protocol.casefold() != pms_protocol.casefold():
        return False
    if direction is not None:
        direction_value = direction.value if isinstance(direction, Direction) else Direction(direction).value
        if entry.direction.value != direction_value:
            return False
    if statuses is not None and entry.status not in statuses:
        return False
    return True


def _transport_acceptance(entry: CompatibilityEntry) -> dict[str, Any]:
    transport = entry.transport.casefold()
    if transport == "serial":
        return {
            "wire_test_permitted": True,
            "configuration_facts_to_record": list(_SERIAL_FACTS),
            "rules": [
                "Use explicit site or evidence-backed serial settings; this plan supplies no baud/parity/flow defaults.",
                "Record the adapter/device identity separately from the PBX application personality.",
                "Do not import TCP reconnect, timing, or endpoint behavior into serial claims.",
            ],
        }
    if transport == "tcp":
        return {
            "wire_test_permitted": True,
            "configuration_facts_to_record": list(_TCP_FACTS),
            "rules": [
                "Record endpoint roles separately from IP addresses and ports.",
                "Treat a site TCP port as installation evidence, not a universal protocol default.",
                "Do not transpose serial framing, timing, or flow-control assumptions into TCP claims.",
            ],
        }
    return {
        "wire_test_permitted": False,
        "configuration_facts_to_record": ["transport_evidence_source"],
        "rules": [
            "Transport is evidence-unqualified; do not start a serial or TCP wire test from this row.",
            "Obtain exact profile-bound transport evidence or a sanitized capture before creating a transport-specific row.",
            "Do not inherit generic Voiceware, Mitel, PhoneSuite, Matrix, or neighboring-profile transport settings.",
        ],
    }


def _direction_acceptance(entry: CompatibilityEntry) -> dict[str, Any]:
    if entry.direction is Direction.BIDIRECTIONAL:
        return {
            "direction": entry.direction.value,
            "rules": [
                "Exercise PBX-to-PMS and PMS-to-PBX observations independently.",
                "A pass in one direction does not erase a direction-specific diagnostic failure in the other.",
            ],
        }
    return {
        "direction": entry.direction.value,
        "rules": [
            f"Exercise only the registered {entry.direction.value} claim for this acceptance record.",
            "Do not manufacture the reverse direction or an aggregate bidirectional claim from this result.",
        ],
    }


def _row_plan(entry: CompatibilityEntry) -> dict[str, Any]:
    readiness = readiness_for(entry)
    transport = _transport_acceptance(entry)

    if entry.status is SupportStatus.SUPPORTED:
        mode = "supported_regression"
    elif entry.status is SupportStatus.PARTIAL:
        mode = "partial_claim_regression_and_evidence_collection"
    else:
        mode = "evidence_acquisition"

    if not transport["wire_test_permitted"]:
        mode = "transport_evidence_acquisition_only"

    return {
        "combination": {
            "pbx_family": entry.pbx_family,
            "pbx_dialect": entry.pbx_dialect,
            "transport": entry.transport,
            "pms_family": entry.pms_family,
            "pms_protocol": entry.pms_protocol,
            "direction": entry.direction.value,
        },
        "current_claim": {
            "status": entry.status.value,
            "evidence_class": entry.evidence_class.value,
            "release_ready": readiness.release_ready,
            "notes": entry.notes,
        },
        "deterministic_tests": list(entry.deterministic_tests),
        "evidence_gaps": [gap.as_dict() for gap in readiness.evidence_gaps],
        "acceptance": {
            "mode": mode,
            "transport": transport,
            "direction": _direction_acceptance(entry),
            "required_provenance": [
                "exact_emulator_source_sha",
                "pbx_model_and_firmware_when_hardware_is_used",
                "pms_product_and_version_when_a_real_pms_is_used",
                "explicit_transport_configuration",
                "direction",
                "synthetic_or_redacted_wire_bytes",
            ],
            "technician_actions": [gap.action for gap in readiness.evidence_gaps],
            "rules": [
                "Use synthetic room, guest, extension, DID, and status values; do not record guest PII in reusable artifacts.",
                "Run only against operator-authorized lab or test hardware; scheduled automation must not connect to live hotel systems.",
                "Do not auto-switch the selected personality because another protocol scores as a likely match.",
                "A passing emulator regression or live observation does not change matrix status by itself.",
                "Any compatibility promotion or new transport row requires a separate evidence review and repository change.",
                "Keep Series2 TDMoE/PRI/D-channel/0x0E station programming outside PBX-PMS application-protocol acceptance.",
            ],
            "pass_condition": (
                "Declared deterministic regressions pass and collected observations stay within the current claim; "
                "new evidence is retained with exact provenance for separate review."
            ),
            "compatibility_promotion_authorized": False,
        },
    }


def build_technician_acceptance_plan(
    *,
    source_sha: str,
    pbx_family: str | None = None,
    transport: str | None = None,
    pms_protocol: str | None = None,
    direction: Direction | str | None = None,
    statuses: Iterable[SupportStatus | str] | None = None,
) -> dict[str, Any]:
    """Build a deterministic, fail-closed acceptance plan for exact matrix rows.

    The plan is a technician/support artifact. It does not execute wire traffic,
    alter the compatibility matrix, or grant a production compatibility claim.
    It may be shared with a separate consumer such as the UCP Hospitality PMS
    Gateway as data/test knowledge only; no emulator runtime dependency is implied.
    """

    if not _SHA_RE.fullmatch(source_sha):
        raise ValueError("source_sha must be an exact 40-character Git commit SHA")

    registry_errors = validate_readiness_registry()
    if registry_errors:
        raise ValueError("compatibility readiness validation failed: " + "; ".join(registry_errors))

    normalized_statuses = _normalize_statuses(statuses)
    rows = [
        _row_plan(entry)
        for entry in COMPATIBILITY_MATRIX
        if _matches(
            entry,
            pbx_family=pbx_family,
            transport=transport,
            pms_protocol=pms_protocol,
            direction=direction,
            statuses=normalized_statuses,
        )
    ]
    if not rows:
        raise ValueError("no exact compatibility rows match the requested acceptance-plan filters")

    return {
        "schema_version": SCHEMA_VERSION,
        "producer": {
            "project": PRODUCER_PROJECT,
            "repository": PRODUCER_REPOSITORY,
            "source_sha": source_sha.casefold(),
        },
        "purpose": "standalone technician/installer PBX-PMS interoperability acceptance planning",
        "architectural_boundary": {
            "emulator_role": "standalone interoperability, simulation, capture-analysis, and diagnostic support tool",
            "ucp_role": "separate production hospitality PMS gateway/runtime",
            "exchange_mode": "data_only",
            "runtime_dependency_on_emulator": False,
        },
        "evidence_rank": [item.value for item in EVIDENCE_RANK],
        "global_rules": {
            "exact_matrix_rows_only": True,
            "synthetic_or_redacted_data_only": True,
            "automatic_profile_switching_allowed": False,
            "automatic_matrix_promotion_allowed": False,
            "unknown_transport_wire_testing_allowed": False,
        },
        "filters": {
            "pbx_family": pbx_family,
            "transport": transport,
            "pms_protocol": pms_protocol,
            "direction": (
                direction.value if isinstance(direction, Direction) else direction
            ),
            "statuses": (
                sorted(status.value for status in normalized_statuses)
                if normalized_statuses is not None
                else None
            ),
        },
        "rows": rows,
    }
