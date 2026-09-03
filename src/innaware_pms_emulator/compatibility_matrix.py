from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable


class SupportStatus(str, Enum):
    SUPPORTED = "supported"
    PARTIAL = "partial"
    PLANNED = "planned"
    UNSUPPORTED = "unsupported"


class EvidenceClass(str, Enum):
    PACKET_CAPTURE = "packet_capture"
    OPERATOR_CONFIRMED = "operator_confirmed"
    LEGACY_SOURCE_PROFILE = "legacy_source_profile"
    SIMULATOR_CHARACTERIZATION = "simulator_characterization"
    INFERENCE = "inference"
    NONE = "none"


class Direction(str, Enum):
    PBX_TO_PMS = "pbx_to_pms"
    PMS_TO_PBX = "pms_to_pbx"
    BIDIRECTIONAL = "bidirectional"


@dataclass(frozen=True, slots=True)
class CompatibilityEntry:
    pbx_family: str
    pbx_dialect: str
    transport: str
    pms_family: str
    pms_protocol: str
    direction: Direction
    status: SupportStatus
    evidence_class: EvidenceClass
    deterministic_tests: tuple[str, ...] = ()
    notes: str = ""

    @property
    def key(self) -> tuple[str, str, str, str, str, str]:
        return (
            self.pbx_family.lower(),
            self.pbx_dialect.lower(),
            self.transport.lower(),
            self.pms_family.lower(),
            self.pms_protocol.lower(),
            self.direction.value,
        )

    def validate(self) -> None:
        values = (
            self.pbx_family,
            self.pbx_dialect,
            self.transport,
            self.pms_family,
            self.pms_protocol,
        )
        if any(not value.strip() for value in values):
            raise ValueError("Compatibility dimensions must be non-empty")
        if self.status is SupportStatus.SUPPORTED and not self.deterministic_tests:
            raise ValueError("SUPPORTED compatibility entries require deterministic test coverage")
        if self.status is SupportStatus.SUPPORTED and self.evidence_class in {EvidenceClass.INFERENCE, EvidenceClass.NONE}:
            raise ValueError("SUPPORTED compatibility entries require evidence stronger than inference")

    def as_dict(self) -> dict[str, Any]:
        return {
            "pbx_family": self.pbx_family,
            "pbx_dialect": self.pbx_dialect,
            "transport": self.transport,
            "pms_family": self.pms_family,
            "pms_protocol": self.pms_protocol,
            "direction": self.direction.value,
            "status": self.status.value,
            "evidence_class": self.evidence_class.value,
            "deterministic_tests": list(self.deterministic_tests),
            "notes": self.notes,
        }


# This is a claim registry, not a wish list. Rows are intentionally conservative.
# Any six-dimensional combination not listed here is UNSUPPORTED by default.
COMPATIBILITY_MATRIX: tuple[CompatibilityEntry, ...] = (
    CompatibilityEntry(
        pbx_family="Mitel",
        pbx_dialect="MITEL 1 / iPocket-characterized",
        transport="tcp",
        pms_family="legacy-hotel-pms",
        pms_protocol="mitel-hospitality",
        direction=Direction.BIDIRECTIONAL,
        status=SupportStatus.PARTIAL,
        evidence_class=EvidenceClass.PACKET_CAPTURE,
        deterministic_tests=(
            "tests/test_mitel_tcp_stream_replay.py",
            "tests/test_mitel_tcp_session.py",
            "tests/test_mitel_tcp_runtime_integration.py",
            "tests/test_mitel_tcp_outbound_transaction_integration.py",
        ),
        notes="Capture-backed ENQ/ACK/NAK, STX/ETX, CHK/NAM, AREYUTHERE, reconnect and stream behavior; model/field variants remain qualified.",
    ),
    CompatibilityEntry(
        pbx_family="Mitel",
        pbx_dialect="legacy MTL-compatible",
        transport="serial",
        pms_family="legacy-hotel-pms",
        pms_protocol="mitel-hospitality",
        direction=Direction.PBX_TO_PMS,
        status=SupportStatus.PARTIAL,
        evidence_class=EvidenceClass.LEGACY_SOURCE_PROFILE,
        deterministic_tests=(
            "tests/test_mitel_serial_session.py",
            "tests/test_mitel_serial_runtime_integration.py",
            "tests/test_mitel_serial_pty_integration.py",
        ),
        notes="Serial session, live runtime, Linux PTY framing/reopen, and outbound ENQ/ACK/NAK transaction paths are deterministic-tested; real PBX hardware and broader model/timing evidence remain incomplete. TCP capture facts are not promoted to serial truth.",
    ),
    CompatibilityEntry(
        pbx_family="PhoneSuite",
        pbx_dialect="MITEL 1-compatible",
        transport="serial",
        pms_family="legacy-hotel-pms",
        pms_protocol="mitel-hospitality",
        direction=Direction.BIDIRECTIONAL,
        status=SupportStatus.PARTIAL,
        evidence_class=EvidenceClass.SIMULATOR_CHARACTERIZATION,
        deterministic_tests=(
            "tests/test_phonesuite_serial_characterization.py",
            "tests/test_phonesuite_serial_session.py",
            "tests/test_phonesuite_serial_runtime_integration.py",
            "tests/test_phonesuite_serial_pty_integration.py",
        ),
        notes="Clean-room simulator-backed ENQ/ACK and STX/ETX CHK/NAM characterization has a dedicated PhoneSuite session, live serial runtime selection, and Linux PTY fragmentation/coalescing/reopen/control-routing coverage. Serial settings remain operator-configured because PhoneSuite-specific defaults and real-hardware timing/retry behavior are not yet evidence-qualified; Series2 TDMoE/PRI station programming remains out of scope.",
    ),
    CompatibilityEntry(
        pbx_family="Matrix",
        pbx_dialect="MICROS Opera / FIAS",
        transport="tcp",
        pms_family="Oracle / MICROS Opera",
        pms_protocol="FIAS",
        direction=Direction.PBX_TO_PMS,
        status=SupportStatus.PARTIAL,
        evidence_class=EvidenceClass.OPERATOR_CONFIRMED,
        deterministic_tests=("tests/test_pbx_brand_catalog.py", "tests/test_protocols.py"),
        notes="Field-observed Matrix SARVAM UCS initiating FIAS LS over TCP; full Matrix session/fixture coverage is still incomplete.",
    ),
    CompatibilityEntry(
        pbx_family="Hitachi",
        pbx_dialect="HITACHI",
        transport="unknown",
        pms_family="unknown",
        pms_protocol="unknown",
        direction=Direction.BIDIRECTIONAL,
        status=SupportStatus.PLANNED,
        evidence_class=EvidenceClass.NONE,
        notes="Fifth PBX family placeholder selected from the existing catalog; no wire-level compatibility is claimed until sanitized evidence exists.",
    ),
)


_INDEX = {entry.key: entry for entry in COMPATIBILITY_MATRIX}
if len(_INDEX) != len(COMPATIBILITY_MATRIX):
    raise RuntimeError("Duplicate compatibility matrix key")
for _entry in COMPATIBILITY_MATRIX:
    _entry.validate()


def compatibility_catalog() -> list[dict[str, Any]]:
    return [entry.as_dict() for entry in COMPATIBILITY_MATRIX]


def find_compatibility(
    *,
    pbx_family: str,
    pbx_dialect: str,
    transport: str,
    pms_family: str,
    pms_protocol: str,
    direction: Direction | str,
) -> CompatibilityEntry:
    direction_value = direction.value if isinstance(direction, Direction) else Direction(direction).value
    key = (
        pbx_family.lower(),
        pbx_dialect.lower(),
        transport.lower(),
        pms_family.lower(),
        pms_protocol.lower(),
        direction_value,
    )
    entry = _INDEX.get(key)
    if entry is not None:
        return entry
    return CompatibilityEntry(
        pbx_family=pbx_family,
        pbx_dialect=pbx_dialect,
        transport=transport,
        pms_family=pms_family,
        pms_protocol=pms_protocol,
        direction=Direction(direction_value),
        status=SupportStatus.UNSUPPORTED,
        evidence_class=EvidenceClass.NONE,
        notes="No verified compatibility row exists for this exact combination. Do not auto-select or infer a different profile.",
    )


def validate_supported_test_coverage(known_test_paths: Iterable[str]) -> list[str]:
    known = set(known_test_paths)
    missing: list[str] = []
    for entry in COMPATIBILITY_MATRIX:
        if entry.status is not SupportStatus.SUPPORTED:
            continue
        for test_path in entry.deterministic_tests:
            if test_path not in known:
                missing.append(test_path)
    return sorted(set(missing))
