from __future__ import annotations

import re
from enum import Enum
from typing import Any, Iterable, Mapping

from .compatibility_matrix import (
    COMPATIBILITY_MATRIX,
    Direction,
    EvidenceClass,
    SupportStatus,
)
from .technician_evidence_result import EvidenceOrigin


SCHEMA_VERSION = "1.0"
PRODUCER_PROJECT = "InnAware PMS-PBX Emulator"
PRODUCER_REPOSITORY = "MusicCityTelecom/innaware-pms-emulator"
_SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")
_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")


class CandidateObservationStatus(str, Enum):
    OBSERVED = "observed"
    REJECTED = "rejected"
    INCONCLUSIVE = "inconclusive"


CANDIDATE_OBSERVATION_CODES = frozenset(
    {
        "transport_opened",
        "transport_open_failed",
        "handshake_observed",
        "handshake_timeout",
        "wire_bytes_observed",
        "application_record_observed",
        "frame_acknowledged",
        "frame_rejected",
        "reconnect_observed",
        "unexpected_wire_bytes",
        "no_wire_response",
    }
)
_OBSERVED_CODES = frozenset(
    {
        "handshake_observed",
        "wire_bytes_observed",
        "application_record_observed",
        "frame_acknowledged",
        "reconnect_observed",
    }
)
_REJECTION_CODES = frozenset(
    {
        "transport_open_failed",
        "handshake_timeout",
        "frame_rejected",
        "no_wire_response",
    }
)

_TCP_FACTS = frozenset(
    {
        "local_endpoint_role",
        "remote_endpoint_role",
        "local_address_and_port",
        "remote_address_and_port",
    }
)
_SERIAL_FACTS = frozenset(
    {
        "serial_device_or_adapter",
        "baud_rate",
        "data_bits",
        "parity",
        "stop_bits",
        "flow_control",
    }
)


def _normalize_hashes(values: Iterable[str], *, field_name: str, required: bool) -> list[str]:
    normalized: set[str] = set()
    for value in values:
        if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
            raise ValueError(f"{field_name} must contain exact 64-character SHA-256 values")
        normalized.add(value.casefold())
    if required and not normalized:
        raise ValueError(f"at least one {field_name} value is required")
    return sorted(normalized)


def _normalize_observations(values: Iterable[str]) -> list[str]:
    normalized = {
        value.strip()
        for value in values
        if isinstance(value, str) and value.strip()
    }
    if not normalized:
        raise ValueError("at least one candidate observation code is required")
    unknown = normalized - CANDIDATE_OBSERVATION_CODES
    if unknown:
        raise ValueError(
            "unknown candidate observation code(s): " + ", ".join(sorted(unknown))
        )
    return sorted(normalized)


def _normalize_endpoint_provenance(
    value: Mapping[str, Any] | None,
) -> dict[str, str]:
    source = dict(value or {})
    allowed = {
        "evidence_origin",
        "pbx_model",
        "pbx_firmware",
        "pms_product",
        "pms_version",
    }
    extra = sorted(set(source) - allowed)
    if extra:
        raise ValueError(
            "endpoint provenance contains unsupported field(s): " + ", ".join(extra)
        )

    raw_origin = source.get("evidence_origin", EvidenceOrigin.UNSPECIFIED.value)
    try:
        origin = (
            raw_origin
            if isinstance(raw_origin, EvidenceOrigin)
            else EvidenceOrigin(str(raw_origin))
        )
    except ValueError as exc:
        raise ValueError("endpoint provenance evidence_origin is not recognized") from exc

    if origin is EvidenceOrigin.UNSPECIFIED:
        raise ValueError(
            "candidate evidence requires explicit endpoint provenance evidence_origin"
        )

    normalized = {"evidence_origin": origin.value}
    for key in ("pbx_model", "pbx_firmware", "pms_product", "pms_version"):
        raw = source.get(key)
        if raw is None:
            continue
        if isinstance(raw, bool) or not isinstance(raw, (str, int, float)):
            raise ValueError(
                f"endpoint provenance {key} must be a non-empty scalar value"
            )
        text = str(raw).strip()
        if not text:
            raise ValueError(
                f"endpoint provenance {key} must be a non-empty scalar value"
            )
        normalized[key] = text

    if origin in {EvidenceOrigin.REAL_PBX_LAB, EvidenceOrigin.REAL_PBX_AND_PMS_LAB}:
        for key in ("pbx_model", "pbx_firmware"):
            if key not in normalized:
                raise ValueError(
                    f"{origin.value} evidence requires endpoint provenance {key}"
                )
    if origin in {EvidenceOrigin.REAL_PMS_LAB, EvidenceOrigin.REAL_PBX_AND_PMS_LAB}:
        for key in ("pms_product", "pms_version"):
            if key not in normalized:
                raise ValueError(
                    f"{origin.value} evidence requires endpoint provenance {key}"
                )

    if origin in {EvidenceOrigin.SYNTHETIC_REPLAY, EvidenceOrigin.EMULATOR_LAB}:
        hardware_fields = {
            "pbx_model",
            "pbx_firmware",
            "pms_product",
            "pms_version",
        } & set(normalized)
        if hardware_fields:
            raise ValueError(
                f"{origin.value} evidence must not claim real endpoint provenance fields: "
                + ", ".join(sorted(hardware_fields))
            )

    return normalized


def _normalize_transport_facts(
    transport: str,
    values: Mapping[str, Any],
) -> dict[str, str]:
    transport_value = transport.strip().casefold()
    if transport_value == "tcp":
        required = _TCP_FACTS
    elif transport_value == "serial":
        required = _SERIAL_FACTS
    else:
        raise ValueError(
            "candidate wire evidence requires an explicit evidence-qualified tcp or serial transport"
        )

    facts = dict(values)
    if set(facts) != set(required):
        missing = sorted(set(required) - set(facts))
        extra = sorted(set(facts) - set(required))
        details: list[str] = []
        if missing:
            details.append("missing=" + ",".join(missing))
        if extra:
            details.append("extra=" + ",".join(extra))
        raise ValueError(
            "transport facts must match the exact candidate transport requirements"
            + (": " + "; ".join(details) if details else "")
        )

    normalized: dict[str, str] = {}
    for key in sorted(required):
        value = facts[key]
        if isinstance(value, bool) or not isinstance(value, (str, int, float)):
            raise ValueError(f"transport fact {key} must be a non-empty scalar value")
        text = str(value).strip()
        if not text:
            raise ValueError(f"transport fact {key} must be a non-empty scalar value")
        normalized[key] = text
    return normalized


def _same_application_dimensions(
    *,
    pbx_family: str,
    pbx_dialect: str,
    transport: str,
    pms_family: str,
    pms_protocol: str,
):
    requested = (
        pbx_family.casefold(),
        pbx_dialect.casefold(),
        transport.casefold(),
        pms_family.casefold(),
        pms_protocol.casefold(),
    )
    return [
        entry
        for entry in COMPATIBILITY_MATRIX
        if (
            entry.pbx_family.casefold(),
            entry.pbx_dialect.casefold(),
            entry.transport.casefold(),
            entry.pms_family.casefold(),
            entry.pms_protocol.casefold(),
        )
        == requested
    ]


def _ensure_unregistered_candidate(
    *,
    pbx_family: str,
    pbx_dialect: str,
    transport: str,
    pms_family: str,
    pms_protocol: str,
    direction: Direction,
) -> list[dict[str, str]]:
    neighbors = _same_application_dimensions(
        pbx_family=pbx_family,
        pbx_dialect=pbx_dialect,
        transport=transport,
        pms_family=pms_family,
        pms_protocol=pms_protocol,
    )

    covered = [
        entry
        for entry in neighbors
        if entry.direction is direction
        or (
            entry.direction is Direction.BIDIRECTIONAL
            and direction in {Direction.PBX_TO_PMS, Direction.PMS_TO_PBX}
        )
    ]
    if covered:
        raise ValueError(
            "an exact or bidirectional registered compatibility row already covers this candidate; use the technician acceptance/result workflow instead"
        )

    return [
        {
            "direction": entry.direction.value,
            "status": entry.status.value,
            "evidence_class": entry.evidence_class.value,
        }
        for entry in sorted(neighbors, key=lambda item: item.direction.value)
    ]


def _diagnostics(
    *,
    status: CandidateObservationStatus,
    observations: set[str],
) -> list[str]:
    findings = [
        "Retain this exact-SHA artifact as pre-admission evidence only. It does not register a matrix row, promote compatibility, or establish production support."
    ]
    if "frame_rejected" in observations:
        findings.append(
            "A peer rejection establishes that the observed frame was rejected, not why. Preserve direction, framing, endpoint identity, timing, and sanitized bytes before attributing checksum or field-layout cause."
        )
    if "handshake_timeout" in observations or "no_wire_response" in observations:
        findings.append(
            "Verify endpoint roles and the explicit site transport facts before changing application personality or borrowing timing from a neighboring row."
        )
    if "unexpected_wire_bytes" in observations:
        findings.append(
            "Characterize the unexpected bytes independently and keep the raw capture outside the repository; reusable artifacts should reference only sanitized evidence digests."
        )
    if status is CandidateObservationStatus.OBSERVED:
        findings.append(
            "An observed candidate still requires manual evidence review before any exact six-dimensional compatibility row may be added."
        )
    return findings


def build_candidate_observation_result(
    *,
    source_sha: str,
    pbx_family: str,
    pbx_dialect: str,
    transport: str,
    pms_family: str,
    pms_protocol: str,
    direction: Direction | str,
    result_status: CandidateObservationStatus | str,
    evidence_class: EvidenceClass | str,
    transport_facts: Mapping[str, Any],
    endpoint_provenance: Mapping[str, Any] | None,
    observation_codes: Iterable[str],
    wire_artifact_sha256s: Iterable[str],
    diagnostic_report_sha256s: Iterable[str] = (),
    candidate_diagnostics_tests_passed: bool,
    exact_head_test_matrix_green: bool,
    exact_head_windows_build_green: bool,
    operator_authorized: bool,
    synthetic_or_redacted_wire_bytes: bool,
    guest_pii_present: bool,
) -> dict[str, Any]:
    """Build deterministic pre-admission evidence for one unregistered combination.

    This function never sends traffic and deliberately cannot create a PASS result,
    register a matrix row, or promote compatibility. It exists so authorized lab/Codex
    observations for an exact *unsupported* combination can be retained safely before
    a human evidence review decides whether a narrowly-scoped matrix row is justified.
    """

    if not _SHA_RE.fullmatch(source_sha):
        raise ValueError("source_sha must be an exact 40-character Git commit SHA")
    source_sha = source_sha.casefold()

    dimensions = {
        "pbx_family": str(pbx_family).strip(),
        "pbx_dialect": str(pbx_dialect).strip(),
        "transport": str(transport).strip().casefold(),
        "pms_family": str(pms_family).strip(),
        "pms_protocol": str(pms_protocol).strip(),
    }
    if any(not value for value in dimensions.values()):
        raise ValueError("candidate compatibility dimensions must be non-empty")

    direction_value = direction if isinstance(direction, Direction) else Direction(direction)
    status = (
        result_status
        if isinstance(result_status, CandidateObservationStatus)
        else CandidateObservationStatus(result_status)
    )
    evidence = (
        evidence_class
        if isinstance(evidence_class, EvidenceClass)
        else EvidenceClass(evidence_class)
    )
    if evidence in {EvidenceClass.INFERENCE, EvidenceClass.NONE}:
        raise ValueError(
            "candidate reusable evidence requires provenance stronger than inference"
        )

    nearby_claims = _ensure_unregistered_candidate(
        **dimensions,
        direction=direction_value,
    )
    facts = _normalize_transport_facts(dimensions["transport"], transport_facts)
    provenance = _normalize_endpoint_provenance(endpoint_provenance)
    observations = _normalize_observations(observation_codes)
    observation_set = set(observations)
    wire_hashes = _normalize_hashes(
        wire_artifact_sha256s,
        field_name="wire_artifact_sha256s",
        required=True,
    )
    diagnostic_hashes = _normalize_hashes(
        diagnostic_report_sha256s,
        field_name="diagnostic_report_sha256s",
        required=False,
    )

    if candidate_diagnostics_tests_passed is not True:
        raise ValueError("candidate evidence requires its deterministic diagnostics tests to pass")
    if exact_head_test_matrix_green is not True or exact_head_windows_build_green is not True:
        raise ValueError("candidate evidence requires green exact-head Test matrix and Windows Build")
    if operator_authorized is not True:
        raise ValueError("operator_authorized must be true for reusable candidate wire evidence")
    if synthetic_or_redacted_wire_bytes is not True:
        raise ValueError("synthetic_or_redacted_wire_bytes must be true for reusable candidate evidence")
    if guest_pii_present is not False:
        raise ValueError("guest PII must not be present in reusable candidate evidence")

    if status is CandidateObservationStatus.OBSERVED and not (
        observation_set & _OBSERVED_CODES
    ):
        raise ValueError("observed candidate status requires an affirmative wire observation")
    if status is CandidateObservationStatus.REJECTED and not (
        observation_set & _REJECTION_CODES
    ):
        raise ValueError("rejected candidate status requires a rejection/failure observation")

    combination = {
        **dimensions,
        "direction": direction_value.value,
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "producer": {
            "project": PRODUCER_PROJECT,
            "repository": PRODUCER_REPOSITORY,
            "source_sha": source_sha,
        },
        "purpose": "pre-admission technician/installer PBX-PMS interoperability candidate evidence",
        "architectural_boundary": {
            "emulator_role": "standalone interoperability, simulation, capture-analysis, and diagnostic support tool",
            "ucp_role": "separate production hospitality PMS gateway/runtime",
            "exchange_mode": "data_only",
            "runtime_dependency_on_emulator": False,
        },
        "combination": combination,
        "matrix_state": {
            "status": SupportStatus.UNSUPPORTED.value,
            "registered_exact_or_covering_row": False,
            "nearby_registered_claims": nearby_claims,
        },
        "result": {
            "status": status.value,
            "evidence_class": evidence.value,
            "transport_facts": facts,
            "endpoint_provenance": provenance,
            "observation_codes": observations,
            "wire_artifact_sha256s": wire_hashes,
            "diagnostic_report_sha256s": diagnostic_hashes,
            "candidate_diagnostics_tests_passed": True,
            "exact_head_test_matrix_green": True,
            "exact_head_windows_build_green": True,
            "operator_authorized": True,
            "synthetic_or_redacted_wire_bytes": True,
            "guest_pii_present": False,
        },
        "technician_diagnostics": _diagnostics(
            status=status,
            observations=observation_set,
        ),
        "claim_policy": {
            "matrix_registration_authorized": False,
            "compatibility_promotion_authorized": False,
            "production_support_claim_authorized": False,
            "manual_evidence_review_required": True,
            "transport_inferred": False,
            "direction_inferred": False,
            "candidate_must_not_enter_normal_interop_fixture_pack": True,
            "raw_capture_or_vendor_profile_embedded": False,
            "series2_tdmoe_pri_station_programming_in_scope": False,
            "scheduled_automation_live_hotel_testing_permitted": False,
        },
        "consumer_exchange": {
            "mode": "pre_admission_data_or_test_evidence_only",
            "ucp_runtime_dependency_allowed": False,
            "artifact_payload_is_digest_only": True,
            "candidate_is_not_a_compatibility_claim": True,
        },
    }
