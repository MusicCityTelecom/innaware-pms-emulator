from __future__ import annotations

import re

from .phonesuite_pms_policy import (
    PhoneSuitePMSFormatDiagnostic,
    PhoneSuitePMSRecordAssessment,
)


_SOURCE_BACKED_FORMATS = {
    "MSG": "MSGn EEE[E], where n is 0-9",
    "DID": "DID1 EEE[E] DDDD to assign a DID or DID0 EEE[E] to clear it",
    "VIP": "VIP1 EEE[E] to set VIP or VIP0 EEE[E] to clear it",
    "WKP": "WKPhhmm EEE[E] to set, WKP9999 EEE[E] or WKP EEE[E] to clear",
}


def _text(payload: bytes) -> str:
    return payload.decode("latin-1", errors="replace").strip("\x00\r\n")


def _valid_extension(token: str) -> bool:
    return len(token) in {3, 4} and token.isdigit()


def _assessment(
    *,
    opcode: str | None,
    family: str | None,
    qualified: bool,
) -> PhoneSuitePMSRecordAssessment:
    return PhoneSuitePMSRecordAssessment(
        opcode=opcode,
        family=family,
        qualified=qualified,
        expected_format=_SOURCE_BACKED_FORMATS.get(family or "") if qualified else None,
    )


def assess_phonesuite_pms_source_extension(payload: bytes) -> PhoneSuitePMSRecordAssessment:
    """Classify additional PMS->PhoneSuite families established by the direct manual.

    The direct PhoneSuite PMS-interface manual explicitly documents PMS-originated
    drop-message (MSGn), DID assignment, VIP status, and wakeup-call commands.
    These families were deliberately omitted from the earlier conservative policy
    until their direction could be resolved. Qualification here means only that
    the application family/direction is source-backed; syntactic validation is
    handled separately and no transport, checksum, or retry behavior is inferred.
    """

    text = _text(payload)
    if not text:
        return _assessment(opcode=None, family=None, qualified=False)

    upper = text.upper()
    for family in ("MSG", "DID", "VIP", "WKP"):
        if not upper.startswith(family):
            continue
        match = re.match(rf"^{family}([0-9]*)", upper)
        suffix = match.group(1) if match else ""
        return _assessment(
            opcode=family + suffix,
            family=family,
            qualified=True,
        )

    return _assessment(opcode=None, family=None, qualified=False)


def _finding(
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


def _extension_finding(family: str, token: str) -> PhoneSuitePMSFormatDiagnostic:
    return _finding(
        code="phonesuite_pms_extension_format_invalid",
        observed=f"{family} record used extension field {token!r}",
        expected="A syntactic 3- or 4-digit room extension; property membership is checked separately",
        corrective_action=(
            f"Correct the {family} room-extension field to 3 or 4 decimal digits, then verify the room exists in "
            "the property mapping. Do not change serial/TCP settings to compensate for an application-field error."
        ),
    )


def diagnose_phonesuite_pms_source_extension_format(
    payload: bytes,
) -> list[PhoneSuitePMSFormatDiagnostic]:
    """Diagnose direct-manual PMS->PhoneSuite MSG/DID/VIP/WKP format errors.

    MSG is direction-sensitive: the direct manual also documents a distinct
    PhoneSuite->PMS MSG2 voicemail-status record. Callers must therefore apply
    this helper only when endpoint identity independently proves PMS->PBX
    direction. The capture-diagnostics integration provides that gate.
    """

    text = _text(payload)
    if not text:
        return []
    upper = text.upper()

    if upper.startswith("MSG"):
        match = re.fullmatch(r"MSG([0-9])\s+(\S+)\s*", text, flags=re.IGNORECASE)
        if not match:
            return [
                _finding(
                    code="phonesuite_pms_msg_format_invalid",
                    observed=f"Malformed PMS-to-PhoneSuite drop-message record {text!r}",
                    expected=_SOURCE_BACKED_FORMATS["MSG"],
                    corrective_action=(
                        "Send MSG0 through MSG9 followed by a space and the 3- or 4-digit room extension. "
                        "Do not apply this PMS-to-PBX rule to PhoneSuite-originated MSG2 voicemail-status records."
                    ),
                )
            ]
        extension = match.group(2)
        return [] if _valid_extension(extension) else [_extension_finding("MSG", extension)]

    if upper.startswith("DID"):
        status_match = re.match(r"^DID([0-9])", text, flags=re.IGNORECASE)
        if not status_match or status_match.group(1) not in {"0", "1"}:
            return [
                _finding(
                    code="phonesuite_pms_did_status_invalid",
                    observed=f"DID command did not use status 0 or 1: {text!r}",
                    expected=_SOURCE_BACKED_FORMATS["DID"],
                    corrective_action="Use DID1 to assign a DID or DID0 to clear the room DID assignment.",
                )
            ]

        status = status_match.group(1)
        if status == "0":
            match = re.fullmatch(r"DID0\s+(\S+)\s*", text, flags=re.IGNORECASE)
            if not match:
                return [
                    _finding(
                        code="phonesuite_pms_did_format_invalid",
                        observed=f"Malformed DID-clear record {text!r}",
                        expected="DID0 EEE[E] with no DID value after the room extension",
                        corrective_action="Send DID0 followed only by the 3- or 4-digit room extension.",
                    )
                ]
            extension = match.group(1)
            return [] if _valid_extension(extension) else [_extension_finding("DID", extension)]

        match = re.fullmatch(r"DID1\s+(\S+)\s+(\S+)\s*", text, flags=re.IGNORECASE)
        if not match:
            return [
                _finding(
                    code="phonesuite_pms_did_format_invalid",
                    observed=f"Malformed DID-assignment record {text!r}",
                    expected="DID1 EEE[E] DDDD",
                    corrective_action="Send DID1, the room extension, and the documented four-digit DID field.",
                )
            ]
        extension, did_value = match.groups()
        findings: list[PhoneSuitePMSFormatDiagnostic] = []
        if not _valid_extension(extension):
            findings.append(_extension_finding("DID", extension))
        if not re.fullmatch(r"\d{4}", did_value):
            findings.append(
                _finding(
                    code="phonesuite_pms_did_number_invalid",
                    observed=f"DID1 used DID field {did_value!r}",
                    expected="The documented four-digit DDDD assignment field",
                    corrective_action=(
                        "Send the four-digit DID assignment field documented for this PhoneSuite application command. "
                        "Do not infer a public E.164 DID layout from this legacy field without stronger site evidence."
                    ),
                )
            )
        return findings

    if upper.startswith("VIP"):
        match = re.fullmatch(r"VIP([01])\s+(\S+)\s*", text, flags=re.IGNORECASE)
        if not match:
            status_match = re.match(r"^VIP([0-9])", text, flags=re.IGNORECASE)
            if status_match and status_match.group(1) not in {"0", "1"}:
                return [
                    _finding(
                        code="phonesuite_pms_vip_status_invalid",
                        observed=f"VIP used status {status_match.group(1)!r}",
                        expected="VIP status 1 to set or 0 to clear",
                        corrective_action="Use VIP1 to set or VIP0 to clear the VIP flag, followed by the room extension.",
                    )
                ]
            return [
                _finding(
                    code="phonesuite_pms_vip_format_invalid",
                    observed=f"Malformed PMS-to-PhoneSuite VIP record {text!r}",
                    expected=_SOURCE_BACKED_FORMATS["VIP"],
                    corrective_action="Send VIP1 or VIP0 followed by the 3- or 4-digit room extension.",
                )
            ]
        extension = match.group(2)
        return [] if _valid_extension(extension) else [_extension_finding("VIP", extension)]

    if upper.startswith("WKP"):
        # A blank/space time field is a documented clear operation: WKP EEE[E].
        clear_match = re.fullmatch(r"WKP\s+(\S+)\s*", text, flags=re.IGNORECASE)
        if clear_match:
            extension = clear_match.group(1)
            return [] if _valid_extension(extension) else [_extension_finding("WKP", extension)]

        timed_match = re.fullmatch(r"WKP(\d{4})\s+(\S+)\s*", text, flags=re.IGNORECASE)
        if timed_match:
            hhmm, extension = timed_match.groups()
            findings: list[PhoneSuitePMSFormatDiagnostic] = []
            if not _valid_extension(extension):
                findings.append(_extension_finding("WKP", extension))
            if hhmm != "9999":
                hours = int(hhmm[:2])
                minutes = int(hhmm[2:])
                if hours > 23 or minutes > 59:
                    findings.append(
                        _finding(
                            code="phonesuite_pms_wkp_time_invalid",
                            observed=f"WKP used non-24-hour time {hhmm!r}",
                            expected="Zero-padded 24-hour hhmm, or 9999 to clear",
                            corrective_action=(
                                "Use a valid 0000-2359 time with minutes 00-59, or use 9999 / a blank time field "
                                "to clear the wakeup call."
                            ),
                        )
                    )
            return findings

        return [
            _finding(
                code="phonesuite_pms_wkp_format_invalid",
                observed=f"Malformed PMS-to-PhoneSuite wakeup record {text!r}",
                expected=_SOURCE_BACKED_FORMATS["WKP"],
                corrective_action=(
                    "Place the four-digit hhmm value immediately after WKP with no separator, then a space and "
                    "the room extension. Use WKP9999 or WKP plus a blank time field to clear."
                ),
            )
        ]

    return []
