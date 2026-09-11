from __future__ import annotations

import re
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
_TRANSPORT = "serial"
_QUALIFIED_OPCODES = {"CHK0", "CHK1", "NAM2"}
_OPCODE_RE = re.compile(r"^([A-Z]+[0-9]*)")


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
            "transport must be serial for the evidence-qualified PhoneSuite MITEL 1-compatible row; "
            "do not infer a PhoneSuite TCP row from this diagnostic"
        )
    return normalized


def _normalize_direction(value: str) -> str:
    normalized = str(value).strip().lower().replace("-", "_")
    if normalized in {"rx", "pbx_to_emulator", "pbx_to_pms"}:
        return "pbx_to_emulator"
    if normalized in {"tx", "emulator_to_pbx", "pms_to_pbx"}:
        return "emulator_to_pbx"
    return normalized or "unknown"


def _record_opcode(item: Any) -> str | None:
    if item.record_family != "legacy_hotel" or not item.payload:
        return None
    text = item.payload.decode("latin-1", errors="replace").strip("\x00\r\n ").upper()
    match = _OPCODE_RE.match(text)
    return match.group(1) if match else None


def _wire_summary(item: Any, *, index: int) -> dict[str, Any]:
    return {
        "index": index,
        "direction": _normalize_direction(item.direction),
        "wire_sha256": sha256(item.data).hexdigest(),
        "wire_length": len(item.data),
        "framing": item.framing,
        "control": item.control,
        "record_family": item.record_family,
        "record_code": item.record_code,
        "record_opcode": _record_opcode(item),
    }


def _is_control(item: Any, *, direction: str, control: str) -> bool:
    return (
        _normalize_direction(item.direction) == direction
        and item.control == control
        and item.framing == "control"
    )


def _is_qualified_frame(item: Any) -> bool:
    return (
        _normalize_direction(item.direction) == "pbx_to_emulator"
        and item.framing == "stx_etx"
        and _record_opcode(item) in _QUALIFIED_OPCODES
    )


def analyze_phonesuite_serial_transactions(
    captures: Iterable[Any],
    *,
    transport: str,
    evidence_class: str,
) -> dict[str, Any]:
    """Characterize the bounded PhoneSuite serial PBX-to-PMS transaction sequence.

    The clean-room simulator fixture qualifies only the receive-side sequence
    ``PBX ENQ -> emulator ACK -> PBX STX/application/ETX -> emulator ACK`` for
    CHK0, CHK1, and NAM2 examples. This analyzer can retain deviations and new
    observations for technician review, but it does not infer serial settings,
    checksum semantics, retry policy, TCP behavior, or compatibility promotion.

    Raw application payloads are deliberately omitted from the reusable report.
    """

    normalized_transport = _require_serial_transport(transport)
    normalized_evidence = _normalize_evidence_class(evidence_class)
    observations = [observe_capture(item) for item in captures]

    exact_transactions: list[dict[str, Any]] = []
    accepted_transactions: list[dict[str, Any]] = []
    rejected_transactions: list[dict[str, Any]] = []
    framing_mismatches: list[dict[str, Any]] = []
    uncharacterized_records: list[dict[str, Any]] = []
    handshake_rejections: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    matched_frame_indexes: set[int] = set()

    for index, item in enumerate(observations):
        if _normalize_direction(item.direction) != "pbx_to_emulator":
            continue
        opcode = _record_opcode(item)
        if opcode in _QUALIFIED_OPCODES and item.framing != "stx_etx":
            summary = _wire_summary(item, index=index)
            framing_mismatches.append(summary)
            findings.append(
                {
                    "id": "phonesuite-serial-application-framing-mismatch",
                    "severity": "warning",
                    "confidence": "high",
                    "summary": (
                        f"PhoneSuite serial {opcode} was observed with {item.framing} framing; "
                        "the clean-room simulator evidence qualifies STX/ETX framing."
                    ),
                    "indexes": [index],
                }
            )
        elif item.record_family == "legacy_hotel" and opcode not in _QUALIFIED_OPCODES:
            uncharacterized_records.append(_wire_summary(item, index=index))

    for index in range(0, max(0, len(observations) - 3)):
        enq, grant, record, response = observations[index : index + 4]
        if not _is_control(enq, direction="pbx_to_emulator", control="ENQ"):
            continue
        if not _is_control(grant, direction="emulator_to_pbx", control="ACK"):
            continue
        if not _is_qualified_frame(record):
            continue
        if not (
            _normalize_direction(response.direction) == "emulator_to_pbx"
            and response.control in {"ACK", "NAK"}
            and response.framing == "control"
        ):
            continue

        transaction = {
            "enq": _wire_summary(enq, index=index),
            "grant": _wire_summary(grant, index=index + 1),
            "record": _wire_summary(record, index=index + 2),
            "response": _wire_summary(response, index=index + 3),
            "record_opcode": _record_opcode(record),
            "outcome": "accepted" if response.control == "ACK" else "rejected",
            "confidence": "high",
        }
        exact_transactions.append(transaction)
        matched_frame_indexes.add(index + 2)
        if response.control == "ACK":
            accepted_transactions.append(transaction)
        else:
            rejected_transactions.append(transaction)
            findings.append(
                {
                    "id": "phonesuite-serial-application-nak",
                    "severity": "warning",
                    "confidence": "high",
                    "summary": (
                        "The emulator returned NAK after an otherwise evidence-qualified "
                        "PhoneSuite serial application transaction. Preserve the exact frame "
                        "and inspect framing/field layout; this does not prove a checksum fault."
                    ),
                    "indexes": [index, index + 1, index + 2, index + 3],
                }
            )

    for index in range(0, max(0, len(observations) - 1)):
        enq, response = observations[index : index + 2]
        if (
            _is_control(enq, direction="pbx_to_emulator", control="ENQ")
            and _is_control(response, direction="emulator_to_pbx", control="NAK")
        ):
            summary = {
                "enq": _wire_summary(enq, index=index),
                "response": _wire_summary(response, index=index + 1),
                "confidence": "high",
            }
            handshake_rejections.append(summary)
            findings.append(
                {
                    "id": "phonesuite-serial-enq-rejected",
                    "severity": "warning",
                    "confidence": "high",
                    "summary": (
                        "An inbound PhoneSuite serial ENQ was answered with NAK. The qualified "
                        "simulator sequence answers ENQ with ACK before the framed record."
                    ),
                    "indexes": [index, index + 1],
                }
            )

    unmatched_qualified_frames: list[dict[str, Any]] = []
    for index, item in enumerate(observations):
        if _is_qualified_frame(item) and index not in matched_frame_indexes:
            unmatched_qualified_frames.append(_wire_summary(item, index=index))

    if unmatched_qualified_frames:
        findings.append(
            {
                "id": "phonesuite-serial-qualified-record-outside-exact-handshake",
                "severity": "info",
                "confidence": "high",
                "summary": (
                    "A characterized PhoneSuite CHK/NAM frame was observed outside the strict "
                    "adjacent ENQ -> ACK -> frame -> ACK|NAK sequence. Confirm capture "
                    "completeness and direction before changing the selected personality."
                ),
                "indexes": [item["index"] for item in unmatched_qualified_frames[:6]],
            }
        )

    if uncharacterized_records:
        findings.append(
            {
                "id": "phonesuite-serial-uncharacterized-record-observed",
                "severity": "info",
                "confidence": "high",
                "summary": (
                    "A recognizable legacy-hotel record outside the simulator-qualified "
                    "CHK0/CHK1/NAM2 set was observed. Retain it as new directional evidence; "
                    "do not promote its semantics from another PBX family."
                ),
                "indexes": [item["index"] for item in uncharacterized_records[:6]],
            }
        )

    return {
        "schema_version": "1.0",
        "diagnostic_profile": "phonesuite_mitel1_serial_pbx_to_pms",
        "transport": normalized_transport,
        "evidence_class": normalized_evidence,
        "reference_contract": {
            "pbx_family": "PhoneSuite",
            "pbx_dialect": "MITEL 1-compatible",
            "transport": "serial",
            "pms_family": "legacy-hotel-pms",
            "pms_protocol": "mitel-hospitality",
            "direction": "PBX_TO_PMS",
            "qualified_sequence": "ENQ -> ACK -> STX/application/ETX -> ACK",
            "qualified_opcodes": sorted(_QUALIFIED_OPCODES),
            "serial_defaults_qualified": False,
            "checksum_contract_qualified": False,
            "retry_policy_qualified": False,
            "tcp_behavior_qualified": False,
            "reverse_direction_qualified_by_this_diagnostic": False,
        },
        "claim_policy": {
            "transport_inferred": False,
            "serial_defaults_inferred": False,
            "checksum_fault_inferred_from_nak": False,
            "retry_policy_inferred": False,
            "broader_opcode_support_inferred": False,
            "reverse_direction_inferred": False,
            "personality_switch_authorized": False,
            "compatibility_promotion_authorized": False,
            "raw_payloads_embedded": False,
            "series2_station_programming_in_scope": False,
        },
        "capture_count": len(observations),
        "exact_transaction_count": len(exact_transactions),
        "exact_transactions": exact_transactions,
        "accepted_transaction_count": len(accepted_transactions),
        "rejected_transaction_count": len(rejected_transactions),
        "handshake_rejection_count": len(handshake_rejections),
        "handshake_rejections": handshake_rejections,
        "framing_mismatch_count": len(framing_mismatches),
        "framing_mismatches": framing_mismatches,
        "unmatched_qualified_frame_count": len(unmatched_qualified_frames),
        "unmatched_qualified_frames": unmatched_qualified_frames,
        "uncharacterized_record_count": len(uncharacterized_records),
        "uncharacterized_records": uncharacterized_records,
        "findings": findings,
        "technician_actions": [
            "Confirm the selected PBX personality is PhoneSuite MITEL 1-compatible, the transport is serial, and the observed direction is PBX-to-PMS before interpreting this sequence.",
            "Record the actual serial adapter/device plus baud, data bits, parity, stop bits, and flow control; this diagnostic does not supply PhoneSuite-specific defaults.",
            "For the simulator-qualified PBX-to-PMS path, verify ENQ -> ACK -> STX/ETX CHK0, CHK1, or NAM2 -> ACK before widening the characterization.",
            "If a framed application record receives NAK, verify framing and exact field layout and retain a sanitized capture; NAK alone does not prove checksum failure.",
            "Treat additional opcodes, retry behavior, optional checksum behavior, and the reverse direction as separate evidence questions tied to their exact matrix rows.",
            "Do not import Mitel TCP reconnect/timing assumptions or Series2 TDMoE/PRI/Q.921/Q.931/0x0E station-programming behavior into this PMS serial diagnostic.",
        ],
    }
