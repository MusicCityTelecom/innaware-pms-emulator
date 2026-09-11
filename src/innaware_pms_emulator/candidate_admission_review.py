from __future__ import annotations

import re
from typing import Any, Mapping

from .compatibility_matrix import COMPATIBILITY_MATRIX, Direction, EvidenceClass, SupportStatus


SCHEMA_VERSION = "1.0"
CANDIDATE_SCHEMA_VERSION = "1.0"
PRODUCER_PROJECT = "InnAware PMS-PBX Emulator"
PRODUCER_REPOSITORY = "MusicCityTelecom/innaware-pms-emulator"
_SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")
_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
_REAL_ENDPOINT_ORIGINS = frozenset(
    {"real_pbx_lab", "real_pms_lab", "real_pbx_and_pms_lab"}
)
_EVIDENCE_RANK = {
    EvidenceClass.NONE.value: 0,
    EvidenceClass.INFERENCE.value: 1,
    EvidenceClass.SIMULATOR_CHARACTERIZATION.value: 2,
    EvidenceClass.LEGACY_SOURCE_PROFILE.value: 3,
    EvidenceClass.OPERATOR_CONFIRMED.value: 4,
    EvidenceClass.PACKET_CAPTURE.value: 5,
}


def _mapping(value: Any, *, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be an object")
    return value


def _exact_sha(value: Any, *, field_name: str) -> str:
    if not isinstance(value, str) or not _SHA_RE.fullmatch(value):
        raise ValueError(f"{field_name} must be an exact 40-character Git commit SHA")
    return value.casefold()


def _sha256_list(value: Any, *, field_name: str, required: bool) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list")
    normalized: set[str] = set()
    for item in value:
        if not isinstance(item, str) or not _SHA256_RE.fullmatch(item):
            raise ValueError(f"{field_name} must contain exact 64-character SHA-256 values")
        normalized.add(item.casefold())
    if required and not normalized:
        raise ValueError(f"{field_name} must contain at least one SHA-256 value")
    return sorted(normalized)


def _normalize_combination(value: Any) -> dict[str, str]:
    source = _mapping(value, field_name="combination")
    required = {
        "pbx_family",
        "pbx_dialect",
        "transport",
        "pms_family",
        "pms_protocol",
        "direction",
    }
    if set(source) != required:
        missing = sorted(required - set(source))
        extra = sorted(set(source) - required)
        details: list[str] = []
        if missing:
            details.append("missing=" + ",".join(missing))
        if extra:
            details.append("extra=" + ",".join(extra))
        raise ValueError(
            "candidate combination must contain exactly the six compatibility dimensions"
            + (": " + "; ".join(details) if details else "")
        )

    normalized: dict[str, str] = {}
    for key in sorted(required):
        raw = source[key]
        if not isinstance(raw, str) or not raw.strip():
            raise ValueError(f"candidate combination {key} must be a non-empty string")
        normalized[key] = raw.strip()
    normalized["transport"] = normalized["transport"].casefold()
    try:
        normalized["direction"] = Direction(normalized["direction"]).value
    except ValueError as exc:
        raise ValueError("candidate combination direction is not recognized") from exc
    return normalized


def _current_covering_rows(combination: Mapping[str, str]) -> list[dict[str, str]]:
    requested = (
        combination["pbx_family"].casefold(),
        combination["pbx_dialect"].casefold(),
        combination["transport"].casefold(),
        combination["pms_family"].casefold(),
        combination["pms_protocol"].casefold(),
    )
    direction = Direction(combination["direction"])
    matches = []
    for entry in COMPATIBILITY_MATRIX:
        dimensions = (
            entry.pbx_family.casefold(),
            entry.pbx_dialect.casefold(),
            entry.transport.casefold(),
            entry.pms_family.casefold(),
            entry.pms_protocol.casefold(),
        )
        if dimensions != requested:
            continue
        if entry.direction is direction or (
            entry.direction is Direction.BIDIRECTIONAL
            and direction in {Direction.PBX_TO_PMS, Direction.PMS_TO_PBX}
        ):
            matches.append(
                {
                    "direction": entry.direction.value,
                    "status": entry.status.value,
                    "evidence_class": entry.evidence_class.value,
                }
            )
    return sorted(matches, key=lambda item: (item["direction"], item["status"]))


def _validate_non_promoting_contract(candidate: Mapping[str, Any]) -> None:
    boundary = _mapping(candidate.get("architectural_boundary"), field_name="architectural_boundary")
    if boundary.get("exchange_mode") != "data_only":
        raise ValueError("candidate architectural boundary must remain data_only")
    if boundary.get("runtime_dependency_on_emulator") is not False:
        raise ValueError("candidate must not create a runtime dependency on the Emulator")

    matrix_state = _mapping(candidate.get("matrix_state"), field_name="matrix_state")
    if matrix_state.get("status") != SupportStatus.UNSUPPORTED.value:
        raise ValueError("candidate admission review only accepts unsupported pre-admission evidence")
    if matrix_state.get("registered_exact_or_covering_row") is not False:
        raise ValueError("candidate artifact already claims a registered compatibility row")

    policy = _mapping(candidate.get("claim_policy"), field_name="claim_policy")
    required_false = (
        "matrix_registration_authorized",
        "compatibility_promotion_authorized",
        "production_support_claim_authorized",
        "raw_capture_or_vendor_profile_embedded",
        "series2_tdmoe_pri_station_programming_in_scope",
    )
    for key in required_false:
        if policy.get(key) is not False:
            raise ValueError(f"candidate claim policy {key} must remain false")
    if policy.get("manual_evidence_review_required") is not True:
        raise ValueError("candidate claim policy must require manual evidence review")
    if policy.get("candidate_must_not_enter_normal_interop_fixture_pack") is not True:
        raise ValueError("candidate must remain outside the normal interop fixture pack")

    exchange = _mapping(candidate.get("consumer_exchange"), field_name="consumer_exchange")
    if exchange.get("ucp_runtime_dependency_allowed") is not False:
        raise ValueError("candidate must not allow a UCP runtime dependency on the Emulator")
    if exchange.get("candidate_is_not_a_compatibility_claim") is not True:
        raise ValueError("candidate consumer exchange must remain non-claim evidence")


def build_candidate_admission_review(
    candidate: Mapping[str, Any],
    *,
    expected_source_sha: str,
) -> dict[str, Any]:
    """Assess whether pre-admission candidate evidence is ready for human review.

    The result is deliberately non-promoting: even a review-ready packet capture cannot
    register a matrix row or establish production support. It only tells a technician
    whether the minimum evidence packet is coherent enough for a human protocol review.
    """

    candidate = _mapping(candidate, field_name="candidate")
    if candidate.get("schema_version") != CANDIDATE_SCHEMA_VERSION:
        raise ValueError(
            f"candidate schema_version must be {CANDIDATE_SCHEMA_VERSION}"
        )

    producer = _mapping(candidate.get("producer"), field_name="producer")
    if producer.get("project") != PRODUCER_PROJECT or producer.get("repository") != PRODUCER_REPOSITORY:
        raise ValueError("candidate producer project/repository does not match this Emulator")
    source_sha = _exact_sha(producer.get("source_sha"), field_name="candidate producer source_sha")
    expected_sha = _exact_sha(expected_source_sha, field_name="expected_source_sha")
    if source_sha != expected_sha:
        raise ValueError(
            "candidate source SHA does not match the exact Emulator SHA being reviewed"
        )

    _validate_non_promoting_contract(candidate)
    combination = _normalize_combination(candidate.get("combination"))
    covering_rows = _current_covering_rows(combination)
    if covering_rows:
        raise ValueError(
            "this candidate combination is now covered by a registered compatibility row; use the registered technician acceptance/result workflow instead"
        )

    result = _mapping(candidate.get("result"), field_name="result")
    status = result.get("status")
    if status not in {"observed", "rejected", "inconclusive"}:
        raise ValueError("candidate result status is not recognized")
    evidence_class = result.get("evidence_class")
    if evidence_class not in _EVIDENCE_RANK:
        raise ValueError("candidate evidence_class is not recognized")

    provenance = _mapping(result.get("endpoint_provenance"), field_name="result.endpoint_provenance")
    evidence_origin = provenance.get("evidence_origin")
    if not isinstance(evidence_origin, str) or not evidence_origin:
        raise ValueError("candidate endpoint provenance evidence_origin is required")

    observations_value = result.get("observation_codes")
    if not isinstance(observations_value, list) or not all(
        isinstance(item, str) and item for item in observations_value
    ):
        raise ValueError("candidate observation_codes must be a non-empty string list")
    observations = sorted(set(observations_value))

    wire_hashes = _sha256_list(
        result.get("wire_artifact_sha256s"),
        field_name="result.wire_artifact_sha256s",
        required=True,
    )
    diagnostic_hashes = _sha256_list(
        result.get("diagnostic_report_sha256s"),
        field_name="result.diagnostic_report_sha256s",
        required=False,
    )

    required_true = (
        "candidate_diagnostics_tests_passed",
        "exact_head_test_matrix_green",
        "exact_head_windows_build_green",
        "operator_authorized",
        "synthetic_or_redacted_wire_bytes",
    )
    for key in required_true:
        if result.get(key) is not True:
            raise ValueError(f"candidate result {key} must be true before admission review")
    if result.get("guest_pii_present") is not False:
        raise ValueError("candidate result must confirm guest_pii_present=false")

    blockers: list[dict[str, str]] = []
    if status != "observed":
        blockers.append(
            {
                "code": "affirmative_observation_missing",
                "action": "Obtain an affirmative authorized observation for this exact combination; rejected or inconclusive evidence remains useful diagnostics but is not admission-review complete.",
            }
        )
    if evidence_class != EvidenceClass.PACKET_CAPTURE.value:
        blockers.append(
            {
                "code": "packet_capture_missing",
                "action": "Obtain a sanitized packet/wire capture for this exact combination. Source, operator, and simulator evidence may guide the test but do not replace direct wire evidence at the admission gate.",
            }
        )
    if evidence_origin not in _REAL_ENDPOINT_ORIGINS:
        blockers.append(
            {
                "code": "real_endpoint_provenance_missing",
                "action": "Repeat the authorized test against at least one real PBX or PMS endpoint and record the exact model/product and version/firmware required by the candidate provenance contract.",
            }
        )
    if "wire_bytes_observed" not in observations:
        blockers.append(
            {
                "code": "wire_observation_missing",
                "action": "Preserve sanitized wire evidence for the exact transaction and reference it by SHA-256.",
            }
        )
    if "application_record_observed" not in observations:
        blockers.append(
            {
                "code": "application_record_observation_missing",
                "action": "Capture at least one application-layer record for the exact direction; transport establishment alone cannot justify an application compatibility row.",
            }
        )
    if not diagnostic_hashes:
        blockers.append(
            {
                "code": "payload_safe_diagnostic_missing",
                "action": "Run the matching bounded Emulator diagnostic and retain the payload-safe report SHA-256 so human review can correlate wire evidence without embedding guest data.",
            }
        )

    strengths: list[str] = []
    if evidence_class == EvidenceClass.PACKET_CAPTURE.value:
        strengths.append("Direct packet/wire evidence is attached by digest.")
    if evidence_origin in _REAL_ENDPOINT_ORIGINS:
        strengths.append("Endpoint provenance identifies at least one real lab endpoint.")
    if "application_record_observed" in observations:
        strengths.append("An application-layer record was observed for the exact direction.")
    if diagnostic_hashes:
        strengths.append("A payload-safe bounded diagnostic report is attached by digest.")

    if blockers:
        next_actions = [item["action"] for item in blockers]
    else:
        next_actions = [
            "Perform manual protocol review of the sanitized wire artifact and bounded diagnostic against the exact six-dimensional candidate. If the evidence justifies a new row, add only a narrowly scoped PARTIAL claim with deterministic regression coverage; do not jump directly to SUPPORTED.",
            "Keep any raw capture, vendor profile, or guest-identifying material outside Git. Export only synthetic/redacted fixtures and evidence digests after the matrix row is explicitly reviewed.",
        ]

    return {
        "schema_version": SCHEMA_VERSION,
        "producer": {
            "project": PRODUCER_PROJECT,
            "repository": PRODUCER_REPOSITORY,
            "reviewed_source_sha": expected_sha,
        },
        "purpose": "fail-closed pre-admission evidence readiness review",
        "candidate": {
            "source_sha": source_sha,
            "combination": combination,
            "result_status": status,
            "evidence_class": evidence_class,
            "evidence_rank": _EVIDENCE_RANK[evidence_class],
            "evidence_origin": evidence_origin,
            "observation_codes": observations,
            "wire_artifact_sha256s": wire_hashes,
            "diagnostic_report_sha256s": diagnostic_hashes,
        },
        "current_matrix_state": {
            "status": SupportStatus.UNSUPPORTED.value,
            "registered_exact_or_covering_row": False,
        },
        "review_gate": {
            "manual_review_ready": not blockers,
            "blocking_requirements": blockers,
            "strengths": strengths,
        },
        "claim_policy": {
            "matrix_registration_authorized": False,
            "compatibility_promotion_authorized": False,
            "production_support_claim_authorized": False,
            "automated_matrix_mutation_allowed": False,
            "human_protocol_review_required": True,
            "review_ready_does_not_equal_supported": True,
            "series2_tdmoe_pri_station_programming_in_scope": False,
        },
        "architectural_boundary": {
            "exchange_mode": "data_only",
            "ucp_runtime_dependency_allowed": False,
            "emulator_remains_standalone_support_tool": True,
        },
        "next_actions": next_actions,
    }
