from __future__ import annotations

from pathlib import Path
import re
from typing import Any

from .hitachi_evidence_admission import admit_hitachi_profile_evidence
from .hitachi_profile_evidence import (
    EXPECTED_PROFILE_NAMES,
    PRODUCER_PROJECT,
    PRODUCER_REPOSITORY,
    build_hitachi_profile_evidence_bundle,
    hitachi_bundle_digest,
)


SCHEMA_VERSION = "1.0"
_SHA40_RE = re.compile(r"^[0-9a-fA-F]{40}$")
_PROTOCOL_ORDER = ("EPIT-HIT", "EPIT-HIT2")


def _require_source_sha(source_sha: str) -> str:
    if not _SHA40_RE.fullmatch(source_sha):
        raise ValueError("source_sha must be an exact 40-character Git commit SHA")
    return source_sha.casefold()


def _required_profile_paths(profile_dir: str | Path) -> dict[str, Path]:
    directory = Path(profile_dir)
    if not directory.exists():
        raise ValueError("profile_dir does not exist")
    if not directory.is_dir():
        raise ValueError("profile_dir must be a directory")

    paths = {
        key: directory / basename
        for key, basename in EXPECTED_PROFILE_NAMES.items()
    }
    missing = [path.name for path in paths.values() if not path.exists()]
    if missing:
        raise ValueError(
            "profile_dir is missing required Hitachi source profiles: "
            + ", ".join(sorted(missing))
        )
    non_files = [path.name for path in paths.values() if not path.is_file()]
    if non_files:
        raise ValueError(
            "required Hitachi profile path is not a regular file: "
            + ", ".join(sorted(non_files))
        )
    return paths


def build_hitachi_profile_intake(
    *,
    profile_dir: str | Path,
    source_sha: str,
) -> dict[str, Any]:
    """Inspect the exact legacy Hitachi profile set without copying raw bodies.

    This is an orchestration/reporting layer over the existing clean-room
    characterizer and admission logic. It is intentionally read-only and never
    mutates the compatibility matrix. The resulting JSON is deterministic and
    omits the local source-directory path as well as all raw profile bodies.
    """

    pinned_sha = _require_source_sha(source_sha)
    paths = _required_profile_paths(profile_dir)

    bundle = build_hitachi_profile_evidence_bundle(
        epitome_path=paths["epitome"],
        epit_hit_path=paths["epit_hit"],
        epit_hit2_path=paths["epit_hit2"],
        source_sha=pinned_sha,
    )
    bundle_digest = hitachi_bundle_digest(bundle)

    admissions = {
        protocol: admit_hitachi_profile_evidence(bundle, pms_protocol=protocol).as_dict()
        for protocol in _PROTOCOL_ORDER
    }

    profiles: dict[str, dict[str, Any]] = {}
    for key in bundle["profile_order"]:
        evidence = bundle["profiles"][key]
        path = paths[key]
        profiles[key] = {
            "source_name": evidence["source_name"],
            "sha256": evidence["sha256"],
            "size_bytes": path.stat().st_size,
            "transport": evidence["transport"],
            "transport_source": evidence["transport_source"],
            "control_byte_names": sorted(evidence["control_bytes"]),
            "record_keys": list(evidence["record_keys"]),
            "record_mask_keys": list(evidence["record_mask_keys"]),
            "warnings": list(evidence["warnings"]),
        }

    observed_transports = sorted(
        {
            admission["observed_transport"]
            for admission in admissions.values()
            if admission["observed_transport"] != "unknown"
        }
    )
    matrix_change_candidates = [
        protocol
        for protocol in _PROTOCOL_ORDER
        if admissions[protocol]["matrix_change_required"]
    ]

    return {
        "schema_version": SCHEMA_VERSION,
        "sanitized": True,
        "read_only": True,
        "raw_profiles_embedded": False,
        "source_directory_path_embedded": False,
        "producer": {
            "project": PRODUCER_PROJECT,
            "repository": PRODUCER_REPOSITORY,
            "source_sha": pinned_sha,
        },
        "purpose": (
            "Read-only intake of the exact Epitome, EPIT-HIT, and EPIT-HIT2 "
            "legacy profile set before any Hitachi compatibility-matrix change."
        ),
        "evidence_class": "legacy_source_profile",
        "source_set": {
            "required_profile_names": [
                EXPECTED_PROFILE_NAMES[key] for key in bundle["profile_order"]
            ],
            "all_required_profiles_present": True,
            "profiles": profiles,
        },
        "evidence_bundle_sha256": bundle_digest,
        "admissions": admissions,
        "observed_concrete_transports": observed_transports,
        "matrix_change_candidates": matrix_change_candidates,
        "claim_policy": {
            "profile_intake_is_not_hardware_interoperability": True,
            "profile_intake_is_not_matrix_registration": True,
            "matrix_mutation_is_automatic": False,
            "compatibility_promotion_authorized": False,
            "transport_requires_explicit_profile_or_wire_evidence": True,
            "unknown_transport_must_not_inherit_neighboring_profile_transport": True,
            "reverse_direction_requires_separate_evidence": True,
            "timing_retry_and_checksum_require_separate_evidence": True,
            "raw_profile_bodies_must_remain_outside_git": True,
            "series2_station_programming_in_scope": False,
        },
        "architectural_boundary": {
            "exchange_mode": "data_only",
            "runtime_dependency_on_emulator": False,
            "ucp_runtime_dependency_allowed": False,
        },
    }
