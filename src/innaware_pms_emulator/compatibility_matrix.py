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
        direction=Direction.PBX_TO_PMS,
        status=SupportStatus.PARTIAL,
        evidence_class=EvidenceClass.SIMULATOR_CHARACTERIZATION,
        deterministic_tests=(
            "tests/test_phonesuite_serial_characterization.py",
            "tests/test_phonesuite_serial_session.py",
            "tests/test_phonesuite_serial_runtime_integration.py",
            "tests/test_phonesuite_serial_pty_integration.py",
        ),
        notes="Clean-room simulator-backed PBX-to-PMS ENQ/ACK and STX/ETX CHK/NAM characterization has a dedicated PhoneSuite session, live serial runtime selection, and Linux PTY fragmentation/coalescing/reopen/control-routing coverage. Serial settings remain operator-configured because PhoneSuite-specific defaults, PMS-to-PBX application semantics, and real-hardware timing/retry behavior are not yet evidence-qualified; Series2 TDMoE/PRI station programming remains out of scope.",
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
        deterministic_tests=(
            "tests/test_matrix_sarvam_characterization.py",
            "tests/test_pbx_brand_catalog.py",
        ),
        notes="Operator-confirmed Matrix SARVAM UCS PBX-to-PMS TCP observation is now preserved as a sanitized STX/ETX-framed FIAS LS fixture. A dedicated Matrix MICROS Opera profile and diagnostics deterministically prevent the known CRLF LS-reply framing mismatch. Link progression, retry timing, site port, ENQ/ACK behavior, guest-event semantics, and broader Matrix models/modes remain unqualified.",
    ),
    CompatibilityEntry(
        pbx_family="Hitachi",
        pbx_dialect="EPIT-HIT / Epitome Hitachi emulation",
        transport="unknown",
        pms_family="Epitome",
        pms_protocol="EPIT-HIT",
        direction=Direction.PMS_TO_PBX,
        status=SupportStatus.PLANNED,
        evidence_class=EvidenceClass.LEGACY_SOURCE_PROFILE,
        notes="Legacy PhoneSuite/Voiceware profile documentation explicitly identifies EPIT-HIT as an Epitome Hitachi-emulation interface. This establishes a real fifth-family integration lineage but does not qualify transport, framing, control bytes, serial parameters, exact record layouts, or reverse-direction behavior; no wire-level compatibility is claimed yet.",
    ),
    CompatibilityEntry(
        pbx_family="Hitachi",
        pbx_dialect="EPIT-HIT2 / Epitome Hitachi room-name layout variant",
        transport="unknown",
        pms_family="Epitome",
        pms_protocol="EPIT-HIT2",
        direction=Direction.PMS_TO_PBX,
        status=SupportStatus.PLANNED,
        evidence_class=EvidenceClass.LEGACY_SOURCE_PROFILE,
        notes="Legacy PhoneSuite/Voiceware documentation explicitly identifies EPIT-HIT2 as the Epitome Hitachi variant used when normal check-ins fail because room and guest-name fields do not appear where expected. The documentation establishes the variant's purpose only; transport, framing, control bytes, serial parameters, exact byte offsets/layout, and reverse-direction behavior remain unqualified and no wire-level compatibility is claimed yet.",
    ),
)


_INDEX = {entry.key: entry for entry in COMPATIBILITY_MATRIX}
if len(_INDEX) != len(COMPATIBILITY_MATRIX):
    raise RuntimeError("Duplicate compatibility matrix key")
for _entry in COMPATIBILITY_MATRIX:
    _entry.validate()


def compatibility_catalog() -> list[dict[str, Any]]:
    return [entry.as_dict() for entry in COMPATIBILITY_MATRIX]


def _transport_neighbor_notes(
    *,
    pbx_family: str,
    pbx_dialect: str,
    transport: str,
    pms_family: str,
    pms_protocol: str,
    direction_value: str,
) -> str | None:
    """Explain transport-only near misses without turning them into claims.

    Application/profile evidence does not qualify a different transport. This helper
    deliberately keeps the returned result UNSUPPORTED while making the failure useful
    to a technician. It is especially important for evidence-indexed rows such as
    EPIT-HIT/EPIT-HIT2 whose transport is still unknown.
    """

    dimensions = (
        pbx_family.casefold(),
        pbx_dialect.casefold(),
        pms_family.casefold(),
        pms_protocol.casefold(),
        direction_value,
    )
    neighbors = [
        entry
        for entry in COMPATIBILITY_MATRIX
        if (
            entry.pbx_family.casefold(),
            entry.pbx_dialect.casefold(),
            entry.pms_family.casefold(),
            entry.pms_protocol.casefold(),
            entry.direction.value,
        ) == dimensions
    ]
    if not neighbors:
        return None

    requested = transport.strip().lower()
    if any(entry.transport.casefold() == "unknown" for entry in neighbors):
        return (
            "An evidence-indexed compatibility lineage exists for this exact PBX/PMS application combination, "
            f"but its transport remains evidence-unqualified. Requested transport '{requested}' is not verified. "
            "Do not inherit generic serial/TCP settings or promote application/profile evidence into transport truth. "
            "Obtain profile-bound transport evidence or a sanitized wire capture before creating an exact transport row."
        )

    qualified = ", ".join(sorted({entry.transport.lower() for entry in neighbors}))
    return (
        "Evidence-indexed matrix row(s) for this exact PBX/PMS application combination exist only for "
        f"transport(s): {qualified}. Requested transport '{requested}' has no exact row. Transport is a separate "
        "compatibility dimension; do not transpose framing, timing, handshake, or application behavior across "
        "transports without transport-specific evidence."
    )


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

    transport_notes = _transport_neighbor_notes(
        pbx_family=pbx_family,
        pbx_dialect=pbx_dialect,
        transport=transport,
        pms_family=pms_family,
        pms_protocol=pms_protocol,
        direction_value=direction_value,
    )
    return CompatibilityEntry(
        pbx_family=pbx_family,
        pbx_dialect=pbx_dialect,
        transport=transport,
        pms_family=pms_family,
        pms_protocol=pms_protocol,
        direction=Direction(direction_value),
        status=SupportStatus.UNSUPPORTED,
        evidence_class=EvidenceClass.NONE,
        notes=(
            transport_notes
            or "No verified compatibility row exists for this exact combination. Do not auto-select or infer a different profile."
        ),
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