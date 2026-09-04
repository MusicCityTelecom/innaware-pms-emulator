from __future__ import annotations

from hashlib import sha256
from typing import Any, Iterable

from .diagnostics import observe_capture


_ALLOWED_EVIDENCE_CLASSES = {
    "packet_capture",
    "operator_confirmed",
    "legacy_source_profile",
    "simulator_characterization",
    "inference",
}
_MATRIX_TRANSPORT = "tcp"
_GUEST_EVENT_CODES = {"GI", "GO", "GC"}


def _normalize_evidence_class(value: str) -> str:
    normalized = str(value).strip().lower()
    if normalized not in _ALLOWED_EVIDENCE_CLASSES:
        raise ValueError(
            "evidence_class must be one of: "
            + ", ".join(sorted(_ALLOWED_EVIDENCE_CLASSES))
        )
    return normalized


def _require_tcp_transport(value: str) -> str:
    normalized = str(value).strip().lower()
    if normalized != _MATRIX_TRANSPORT:
        raise ValueError(
            "transport must be tcp for the evidence-qualified Matrix MICROS Opera/FIAS row; "
            "do not infer or test a Matrix serial row from this diagnostic"
        )
    return normalized


def _wire_summary(item: Any, *, index: int) -> dict[str, Any]:
    return {
        "index": index,
        "direction": item.direction,
        "wire_sha256": sha256(item.data).hexdigest(),
        "wire_length": len(item.data),
        "framing": item.framing,
        "record_family": item.record_family,
        "record_code": item.record_code,
    }


def analyze_matrix_fias_link_start(
    captures: Iterable[Any],
    *,
    transport: str,
    evidence_class: str,
) -> dict[str, Any]:
    """Characterize the evidence-bounded Matrix MICROS Opera/FIAS link start.

    Project evidence qualifies one narrow behavior: a Matrix SARVAM UCS PBX initiated
    TCP toward a PMS operating in MICROS Opera/FIAS mode and sent an ``LS`` record in
    STX/ETX framing. The analyzer can preserve newly observed post-LS facts for review,
    but it never promotes those observations into compatibility claims automatically.

    Raw payload bytes are deliberately omitted from the reusable report.
    """

    normalized_transport = _require_tcp_transport(transport)
    normalized_evidence = _normalize_evidence_class(evidence_class)
    observations = [observe_capture(item) for item in captures]

    inbound_ls: list[dict[str, Any]] = []
    outbound_ls: list[dict[str, Any]] = []
    exact_pairs: list[dict[str, Any]] = []
    framing_mismatches: list[dict[str, Any]] = []
    post_ls_progression: list[dict[str, Any]] = []
    control_handshake_observations: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []

    first_inbound_ls_index: int | None = None

    for index, item in enumerate(observations):
        if item.record_family == "fias" and item.record_code == "LS":
            summary = _wire_summary(item, index=index)
            if item.direction == "rx":
                inbound_ls.append(summary)
                if first_inbound_ls_index is None:
                    first_inbound_ls_index = index
                if item.framing != "stx_etx":
                    framing_mismatches.append(summary)
                    findings.append(
                        {
                            "id": "matrix-inbound-ls-framing-mismatch",
                            "severity": "warning",
                            "confidence": "high",
                            "summary": (
                                "Inbound Matrix/FIAS LS was not STX/ETX framed. The qualified "
                                "field observation used STX/ETX framing."
                            ),
                            "indexes": [index],
                        }
                    )
            elif item.direction == "tx":
                outbound_ls.append(summary)
                if item.framing != "stx_etx":
                    framing_mismatches.append(summary)
                    findings.append(
                        {
                            "id": "matrix-outbound-ls-framing-mismatch",
                            "severity": "warning",
                            "confidence": "high",
                            "summary": (
                                "Outbound FIAS LS reply was not STX/ETX framed. Keep the "
                                "application FIAS reply separate from TCP transport details."
                            ),
                            "indexes": [index],
                        }
                    )

        if first_inbound_ls_index is not None and index > first_inbound_ls_index:
            if item.control in {"ENQ", "ACK", "NAK"}:
                control_handshake_observations.append(_wire_summary(item, index=index))
            if (
                item.record_family == "fias"
                and item.record_code is not None
                and item.record_code != "LS"
            ):
                post_ls_progression.append(_wire_summary(item, index=index))

    for index in range(0, max(0, len(observations) - 1)):
        request, reply = observations[index : index + 2]
        if not (
            request.direction == "rx"
            and request.record_family == "fias"
            and request.record_code == "LS"
            and request.framing == "stx_etx"
            and reply.direction == "tx"
            and reply.record_family == "fias"
            and reply.record_code == "LS"
            and reply.framing == "stx_etx"
        ):
            continue
        exact_pairs.append(
            {
                "request": _wire_summary(request, index=index),
                "reply": _wire_summary(reply, index=index + 1),
                "confidence": "high",
            }
        )

    if inbound_ls and not exact_pairs:
        findings.append(
            {
                "id": "matrix-ls-reply-not-observed-adjacent",
                "severity": "info",
                "confidence": "medium",
                "summary": (
                    "An inbound Matrix/FIAS LS was observed without an immediately adjacent "
                    "STX/ETX LS reply. Confirm capture completeness before diagnosing link "
                    "progression or timing."
                ),
                "indexes": [item["index"] for item in inbound_ls[:3]],
            }
        )

    if control_handshake_observations:
        findings.append(
            {
                "id": "matrix-unqualified-control-handshake-observed",
                "severity": "info",
                "confidence": "high",
                "summary": (
                    "ENQ/ACK/NAK control bytes were observed after Matrix/FIAS LS. Current "
                    "Matrix evidence does not qualify such a control handshake; retain this "
                    "as new evidence instead of changing the profile automatically."
                ),
                "indexes": [item["index"] for item in control_handshake_observations[:6]],
            }
        )

    if post_ls_progression:
        findings.append(
            {
                "id": "matrix-post-ls-progression-observed",
                "severity": "info",
                "confidence": "high",
                "summary": (
                    "Recognizable FIAS records were observed after link start. These records "
                    "are evidence-expansion candidates, not automatic Matrix compatibility "
                    "promotion."
                ),
                "indexes": [item["index"] for item in post_ls_progression[:6]],
            }
        )

    guest_event_candidates = [
        item for item in post_ls_progression if item["record_code"] in _GUEST_EVENT_CODES
    ]

    return {
        "schema_version": "1.0",
        "diagnostic_profile": "matrix_micros_opera_fias_link_start",
        "transport": normalized_transport,
        "evidence_class": normalized_evidence,
        "reference_contract": {
            "pbx_family": "Matrix",
            "pbx_dialect": "MICROS Opera / FIAS",
            "transport": "tcp",
            "pms_family": "Oracle/MICROS Opera",
            "pms_protocol": "FIAS",
            "direction": "PBX_TO_PMS",
            "qualified_observation": "PBX-initiated TCP carried inbound STX/ETX-framed FIAS LS",
            "qualified_framing": "stx_etx",
            "post_ls_progression_qualified": False,
            "retry_timing_qualified": False,
            "control_handshake_qualified": False,
            "guest_events_qualified": False,
            "reverse_direction_qualified": False,
            "site_port_is_protocol_constant": False,
        },
        "claim_policy": {
            "transport_inferred": False,
            "serial_variant_inferred": False,
            "tcp_port_inferred": False,
            "control_handshake_inferred": False,
            "guest_event_support_inferred": False,
            "reverse_direction_inferred": False,
            "personality_switch_authorized": False,
            "compatibility_promotion_authorized": False,
            "raw_payloads_embedded": False,
            "series2_station_programming_in_scope": False,
        },
        "capture_count": len(observations),
        "inbound_ls_count": len(inbound_ls),
        "inbound_ls": inbound_ls,
        "outbound_ls_count": len(outbound_ls),
        "outbound_ls": outbound_ls,
        "exact_link_start_pair_count": len(exact_pairs),
        "exact_link_start_pairs": exact_pairs,
        "framing_mismatch_count": len(framing_mismatches),
        "framing_mismatches": framing_mismatches,
        "control_handshake_observation_count": len(control_handshake_observations),
        "control_handshake_observations": control_handshake_observations,
        "post_ls_progression_count": len(post_ls_progression),
        "post_ls_progression": post_ls_progression,
        "guest_event_candidate_count": len(guest_event_candidates),
        "guest_event_candidates": guest_event_candidates,
        "findings": findings,
        "technician_actions": [
            "Confirm the selected personality is Matrix MICROS Opera/FIAS and the transport is TCP; do not substitute a serial profile based on application framing.",
            "Record which endpoint initiated TCP plus both endpoint addresses and the actual site port; do not treat the observed site port as a universal Matrix constant.",
            "Verify inbound and outbound LS records use STX/ETX framing and are not CR/LF-delimited.",
            "If records appear after LS, preserve a sanitized timestamped capture and exact endpoint/product versions so progression can be reviewed as new evidence.",
            "If ENQ/ACK/NAK appears, preserve it as separate evidence; the current Matrix field observation does not qualify a control-character handshake.",
            "Do not promote guest-event or reverse-direction support until those exact six-dimensional combinations have evidence and deterministic fixtures.",
        ],
    }
