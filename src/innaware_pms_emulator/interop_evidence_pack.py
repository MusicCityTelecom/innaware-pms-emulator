from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any

from .compatibility_matrix import (
    COMPATIBILITY_MATRIX,
    CompatibilityEntry,
    Direction,
    EvidenceClass,
    SupportStatus,
)
from .compatibility_readiness import (
    compatibility_readiness_catalog,
    validate_readiness_registry,
)


SCHEMA_VERSION = "1.0"
PRODUCER_PROJECT = "InnAware PMS-PBX Emulator"
PRODUCER_REPOSITORY = "MusicCityTelecom/innaware-pms-emulator"
_SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")

# Highest-confidence evidence first. Keep this order aligned with the project
# evidence policy; it is exported so downstream consumers do not invent their
# own evidence precedence.
EVIDENCE_RANK: tuple[EvidenceClass, ...] = (
    EvidenceClass.PACKET_CAPTURE,
    EvidenceClass.OPERATOR_CONFIRMED,
    EvidenceClass.LEGACY_SOURCE_PROFILE,
    EvidenceClass.SIMULATOR_CHARACTERIZATION,
    EvidenceClass.INFERENCE,
    EvidenceClass.NONE,
)


@dataclass(frozen=True, slots=True)
class ShareableFixture:
    """One sanitized fixture that may cross project boundaries as data only."""

    path: str
    pbx_family: str
    pbx_dialect: str
    transport: str
    pms_family: str
    pms_protocol: str
    direction: Direction
    evidence_class: EvidenceClass
    purpose: str

    @property
    def matrix_key(self) -> tuple[str, str, str, str, str, str]:
        return (
            self.pbx_family.casefold(),
            self.pbx_dialect.casefold(),
            self.transport.casefold(),
            self.pms_family.casefold(),
            self.pms_protocol.casefold(),
            self.direction.value,
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "pbx_family": self.pbx_family,
            "pbx_dialect": self.pbx_dialect,
            "transport": self.transport,
            "pms_family": self.pms_family,
            "pms_protocol": self.pms_protocol,
            "direction": self.direction.value,
            "evidence_class": self.evidence_class.value,
            "purpose": self.purpose,
        }


# Only sanitized, repository-owned JSON fixtures belong here. Vendor binaries,
# original captures, manuals, legacy profile bodies, credentials, and guest PII
# must never be exported by this registry.
SHAREABLE_FIXTURES: tuple[ShareableFixture, ...] = (
    ShareableFixture(
        path="tests/data/emulation/mitel_ipocket_tcp.json",
        pbx_family="Mitel",
        pbx_dialect="MITEL 1 / iPocket-characterized",
        transport="tcp",
        pms_family="legacy-hotel-pms",
        pms_protocol="mitel-hospitality",
        direction=Direction.BIDIRECTIONAL,
        evidence_class=EvidenceClass.PACKET_CAPTURE,
        purpose="Sanitized Mitel/iPocket TCP control, framing, application-family, and reconnect replay evidence.",
    ),
    ShareableFixture(
        path="tests/data/emulation/mitel_serial_pms_to_pbx.json",
        pbx_family="Mitel",
        pbx_dialect="legacy MTL-compatible",
        transport="serial",
        pms_family="legacy-hotel-pms",
        pms_protocol="mitel-hospitality",
        direction=Direction.PMS_TO_PBX,
        evidence_class=EvidenceClass.SIMULATOR_CHARACTERIZATION,
        purpose="Sanitized Mitel serial PMS-to-PBX ENQ/ACK and CHK1/CHK0 simulator-characterization replay.",
    ),
    ShareableFixture(
        path="tests/fixtures/pbx/phonesuite_serial_characterization.json",
        pbx_family="PhoneSuite",
        pbx_dialect="MITEL 1-compatible",
        transport="serial",
        pms_family="legacy-hotel-pms",
        pms_protocol="mitel-hospitality",
        direction=Direction.PBX_TO_PMS,
        evidence_class=EvidenceClass.SIMULATOR_CHARACTERIZATION,
        purpose="Sanitized PhoneSuite serial PBX-to-PMS ENQ/ACK plus STX/ETX CHK/NAM characterization.",
    ),
    ShareableFixture(
        path="tests/fixtures/pbx/matrix_sarvam_micros_opera_characterization.json",
        pbx_family="Matrix",
        pbx_dialect="MICROS Opera / FIAS",
        transport="tcp",
        pms_family="Oracle / MICROS Opera",
        pms_protocol="FIAS",
        direction=Direction.PBX_TO_PMS,
        evidence_class=EvidenceClass.OPERATOR_CONFIRMED,
        purpose="Sanitized Matrix SARVAM MICROS Opera TCP STX/ETX FIAS LS field-observation fixture.",
    ),
    ShareableFixture(
        path="tests/fixtures/pbx/3cx_mitel_sx2000_pms_to_pbx.json",
        pbx_family="3CX",
        pbx_dialect="Hotel Module / Mitel SX2000-compatible",
        transport="tcp",
        pms_family="legacy-hotel-pms",
        pms_protocol="mitel-hospitality",
        direction=Direction.PMS_TO_PBX,
        evidence_class=EvidenceClass.LEGACY_SOURCE_PROFILE,
        purpose="Synthetic source-derived 3CX Hotel Module Mitel-SX2000 PMS-to-PBX transaction evidence without guest PII or vendor material.",
    ),
)


def _matrix_index() -> dict[tuple[str, str, str, str, str, str], CompatibilityEntry]:
    return {entry.key: entry for entry in COMPATIBILITY_MATRIX}


def _document_is_sanitized(document: Any) -> bool:
    if not isinstance(document, dict):
        return False
    if "sanitized" in document:
        return document.get("sanitized") is True
    fixtures = document.get("fixtures")
    return (
        isinstance(fixtures, list)
        and bool(fixtures)
        and all(isinstance(item, dict) and item.get("sanitized") is True for item in fixtures)
    )


def _load_fixture(repo_root: Path, fixture: ShareableFixture) -> tuple[dict[str, Any], str]:
    root = repo_root.resolve()
    path = (root / fixture.path).resolve()
    if not path.is_relative_to(root):
        raise ValueError(f"fixture escapes repository root: {fixture.path}")
    if path.suffix.casefold() != ".json":
        raise ValueError(f"shareable fixture must be JSON data, not executable/source material: {fixture.path}")
    raw = path.read_bytes()
    document = json.loads(raw.decode("utf-8"))
    if not _document_is_sanitized(document):
        raise ValueError(f"fixture is not explicitly sanitized: {fixture.path}")
    return document, sha256(raw).hexdigest()


def validate_fixture_registry(repo_root: Path | None = None) -> list[str]:
    """Return shareable-fixture registry errors without weakening matrix claims."""

    matrix = _matrix_index()
    errors: list[str] = []
    seen_paths: set[str] = set()
    seen_keys: set[tuple[str, str, str, str, str, str]] = set()

    for fixture in SHAREABLE_FIXTURES:
        if fixture.path in seen_paths:
            errors.append(f"duplicate shareable fixture path: {fixture.path}")
        seen_paths.add(fixture.path)

        entry = matrix.get(fixture.matrix_key)
        if entry is None:
            errors.append(f"shareable fixture has no exact compatibility row: {fixture.path}")
        else:
            seen_keys.add(entry.key)
            if entry.evidence_class is not fixture.evidence_class:
                errors.append(
                    "shareable fixture evidence class does not match matrix row: "
                    f"{fixture.path} ({fixture.evidence_class.value} != {entry.evidence_class.value})"
                )

        if repo_root is not None:
            try:
                _load_fixture(repo_root, fixture)
            except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
                errors.append(f"invalid shareable fixture {fixture.path}: {exc}")

    # The operator requires a deterministic fixture for every SUPPORTED row.
    # PARTIAL/PLANNED rows may remain evidence-only, but once a row is promoted
    # it cannot be exported as production-ready without a reusable fixture.
    for entry in COMPATIBILITY_MATRIX:
        if entry.status is SupportStatus.SUPPORTED and entry.key not in seen_keys:
            errors.append(f"SUPPORTED compatibility row has no shareable fixture: {entry.key!r}")

    return sorted(errors)


def build_interop_evidence_pack(*, repo_root: Path, source_sha: str) -> dict[str, Any]:
    """Build a deterministic, consumer-neutral evidence/fixture exchange document.

    The pack is deliberately data-only. A production consumer such as the InnAware
    UCP Hospitality PMS Gateway may ingest a pinned pack or copy individual sanitized
    fixtures into its own tests, but it must not import the emulator package as a
    runtime dependency or adopt emulator service/UI/support-tool responsibilities.
    """

    if not _SHA_RE.fullmatch(source_sha):
        raise ValueError("source_sha must be an exact 40-character Git commit SHA")

    errors = validate_readiness_registry() + validate_fixture_registry(repo_root)
    if errors:
        raise ValueError("interop evidence pack validation failed: " + "; ".join(errors))

    fixtures: list[dict[str, Any]] = []
    for descriptor in SHAREABLE_FIXTURES:
        document, digest = _load_fixture(repo_root, descriptor)
        item = descriptor.as_dict()
        item["sha256"] = digest
        item["document"] = document
        fixtures.append(item)

    return {
        "schema_version": SCHEMA_VERSION,
        "producer": {
            "project": PRODUCER_PROJECT,
            "repository": PRODUCER_REPOSITORY,
            "source_sha": source_sha.casefold(),
        },
        "architectural_boundary": {
            "emulator_role": "standalone technician/installer PMS-PBX interoperability, simulation, and diagnostic support tool",
            "ucp_role": "separate production hospitality PMS gateway/runtime",
            "exchange_mode": "data_only",
            "runtime_dependency_on_emulator": False,
            "rules": [
                "Share sanitized fixtures, compatibility evidence, and test knowledge only.",
                "Do not import InnAware PMS-PBX Emulator Python modules into the InnAware UCP production runtime.",
                "Do not move emulator UI, support-tool lifecycle, simulator orchestration, or field-diagnostic responsibilities into the UCP hospitality runtime.",
                "Pin the producer Git SHA when consuming evidence so runtime claims remain traceable to the exact emulator revision.",
            ],
        },
        "evidence_rank": [item.value for item in EVIDENCE_RANK],
        "production_claim_policy": {
            "supported_rows_may_be_runtime_candidates": True,
            "partial_rows_are_diagnostic_or_test_evidence_only": True,
            "planned_rows_are_not_runtime_compatibility_claims": True,
            "unsupported_combinations_must_fail_closed": True,
        },
        "compatibility_rows": compatibility_readiness_catalog(),
        "fixtures": fixtures,
    }
