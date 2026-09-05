from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import re
from typing import Any

from .legacy_profile_compare import compare_legacy_profile_evidence
from .legacy_profile_evidence import (
    LegacyProfileEvidence,
    characterize_legacy_profile_file,
)


SCHEMA_VERSION = "1.0"
PRODUCER_PROJECT = "InnAware PMS-PBX Emulator"
PRODUCER_REPOSITORY = "MusicCityTelecom/innaware-pms-emulator"
_SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")

EXPECTED_PROFILE_NAMES = {
    "epitome": "psip-pbx-protocol.Epitome",
    "epit_hit": "psip-pbx-protocol.EPIT-HIT",
    "epit_hit2": "psip-pbx-protocol.EPIT-HIT2",
}


def _require_source_sha(source_sha: str) -> str:
    if not _SHA_RE.fullmatch(source_sha):
        raise ValueError("source_sha must be an exact 40-character Git commit SHA")
    return source_sha.casefold()


def _require_expected_basename(path: str | Path, expected: str) -> Path:
    profile_path = Path(path)
    if profile_path.name != expected:
        raise ValueError(
            f"expected profile basename {expected!r}, got {profile_path.name!r}; "
            "refusing to relabel evidence"
        )
    return profile_path


def _characterize(path: Path) -> LegacyProfileEvidence:
    return characterize_legacy_profile_file(path, include_record_layouts=True)


def _profile_payload(evidence: LegacyProfileEvidence) -> dict[str, Any]:
    payload = evidence.as_dict()
    payload["raw_profile_embedded"] = False
    return payload


def build_hitachi_profile_evidence_bundle(
    *,
    epitome_path: str | Path,
    epit_hit_path: str | Path,
    epit_hit2_path: str | Path,
    source_sha: str,
) -> dict[str, Any]:
    """Build a deterministic sanitized evidence bundle for the three Hitachi profiles.

    Raw vendor profile bodies are never embedded. Only facts admitted by the
    existing legacy-profile characterizer and comparator are emitted. The
    bundle intentionally does not promote transport, direction, timing, or
    compatibility status; those remain separate evidence/readiness decisions.
    """

    pinned_sha = _require_source_sha(source_sha)
    paths = {
        "epitome": _require_expected_basename(
            epitome_path, EXPECTED_PROFILE_NAMES["epitome"]
        ),
        "epit_hit": _require_expected_basename(
            epit_hit_path, EXPECTED_PROFILE_NAMES["epit_hit"]
        ),
        "epit_hit2": _require_expected_basename(
            epit_hit2_path, EXPECTED_PROFILE_NAMES["epit_hit2"]
        ),
    }

    observations = {name: _characterize(path) for name, path in paths.items()}
    epitome = observations["epitome"]
    epit_hit = observations["epit_hit"]
    epit_hit2 = observations["epit_hit2"]

    comparisons = {
        "epitome_to_epit_hit": compare_legacy_profile_evidence(
            epitome, epit_hit
        ).as_dict(),
        "epit_hit_to_epit_hit2": compare_legacy_profile_evidence(
            epit_hit, epit_hit2
        ).as_dict(),
        "epitome_to_epit_hit2": compare_legacy_profile_evidence(
            epitome, epit_hit2
        ).as_dict(),
    }

    return {
        "schema_version": SCHEMA_VERSION,
        "sanitized": True,
        "raw_profiles_embedded": False,
        "producer": {
            "project": PRODUCER_PROJECT,
            "repository": PRODUCER_REPOSITORY,
            "source_sha": pinned_sha,
        },
        "purpose": (
            "Read-only sanitized characterization of Epitome, EPIT-HIT, and "
            "EPIT-HIT2 legacy PBX profile lineage for Hitachi interoperability evidence."
        ),
        "evidence_class": "legacy_source_profile",
        "profile_order": ["epitome", "epit_hit", "epit_hit2"],
        "profiles": {
            name: _profile_payload(observations[name])
            for name in ("epitome", "epit_hit", "epit_hit2")
        },
        "comparisons": comparisons,
        "claim_policy": {
            "profile_facts_do_not_prove_hardware_interoperability": True,
            "transport_requires_explicit_profile_or_wire_evidence": True,
            "layout_delta_does_not_qualify_transport": True,
            "reverse_direction_requires_separate_evidence": True,
            "timing_and_retry_require_separate_evidence": True,
            "compatibility_status_is_not_promoted_by_bundle_generation": True,
        },
    }


def hitachi_bundle_digest(bundle: dict[str, Any]) -> str:
    """Return a deterministic digest for a serialized bundle-like mapping.

    This helper is intentionally content-only and timestamp-free so a reviewed
    bundle can be pinned when passed to another project as data/test evidence.
    """

    import json

    raw = json.dumps(
        bundle,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return sha256(raw).hexdigest()
