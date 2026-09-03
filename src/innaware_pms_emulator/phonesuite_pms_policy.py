from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


PHONESUITE_PMS_MAX_GAP_SECONDS = 0.1
_OPCODE_RE = re.compile(r"^([A-Z]+)([0-9]*)")
_VENDOR_PMS_TO_PBX_OPCODES = {"CHK0", "CHK1"}


@dataclass(frozen=True, slots=True)
class PhoneSuitePMSRecordAssessment:
    opcode: str | None
    family: str | None
    qualified: bool
    direction: str = "pms_to_pbx"
    evidence_class: str = "legacy_source_profile"

    def as_dict(self) -> dict[str, Any]:
        return {
            "opcode": self.opcode,
            "family": self.family,
            "qualified": self.qualified,
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


def assess_phonesuite_pms_record(payload: bytes) -> PhoneSuitePMSRecordAssessment:
    """Classify only PMS->PhoneSuite records explicitly qualified by legacy docs.

    The PhoneSuite/Voiceware PMS interface documentation explicitly describes
    CHK1 and CHK0 as PMS-to-PhoneSuite Check In/Out commands. Other message
    families may exist in the same documentation, but they are intentionally
    not promoted through this narrow evidence boundary until separately
    modeled and tested.
    """

    text = payload.decode("latin-1", errors="replace").strip("\x00\r\n ")
    match = _OPCODE_RE.match(text.upper()) if text else None
    if not match:
        return PhoneSuitePMSRecordAssessment(None, None, False)
    family = match.group(1)
    opcode = family + match.group(2)
    return PhoneSuitePMSRecordAssessment(
        opcode=opcode,
        family=family,
        qualified=opcode in _VENDOR_PMS_TO_PBX_OPCODES,
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
