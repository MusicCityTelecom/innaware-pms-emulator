from __future__ import annotations

from typing import Any, Iterable

from .diagnostics import observe_capture
from .mitel_half_duplex_diagnostics import analyze_mitel_half_duplex_sequence


_ALLOWED_EVIDENCE_CLASSES = {
    "packet_capture",
    "operator_confirmed",
    "legacy_source_profile",
    "simulator_characterization",
    "inference",
}
_PMS_DIRECTIONS = {"rx", "tx"}
_SOURCE_QUALIFIED_PMS_RECORD_CODES = {"CHK", "NAM", "MW", "DND", "RST"}


def _normalize_choice(value: str, *, name: str, allowed: set[str]) -> str:
    normalized = str(value).strip().lower()
    if normalized not in allowed:
        raise ValueError(f"{name} must be one of: {', '.join(sorted(allowed))}")
    return normalized


def _relative_to_pms(captures: Iterable[Any], *, pms_direction: str) -> list[dict[str, Any]]:
    """Normalize a local capture so PMS-originated bytes are TX.

    The generic Mitel half-duplex analyzer is written from the sender/PMS
    viewpoint. A field capture can be taken at either endpoint, so endpoint
    direction must be supplied explicitly instead of guessed from opcodes.
    """

    opposite = "rx" if pms_direction == "tx" else "tx"
    normalized: list[dict[str, Any]] = []
    for item in captures:
        observation = observe_capture(item)
        if observation.direction == pms_direction:
            direction = "tx"
        elif observation.direction == opposite:
            direction = "rx"
        else:
            direction = observation.direction
        normalized.append(
            {
                "direction": direction,
                "data": observation.data,
                "timestamp": observation.timestamp,
                "peer": observation.peer,
                "note": observation.note,
            }
        )
    return normalized


def analyze_3cx_mitel_sx2000(
    captures: Iterable[Any],
    *,
    transport: str,
    evidence_class: str,
    pms_direction: str,
) -> dict[str, Any]:
    """Analyze the documented 3CX Mitel-SX2000 PMS-to-PBX transaction surface.

    This is deliberately a 3CX identity wrapper around the already bounded
    Mitel-compatible application transaction analyzer. It does not turn 3CX
    into a Mitel PBX, infer another transport, infer a universal site port, or
    qualify the reverse PBX-to-PMS direction.
    """

    normalized_transport = _normalize_choice(
        transport, name="transport", allowed={"tcp"}
    )
    normalized_evidence = _normalize_choice(
        evidence_class,
        name="evidence_class",
        allowed=_ALLOWED_EVIDENCE_CLASSES,
    )
    normalized_pms_direction = _normalize_choice(
        pms_direction,
        name="pms_direction",
        allowed=_PMS_DIRECTIONS,
    )

    relative = _relative_to_pms(captures, pms_direction=normalized_pms_direction)
    sequence = analyze_mitel_half_duplex_sequence(
        relative,
        transport=normalized_transport,
        evidence_class=normalized_evidence,
    )

    exact_transactions = sequence["exact_successful_transactions"]
    qualified = [
        item
        for item in exact_transactions
        if item.get("tx_record_family") == "legacy_hotel"
        and item.get("tx_record_code") in _SOURCE_QUALIFIED_PMS_RECORD_CODES
    ]
    unqualified = [item for item in exact_transactions if item not in qualified]

    findings = list(sequence["findings"])
    if unqualified:
        findings.append(
            {
                "id": "3cx-mitel-record-outside-source-qualified-pms-set",
                "severity": "warning",
                "confidence": "high",
                "summary": (
                    "A Mitel-compatible framed transaction was acknowledged by the peer, "
                    "but its application record code is outside the currently source-qualified "
                    "3CX PMS-to-system record set. Retain it as evidence; do not widen the 3CX row automatically."
                ),
                "transaction_count": len(unqualified),
            }
        )

    return {
        "schema_version": "1.0",
        "diagnostic_profile": "3cx_mitel_sx2000_pms_to_pbx",
        "combination": {
            "pbx_family": "3CX",
            "pbx_dialect": "Hotel Module / Mitel SX2000-compatible",
            "transport": "tcp",
            "pms_family": "legacy-hotel-pms",
            "pms_protocol": "mitel-hospitality",
            "direction": "pms_to_pbx",
        },
        "transport": normalized_transport,
        "evidence_class": normalized_evidence,
        "capture_pms_direction": normalized_pms_direction,
        "reference_contract": {
            "peer_role": "3CX Hotel Module server; PMS connects and sends messages",
            "application_sequence": "PMS ENQ -> 3CX ACK_or_NAK -> PMS STX/application/ETX -> 3CX ACK_or_NAK",
            "response_window_seconds": 3,
            "max_frame_only_retries_after_initial": 3,
            "retry_requires_new_enq": False,
            "qualified_pms_record_codes": sorted(_SOURCE_QUALIFIED_PMS_RECORD_CODES),
            "site_port_is_configured_not_universal": True,
            "billing_carried_by_this_pms_protocol": False,
            "scope": (
                "3CX Hotel Services Mitel SX2000-compatible PMS integration only. "
                "The separate 3CX Fidelio/FIAS and CDR/billing interfaces are out of scope."
            ),
        },
        "claim_policy": {
            "3cx_identity_preserved": True,
            "mitel_application_compatibility_is_not_pbx_identity": True,
            "transport_inferred": False,
            "site_port_inferred": False,
            "pbx_to_pms_support_inferred": False,
            "billing_or_cdr_transport_inferred": False,
            "personality_switch_authorized": False,
            "compatibility_promotion_authorized": False,
            "raw_payloads_embedded": False,
            "series2_station_programming_in_scope": False,
        },
        "source_qualified_success_count": len(qualified),
        "source_qualified_successes": qualified,
        "unqualified_mitel_record_success_count": len(unqualified),
        "unqualified_mitel_record_successes": unqualified,
        "application_frame_nak_count": sequence["application_frame_nak_count"],
        "handshake_nak_count": sequence["handshake_nak_count"],
        "frame_only_retry_count": sequence["frame_only_retry_count"],
        "frame_only_retries": sequence["frame_only_retries"],
        "findings": findings,
        "technician_actions": [
            "Confirm 3CX Hotel Services is configured for Mitel SX2000 and record the exact 3CX version/build under test.",
            "Record the actual 3CX Hotel Services address and site-configured port; do not substitute a lab or remembered port as a protocol default.",
            "Confirm which local capture direction is PMS-originated before interpreting ENQ/ACK transaction order.",
            "For PMS-to-3CX testing, send synthetic/redacted CHK/NAM/MW/DND/RST records only and retain exact wire SHA-256 evidence.",
            "Treat NAK as rejection evidence. Check STX/ETX framing, function/status code, field layout, and timing before assigning a cause.",
            "Keep 3CX CDR/billing and Fidelio/FIAS interfaces separate from this Mitel-SX2000 PMS application session.",
            "Do not promote the compatibility row from this report alone; exact endpoint/version and sanitized field evidence require separate review.",
        ],
    }
