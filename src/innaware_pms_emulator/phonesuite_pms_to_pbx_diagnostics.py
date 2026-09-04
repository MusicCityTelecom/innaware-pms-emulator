from __future__ import annotations

from datetime import datetime
from hashlib import sha256
from typing import Any, Iterable

from .diagnostics import observe_capture
from .phonesuite_pms_policy import (
    PHONESUITE_PMS_MAX_GAP_SECONDS,
    assess_phonesuite_pms_record,
    diagnose_phonesuite_pms_receive_timing,
    diagnose_phonesuite_pms_record_format,
)
from .phonesuite_pms_source_extensions import (
    assess_phonesuite_pms_source_extension,
    diagnose_phonesuite_pms_source_extension_format,
)


_ALLOWED_EVIDENCE_CLASSES = {
    "packet_capture",
    "operator_confirmed",
    "legacy_source_profile",
    "simulator_characterization",
    "inference",
}
_TRANSPORT = "serial"


def _normalize_evidence_class(value: str) -> str:
    normalized = str(value).strip().lower()
    if normalized not in _ALLOWED_EVIDENCE_CLASSES:
        raise ValueError(
            "evidence_class must be one of: "
            + ", ".join(sorted(_ALLOWED_EVIDENCE_CLASSES))
        )
    return normalized


def _require_serial_transport(value: str) -> str:
    normalized = str(value).strip().lower()
    if normalized != _TRANSPORT:
        raise ValueError(
            "transport must be serial for the currently registered PhoneSuite "
            "MITEL 1-compatible PMS-to-PBX row; do not infer a PhoneSuite TCP row"
        )
    return normalized


def _require_pms_capture_direction(value: str) -> str:
    normalized = str(value).strip().lower().replace("-", "_")
    if normalized not in {"rx", "tx"}:
        raise ValueError(
            "pms_capture_direction must be rx or tx so PMS-to-PBX direction is "
            "independently established before applying direction-sensitive records"
        )
    return normalized


def _normalized_direction(value: str) -> str:
    return str(value or "").strip().lower().replace("-", "_")


def _endpoint_side(item: Any, *, pms_capture_direction: str) -> str:
    direction = _normalized_direction(item.direction)
    if direction == "pms_to_pbx":
        return "pms"
    if direction == "pbx_to_pms":
        return "pbx"
    if direction in {"rx", "tx"}:
        return "pms" if direction == pms_capture_direction else "pbx"
    return "unknown"


def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _elapsed_seconds(start: Any, end: Any) -> float | None:
    first = _parse_timestamp(start)
    second = _parse_timestamp(end)
    if first is None or second is None:
        return None
    if (first.tzinfo is None) != (second.tzinfo is None):
        return None
    delta = (second - first).total_seconds()
    if delta < 0:
        return None
    return delta


def _application_assessment(payload: bytes) -> dict[str, Any]:
    direct = assess_phonesuite_pms_source_extension(payload)
    if direct.qualified:
        return {
            "qualified": True,
            "opcode": direct.opcode,
            "family": direct.family,
            "expected_format": direct.expected_format,
            "evidence_class": direct.evidence_class,
            "source_layer": "direct_manual_extension",
        }

    base = assess_phonesuite_pms_record(payload)
    return {
        "qualified": base.qualified,
        "opcode": base.opcode,
        "family": base.family,
        "expected_format": base.expected_format,
        "evidence_class": base.evidence_class,
        "source_layer": "legacy_source_profile" if base.qualified else None,
    }


def _format_diagnostics(payload: bytes) -> list[dict[str, str]]:
    diagnostics = list(diagnose_phonesuite_pms_record_format(payload))
    diagnostics.extend(diagnose_phonesuite_pms_source_extension_format(payload))
    return [
        {
            "code": item.code,
            "severity": item.severity,
            "confidence": item.confidence,
            "evidence_class": item.evidence_class,
            "expected": item.expected,
            "corrective_action": item.corrective_action,
        }
        for item in diagnostics
    ]


def _wire_summary(
    item: Any,
    *,
    index: int,
    pms_capture_direction: str,
    assessment: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result = {
        "index": index,
        "endpoint_side": _endpoint_side(
            item,
            pms_capture_direction=pms_capture_direction,
        ),
        "capture_direction": _normalized_direction(item.direction),
        "wire_sha256": sha256(item.data).hexdigest(),
        "wire_length": len(item.data),
        "framing": item.framing,
        "control": item.control,
        "record_family": item.record_family,
        "record_code": item.record_code,
    }
    if assessment is not None:
        result.update(
            {
                "application_family": assessment.get("family"),
                "application_opcode": assessment.get("opcode"),
                "application_expected_format": assessment.get("expected_format"),
                "application_evidence_class": assessment.get("evidence_class"),
                "application_source_layer": assessment.get("source_layer"),
            }
        )
    return result


def _is_control(
    item: Any,
    *,
    endpoint_side: str,
    control: str,
    pms_capture_direction: str,
) -> bool:
    return (
        _endpoint_side(item, pms_capture_direction=pms_capture_direction)
        == endpoint_side
        and item.control == control
        and item.framing == "control"
    )


def analyze_phonesuite_pms_to_pbx_transactions(
    captures: Iterable[Any],
    *,
    transport: str,
    evidence_class: str,
    pms_capture_direction: str,
) -> dict[str, Any]:
    """Characterize the source-backed PhoneSuite PMS-to-PBX receive sequence.

    The direct PhoneSuite/Voiceware interface documentation qualifies the
    application/session sequence in both sender roles and gives PhoneSuite
    receive-side timing for PMS-originated transactions. This analyzer is
    deliberately bounded to the registered serial PMS_TO_PBX row and requires
    the caller to independently state which local capture direction represents
    PMS-originated traffic.

    Raw application payloads are never copied into the reusable report.
    """

    normalized_transport = _require_serial_transport(transport)
    normalized_evidence = _normalize_evidence_class(evidence_class)
    normalized_pms_direction = _require_pms_capture_direction(
        pms_capture_direction
    )
    observations = [observe_capture(item) for item in captures]

    assessments = [
        _application_assessment(item.payload)
        if item.payload and _endpoint_side(
            item,
            pms_capture_direction=normalized_pms_direction,
        )
        == "pms"
        else {
            "qualified": False,
            "opcode": None,
            "family": None,
            "expected_format": None,
            "evidence_class": None,
            "source_layer": None,
        }
        for item in observations
    ]

    strict_transactions: list[dict[str, Any]] = []
    matched_frame_indexes: set[int] = set()
    timing_assessed_count = 0
    timing_violation_count = 0
    format_error_count = 0
    peer_ack_count = 0
    peer_nak_count = 0
    qualified_success_count = 0
    findings: list[dict[str, Any]] = []

    checksum_variant_candidates: list[dict[str, Any]] = []
    incomplete_stx_candidates: list[dict[str, Any]] = []
    wrong_framing_records: list[dict[str, Any]] = []
    unqualified_records: list[dict[str, Any]] = []

    for index, item in enumerate(observations):
        if _endpoint_side(
            item,
            pms_capture_direction=normalized_pms_direction,
        ) != "pms":
            continue

        assessment = assessments[index]

        if item.framing == "stx_etx_bcc":
            checksum_variant_candidates.append(
                _wire_summary(
                    item,
                    index=index,
                    pms_capture_direction=normalized_pms_direction,
                    assessment=assessment,
                )
            )
            findings.append(
                {
                    "id": "phonesuite-pms-optional-checksum-variant-observed",
                    "severity": "info",
                    "confidence": "medium",
                    "summary": (
                        "A PMS-originated STX/ETX frame carried one trailing byte. "
                        "PhoneSuite documentation permits an optional checksum, but "
                        "the current evidence does not qualify its algorithm, byte "
                        "coverage, placement, or validation behavior."
                    ),
                    "indexes": [index],
                }
            )
            continue

        if item.data.startswith(b"\x02") and item.framing not in {
            "stx_etx",
            "stx_etx_bcc",
        }:
            incomplete_stx_candidates.append(
                _wire_summary(
                    item,
                    index=index,
                    pms_capture_direction=normalized_pms_direction,
                    assessment=assessment,
                )
            )
            findings.append(
                {
                    "id": "phonesuite-pms-stx-frame-not-terminated",
                    "severity": "warning",
                    "confidence": "high",
                    "summary": (
                        "A PMS-originated observation began with STX but was not "
                        "recognized as a complete STX/ETX frame. Preserve the "
                        "sanitized wire evidence and verify capture completeness "
                        "and the documented ETX receive deadline."
                    ),
                    "indexes": [index],
                }
            )
            continue

        if assessment["qualified"] and item.framing != "stx_etx":
            wrong_framing_records.append(
                _wire_summary(
                    item,
                    index=index,
                    pms_capture_direction=normalized_pms_direction,
                    assessment=assessment,
                )
            )
            findings.append(
                {
                    "id": "phonesuite-pms-application-framing-mismatch",
                    "severity": "warning",
                    "confidence": "high",
                    "summary": (
                        "A source-qualified PMS-to-PhoneSuite application record "
                        f"was observed with {item.framing} framing instead of the "
                        "documented STX/ETX application frame."
                    ),
                    "indexes": [index],
                }
            )
        elif (
            item.framing == "stx_etx"
            and item.payload
            and not assessment["qualified"]
        ):
            unqualified_records.append(
                _wire_summary(
                    item,
                    index=index,
                    pms_capture_direction=normalized_pms_direction,
                    assessment=assessment,
                )
            )

    for index in range(0, max(0, len(observations) - 3)):
        enq, grant, record, response = observations[index : index + 4]
        if not _is_control(
            enq,
            endpoint_side="pms",
            control="ENQ",
            pms_capture_direction=normalized_pms_direction,
        ):
            continue
        if not _is_control(
            grant,
            endpoint_side="pbx",
            control="ACK",
            pms_capture_direction=normalized_pms_direction,
        ):
            continue

        assessment = assessments[index + 2]
        if (
            _endpoint_side(
                record,
                pms_capture_direction=normalized_pms_direction,
            )
            != "pms"
            or record.framing != "stx_etx"
            or not assessment["qualified"]
        ):
            continue
        if not (
            _endpoint_side(
                response,
                pms_capture_direction=normalized_pms_direction,
            )
            == "pbx"
            and response.framing == "control"
            and response.control in {"ACK", "NAK"}
        ):
            continue

        format_diagnostics = _format_diagnostics(record.payload)
        format_valid = not format_diagnostics
        format_error_count += len(format_diagnostics)

        ack_to_frame_seconds = _elapsed_seconds(grant.timestamp, record.timestamp)
        within_stx_deadline: bool | None = None
        timing_findings: list[dict[str, str]] = []
        if ack_to_frame_seconds is not None:
            timing_assessed_count += 1
            within_stx_deadline = (
                ack_to_frame_seconds <= PHONESUITE_PMS_MAX_GAP_SECONDS
            )
            source_timing = diagnose_phonesuite_pms_receive_timing(
                enq_ack_to_stx_seconds=ack_to_frame_seconds
            )
            timing_findings = [
                {
                    "code": item.code,
                    "severity": item.severity,
                    "confidence": item.confidence,
                    "evidence_class": item.evidence_class,
                    "expected": item.expected,
                    "corrective_action": item.corrective_action,
                }
                for item in source_timing
            ]
            if timing_findings:
                timing_violation_count += len(timing_findings)

        outcome = "peer_ack" if response.control == "ACK" else "peer_nak"
        if response.control == "ACK":
            peer_ack_count += 1
        else:
            peer_nak_count += 1
            findings.append(
                {
                    "id": "phonesuite-pms-application-nak",
                    "severity": "warning",
                    "confidence": "high",
                    "summary": (
                        "PhoneSuite returned NAK after a source-qualified "
                        "PMS-originated transaction. Verify role/direction, framing, "
                        "field layout, receive timing, and any site-specific checksum "
                        "configuration; NAK alone does not prove a checksum fault."
                    ),
                    "indexes": [index, index + 1, index + 2, index + 3],
                }
            )

        if format_diagnostics:
            findings.append(
                {
                    "id": "phonesuite-pms-source-format-problem",
                    "severity": "warning",
                    "confidence": "high",
                    "summary": (
                        "A source-qualified PMS-to-PhoneSuite record family was "
                        "observed with one or more documented application-format "
                        "problems. Use the per-transaction diagnostic codes without "
                        "changing transport settings."
                    ),
                    "indexes": [index + 2],
                }
            )

        if timing_findings:
            findings.append(
                {
                    "id": "phonesuite-pms-stx-deadline-exceeded",
                    "severity": "warning",
                    "confidence": "high",
                    "summary": (
                        "Capture timestamps place the PMS STX-framed observation "
                        "more than 0.100 second after PhoneSuite's ACK. Confirm the "
                        "capture timestamp semantics and serial buffering before "
                        "treating this as field timing evidence."
                    ),
                    "indexes": [index + 1, index + 2],
                }
            )

        qualified_success = (
            response.control == "ACK"
            and format_valid
            and within_stx_deadline is not False
        )
        if qualified_success:
            qualified_success_count += 1

        transaction = {
            "enq": _wire_summary(
                enq,
                index=index,
                pms_capture_direction=normalized_pms_direction,
            ),
            "grant": _wire_summary(
                grant,
                index=index + 1,
                pms_capture_direction=normalized_pms_direction,
            ),
            "record": _wire_summary(
                record,
                index=index + 2,
                pms_capture_direction=normalized_pms_direction,
                assessment=assessment,
            ),
            "response": _wire_summary(
                response,
                index=index + 3,
                pms_capture_direction=normalized_pms_direction,
            ),
            "outcome": outcome,
            "format_valid": format_valid,
            "format_diagnostics": format_diagnostics,
            "ack_to_stx_observation_seconds": (
                round(ack_to_frame_seconds, 6)
                if ack_to_frame_seconds is not None
                else None
            ),
            "ack_to_stx_deadline_assessed": ack_to_frame_seconds is not None,
            "within_ack_to_stx_deadline": within_stx_deadline,
            "timing_diagnostics": timing_findings,
            "qualified_success": qualified_success,
            "confidence": "high",
        }
        strict_transactions.append(transaction)
        matched_frame_indexes.add(index + 2)

    unmatched_qualified_frames: list[dict[str, Any]] = []
    for index, item in enumerate(observations):
        assessment = assessments[index]
        if (
            _endpoint_side(
                item,
                pms_capture_direction=normalized_pms_direction,
            )
            == "pms"
            and item.framing == "stx_etx"
            and assessment["qualified"]
            and index not in matched_frame_indexes
        ):
            unmatched_qualified_frames.append(
                _wire_summary(
                    item,
                    index=index,
                    pms_capture_direction=normalized_pms_direction,
                    assessment=assessment,
                )
            )

    if unmatched_qualified_frames:
        findings.append(
            {
                "id": "phonesuite-pms-qualified-record-outside-exact-handshake",
                "severity": "info",
                "confidence": "high",
                "summary": (
                    "A source-qualified PMS-to-PhoneSuite frame was observed "
                    "outside the strict adjacent ENQ -> ACK -> frame -> ACK|NAK "
                    "sequence. Confirm capture completeness and endpoint roles "
                    "before changing the personality."
                ),
                "indexes": [
                    item["index"] for item in unmatched_qualified_frames[:6]
                ],
            }
        )

    if unqualified_records:
        findings.append(
            {
                "id": "phonesuite-pms-unqualified-record-observed",
                "severity": "info",
                "confidence": "high",
                "summary": (
                    "A PMS-originated STX/ETX application frame was not within the "
                    "current source-qualified PhoneSuite PMS-to-PBX record set. "
                    "Retain its sanitized digest as new evidence rather than "
                    "promoting semantics from another direction or PBX family."
                ),
                "indexes": [item["index"] for item in unqualified_records[:6]],
            }
        )

    source_qualified_frame_count = sum(
        1
        for index, item in enumerate(observations)
        if _endpoint_side(
            item,
            pms_capture_direction=normalized_pms_direction,
        )
        == "pms"
        and item.framing == "stx_etx"
        and assessments[index]["qualified"]
    )

    return {
        "schema_version": "1.0",
        "diagnostic_profile": "phonesuite_mitel1_serial_pms_to_pbx",
        "transport": normalized_transport,
        "evidence_class": normalized_evidence,
        "pms_capture_direction": normalized_pms_direction,
        "reference_contract": {
            "pbx_family": "PhoneSuite",
            "pbx_dialect": "MITEL 1-compatible",
            "transport": "serial",
            "pms_family": "legacy-hotel-pms",
            "pms_protocol": "mitel-hospitality",
            "direction": "PMS_TO_PBX",
            "qualified_sequence": (
                "PMS ENQ -> PhoneSuite ACK -> "
                "PMS STX/application/ETX -> PhoneSuite ACK|NAK"
            ),
            "phonesuite_ack_to_stx_max_seconds": PHONESUITE_PMS_MAX_GAP_SECONDS,
            "phonesuite_max_inter_character_gap_seconds": (
                PHONESUITE_PMS_MAX_GAP_SECONDS
            ),
            "optional_checksum_documented": True,
            "checksum_contract_qualified": False,
            "serial_defaults_qualified": False,
            "retry_policy_qualified": False,
            "reverse_direction_qualified_by_this_diagnostic": False,
            "capture_timestamp_semantics": (
                "ACK-to-next STX-framed capture observation only; aggregate "
                "capture items do not assess between-character timing"
            ),
        },
        "claim_policy": {
            "transport_inferred": False,
            "serial_defaults_inferred": False,
            "checksum_contract_inferred": False,
            "checksum_fault_inferred_from_nak": False,
            "retry_policy_inferred": False,
            "reverse_direction_inferred": False,
            "personality_switch_authorized": False,
            "compatibility_promotion_authorized": False,
            "raw_payloads_embedded": False,
            "guest_pii_allowed_in_report": False,
            "series2_station_programming_in_scope": False,
        },
        "capture_count": len(observations),
        "source_qualified_frame_count": source_qualified_frame_count,
        "strict_transaction_count": len(strict_transactions),
        "strict_transactions": strict_transactions,
        "peer_ack_count": peer_ack_count,
        "peer_nak_count": peer_nak_count,
        "qualified_success_count": qualified_success_count,
        "format_error_count": format_error_count,
        "timing_assessed_count": timing_assessed_count,
        "timing_violation_count": timing_violation_count,
        "between_character_timing_assessed": False,
        "checksum_variant_candidate_count": len(checksum_variant_candidates),
        "checksum_variant_candidates": checksum_variant_candidates,
        "incomplete_stx_candidate_count": len(incomplete_stx_candidates),
        "incomplete_stx_candidates": incomplete_stx_candidates,
        "wrong_framing_record_count": len(wrong_framing_records),
        "wrong_framing_records": wrong_framing_records,
        "unmatched_qualified_frame_count": len(unmatched_qualified_frames),
        "unmatched_qualified_frames": unmatched_qualified_frames,
        "unqualified_record_count": len(unqualified_records),
        "unqualified_records": unqualified_records,
        "findings": findings,
        "technician_actions": [
            "Independently confirm which local capture direction is PMS-originated before applying this direction-sensitive PhoneSuite diagnostic.",
            "Record the actual serial adapter/device, baud, data bits, parity, stop bits, and flow control; the source-backed application sequence does not establish universal PhoneSuite serial defaults.",
            "For PMS-to-PhoneSuite transactions, verify ENQ -> ACK -> STX/application/ETX -> ACK|NAK and, where trustworthy timestamps exist, STX within 0.100 second after the PhoneSuite ACK.",
            "Use byte-level timestamp evidence to assess the separate 0.100-second between-character rule; aggregate frame captures cannot prove that condition.",
            "If PhoneSuite returns NAK, verify framing, documented field layout, timing, and site checksum configuration; do not label NAK as a checksum failure without independent checksum evidence.",
            "Treat any checksum-bearing frame as a new evidence candidate until algorithm, byte coverage, placement, and validation behavior are independently qualified.",
            "Do not import Mitel TCP reconnect/timing behavior, Mitel frame-only retry counts, or Series2 TDMoE/PRI/Q.921/Q.931/0x0E station programming into this PMS application-protocol diagnostic.",
        ],
    }
