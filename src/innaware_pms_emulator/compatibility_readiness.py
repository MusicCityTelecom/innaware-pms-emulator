from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .compatibility_matrix import (
    COMPATIBILITY_MATRIX,
    CompatibilityEntry,
    Direction,
    SupportStatus,
)


@dataclass(frozen=True, slots=True)
class EvidenceGap:
    """One evidence requirement that still blocks a compatibility claim."""

    code: str
    action: str

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "action": self.action}


@dataclass(frozen=True, slots=True)
class CompatibilityReadiness:
    """A compatibility row plus its explicit evidence-to-promotion work."""

    entry: CompatibilityEntry
    evidence_gaps: tuple[EvidenceGap, ...]

    @property
    def release_ready(self) -> bool:
        return self.entry.status is SupportStatus.SUPPORTED and not self.evidence_gaps

    def as_dict(self) -> dict[str, Any]:
        result = self.entry.as_dict()
        result["evidence_gaps"] = [gap.as_dict() for gap in self.evidence_gaps]
        result["release_ready"] = self.release_ready
        return result


def _key(
    pbx_family: str,
    pbx_dialect: str,
    transport: str,
    pms_family: str,
    pms_protocol: str,
    direction: Direction,
) -> tuple[str, str, str, str, str, str]:
    return (
        pbx_family.casefold(),
        pbx_dialect.casefold(),
        transport.casefold(),
        pms_family.casefold(),
        pms_protocol.casefold(),
        direction.value,
    )


def _gap(code: str, action: str) -> EvidenceGap:
    return EvidenceGap(code=code, action=action)


# Keep the evidence-to-promotion work explicit and keyed by the same six
# compatibility dimensions as the authoritative matrix. These entries describe
# what is still missing; they are not protocol defaults and cannot promote a row.
_EVIDENCE_GAPS: dict[tuple[str, str, str, str, str, str], tuple[EvidenceGap, ...]] = {
    _key(
        "Mitel",
        "MITEL 1 / iPocket-characterized",
        "tcp",
        "legacy-hotel-pms",
        "mitel-hospitality",
        Direction.BIDIRECTIONAL,
    ): (
        _gap(
            "model_scope",
            "Capture or operator-confirm additional Mitel model/firmware combinations before generalizing the iPocket-characterized TCP behavior.",
        ),
        _gap(
            "field_variants",
            "Add sanitized packet-capture fixtures for any remaining CHK/NAM/control field variants before calling the TCP dialect complete.",
        ),
    ),
    _key(
        "Mitel",
        "legacy MTL-compatible",
        "serial",
        "legacy-hotel-pms",
        "mitel-hospitality",
        Direction.PBX_TO_PMS,
    ): (
        _gap(
            "real_hardware_serial",
            "Characterize a real Mitel-family serial PBX using synthetic room data and record model, firmware, exact serial settings, direction, and wire bytes.",
        ),
        _gap(
            "serial_timing_scope",
            "Confirm serial-specific timeout and retry behavior from serial evidence; do not import Mitel TCP timing or reconnect behavior.",
        ),
    ),
    _key(
        "Mitel",
        "legacy MTL-compatible",
        "serial",
        "legacy-hotel-pms",
        "mitel-hospitality",
        Direction.PMS_TO_PBX,
    ): (
        _gap(
            "real_hardware_serial",
            "Repeat the sanitized ENQ/ACK plus CHK1/CHK0 receive-side transaction against real Mitel-family serial hardware with explicit model, firmware, and serial settings.",
        ),
        _gap(
            "serial_timing_scope",
            "Qualify receive-side serial timeout/retry behavior from serial evidence instead of inheriting the TCP application or reconnect timers.",
        ),
    ),
    _key(
        "PhoneSuite",
        "MITEL 1-compatible",
        "serial",
        "legacy-hotel-pms",
        "mitel-hospitality",
        Direction.PBX_TO_PMS,
    ): (
        _gap(
            "real_hardware_serial",
            "Validate the characterized PBX-to-PMS transaction set against real PhoneSuite hardware using synthetic rooms and explicit site serial settings.",
        ),
        _gap(
            "serial_parameter_scope",
            "Qualify PhoneSuite-specific baud/data/parity/stop/flow settings from direct evidence; generic Voiceware serial guidance is not a PhoneSuite default.",
        ),
    ),
    _key(
        "PhoneSuite",
        "MITEL 1-compatible",
        "serial",
        "legacy-hotel-pms",
        "mitel-hospitality",
        Direction.PMS_TO_PBX,
    ): (
        _gap(
            "real_hardware_serial",
            "Validate the source-backed PMS-to-PhoneSuite commands and 0.100-second receive boundary against real PhoneSuite hardware using synthetic guest data.",
        ),
        _gap(
            "serial_parameter_scope",
            "Record PhoneSuite-specific serial parameters from direct source or hardware evidence rather than inheriting generic Voiceware defaults.",
        ),
        _gap(
            "checksum_contract",
            "Obtain direct source or wire evidence for the optional PhoneSuite checksum algorithm, coverage, placement, and ACK/NAK behavior before implementing it.",
        ),
        _gap(
            "retry_policy",
            "Characterize PhoneSuite-specific retry behavior; do not import the Mitel-compatible frame retry count.",
        ),
    ),
    _key(
        "Matrix",
        "MICROS Opera / FIAS",
        "tcp",
        "Oracle / MICROS Opera",
        "FIAS",
        Direction.PBX_TO_PMS,
    ): (
        _gap(
            "post_ls_progression",
            "Capture Matrix SARVAM behavior after the known STX/ETX-framed LS record, including the next expected link-state exchange.",
        ),
        _gap(
            "retry_timing",
            "Measure Matrix-specific retry and timeout behavior instead of substituting generic FIAS timing.",
        ),
        _gap(
            "site_port",
            "Record the configured Matrix PMS TCP port as site/runtime evidence without treating one installation value as a universal default.",
        ),
        _gap(
            "handshake",
            "Capture whether the characterized Matrix mode uses any ENQ/ACK control exchange; do not infer one from Mitel or PhoneSuite.",
        ),
        _gap(
            "guest_events",
            "Capture sanitized Matrix-specific guest-event records before qualifying check-in, checkout, name, wakeup, or status semantics.",
        ),
        _gap(
            "reverse_direction",
            "Obtain Matrix PMS-to-PBX application evidence before registering the reverse direction or a bidirectional row.",
        ),
    ),
    _key(
        "Hitachi",
        "EPIT-HIT / Epitome Hitachi emulation",
        "unknown",
        "Epitome",
        "EPIT-HIT",
        Direction.PMS_TO_PBX,
    ): (
        _gap(
            "profile_body",
            "Characterize the exact psip-pbx-protocol.EPIT-HIT file read-only and retain only sanitized interoperability facts plus its source SHA-256.",
        ),
        _gap(
            "transport",
            "Qualify serial or TCP only from the profile itself or sanitized wire evidence; do not inherit generic Voiceware transport guidance.",
        ),
        _gap(
            "framing_control",
            "Extract framing and control-byte behavior from the exact profile or capture before creating a wire-compatible implementation.",
        ),
        _gap(
            "record_layout",
            "Capture only the recognized synthetic-safe CHK/NAM record-layout facts needed for deterministic Hitachi fixtures.",
        ),
        _gap(
            "checksum_contract",
            "Qualify any checksum/BCC behavior from exact profile or wire evidence rather than inference.",
        ),
        _gap(
            "reverse_direction",
            "Obtain Hitachi PBX-to-PMS evidence before registering the reverse direction or a bidirectional row.",
        ),
    ),
    _key(
        "Hitachi",
        "EPIT-HIT2 / Epitome Hitachi room-name layout variant",
        "unknown",
        "Epitome",
        "EPIT-HIT2",
        Direction.PMS_TO_PBX,
    ): (
        _gap(
            "profile_body",
            "Characterize the exact psip-pbx-protocol.EPIT-HIT2 file read-only and retain only sanitized interoperability facts plus its source SHA-256.",
        ),
        _gap(
            "profile_delta",
            "Compare EPIT-HIT2 against EPIT-HIT and Epitome with the sanitized comparator to isolate the room/name layout delta without retaining vendor profile bodies.",
        ),
        _gap(
            "transport",
            "Qualify serial or TCP only from the profile itself or sanitized wire evidence; do not inherit generic Voiceware transport guidance.",
        ),
        _gap(
            "framing_control",
            "Extract framing and control-byte behavior from the exact profile or capture before creating a wire-compatible implementation.",
        ),
        _gap(
            "record_layout",
            "Capture only the recognized synthetic-safe room/name layout facts needed for a deterministic EPIT-HIT2 fixture.",
        ),
        _gap(
            "checksum_contract",
            "Qualify any checksum/BCC behavior from exact profile or wire evidence rather than inference.",
        ),
        _gap(
            "reverse_direction",
            "Obtain Hitachi PBX-to-PMS evidence before registering the reverse direction or a bidirectional row.",
        ),
    ),
}


def readiness_for(entry: CompatibilityEntry) -> CompatibilityReadiness:
    """Return fail-closed evidence readiness for one compatibility result."""

    if entry.status is SupportStatus.UNSUPPORTED:
        gaps = (
            _gap(
                "exact_row_missing",
                "Obtain evidence for this exact six-dimensional combination before selecting or promoting a nearby personality or transport.",
            ),
        )
    elif entry.status is SupportStatus.SUPPORTED:
        gaps = ()
    else:
        gaps = _EVIDENCE_GAPS.get(entry.key)
        if gaps is None:
            gaps = (
                _gap(
                    "readiness_registry_missing",
                    "Do not promote this row until its unresolved evidence requirements are explicitly registered and reviewed.",
                ),
            )
    return CompatibilityReadiness(entry=entry, evidence_gaps=gaps)


def compatibility_readiness_catalog(
    *,
    statuses: Iterable[SupportStatus] | None = None,
) -> list[dict[str, Any]]:
    """Return matrix rows with actionable, machine-readable evidence gaps."""

    allowed = set(statuses) if statuses is not None else None
    return [
        readiness_for(entry).as_dict()
        for entry in COMPATIBILITY_MATRIX
        if allowed is None or entry.status in allowed
    ]


def validate_readiness_registry() -> list[str]:
    """Return coverage errors between the compatibility matrix and gap registry."""

    matrix_by_key = {entry.key: entry for entry in COMPATIBILITY_MATRIX}
    errors: list[str] = []

    for entry in COMPATIBILITY_MATRIX:
        registered = _EVIDENCE_GAPS.get(entry.key)
        if entry.status in {SupportStatus.PARTIAL, SupportStatus.PLANNED} and not registered:
            errors.append(f"missing evidence-gap registry entry for {entry.key!r}")
        if entry.status is SupportStatus.SUPPORTED and registered:
            errors.append(f"SUPPORTED row still has registered evidence gaps for {entry.key!r}")

    for key in _EVIDENCE_GAPS:
        if key not in matrix_by_key:
            errors.append(f"stale evidence-gap registry entry for {key!r}")

    return sorted(errors)
