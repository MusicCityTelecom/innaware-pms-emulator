from __future__ import annotations

from hashlib import sha256
from typing import Any, Iterable

from .diagnostics import observe_capture


_ALLOWED_TRANSPORTS = {"tcp", "serial", "unknown"}
_ALLOWED_EVIDENCE_CLASSES = {
    "packet_capture",
    "operator_confirmed",
    "legacy_source_profile",
    "simulator_characterization",
    "inference",
}
_APPLICATION_FRAMINGS = {"stx_etx", "stx_etx_bcc"}
_REFERENCE_MAX_RECORD_RETRIES = 3
_REFERENCE_TOTAL_RECORD_TRANSMISSIONS = 4
_REFERENCE_ACK_NAK_WINDOW_SECONDS = 3


def _normalize_choice(value: str, *, name: str, allowed: set[str]) -> str:
    normalized = str(value).strip().lower()
    if normalized not in allowed:
        raise ValueError(f"{name} must be one of: {', '.join(sorted(allowed))}")
    return normalized


def _is_outbound_application_frame(item: Any) -> bool:
    return (
        item.direction == "tx"
        and item.framing in _APPLICATION_FRAMINGS
        and bool(item.data)
    )


def _frame_summary(item: Any, *, index: int) -> dict[str, Any]:
    return {
        "tx_index": index,
        "tx_sha256": sha256(item.data).hexdigest(),
        "tx_length": len(item.data),
        "tx_framing": item.framing,
        "tx_record_family": item.record_family,
        "tx_record_code": item.record_code,
    }


def _canonical_successes(observations: list[Any]) -> list[dict[str, Any]]:
    """Return only strict adjacent ENQ/ACK/frame/ACK successes.

    This intentionally avoids inferring success through unrelated or missing capture
    elements. The result is therefore a high-confidence lower bound, not a complete
    transaction reconstruction engine.
    """

    successes: list[dict[str, Any]] = []
    for index in range(0, max(0, len(observations) - 3)):
        enq, enq_ack, frame, frame_ack = observations[index : index + 4]
        if not (
            enq.direction == "tx"
            and enq.control == "ENQ"
            and enq_ack.direction == "rx"
            and enq_ack.control == "ACK"
            and _is_outbound_application_frame(frame)
            and frame_ack.direction == "rx"
            and frame_ack.control == "ACK"
        ):
            continue
        summary = _frame_summary(frame, index=index + 2)
        successes.append(
            {
                "enq_index": index,
                "enq_ack_index": index + 1,
                "frame_ack_index": index + 3,
                **summary,
            }
        )
    return successes


def _transport_actions(transport: str) -> list[str]:
    if transport == "serial":
        return [
            "Record the actual serial adapter/device, baud, data bits, parity, stop bits, and flow control with the capture; this application sequence does not establish serial defaults.",
            "Do not import TCP reconnect or stream behavior into the serial diagnosis.",
        ]
    if transport == "tcp":
        return [
            "Record the actual TCP endpoint roles, addresses, and site port with the capture; the observed port is not a universal Mitel protocol constant.",
            "Evaluate TCP stream fragmentation/coalescing and reconnect state separately from this application transaction sequence.",
        ]
    return [
        "Resolve transport from independent evidence before giving transport-specific corrective advice.",
        "Do not infer serial or TCP from the ENQ/ACK/STX/ETX application sequence alone.",
    ]


def analyze_mitel_half_duplex_sequence(
    captures: Iterable[Any],
    *,
    transport: str,
    evidence_class: str,
) -> dict[str, Any]:
    """Characterize Mitel-compatible half-duplex transaction/retry sequences.

    The reference behavior is evidence-bounded to the Mitel-compatible hotel PMS
    profile documented in project Sources: ENQ -> ACK -> framed record -> ACK/NAK,
    with up to three frame-only retries after an application-frame rejection. This
    analyzer does not apply those values as universal Mitel model/transport rules.

    Raw payload bytes are never emitted. Outbound application frames are represented
    by SHA-256, length, framing, and parser metadata only.
    """

    normalized_transport = _normalize_choice(
        transport, name="transport", allowed=_ALLOWED_TRANSPORTS
    )
    normalized_evidence = _normalize_choice(
        evidence_class,
        name="evidence_class",
        allowed=_ALLOWED_EVIDENCE_CLASSES,
    )
    observations = [observe_capture(item) for item in captures]

    retry_events: list[dict[str, Any]] = []
    enq_reissue_events: list[dict[str, Any]] = []
    changed_frame_events: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    frame_nak_count = 0
    handshake_nak_count = 0
    uncorrelated_nak_count = 0

    current_frame: dict[str, Any] | None = None
    rejected_frame: dict[str, Any] | None = None
    awaiting_frame_retry = False
    last_frame_nak_index: int | None = None

    for index, item in enumerate(observations):
        if item.direction == "rx" and item.control == "NAK":
            previous = observations[index - 1] if index > 0 else None
            if previous is not None and _is_outbound_application_frame(previous):
                frame_nak_count += 1
                if current_frame is None or current_frame["tx_index"] != index - 1:
                    current_frame = {
                        **_frame_summary(previous, index=index - 1),
                        "transmissions": 1,
                    }
                rejected_frame = dict(current_frame)
                awaiting_frame_retry = True
                last_frame_nak_index = index
            elif (
                previous is not None
                and previous.direction == "tx"
                and previous.control == "ENQ"
            ):
                handshake_nak_count += 1
                current_frame = None
                rejected_frame = None
                awaiting_frame_retry = False
                last_frame_nak_index = None
            else:
                uncorrelated_nak_count += 1
                current_frame = None
                rejected_frame = None
                awaiting_frame_retry = False
                last_frame_nak_index = None
            continue

        if item.direction == "tx" and item.control == "ENQ":
            if awaiting_frame_retry and rejected_frame is not None:
                event = {
                    "nak_index": last_frame_nak_index,
                    "enq_index": index,
                    "rejected_tx_sha256": rejected_frame["tx_sha256"],
                    "rejected_tx_index": rejected_frame["tx_index"],
                    "confidence": "high",
                }
                enq_reissue_events.append(event)
                findings.append(
                    {
                        "id": "enq-reissued-before-record-retry",
                        "severity": "warning",
                        "confidence": "high",
                        "summary": (
                            "A new outbound ENQ followed an application-frame NAK before a "
                            "frame-only retry. This differs from the selected Mitel-compatible "
                            "reference behavior, which retries the framed record without ENQ."
                        ),
                        "indexes": [last_frame_nak_index, index],
                        "tx_sha256": rejected_frame["tx_sha256"],
                    }
                )
            current_frame = None
            rejected_frame = None
            awaiting_frame_retry = False
            last_frame_nak_index = None
            continue

        if _is_outbound_application_frame(item):
            summary = _frame_summary(item, index=index)
            if awaiting_frame_retry and rejected_frame is not None:
                if summary["tx_sha256"] == rejected_frame["tx_sha256"]:
                    transmissions = int(rejected_frame["transmissions"]) + 1
                    retry_ordinal = transmissions - 1
                    event = {
                        "nak_index": last_frame_nak_index,
                        "retry_tx_index": index,
                        "tx_sha256": summary["tx_sha256"],
                        "retry_ordinal": retry_ordinal,
                        "total_record_transmissions": transmissions,
                        "within_reference_retry_limit": (
                            retry_ordinal <= _REFERENCE_MAX_RECORD_RETRIES
                        ),
                        "new_enq_before_retry": False,
                        "confidence": "high",
                    }
                    retry_events.append(event)
                    current_frame = {**summary, "transmissions": transmissions}
                    if retry_ordinal > _REFERENCE_MAX_RECORD_RETRIES:
                        findings.append(
                            {
                                "id": "record-retry-limit-exceeded",
                                "severity": "warning",
                                "confidence": "high",
                                "summary": (
                                    "The same framed record was transmitted more than four "
                                    "times in one rejection chain. That exceeds the selected "
                                    "Mitel-compatible reference of the initial send plus three "
                                    "frame-only retries."
                                ),
                                "indexes": [last_frame_nak_index, index],
                                "tx_sha256": summary["tx_sha256"],
                                "total_record_transmissions": transmissions,
                            }
                        )
                else:
                    event = {
                        "nak_index": last_frame_nak_index,
                        "replacement_tx_index": index,
                        "rejected_tx_sha256": rejected_frame["tx_sha256"],
                        "replacement_tx_sha256": summary["tx_sha256"],
                        "confidence": "medium",
                    }
                    changed_frame_events.append(event)
                    findings.append(
                        {
                            "id": "frame-changed-after-nak-without-enq",
                            "severity": "warning",
                            "confidence": "medium",
                            "summary": (
                                "A different framed record followed an application-frame NAK "
                                "without a new ENQ. Confirm capture completeness and transaction "
                                "boundaries before treating this as a retry or protocol fault."
                            ),
                            "indexes": [last_frame_nak_index, index],
                            "rejected_tx_sha256": rejected_frame["tx_sha256"],
                            "replacement_tx_sha256": summary["tx_sha256"],
                        }
                    )
                    current_frame = {**summary, "transmissions": 1}
            else:
                current_frame = {**summary, "transmissions": 1}
            rejected_frame = None
            awaiting_frame_retry = False
            last_frame_nak_index = None
            continue

        if item.direction == "rx" and item.control == "ACK":
            if current_frame is not None and current_frame["tx_index"] == index - 1:
                current_frame = None
            rejected_frame = None
            awaiting_frame_retry = False
            last_frame_nak_index = None
            continue

        if item.direction == "rx" and (
            item.control == "ENQ" or item.record_code is not None
        ):
            current_frame = None
            rejected_frame = None
            awaiting_frame_retry = False
            last_frame_nak_index = None

    successes = _canonical_successes(observations)
    return {
        "schema_version": "1.0",
        "diagnostic_profile": "mitel_compatible_half_duplex",
        "transport": normalized_transport,
        "evidence_class": normalized_evidence,
        "reference_contract": {
            "application_sequence": "TX ENQ -> RX ACK -> TX STX/application/ETX -> RX ACK_or_NAK",
            "ack_nak_window_seconds": _REFERENCE_ACK_NAK_WINDOW_SECONDS,
            "max_record_retries_after_initial": _REFERENCE_MAX_RECORD_RETRIES,
            "max_total_record_transmissions": _REFERENCE_TOTAL_RECORD_TRANSMISSIONS,
            "record_retry_requires_new_enq": False,
            "timing_assessed_by_this_analyzer": False,
            "scope": (
                "Mitel-compatible hotel PMS application/session profile evidence only; "
                "not a universal Mitel model, firmware, serial, or TCP contract."
            ),
        },
        "claim_policy": {
            "transport_inferred": False,
            "serial_defaults_inferred": False,
            "tcp_port_inferred": False,
            "personality_switch_authorized": False,
            "compatibility_promotion_authorized": False,
            "raw_payloads_embedded": False,
            "series2_station_programming_in_scope": False,
        },
        "capture_count": len(observations),
        "exact_successful_transaction_count": len(successes),
        "exact_successful_transactions": successes,
        "application_frame_nak_count": frame_nak_count,
        "handshake_nak_count": handshake_nak_count,
        "uncorrelated_nak_count": uncorrelated_nak_count,
        "frame_only_retry_count": len(retry_events),
        "frame_only_retries": retry_events,
        "enq_reissue_after_frame_nak_count": len(enq_reissue_events),
        "enq_reissue_after_frame_nak": enq_reissue_events,
        "changed_frame_after_nak_without_enq_count": len(changed_frame_events),
        "changed_frame_after_nak_without_enq": changed_frame_events,
        "findings": findings,
        "technician_actions": [
            "Use this report to characterize the selected Mitel-compatible transaction profile; do not silently switch personality or transport.",
            "For timing conclusions, use a timestamped capture and qualify the three-second window against the exact PBX/PMS model, firmware/version, and transport under test.",
            "A NAK proves rejection of a transaction, not the cause; compare framing, record layout, documented checksum behavior, and sequence one variable at a time.",
            *_transport_actions(normalized_transport),
        ],
    }
