from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

from .legacy_profile_evidence import (
    LegacyProfileEvidence,
    characterize_legacy_profile_file,
)


@dataclass(frozen=True, slots=True)
class LegacyProfileEvidenceDelta:
    """Sanitized differences between two legacy-profile characterizations.

    This object only compares fields already admitted by LegacyProfileEvidence.
    Unknown source-profile values are therefore never surfaced by comparison.
    Exact record and PBX-mask layout values are compared only when both input
    characterizations contain complete opt-in layout data.
    """

    baseline_source_name: str
    baseline_sha256: str
    candidate_source_name: str
    candidate_sha256: str
    evidence_class: str
    profile_identity_changes: dict[str, dict[str, object | None]]
    transport_change: dict[str, str] | None
    control_byte_changes: dict[str, dict[str, int | None]]
    serial_parameter_changes: dict[str, dict[str, object | None]]
    record_keys_added: tuple[str, ...]
    record_keys_removed: tuple[str, ...]
    record_layout_changes: dict[str, dict[str, str | None]]
    record_mask_keys_added: tuple[str, ...]
    record_mask_keys_removed: tuple[str, ...]
    record_mask_layout_changes: dict[str, dict[str, str | None]]
    unknown_key_count_change: dict[str, int] | None
    unknown_mask_key_count_change: dict[str, int] | None
    warnings: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["record_keys_added"] = list(self.record_keys_added)
        value["record_keys_removed"] = list(self.record_keys_removed)
        value["record_mask_keys_added"] = list(self.record_mask_keys_added)
        value["record_mask_keys_removed"] = list(self.record_mask_keys_removed)
        value["warnings"] = list(self.warnings)
        return value


def _mapping_changes(
    baseline: Mapping[str, object],
    candidate: Mapping[str, object],
) -> dict[str, dict[str, object | None]]:
    changes: dict[str, dict[str, object | None]] = {}
    for key in sorted(set(baseline) | set(candidate)):
        before = baseline.get(key)
        after = candidate.get(key)
        if before != after:
            changes[key] = {"baseline": before, "candidate": after}
    return changes


def _complete_layouts(keys: tuple[str, ...], layouts: Mapping[str, str]) -> bool:
    return not keys or set(layouts) == set(keys)


def _count_change(baseline: int, candidate: int) -> dict[str, int] | None:
    if baseline == candidate:
        return None
    return {"baseline": baseline, "candidate": candidate}


def compare_legacy_profile_evidence(
    baseline: LegacyProfileEvidence,
    candidate: LegacyProfileEvidence,
) -> LegacyProfileEvidenceDelta:
    """Compare two already-sanitized profile observations without inference.

    Key membership can always be compared because key names are part of the
    default safe characterization. Exact layout values are intentionally held
    back unless both observations were characterized with complete opt-in
    layout data. This prevents a metadata-only run from being misread as a
    real layout difference.
    """

    warnings: list[str] = []

    transport_change = None
    if (
        baseline.transport != candidate.transport
        or baseline.transport_source != candidate.transport_source
    ):
        transport_change = {
            "baseline": baseline.transport,
            "candidate": candidate.transport,
            "baseline_source": baseline.transport_source,
            "candidate_source": candidate.transport_source,
        }

    baseline_record_keys = set(baseline.record_keys)
    candidate_record_keys = set(candidate.record_keys)
    record_keys_added = tuple(sorted(candidate_record_keys - baseline_record_keys))
    record_keys_removed = tuple(sorted(baseline_record_keys - candidate_record_keys))

    baseline_mask_keys = set(baseline.record_mask_keys)
    candidate_mask_keys = set(candidate.record_mask_keys)
    record_mask_keys_added = tuple(sorted(candidate_mask_keys - baseline_mask_keys))
    record_mask_keys_removed = tuple(sorted(baseline_mask_keys - candidate_mask_keys))

    record_layout_changes: dict[str, dict[str, str | None]] = {}
    record_layouts_comparable = _complete_layouts(
        baseline.record_keys, baseline.record_layouts
    ) and _complete_layouts(candidate.record_keys, candidate.record_layouts)
    if record_layouts_comparable:
        record_layout_changes = {
            key: {"baseline": change["baseline"], "candidate": change["candidate"]}
            for key, change in _mapping_changes(
                baseline.record_layouts,
                candidate.record_layouts,
            ).items()
        }
    elif baseline.record_keys or candidate.record_keys:
        warnings.append(
            "record layout values were not compared because both observations do not "
            "contain complete opt-in record layouts"
        )

    record_mask_layout_changes: dict[str, dict[str, str | None]] = {}
    mask_layouts_comparable = _complete_layouts(
        baseline.record_mask_keys, baseline.record_mask_layouts
    ) and _complete_layouts(candidate.record_mask_keys, candidate.record_mask_layouts)
    if mask_layouts_comparable:
        record_mask_layout_changes = {
            key: {"baseline": change["baseline"], "candidate": change["candidate"]}
            for key, change in _mapping_changes(
                baseline.record_mask_layouts,
                candidate.record_mask_layouts,
            ).items()
        }
    elif baseline.record_mask_keys or candidate.record_mask_keys:
        warnings.append(
            "PBX mask layout values were not compared because both observations do not "
            "contain complete opt-in mask layouts"
        )

    if baseline.evidence_class != candidate.evidence_class:
        warnings.append(
            "evidence classes differ; do not promote the comparison above the weaker source"
        )

    return LegacyProfileEvidenceDelta(
        baseline_source_name=Path(baseline.source_name).name,
        baseline_sha256=baseline.sha256,
        candidate_source_name=Path(candidate.source_name).name,
        candidate_sha256=candidate.sha256,
        evidence_class="legacy_source_profile_delta",
        profile_identity_changes=_mapping_changes(
            baseline.profile_identity,
            candidate.profile_identity,
        ),
        transport_change=transport_change,
        control_byte_changes={
            key: {"baseline": change["baseline"], "candidate": change["candidate"]}
            for key, change in _mapping_changes(
                baseline.control_bytes,
                candidate.control_bytes,
            ).items()
        },
        serial_parameter_changes=_mapping_changes(
            baseline.serial_parameters,
            candidate.serial_parameters,
        ),
        record_keys_added=record_keys_added,
        record_keys_removed=record_keys_removed,
        record_layout_changes=record_layout_changes,
        record_mask_keys_added=record_mask_keys_added,
        record_mask_keys_removed=record_mask_keys_removed,
        record_mask_layout_changes=record_mask_layout_changes,
        unknown_key_count_change=_count_change(
            baseline.unknown_key_count,
            candidate.unknown_key_count,
        ),
        unknown_mask_key_count_change=_count_change(
            baseline.unknown_mask_key_count,
            candidate.unknown_mask_key_count,
        ),
        warnings=tuple(warnings),
    )


def compare_legacy_profile_files(
    baseline_path: str | Path,
    candidate_path: str | Path,
    *,
    include_record_layouts: bool = False,
) -> LegacyProfileEvidenceDelta:
    """Read two authorized profiles and return only their sanitized delta."""

    baseline = characterize_legacy_profile_file(
        baseline_path,
        include_record_layouts=include_record_layouts,
    )
    candidate = characterize_legacy_profile_file(
        candidate_path,
        include_record_layouts=include_record_layouts,
    )
    return compare_legacy_profile_evidence(baseline, candidate)
