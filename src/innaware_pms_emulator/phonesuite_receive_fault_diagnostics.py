from __future__ import annotations

from datetime import datetime
from hashlib import sha256
from typing import Any, Iterable

from .diagnostics import observe_capture
from .phonesuite_pms_policy import (
    PHONESUITE_PMS_MAX_GAP_SECONDS,
    diagnose_phonesuite_pms_record_format,
)

_ALLOWED_EVIDENCE_CLASSES = {
    "packet_capture",
    "operator_confirmed",
    "legacy_source_profile",
    "simulator_characterization",
    "inference",
}
_TRANSPORT = "serial"
_DOCUMENTED_INVALID_EXTENSION_NAK_FAMILIES = {"CHK", "DND", "MW"}


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
            "transport must be serial for the registered PhoneSuite "
            "MITEL 1-compatible PMS-to-PBX row; do not infer a PhoneSuite TCP row"
        )
    return normalized


def _require_pms_capture_direction(value: str) -> str:
    normalized = str(value).strip().lower().replace("-", "_")
    if normalized not in {"rx", "tx"}:
        raise ValueError(
            "pms_capture_direction must be rx or tx so endpoint roles are explicit"
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


def _wire_summary(
    item: Any,
    *,
    index: int,
    pms_capture_direction: str,
) -> dict[str, Any]:
    return {
        "index": index,
        "endpoint_side": _endpoint_side(
            item, pms_capture_direction=pms_capture_direction
        ),
        "capture_direction": _normalized_direction(item.direction),
        "wire_sha256": sha256(item.data).hexdigest(),
        "wire_length": len(item.data),
        "framing": item.framing,
        "control": item.control,
        "record_family": item.record_family,
        "record_code": item.record_code,
    }


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
        and item.framing == "control"
        and item.control == control
    )


def _safe_format_diagnostics(payload: bytes) -> list[dict[str, str]]:
    return [
        {
            "code": item.code,
            "severity": item.severity,
            "confidence": item.confidence,
            "evidence_class": item.evidence_class,
            "expected": item.expected,
            "corrective_action": item.corrective_action,
        }
        for item in diagnose_phonesuite_pms_record_format(payload)
    ]


def analyze_phonesuite_receive_faults(
    captures: Iterable[Any],
    *,
    transport: str,
    evidence_class: str,
    pms_capture_direction: str,
) -> dict[str, Any]:
    """Correlate source-backed PhoneSuite PMS receive faults without guessing cause.

    The PhoneSuite/Voiceware PMS Interface manual documents a 0.100-second
    receive deadline after PhoneSuite ACKs a PMS ENQ, NAK behavior for late
    non-ENQ data after that timeout, NAK behavior for an unterminated message,
    and NAK behavior for invalid extension numbers in selected command
    families. This analyzer reports only evidence that can be supported by the
    supplied capture granularity. Raw application payloads are never emitted.
    """

    normalized_transport = _require_serial_transport(transport)
    normalized_evidence = _normalize_evidence_class(evidence_class)
    normalized_pms_direction = _require_pms_capture_direction(
        pms_capture_direction
    )
    observations = [observe_capture(item) for item in captures]

    handshakes: list[dict[str, Any]] = []
    late_data_events: list[dict[str, Any]] = []
    incomplete_frame_events: list[dict[str, Any]] = []
    invalid_extension_nak_events: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []

    for index in range(max(0, len(observations) - 1)):
        enq = observations[index]
        grant = observations[index + 1]
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

        handshake: dict[str, Any] = {
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
            "next_observation": None,
            "ack_to_next_observation_seconds": None,
            "receive_deadline_assessed": False,
            "late_non_enq_data": False,
            "expected_late_data_response": None,
            "observed_response": None,
        }

        if index + 2 >= len(observations):
            handshake["state"] = "capture_ended_after_grant"
            handshakes.append(handshake)
            continue

        next_item = observations[index + 2]
        next_side = _endpoint_side(
            next_item, pms_capture_direction=normalized_pms_direction
        )
        handshake["next_observation"] = _wire_summary(
            next_item,
            index=index + 2,
            pms_capture_direction=normalized_pms_direction,
        )
        elapsed = _elapsed_seconds(grant.timestamp, next_item.timestamp)
        if elapsed is not None:
            handshake["receive_deadline_assessed"] = True
            handshake["ack_to_next_observation_seconds"] = round(elapsed, 6)

        if _is_control(
            next_item,
            endpoint_side="pms",
            control="ENQ",
            pms_capture_direction=normalized_pms_direction,
        ):
            handshake["state"] = "new_enq_started"
            handshakes.append(handshake)
            continue

        if (
            next_side == "pms"
            and elapsed is not None
            and elapsed > PHONESUITE_PMS_MAX_GAP_SECONDS
        ):
            response = observations[index + 3] if index + 3 < len(observations) else None
            response_control = None
            response_summary = None
            if response is not None and _endpoint_side(
                response, pms_capture_direction=normalized_pms_direction
            ) == "pbx":
                if response.framing == "control" and response.control in {"ACK", "NAK"}:
                    response_control = response.control
                    response_summary = _wire_summary(
                        response,
                        index=index + 3,
                        pms_capture_direction=normalized_pms_direction,
                    )

            event = {
                "grant_index": index + 1,
                "late_data": _wire_summary(
                    next_item,
                    index=index + 2,
                    pms_capture_direction=normalized_pms_direction,
                ),
                "ack_to_late_data_seconds": round(elapsed, 6),
                "documented_timeout_seconds": PHONESUITE_PMS_MAX_GAP_SECONDS,
                "expected_response": "NAK",
                "observed_response": response_summary,
                "response_consistent_with_source": response_control == "NAK",
            }
            late_data_events.append(event)
            handshake["state"] = "late_non_enq_data_after_timeout"
            handshake["late_non_enq_data"] = True
            handshake["expected_late_data_response"] = "NAK"
            handshake["observed_response"] = response_summary

            if response_control == "NAK":
                findings.append(
                    {
                        "id": "phonesuite-late-data-nak-source-consistent",
                        "severity": "info",
                        "confidence": "high",
                        "summary": (
                            "PhoneSuite NAK followed PMS data observed more than "
                            "0.100 second after the ENQ grant ACK. This is consistent "
                            "with the documented late-data-after-timeout behavior."
                        ),
                        "indexes": [index + 1, index + 2, index + 3],
                    }
                )
            elif response_control == "ACK":
                findings.append(
                    {
                        "id": "phonesuite-late-data-ack-source-deviation",
                        "severity": "warning",
                        "confidence": "high",
                        "summary": (
                            "PhoneSuite ACK was observed after PMS data arrived more "
                            "than 0.100 second after the ENQ grant ACK, while the "
                            "source documentation describes NAK for late non-ENQ data. "
                            "Verify capture timestamp semantics and buffering before "
                            "treating this as a device/protocol deviation."
                        ),
                        "indexes": [index + 1, index + 2, index + 3],
                    }
                )
            else:
                findings.append(
                    {
                        "id": "phonesuite-late-data-response-not-observed",
                        "severity": "info",
                        "confidence": "high",
                        "summary": (
                            "PMS data was observed more than 0.100 second after the "
                            "PhoneSuite ENQ grant ACK, but a directly adjacent "
                            "PhoneSuite ACK/NAK response was not captured."
                        ),
                        "indexes": [index + 1, index + 2],
                    }
                )
            handshakes.append(handshake)
            continue

        handshake["state"] = "within_observed_receive_window_or_unassessed"
        handshakes.append(handshake)

    for index, item in enumerate(observations):
        if _endpoint_side(
            item, pms_capture_direction=normalized_pms_direction
        ) != "pms":
            continue

        if item.data.startswith(b"\x02") and item.framing not in {
            "stx_etx",
            "stx_etx_bcc",
        }:
            response = observations[index + 1] if index + 1 < len(observations) else None
            response_is_nak = bool(
                response is not None
                and _is_control(
                    response,
                    endpoint_side="pbx",
                    control="NAK",
                    pms_capture_direction=normalized_pms_direction,
                )
            )
            event = {
                "frame": _wire_summary(
                    item,
                    index=index,
                    pms_capture_direction=normalized_pms_direction,
                ),
                "peer_nak_observed": response_is_nak,
                "peer_response": (
                    _wire_summary(
                        response,
                        index=index + 1,
                        pms_capture_direction=normalized_pms_direction,
                    )
                    if response_is_nak
                    else None
                ),
                "missing_etx_timing_assessed": False,
                "source_consistency": (
                    "consistent_with_documented_missing_etx_nak"
                    if response_is_nak
                    else "incomplete_frame_observed_without_adjacent_nak"
                ),
            }
            incomplete_frame_events.append(event)
            findings.append(
                {
                    "id": (
                        "phonesuite-incomplete-frame-nak-source-consistent"
                        if response_is_nak
                        else "phonesuite-incomplete-frame-observed"
                    ),
                    "severity": "warning",
                    "confidence": "medium" if response_is_nak else "high",
                    "summary": (
                        "A PMS-originated observation began with STX but had no "
                        "recognized ETX termination. "
                        + (
                            "The adjacent PhoneSuite NAK is consistent with the "
                            "documented missing-ETX condition, but aggregate capture "
                            "items do not prove the 0.100-second character timing."
                            if response_is_nak
                            else
                            "Preserve byte-level timing if available; aggregate "
                            "capture items cannot prove the documented 0.100-second "
                            "missing-ETX timeout."
                        )
                    ),
                    "indexes": [index] + ([index + 1] if response_is_nak else []),
                }
            )
            continue

        if item.framing != "stx_etx" or item.record_code not in {
            "CHK",
            "DND",
            "MW",
        }:
            continue

        format_diagnostics = _safe_format_diagnostics(item.payload)
        extension_errors = [
            diagnostic
            for diagnostic in format_diagnostics
            if diagnostic["code"] == "phonesuite_pms_extension_format_invalid"
        ]
        if not extension_errors:
            continue

        response = observations[index + 1] if index + 1 < len(observations) else None
        if response is None or not _is_control(
            response,
            endpoint_side="pbx",
            control="NAK",
            pms_capture_direction=normalized_pms_direction,
        ):
            continue

        event = {
            "record": _wire_summary(
                item,
                index=index,
                pms_capture_direction=normalized_pms_direction,
            ),
            "peer_nak": _wire_summary(
                response,
                index=index + 1,
                pms_capture_direction=normalized_pms_direction,
            ),
            "record_family": item.record_code,
            "safe_format_diagnostics": extension_errors,
            "source_consistency": "documented_invalid_extension_nak",
        }
        invalid_extension_nak_events.append(event)
        findings.append(
            {
                "id": "phonesuite-invalid-extension-nak-source-consistent",
                "severity": "warning",
                "confidence": "high",
                "summary": (
                    f"PhoneSuite NAK followed a {item.record_code} record with a "
                    "syntactically invalid 3/4-digit extension field. The source "
                    "documentation explicitly describes NAK for invalid extension "
                    "numbers in this command family."
                ),
                "indexes": [index, index + 1],
            }
        )

    return {
        "schema_version": "1.0",
        "diagnostic_profile": "phonesuite_serial_receive_faults",
        "transport": normalized_transport,
        "evidence_class": normalized_evidence,
        "pms_capture_direction": normalized_pms_direction,
        "combination": {
            "pbx_family": "PhoneSuite",
            "pbx_dialect": "MITEL 1-compatible",
            "transport": "serial",
            "pms_family": "legacy-hotel-pms",
            "pms_protocol": "mitel-hospitality",
            "direction": "pms_to_pbx",
        },
        "reference_contract": {
            "phonesuite_ack_to_next_pms_data_max_seconds": (
                PHONESUITE_PMS_MAX_GAP_SECONDS
            ),
            "late_non_enq_data_after_timeout_expected_response": "NAK",
            "missing_etx_expected_response": "NAK",
            "documented_invalid_extension_nak_families": sorted(
                _DOCUMENTED_INVALID_EXTENSION_NAK_FAMILIES
            ),
            "checksum_contract_qualified": False,
            "serial_defaults_qualified": False,
            "retry_policy_qualified": False,
            "byte_level_character_timing_required_for_inter_character_claims": True,
            "source_scope": (
                "PhoneSuite/Voiceware PMS Interface manual, PBX Interface basic "
                "message format and CHK/DND/MW command notes"
            ),
        },
        "claim_policy": {
            "transport_inferred": False,
            "checksum_fault_inferred_from_nak": False,
            "checksum_contract_inferred": False,
            "serial_defaults_inferred": False,
            "retry_policy_inferred": False,
            "between_character_timing_inferred": False,
            "personality_switch_authorized": False,
            "compatibility_promotion_authorized": False,
            "raw_payloads_embedded": False,
            "guest_pii_allowed_in_report": False,
            "series2_station_programming_in_scope": False,
        },
        "capture_count": len(observations),
        "enq_grant_handshake_count": len(handshakes),
        "enq_grant_handshakes": handshakes,
        "late_data_event_count": len(late_data_events),
        "late_data_events": late_data_events,
        "incomplete_frame_event_count": len(incomplete_frame_events),
        "incomplete_frame_events": incomplete_frame_events,
        "invalid_extension_nak_event_count": len(invalid_extension_nak_events),
        "invalid_extension_nak_events": invalid_extension_nak_events,
        "findings": findings,
        "technician_actions": [
            "Confirm which local capture direction is PMS-originated before interpreting the sequence.",
            "Record the actual serial adapter/device, baud, data bits, parity, stop bits, and flow control; this diagnostic does not infer site serial defaults.",
            "If PMS data follows a PhoneSuite ENQ grant ACK after more than 0.100 second, expect the documented timeout behavior and preserve the adjacent ACK/NAK plus trustworthy timestamps.",
            "For an STX observation without ETX, preserve byte-level timestamps before asserting the documented 0.100-second missing-ETX or between-character timeout.",
            "For CHK, DND, and MW NAKs, verify the room/extension field is syntactically 3 or 4 decimal digits and separately confirm that the extension exists at the property.",
            "Do not label a NAK as a checksum fault unless independent evidence establishes the site's checksum algorithm, coverage, placement, and verification behavior.",
            "Do not import Mitel TCP reconnect behavior, Mitel frame retry counts, or Series2 TDMoE/PRI/Q.921/Q.931/0x0E station programming into this PhoneSuite PMS application diagnostic.",
        ],
    }
