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


@dataclass(frozen=True, slots=True)
class PhoneSuitePMSFormatDiagnostic:
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


def _format_diagnostic(
    *,
    code: str,
    observed: str,
    expected: str,
    corrective_action: str,
) -> PhoneSuitePMSFormatDiagnostic:
    return PhoneSuitePMSFormatDiagnostic(
        code=code,
        severity="warning",
        confidence="high",
        evidence_class="legacy_source_profile",
        observed=observed,
        expected=expected,
        corrective_action=corrective_action,
    )


def _valid_extension_token(token: str) -> bool:
    return len(token) in {3, 4} and token.isdigit()


def diagnose_phonesuite_pms_record_format(payload: bytes) -> list[PhoneSuitePMSFormatDiagnostic]:
    """Diagnose source-backed PMS->PhoneSuite record-format mistakes.

    This validates only syntax explicitly described by the historical
    PhoneSuite/Voiceware PMS-interface documentation. It does not decide whether
    a syntactically valid extension exists at a property, infer transport
    settings, add a checksum, define retries, or promote ambiguous/reverse-
    direction command families.
    """

    text = payload.decode("latin-1", errors="replace").strip("\x00\r\n")
    if not text:
        return []

    upper = text.upper()
    findings: list[PhoneSuitePMSFormatDiagnostic] = []

    def extension_finding(family: str, token: str) -> PhoneSuitePMSFormatDiagnostic:
        return _format_diagnostic(
            code="phonesuite_pms_extension_format_invalid",
            observed=f"{family} record used extension field {token!r}",
            expected="A syntactic 3- or 4-digit extension field; property membership is checked separately",
            corrective_action=(
                f"Correct the {family} extension field to 3 or 4 decimal digits, then verify the room/extension "
                "exists in the property configuration. Do not change serial/TCP settings to compensate for an "
                "application-field error."
            ),
        )

    if upper.startswith("CHK"):
        match = re.match(r"^CHK([01])\s+(.+)$", text, flags=re.IGNORECASE)
        if not match:
            findings.append(_format_diagnostic(
                code="phonesuite_pms_chk_format_invalid",
                observed=f"Malformed PhoneSuite check-in/out record {text!r}",
                expected="CHK1 EEEE [Name] or CHK0 EEEE, with a space after CHK0/CHK1",
                corrective_action="Send CHK0 or CHK1 followed by a space and a 3- or 4-digit extension.",
            ))
            return findings

        status, rest = match.groups()
        parts = rest.split()
        if not parts:
            findings.append(extension_finding("CHK", ""))
            return findings
        extension = parts[0]
        if not _valid_extension_token(extension):
            findings.append(extension_finding("CHK", extension))
            return findings

        if status == "1":
            name = rest[len(extension):].strip()
            if name and len(name) > 20:
                findings.append(_format_diagnostic(
                    code="phonesuite_pms_chk_name_too_long",
                    observed=f"CHK1 supplied a {len(name)}-character guest name",
                    expected="Optional CHK1 guest name no longer than 20 characters",
                    corrective_action="Shorten the synthetic/guest-name field to 20 characters or fewer without changing framing.",
                ))
        return findings

    if upper.startswith("LMT"):
        match = re.match(r"^LMT\s+(\S+)\s+(\S+)\s*$", text, flags=re.IGNORECASE)
        if not match:
            return [_format_diagnostic(
                code="phonesuite_pms_lmt_format_invalid",
                observed=f"Malformed PhoneSuite credit-limit record {text!r}",
                expected="LMT EEE[E] dd.cc with an optional leading $ on the amount",
                corrective_action="Send LMT, a 3- or 4-digit extension, and a decimal amount no greater than 999.99.",
            )]
        extension, amount = match.groups()
        if not _valid_extension_token(extension):
            findings.append(extension_finding("LMT", extension))
        amount_value = amount[1:] if amount.startswith("$") else amount
        if not re.fullmatch(r"\d{1,3}\.\d{2}", amount_value):
            findings.append(_format_diagnostic(
                code="phonesuite_pms_lmt_amount_invalid",
                observed=f"LMT used credit-limit amount {amount!r}",
                expected="Decimal credit limit dd.cc through 999.99; a leading $ is optional and preferably omitted",
                corrective_action="Send a decimal amount with exactly two fractional digits and no more than 999.99.",
            ))
        return findings

    if upper.startswith("DND"):
        match = re.match(r"^DND([01])\s+(\S+)\s*$", text, flags=re.IGNORECASE)
        if not match:
            return [_format_diagnostic(
                code="phonesuite_pms_dnd_format_invalid",
                observed=f"Malformed PhoneSuite DND record {text!r}",
                expected="DND1 EEEE or DND0 EEEE",
                corrective_action="Use DND1 to enable or DND0 to disable DND, followed by the 3- or 4-digit extension.",
            )]
        extension = match.group(2)
        if not _valid_extension_token(extension):
            findings.append(extension_finding("DND", extension))
        return findings

    if upper.startswith("GRP"):
        match = re.match(r"^GRP\s+(\S+)\s+(\S+)\s*$", text, flags=re.IGNORECASE)
        if not match:
            return [_format_diagnostic(
                code="phonesuite_pms_grp_format_invalid",
                observed=f"Malformed PhoneSuite group-code record {text!r}",
                expected="GRP EEE[E] AAAAAAAAAA",
                corrective_action="Send GRP, a 3- or 4-digit extension, and a group code containing only letters/numbers.",
            )]
        extension, group_code = match.groups()
        if not _valid_extension_token(extension):
            findings.append(extension_finding("GRP", extension))
        if not group_code.isalnum() or len(group_code) > 10:
            findings.append(_format_diagnostic(
                code="phonesuite_pms_group_code_invalid",
                observed=f"GRP used group code {group_code!r}",
                expected="A human-readable letters/numbers group code of at most 10 characters",
                corrective_action="Use a group code containing only letters and numbers and keep it within the documented 10-character field.",
            ))
        return findings

    if upper.startswith("LNG"):
        match = re.fullmatch(r"LNG([a-z]{2})(\d{3,4})", text)
        if match:
            return []
        code = text[3:5] if len(text) >= 5 else ""
        if len(code) != 2 or not code.isalpha() or code != code.lower():
            findings.append(_format_diagnostic(
                code="phonesuite_pms_language_code_invalid",
                observed=f"LNG used language-code field {code!r}",
                expected="Exactly two lowercase ISO 639-1 letters immediately after LNG",
                corrective_action="Send a two-letter lowercase ISO 639-1 language code, for example 'en'; do not use uppercase or three-letter codes.",
            ))
        else:
            findings.append(_format_diagnostic(
                code="phonesuite_pms_lng_format_invalid",
                observed=f"Malformed PhoneSuite language record {text!r}",
                expected="LNGxxEEE or LNGxxEEEE with no separator before the extension",
                corrective_action="Place the 3- or 4-digit extension immediately after the two lowercase language-code letters.",
            ))
        return findings

    if upper.startswith("MW"):
        status_match = re.match(r"^MW\s*([0-9])", text, flags=re.IGNORECASE)
        if status_match and status_match.group(1) not in {"0", "1"}:
            findings.append(_format_diagnostic(
                code="phonesuite_pms_mw_status_invalid",
                observed=f"MW used status {status_match.group(1)!r}",
                expected="MW status 0 or 1",
                corrective_action="Use MW 1 to turn the lamp on or MW 0 to turn it off.",
            ))
            return findings

        prefix_match = re.match(r"^MW ([01])(?:\s|$)", text, flags=re.IGNORECASE)
        if not prefix_match:
            findings.append(_format_diagnostic(
                code="phonesuite_pms_mw_spacing_invalid",
                observed=f"MW command did not use the documented single-space status delimiter: {text!r}",
                expected="Exactly one space between MW and the 0/1 status",
                corrective_action="Transmit 'MW 1 ...' or 'MW 0 ...' with exactly one space between MW and the status digit.",
            ))
            return findings

        match = re.match(r"^MW ([01])\s+(\S+)\s*$", text, flags=re.IGNORECASE)
        if not match:
            findings.append(_format_diagnostic(
                code="phonesuite_pms_mw_format_invalid",
                observed=f"Malformed PhoneSuite message-waiting record {text!r}",
                expected="MW 1 EEEE or MW 0 EEEE",
                corrective_action="After the status digit, send the 3- or 4-digit extension and no unrelated fields.",
            ))
            return findings
        extension = match.group(2)
        if not _valid_extension_token(extension):
            findings.append(extension_finding("MW", extension))
        return findings

    if upper.startswith("RST"):
        match = re.match(r"^RST([0-9]+)\s+(\S+)\s*$", text, flags=re.IGNORECASE)
        if not match:
            return [_format_diagnostic(
                code="phonesuite_pms_rst_format_invalid",
                observed=f"Malformed PhoneSuite restriction record {text!r}",
                expected="RSTn EEEE, where n is the restriction code",
                corrective_action="Append the restriction code directly to RST, then a space and the 3- or 4-digit extension.",
            )]
        extension = match.group(2)
        if not _valid_extension_token(extension):
            findings.append(extension_finding("RST", extension))
        return findings

    if upper.startswith("NAM"):
        index_match = re.match(r"^NAM([0-9])", text, flags=re.IGNORECASE)
        if not index_match or index_match.group(1) not in {"1", "2", "3", "4"}:
            findings.append(_format_diagnostic(
                code="phonesuite_pms_nam_index_invalid",
                observed=f"NAM command did not use an immediately adjacent index 1-4: {text!r}",
                expected="NAMn Name EEEE where n is 1, 2, 3, or 4 and immediately follows NAM",
                corrective_action="Use NAM1 through NAM4 with no space between NAM and the index.",
            ))
            return findings

        match = re.match(r"^NAM([1-4])\s+(.+?)\s+(\d{3,4})\s*$", text, flags=re.IGNORECASE)
        if not match:
            findings.append(_format_diagnostic(
                code="phonesuite_pms_nam_format_invalid",
                observed=f"Malformed PhoneSuite guest-name record {text!r}",
                expected="NAMn Name EEEE with a name and a 3- or 4-digit extension",
                corrective_action="Send NAM1-NAM4, a space, the guest name, at least one space, and the extension.",
            ))
            return findings
        name = match.group(2).strip()
        if len(name) > 20:
            findings.append(_format_diagnostic(
                code="phonesuite_pms_nam_name_too_long",
                observed=f"NAM{match.group(1)} supplied a {len(name)}-character guest name",
                expected="Guest name no longer than 20 characters",
                corrective_action="Shorten the guest-name field to 20 characters or fewer while preserving the selected name delimiter.",
            ))
        return findings

    for token in ("AREYUTHERE", "GRS", "END"):
        if upper.startswith(token):
            if text.upper() != token:
                findings.append(_format_diagnostic(
                    code="phonesuite_pms_control_record_has_arguments",
                    observed=f"{token} included unexpected trailing application text: {text!r}",
                    expected=f"Exact {token} control record with no arguments",
                    corrective_action=f"Send {token} by itself inside the normal PhoneSuite application frame.",
                ))
            return findings

    # MOV, MSGn, STSn, RQINZ, and unknown commands remain outside the
    # evidence-qualified PMS->PhoneSuite direction. Returning no format finding
    # here avoids turning a parser hint into a directional compatibility claim.
    return []


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
