from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Mapping

from .compatibility_matrix import Direction, find_compatibility
from .compatibility_readiness import readiness_for
from .hitachi_profile_evidence import (
    EXPECTED_PROFILE_NAMES,
    PRODUCER_REPOSITORY,
    SCHEMA_VERSION,
    hitachi_bundle_digest,
)


_SHA40_RE = re.compile(r"^[0-9a-fA-F]{40}$")
_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
_REQUIRED_CONTROL_BYTES = frozenset({"enq", "stx", "etx", "ack", "nak"})
_ROOM_NAME_DELTA_PREFIXES = ("NAM", "NAME")

_TARGETS: dict[str, dict[str, str]] = {
    "EPIT-HIT": {
        "profile_key": "epit_hit",
        "dialect": "EPIT-HIT / Epitome Hitachi emulation",
    },
    "EPIT-HIT2": {
        "profile_key": "epit_hit2",
        "dialect": "EPIT-HIT2 / Epitome Hitachi room-name layout variant",
    },
}

_COMPARISON_PAIRS = {
    "epitome_to_epit_hit": ("epitome", "epit_hit"),
    "epit_hit_to_epit_hit2": ("epit_hit", "epit_hit2"),
    "epitome_to_epit_hit2": ("epitome", "epit_hit2"),
}


@dataclass(frozen=True, slots=True)
class HitachiEvidenceAdmission:
    """Fail-closed interpretation of one reviewed Hitachi profile evidence bundle.

    Admission can close evidence-acquisition gaps, but it never changes the
    compatibility matrix or authorizes a runtime compatibility claim. A matrix
    change remains an explicit, reviewed repository action.
    """

    pms_protocol: str
    producer_source_sha: str
    bundle_sha256: str
    source_profile_sha256s: dict[str, str]
    current_matrix_status: str
    current_matrix_transport: str
    observed_transport: str
    resolved_gap_codes: tuple[str, ...]
    remaining_gap_codes: tuple[str, ...]
    technician_actions: tuple[str, ...]
    matrix_change_required: bool
    compatibility_promotion_authorized: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "pms_protocol": self.pms_protocol,
            "producer_source_sha": self.producer_source_sha,
            "bundle_sha256": self.bundle_sha256,
            "source_profile_sha256s": dict(self.source_profile_sha256s),
            "current_matrix_status": self.current_matrix_status,
            "current_matrix_transport": self.current_matrix_transport,
            "observed_transport": self.observed_transport,
            "resolved_gap_codes": list(self.resolved_gap_codes),
            "remaining_gap_codes": list(self.remaining_gap_codes),
            "technician_actions": list(self.technician_actions),
            "matrix_change_required": self.matrix_change_required,
            "compatibility_promotion_authorized": self.compatibility_promotion_authorized,
        }


def _require_mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    return value


def _require_sha(value: object, pattern: re.Pattern[str], label: str) -> str:
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise ValueError(f"{label} is not a valid pinned digest")
    return value.casefold()


def _validated_profiles(bundle: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    profiles_raw = _require_mapping(bundle.get("profiles"), "profiles")
    if set(profiles_raw) != set(EXPECTED_PROFILE_NAMES):
        raise ValueError("profiles must contain exactly Epitome, EPIT-HIT, and EPIT-HIT2")

    profiles: dict[str, Mapping[str, Any]] = {}
    for key, expected_name in EXPECTED_PROFILE_NAMES.items():
        profile = _require_mapping(profiles_raw.get(key), f"profiles.{key}")
        if profile.get("source_name") != expected_name:
            raise ValueError(f"profiles.{key}.source_name does not match the expected profile")
        if profile.get("evidence_class") != "legacy_source_profile":
            raise ValueError(f"profiles.{key} has an unexpected evidence class")
        if profile.get("raw_profile_embedded") is not False:
            raise ValueError(f"profiles.{key} must not embed the raw profile")
        _require_sha(profile.get("sha256"), _SHA256_RE, f"profiles.{key}.sha256")
        profiles[key] = profile
    return profiles


def _validate_comparisons(
    bundle: Mapping[str, Any],
    profiles: Mapping[str, Mapping[str, Any]],
) -> Mapping[str, Any]:
    comparisons = _require_mapping(bundle.get("comparisons"), "comparisons")
    if set(comparisons) != set(_COMPARISON_PAIRS):
        raise ValueError("comparisons do not match the required Hitachi profile lineage")

    for name, (baseline_key, candidate_key) in _COMPARISON_PAIRS.items():
        comparison = _require_mapping(comparisons.get(name), f"comparisons.{name}")
        baseline = profiles[baseline_key]
        candidate = profiles[candidate_key]
        if comparison.get("evidence_class") != "legacy_source_profile_delta":
            raise ValueError(f"comparisons.{name} has an unexpected evidence class")
        if comparison.get("baseline_source_name") != baseline.get("source_name"):
            raise ValueError(f"comparisons.{name} baseline profile identity mismatch")
        if comparison.get("candidate_source_name") != candidate.get("source_name"):
            raise ValueError(f"comparisons.{name} candidate profile identity mismatch")
        if str(comparison.get("baseline_sha256", "")).casefold() != str(
            baseline.get("sha256", "")
        ).casefold():
            raise ValueError(f"comparisons.{name} baseline digest mismatch")
        if str(comparison.get("candidate_sha256", "")).casefold() != str(
            candidate.get("sha256", "")
        ).casefold():
            raise ValueError(f"comparisons.{name} candidate digest mismatch")
    return comparisons


def validate_hitachi_profile_evidence_bundle(
    bundle: Mapping[str, Any],
) -> tuple[dict[str, Mapping[str, Any]], Mapping[str, Any], str]:
    """Validate provenance and sanitization without interpreting compatibility."""

    if bundle.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported Hitachi evidence bundle schema version")
    if bundle.get("sanitized") is not True or bundle.get("raw_profiles_embedded") is not False:
        raise ValueError("Hitachi evidence bundle must be sanitized and data-only")
    if bundle.get("evidence_class") != "legacy_source_profile":
        raise ValueError("Hitachi evidence bundle has an unexpected evidence class")
    if bundle.get("profile_order") != ["epitome", "epit_hit", "epit_hit2"]:
        raise ValueError("Hitachi evidence profile order is incomplete or unexpected")

    producer = _require_mapping(bundle.get("producer"), "producer")
    if producer.get("repository") != PRODUCER_REPOSITORY:
        raise ValueError("Hitachi evidence bundle was not produced by the expected repository")
    producer_sha = _require_sha(
        producer.get("source_sha"), _SHA40_RE, "producer.source_sha"
    )

    policy = _require_mapping(bundle.get("claim_policy"), "claim_policy")
    required_policy = (
        "profile_facts_do_not_prove_hardware_interoperability",
        "transport_requires_explicit_profile_or_wire_evidence",
        "layout_delta_does_not_qualify_transport",
        "reverse_direction_requires_separate_evidence",
        "timing_and_retry_require_separate_evidence",
        "compatibility_status_is_not_promoted_by_bundle_generation",
    )
    if any(policy.get(key) is not True for key in required_policy):
        raise ValueError("Hitachi evidence bundle claim policy is incomplete")

    profiles = _validated_profiles(bundle)
    comparisons = _validate_comparisons(bundle, profiles)
    return profiles, comparisons, producer_sha


def _has_chk_nam_layout(profile: Mapping[str, Any]) -> bool:
    record_keys = {str(value).upper() for value in profile.get("record_keys", [])}
    layouts = _require_mapping(profile.get("record_layouts", {}), "record_layouts")
    if {"CHK", "NAM"} <= record_keys and {"CHK", "NAM"} <= set(layouts):
        return True

    mask_layouts = _require_mapping(
        profile.get("record_mask_layouts", {}), "record_mask_layouts"
    )
    mask_keys = {str(key).upper() for key in mask_layouts}
    return any(key.startswith("CHK") for key in mask_keys) and any(
        key.startswith(("NAM", "NAME")) for key in mask_keys
    )


def _has_room_name_delta(comparison: Mapping[str, Any]) -> bool:
    changed_keys: set[str] = set()
    for field in ("record_layout_changes", "record_mask_layout_changes"):
        changes = _require_mapping(comparison.get(field, {}), field)
        changed_keys.update(str(key).upper() for key in changes)
    if not changed_keys:
        return False
    return all(key.startswith(_ROOM_NAME_DELTA_PREFIXES) for key in changed_keys)


def admit_hitachi_profile_evidence(
    bundle: Mapping[str, Any],
    *,
    pms_protocol: str,
) -> HitachiEvidenceAdmission:
    """Map a reviewed bundle to gaps it can actually close, without promotion.

    Profile characterization may prove profile presence, sanitized CHK/NAM
    layouts, explicit profile-declared transport, and complete control-byte
    declarations. It deliberately cannot close checksum semantics, timing/retry,
    reverse direction, or real-hardware interoperability by itself.
    """

    protocol = pms_protocol.strip().upper()
    target = _TARGETS.get(protocol)
    if target is None:
        raise ValueError("pms_protocol must be EPIT-HIT or EPIT-HIT2")

    profiles, comparisons, producer_sha = validate_hitachi_profile_evidence_bundle(bundle)
    profile = profiles[target["profile_key"]]

    entry = find_compatibility(
        pbx_family="Hitachi",
        pbx_dialect=target["dialect"],
        transport="unknown",
        pms_family="Epitome",
        pms_protocol=protocol,
        direction=Direction.PMS_TO_PBX,
    )
    readiness = readiness_for(entry)
    registered = {gap.code: gap for gap in readiness.evidence_gaps}

    resolved: set[str] = {"profile_body"}
    if "record_layout" in registered and _has_chk_nam_layout(profile):
        resolved.add("record_layout")

    observed_transport = str(profile.get("transport", "unknown")).casefold()
    transport_source = str(profile.get("transport_source", "none")).casefold()
    if (
        "transport" in registered
        and observed_transport in {"serial", "tcp", "tcp_client", "tcp_server"}
        and transport_source == "explicit_profile_key"
    ):
        resolved.add("transport")
    else:
        observed_transport = "unknown"

    control_bytes = _require_mapping(profile.get("control_bytes", {}), "control_bytes")
    if "framing_control" in registered and _REQUIRED_CONTROL_BYTES <= set(control_bytes):
        resolved.add("framing_control")

    if protocol == "EPIT-HIT2" and "profile_delta" in registered:
        if _has_room_name_delta(comparisons["epit_hit_to_epit_hit2"]):
            resolved.add("profile_delta")

    resolved &= set(registered)
    remaining = tuple(code for code in registered if code not in resolved)
    actions = tuple(registered[code].action for code in remaining)
    source_shas = {
        key: str(profile_value["sha256"]).casefold()
        for key, profile_value in profiles.items()
    }

    return HitachiEvidenceAdmission(
        pms_protocol=protocol,
        producer_source_sha=producer_sha,
        bundle_sha256=hitachi_bundle_digest(dict(bundle)),
        source_profile_sha256s=source_shas,
        current_matrix_status=entry.status.value,
        current_matrix_transport=entry.transport,
        observed_transport=observed_transport,
        resolved_gap_codes=tuple(code for code in registered if code in resolved),
        remaining_gap_codes=remaining,
        technician_actions=actions,
        matrix_change_required=(
            observed_transport != "unknown" and observed_transport != entry.transport
        ),
        compatibility_promotion_authorized=False,
    )
