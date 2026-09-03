from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


PHONESUITE_PMS_MAX_GAP_SECONDS = 0.1
_OPCODE_RE = re.compile(r"^([A-Z]+)([0-9]*)")
_VENDOR_PMS_TO_PBX_EXACT_OPCODES = {
    "CHK0",
    "CHK1",
    "DND0",
    "DND1",
    "MW0",
    "MW1",
    "NAM1",
    "NAM2",
    "NAM3",
    "NAM4",
    "AREYUTHERE",
    "GRS",
    "END",
}
_VENDOR_PMS_TO_PBX_FAMILIES = {"LMT", "GRP", "LNG", "RST"}
_VENDOR_PMS_TO_PBX_FORMATS = {
    "CHK": "CHK1 EEEE [Name] or CHK0 EEEE",
    "LMT": "LMT EEE dd.cc or LMT EEEE $dd.cc",
    "DND": "DND1 EEEE or DND0 EEEE",
    "GRP": "GRP EEE[E] AAAAAAAAAA",
    "LNG": "LNGxxEEE[E] with lowercase two-letter ISO 639-1 code xx",
    "MW": "MW 1 EEEE or MW 0 EEEE; exactly one space between MW and status",
    "RST": "RSTn EEEE",
    "AREYUTHERE": "AREYUTHERE",
    "GRS": "GRS",
    "END": "END",
    "NAM": "NAMn Name EEEE where n is 1-4",
}


@dataclass(frozen=True, slots=True)
class PhoneSuitePMSRecordAssessment:
    opcode: str | None
    family: str | None
    qualified: bool
    expected_format: str | None = None
    direction: str = "pms_to_pbx"
    evidence_class: str = "legacy_source_profile"

    def as_dict(self) -> dict[str, Any]:
        return {
            "opcode": self.opcode,
            "family": self.family,
            "qualified": self.qualified,
            "expected_format": self.expected_format,
            "direction": self.direction,
            "evidence_class": self.evidence_class,
        }


@dataclass(frozen=True, slots=True)
class PhoneSuitePMSTimingDiagnostic:
    code: str
    severity: str
    confidence: str
    evidence_class: str
    observed: str
    expected: str
    corrective_action: str

    def as_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "severity": self.severity,
            "confidence": self.confidence,
            "evidence_class": self.evidence_class,
            "observed": self.observed,
            "expected": self.expected,
            "corrective_action": self.corrective_action,
        }


def _extract_phonesuite_pms_opcode(text: str) -> tuple[str | None, str | None]:
    """Normalize documented PhoneSuite PMS command spellings without guessing transport."""

    if not text:
        return None, None

    upper = text.upper()

    # The legacy source requires a literal space between MW and the 0/1 status.
    mw_match = re.match(r"^MW\s+([01])(?:\s|$)", upper)
    if mw_match:
        return f"MW{mw_match.group(1)}", "MW"

    # LNG carries the ISO 639-1 code immediately after the family token, so a
    # generic alpha-prefix parser would otherwise misclassify LNGen101 as a
    # distinct family. Qualification here is family-level; the format hint
    # retains the documented lowercase-code requirement for technicians.
    if upper.startswith("LNG") and len(text) >= 5 and text[3:5].isalpha():
        return f"LNG{text[3:5]}", "LNG"

    match = _OPCODE_RE.match(upper)
    if not match:
        return None, None
    family = match.group(1)
    opcode = family + match.group(2)
    return opcode, family


def assess_phonesuite_pms_record(payload: bytes) -> PhoneSuitePMSRecordAssessment:
    """Classify PMS->PhoneSuite records explicitly qualified by legacy docs.

    The historical PhoneSuite/Voiceware PMS-interface documentation explicitly
    documents PMS-originated check-in/out, credit-limit, DND, group-code,
    language, message-waiting, phone-restriction, database-dump control, and
    guest-name command families. This classifier exposes only those documented
    families. Ambiguous/reverse-direction families such as MOV, MSG, STS, and
    RQINZ are deliberately not promoted here.

    Qualification means the command family/direction is evidence-backed; it is
    not a blanket assertion that every payload instance is syntactically valid.
    expected_format provides the source-backed technician hint without importing
    serial defaults, checksum behavior, retry policy, or Mitel TCP timing.
    """

    text = payload.decode("latin-1", errors="replace").strip("\x00\r\n ")
    opcode, family = _extract_phonesuite_pms_opcode(text)
    if not opcode or not family:
        return PhoneSuitePMSRecordAssessment(None, None, False)

    qualified = (
        opcode in _VENDOR_PMS_TO_PBX_EXACT_OPCODES
        or family in _VENDOR_PMS_TO_PBX_FAMILIES
    )
    expected_format = _VENDOR_PMS_TO_PBX_FORMATS.get(family) if qualified else None
    return PhoneSuitePMSRecordAssessment(
        opcode=opcode,
        family=family,
        qualified=qualified,
        expected_format=expected_format,
    )


def diagnose_phonesuite_pms_receive_timing(
    *,
    enq_ack_to_stx_seconds: float | None = None,
    max_inter_byte_gap_seconds: float | None = None,
    complete_etx: bool = True,
    late_data_after_timeout: bool = False,
) -> list[PhoneSuitePMSTimingDiagnostic]:
    """Evaluate documented PhoneSuite receiver timing without inventing retries.

    Legacy PhoneSuite/Voiceware PMS-interface documentation states that, after
    PhoneSuite ACKs a PMS ENQ, STX must follow within one tenth of a second;
    message bytes/ETX must not be separated by more than one tenth of a second.
    A timed-out transaction receives no further response until later non-ENQ
    data arrives, at which point PhoneSuite sends NAK. The source does not
    qualify Mitel-style three-second timers or frame-only retry counts for this
    PhoneSuite direction, so this helper deliberately does not infer them.
    """

    values = {
        "enq_ack_to_stx_seconds": enq_ack_to_stx_seconds,
        "max_inter_byte_gap_seconds": max_inter_byte_gap_seconds,
    }
    for name, value in values.items():
        if value is not None and value < 0:
            raise ValueError(f"{name} must be non-negative")

    findings: list[PhoneSuitePMSTimingDiagnostic] = []
    evidence = "legacy_source_profile"

    if enq_ack_to_stx_seconds is not None and enq_ack_to_stx_seconds > PHONESUITE_PMS_MAX_GAP_SECONDS:
        findings.append(
            PhoneSuitePMSTimingDiagnostic(
                code="phonesuite_pms_stx_deadline_exceeded",
                severity="warning",
                confidence="high",
                evidence_class=evidence,
                observed=(
                    f"PMS STX followed the PhoneSuite ACK after {enq_ack_to_stx_seconds:.3f} second(s)"
                ),
                expected="STX within 0.100 second after PhoneSuite ACKs the PMS ENQ",
                corrective_action=(
                    "Transmit the STX/application frame immediately after the ENQ grant. Do not substitute the "
                    "Mitel-compatible 3-second transaction timer for this PhoneSuite receive-side timing rule."
                ),
            )
        )

    if max_inter_byte_gap_seconds is not None and max_inter_byte_gap_seconds > PHONESUITE_PMS_MAX_GAP_SECONDS:
        findings.append(
            PhoneSuitePMSTimingDiagnostic(
                code="phonesuite_pms_interbyte_deadline_exceeded",
                severity="warning",
                confidence="high",
                evidence_class=evidence,
                observed=f"Largest observed in-frame byte gap was {max_inter_byte_gap_seconds:.3f} second(s)",
                expected="No between-character delay greater than 0.100 second while the PMS frame is arriving",
                corrective_action=(
                    "Inspect serial buffering, USB/serial adapters, driver latency, and application write chunking. "
                    "Keep physical serial settings operator-configured; this timing evidence does not qualify baud, "
                    "parity, data bits, stop bits, or flow control."
                ),
            )
        )

    if not complete_etx:
        findings.append(
            PhoneSuitePMSTimingDiagnostic(
                code="phonesuite_pms_etx_deadline_missing",
                severity="warning",
                confidence="high",
                evidence_class=evidence,
                observed="PMS application message did not complete with ETX inside the characterized receive window",
                expected="ETX to terminate the STX/application frame without a gap greater than 0.100 second",
                corrective_action=(
                    "Verify STX/ETX framing and ensure the complete message is written as a continuous transaction. "
                    "Do not add a checksum or retry policy unless the selected PhoneSuite profile evidence requires it."
                ),
            )
        )

    if late_data_after_timeout:
        findings.append(
            PhoneSuitePMSTimingDiagnostic(
                code="phonesuite_pms_late_data_after_timeout",
                severity="warning",
                confidence="high",
                evidence_class=evidence,
                observed="Non-ENQ PMS data arrived after the PhoneSuite receive transaction had already timed out",
                expected="A new ENQ to begin a fresh transaction after timeout",
                corrective_action=(
                    "Restart the transaction with ENQ rather than continuing the expired frame. A PhoneSuite NAK "
                    "after late non-ENQ data is evidence-consistent and should not trigger an automatic profile switch."
                ),
            )
        )

    return findings
