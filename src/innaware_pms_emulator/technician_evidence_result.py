from __future__ import annotations

import hashlib
import json
import re
from enum import Enum
from typing import Any, Iterable, Mapping


SCHEMA_VERSION = "1.1"
PRODUCER_PROJECT = "InnAware PMS-PBX Emulator"
PRODUCER_REPOSITORY = "MusicCityTelecom/innaware-pms-emulator"
_SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")
_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")


class AcceptanceResultStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    INCONCLUSIVE = "inconclusive"


class EvidenceOrigin(str, Enum):
    UNSPECIFIED = "unspecified"
    SYNTHETIC_REPLAY = "synthetic_replay"
    EMULATOR_LAB = "emulator_lab"
    REAL_PBX_LAB = "real_pbx_lab"
    REAL_PMS_LAB = "real_pms_lab"
    REAL_PBX_AND_PMS_LAB = "real_pbx_and_pms_lab"


OBSERVATION_CODES = frosted = frozenset(
    {
        "transport_opened",
        "transport_open_failed",
        "handshake_success",
        "handshake_timeout",
        "frame_acknowledged",
        "frame_rejected",
        "application_record_accepted",
        "application_record_rejected",
        "reconnect_observed",
        "unexpected_wire_bytes",
        "no_wire_response",
    }
)
_PROTOCOL_SUCCESS_CODES = frozenset(
    {
        "handshake_success",
        "frame_acknowledged",
        "application_record_accepted",
    }
)
_FAILURE_CODES = frozenset(
    {
        "transport_open_failed",
        "handshake_timeout",
        "frame_rejected",
        "application_record_rejected",
        "unexpected_wire_bytes",
        "no_wire_response",
    }
)
_DIAGNOSTICS = {
    "transport_open_failed": (
        "Verify the explicit site transport configuration, adapter or endpoint identity, cabling, and listener state before changing application personality."
    ),
    "handshake_timeout": (
        "Verify direction, ENQ/ACK or protocol-specific handshake expectations, and the exact transport facts; do not borrow timing from another transport."
    ),
    "frame_rejected": (
        "Compare the sanitized frame against the exact dialect framing and checksum evidence before changing field layout or retry behavior."
    ),
    "application_record_rejected": (
        "Verify the exact PBX family, dialect, direction, and synthetic record layout; do not auto-switch to a neighboring personality."
    ),
    "unexpected_wire_bytes": (
        "Retain a sanitized byte-for-byte capture with framing boundaries and direction so the unexpected sequence can be characterized separately."
    ),
    "no_wire_response": (
        "Confirm endpoint roles and direction, then verify physical/link transport independently from application-protocol assumptions."
    ),
}


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")


def _normalize_hashes(values: Iterable[str]) -> list[str]:
    normalized: set[str] = set()
    for value in values:
        if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
            raise ValueError("wire_artifact_sha256s must contain exact 64-character SHA-256 values")
        normalized.add(value.casefold())
    if not normalized:
        raise ValueError("at least one sanitized wire artifact SHA-256 is required")
    return sorted(normalized)


def _normalize_observations(values: Iterable[str]) -> list[str]:
    normalized = {value.strip() for value in values if isinstance(value, str) and value.strip()}
    if not normalized:
        raise ValueError("at least one observation code is required")
    unknown = normalized - OBSERVATION_CODES
    if unknown:
        raise ValueError("unknown observation code(s): " + ", ".join(sorted(unknown)))
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
        raise ValueError("endpoint provenance contains unsupported field(s): " + ", ".join(extra))

    raw_origin = source.get("evidence_origin", EvidenceOrigin.UNSPECIFIED.value)
    try:
        origin = raw_origin if isinstance(raw_origin, EvidenceOrigin) else EvidenceOrigin(str(raw_origin))
    except ValueError as exc:
        raise ValueError("endpoint provenance evidence_origin is not recognized") from exc

    normalized = {"evidence_origin": origin.value}
    for key in ("pbx_model", "pbx_firmware", "pms_product", "pms_version"):
        raw = source.get(key)
        if raw is None:
            continue
        if isinstance(raw, bool) or not isinstance(raw, (str, int, float)):
            raise ValueError(f"endpoint provenance {key} must be a non-empty scalar value")
        text = str(raw).strip()
        if not text:
            raise ValueError(f"endpoint provenance {key} must be a non-empty scalar value")
        normalized[key] = text

    if origin in {EvidenceOrigin.REAL_PBX_LAB, EvidenceOrigin.REAL_PBX_AND_PMS_LAB}:
        for key in ("pbx_model", "pbx_firmware"):
            if key not in normalized:
                raise ValueError(f"{origin.value} evidence requires endpoint provenance {key}")
    if origin in {EvidenceOrigin.REAL_PMS_LAB, EvidenceOrigin.REAL_PBX_AND_PMS_LAB}:
        for key in ("pms_product", "pms_version"):
            if key not in normalized:
                raise _missing_pms_provenance(origin, key)

    if origin in {EvidenceOrigin.SYNTHETIC_REPLAY, EvidenceOrigin.EMULATOR_LAB}:
        hardware_fields = {"pbx_model", "pbx_firmware", "pms_product", "pms_version"} & set(normalized)
        if hardware_fields:
            raise ValueError(
                f"{origin.value} evidence must not claim real endpoint provenance fields: "
                + ", ".join(sorted(hardware_fields))
            )

    return normalized


def _missing_pms_provenance(origin: EvidenceOrigin, key: str) -> ValueError:
    return ValueError(f"{origin.value} evidence requires endpoint provenance {key}")


def _validate_plan(
    plan: Mapping[str, Any],
    *,
    source_sha: str,
) -> tuple[dict[str, Any], str]:
    producer = plan.get("producer")
    if not isinstance(producer, Mapping):
        raise ValueError("acceptance plan producer metadata is missing")
    if producer.get("project") != PRODUCER_PROJECT or producer.get("repository") != PRODUCER_REPOSITORY:
        raise ValueError("acceptance plan producer does not identify this standalone emulator project")
    if str(producer.get("source_sha", "")).casefold() != source_sha.casefold():
        raise ValueError("acceptance plan producer SHA does not match source_sha")

    boundary = plan.get("architectural_boundary")
    if not isinstance(boundary, Mapping):
        raise ValueError("acceptance plan architectural boundary is missing")
    if boundary.get("exchange_mode") != "data_only" or boundary.get("runtime_dependency_on_emulator") is not False:
        raise do_not_couple_error()

    rows = plan.get("rows")
    if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
        raise ValueError("acceptance result requires a plan containing exactly one compatibility row")
    row = rows[0]
    acceptance = row.get("acceptance")
    if not isinstance(acceptance, Mapping):
        raise ValueError("acceptance row metadata is missing")
    if acceptance.get("compatibility_promotion_authorized") is not False:
        raise ValueError("acceptance plan must not authorize compatibility promotion")

    transport = acceptance.get("transport")
    if not isinstance(transport, Mapping) or transport.get("wire_test_permitted") is not True:
        raise ValueError("wire evidence cannot be recorded for an evidence-unqualified transport row")

    digest = hashlib.sha256(_canonical_json_bytes(plan)).hexdigest()
    return row, digest


def do_not_couple_error() -> ValueError:
    return ValueError("acceptance plan does not preserve the data-only project boundary")


def _validate_transport_facts(
    row: Mapping[str, Any],
    transport_facts: Mapping[str, Any],
) -> dict[str, str]:
    acceptance = row["acceptance"]
    transport = acceptance["transport"]
    required = transport.get("configuration_facts_to_record")
    if not isinstance(required, list) or not required or not all(isinstance(item, str) and item for item in required):
        raise ValueError("acceptance plan transport fact requirements are invalid")

    facts = dict(transport_facts)
    if set(facts) != set(required):
        missing = sorted(set(required) - set(facts))
        extra = sorted(set(facts) - set(required))
        detail = []
        if missing:
            detail.append("missing=" + ",".join(missing))
        if extra:
            detail.append("extra=" + ",".join(extra))
        raise ValueError("transport facts must match the exact acceptance-plan requirements" + (": " + "; ".join(detail) if detail else ""))

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


def _diagnostics(
    status: AcceptanceResultStatus,
    observations: set[str],
    provenance: Mapping[str, str],
) -> list[str]:
    findings = [_DIAGNOSTICS[code] for code in sorted(observations) if code in _DIAGNOSTICS]
    if status is AcceptanceResultStatus.PASS:
        findings.append(
            "Retain this exact-SHA result and sanitized evidence as regression knowledge; a pass does not change compatibility status or authorize production support."
        )
        if provenance.get("evidence_origin") in {
            EvidenceOrigin.SYNTHETIC_REPLAY.value,
            EvidenceOrigin.EMULATOR_LAB.value,
        }:
            findings.append(
                "This pass is simulator/emulator evidence only; it does not close a real-hardware evidence gap or qualify hardware-specific transport defaults."
            )
    elif status is AcceptanceResultStatus.INCONCLUSIVE:
        findings.append(
            "Repeat the exact row with explicit transport facts and synthetic/redacted wire evidence; do not infer the missing behavior from another personality or transport."
        )
    return findings


def build_technician_evidence_result(
    *,
    source_sha: str,
    acceptance_plan: Mapping[str, Any],
    result_status: AcceptanceResultStatus | str,
    transport_facts: Mapping[str, Any],
    observation_codes: Iterable[str],
    wire_artifact_sha256s: Iterable[str],
    deterministic_tests_passed: bool,
    exact_head_test_matrix_green: bool,
    exact_head_windows_build_green: bool,
    operator_authorized: bool,
    synthetic_or_redacted_wire_bytes: bool,
    guest_pii_present: bool,
    endpoint_provenance: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a deterministic technician/Codex acceptance-result artifact.

    This records evidence for one already-registered six-dimensional matrix row.
    It never sends traffic, changes the matrix, promotes compatibility, embeds raw
    captures, or creates a runtime dependency for the separate UCP Hospitality
    PMS Gateway.
    """

    if not _SHA_RE.fullmatch(source_sha):
        raise ValueError("source_sha must be an exact 40-character Git commit SHA")
    source_sha = source_sha.casefold()

    row, plan_sha256 = _validate_plan(acceptance_plan, source_sha=source_sha)
    facts = _validate_transport_facts(row, transport_facts)
    provenance = _normalize_endpoint_provenance(endpoint_provenance)
    observations = _normalize_observations(observation_codes)
    observation_set = set(observations)
    artifact_hashes = _normalize_hashes(wire_artifact_sha256s)

    status = result_status if isinstance(result_status, AcceptanceResultStatus) else AcceptanceResultStatus(result_status)

    if operator_authorized is not True:
        raise ValueError("operator_authorized must be true for reusable wire-test evidence")
    if synthetic_or_redacted_wire_bytes is not True:
        raise ValueError("synthetic_or_redacted_wire_bytes must be true for reusable evidence")
    if guest_pii_present is not False:
        raise ValueError("guest PII must not be present in reusable technician evidence")

    if status is AcceptanceResultStatus.PASS:
        if provenance["evidence_origin"] == EvidenceOrigin.UNSPECIFIED.value:
            raise ValueError("pass requires explicit endpoint provenance evidence_origin")
        if not deterministic_tests_passed:
            raise ValueError("pass requires the row's declared deterministic tests to pass")
        if not exact_head_test_matrix_green or not exact_head_windows_build_green:
            raise ValueError("pass requires green exact-head Test matrix and Windows Build")
        if not (observation_set & _PROTOCOL_SUCCESS_CODES):
            raise ValueError("pass requires at least one protocol-level success observation")
        if observation_set & _FAILURE_CODES:
            raise ValueError("pass cannot contain failure observation codes")
    elif status is AcceptanceResultStatus.FAIL and not (observation_set & _FAILURE_CODES):
        raise ValueError("fail requires at least one failure observation code")

    combination = row.get("combination")
    current_claim = row.get("current_claim")
    if not isinstance(combination, Mapping) or not isinstance(current_claim, Mapping):
        raise ValueError("acceptance row does not contain an exact compatibility claim")

    return {
        "schema_version": SCHEMA_VERSION,
        "producer": {
            "project": PRODUCER_PROJECT,
            "repository": PRODUCER_REPOSITORY,
            "source_sha": source_sha,
        },
        "purpose": "deterministic technician/installer PBX-PMS interoperability evidence result",
        "architectural_boundary": {
            "emulator_role": "standalone interoperability, simulation, capture-analysis, and diagnostic support tool",
            "ucp_role": "separate production hospitality PMS gateway/runtime",
            "exchange_mode": "data_only",
            "runtime_dependency_on_emulator": False,
        },
        "acceptance_plan_sha256": plan_sha256,
        "combination": dict(combination),
        "current_claim": dict(current_claim),
        "result": {
            "status": status.value,
            "transport_facts": facts,
            "endpoint_provenance": provenance,
            "observation_codes": observations,
            "wire_artifact_sha256s": artifact_hashes,
            "deterministic_tests_passed": bool(deterministic_tests_passed),
            "exact_head_test_matrix_green": bool(exact_head_test_matrix_green),
            "exact_head_windows_build_green": bool(exact_head_windows_build_green),
            "operator_authorized": True,
            "synthetic_or_redacted_wire_bytes": True,
            "guest_pii_present": False,
        },
        "technician_diagnostics": _diagnostics(status, observation_set, provenance),
        "claim_policy": {
            "compatibility_promotion_authorized": False,
            "matrix_mutation_authorized": False,
            "result_may_only_apply_to_exact_combination_and_direction": True,
            "partial_or_planned_pass_is_not_production_support": True,
            "raw_capture_or_vendor_profile_embedded": False,
            "series2_tdmoe_pri_station_programming_in_scope": False,
            "hardware_evidence_requires_explicit_model_version_provenance": True,
            "scheduled_automation_live_hotel_testing_permitted": False,
        },
        "consumer_exchange": {
            "mode": "data_or_test_evidence_only",
            "ucp_runtime_dependency_allowed": False,
            "artifact_payload_is_digest_only": True,
        },
    }
