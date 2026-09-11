from __future__ import annotations

import hashlib
from typing import Any, Iterable

STX = 0x02
ETX = 0x03
ACK = 0x06
NAK = 0x15

_EVIDENCE_CLASSES = {
    "packet_capture",
    "operator_confirmed",
    "legacy_source_profile",
    "simulator_characterization",
    "inference",
}

# Historical operator-confirmed Matrix SARVAM/FIAS runtime evidence retained outside
# Git showed this exact field-identifier shape on one PMS-originated GI record. The
# values themselves are deliberately not retained here or in committed fixtures.
_OBSERVED_GI_FIELD_IDENTIFIERS = (
    "RN",
    "G#",
    "GN",
    "GL",
    "GV",
    "CS",
    "GA",
    "GD",
    "GS",
)


def _capture_bytes(item: object) -> bytes:
    if isinstance(item, dict):
        data = item.get("data")
        if isinstance(data, bytes):
            return data
        if isinstance(data, bytearray):
            return bytes(data)
        raw_hex = item.get("hex")
        if isinstance(raw_hex, str) and raw_hex.strip():
            try:
                return bytes.fromhex(raw_hex)
            except ValueError as exc:
                raise ValueError("capture hex is not valid hexadecimal") from exc
        text = item.get("text")
        if isinstance(text, str):
            return text.encode("latin-1", errors="replace")
        return b""
    data = getattr(item, "data", b"")
    if isinstance(data, bytes):
        return data
    if isinstance(data, bytearray):
        return bytes(data)
    return b""


def _capture_value(item: object, name: str, default: Any = None) -> Any:
    if isinstance(item, dict):
        return item.get(name, default)
    return getattr(item, name, default)


def _frame_payload(data: bytes) -> tuple[str, bytes]:
    if len(data) >= 2 and data[0] == STX and data[-1] == ETX:
        return "stx_etx", data[1:-1]
    if data.endswith(b"\r\n"):
        return "crlf", data[:-2]
    if data.endswith(b"\r"):
        return "cr", data[:-1]
    if data.endswith(b"\n"):
        return "lf", data[:-1]
    return "raw", data


def _field_identifier(token: str) -> str | None:
    if len(token) < 2:
        return None
    candidate = token[:2].upper()
    if not all(char.isalnum() or char == "#" for char in candidate):
        return None
    return candidate


def _classify_application(data: bytes) -> tuple[str, str | None, list[str]]:
    framing, payload = _frame_payload(data)
    text = payload.decode("latin-1", errors="replace").strip("\x00\r\n ")
    if len(text) < 3 or text[2] != "|":
        return framing, None, []
    code = text[:2].upper()
    if not code.isalnum():
        return framing, None, []

    identifiers: list[str] = []
    for token in text.split("|")[1:]:
        identifier = _field_identifier(token)
        if identifier is not None:
            identifiers.append(identifier)
    return framing, code, identifiers


def _observation(
    *,
    capture_index: int,
    direction: str,
    endpoint_role: str,
    data: bytes,
) -> dict[str, Any] | None:
    if data == bytes((ACK,)):
        return {
            "capture_index": capture_index,
            "direction": direction,
            "endpoint_role": endpoint_role,
            "kind": "control",
            "control_code": "ACK",
            "wire_length": 1,
            "wire_sha256": hashlib.sha256(data).hexdigest(),
        }
    if data == bytes((NAK,)):
        return {
            "capture_index": capture_index,
            "direction": direction,
            "endpoint_role": endpoint_role,
            "kind": "control",
            "control_code": "NAK",
            "wire_length": 1,
            "wire_sha256": hashlib.sha256(data).hexdigest(),
        }

    framing, code, field_identifiers = _classify_application(data)
    if code is None:
        return None
    return {
        "capture_index": capture_index,
        "direction": direction,
        "endpoint_role": endpoint_role,
        "kind": "application",
        "framing": framing,
        "record_code": code,
        "field_identifiers": field_identifiers,
        "wire_length": len(data),
        "wire_sha256": hashlib.sha256(data).hexdigest(),
    }


def analyze_matrix_fias_pms_to_pbx_candidate(
    captures: Iterable[object],
    *,
    transport: str,
    pms_direction: str,
    evidence_class: str,
) -> dict[str, Any]:
    """Characterize a narrow Matrix/FIAS PMS-to-PBX GI candidate transaction.

    This is a pre-admission diagnostic, not a compatibility-registry mutation. It
    preserves a historical operator-confirmed observation that a Matrix SARVAM UCS
    FIAS session accepted one PMS-originated STX/ETX GI record with a single-byte ACK.
    Because that historical runtime evidence predates the current Emulator exact SHA,
    the result deliberately cannot authorize a Matrix PMS_TO_PBX compatibility row.

    Transport, application personality, direction, and evidence provenance remain
    independent. No serial behavior, site port, ACK timing, retry policy, checksum/LRC
    contract, other FIAS record type, or broader Matrix model is inferred.
    """

    normalized_transport = transport.strip().lower()
    if normalized_transport != "tcp":
        raise ValueError(
            "Matrix MICROS Opera PMS-to-PBX candidate diagnostics are qualified only for TCP"
        )

    normalized_direction = pms_direction.strip().lower()
    if normalized_direction not in {"rx", "tx"}:
        raise ValueError("pms_direction must be 'rx' or 'tx'")

    normalized_evidence = evidence_class.strip().lower()
    if normalized_evidence not in _EVIDENCE_CLASSES:
        raise ValueError("unsupported evidence_class")

    pbx_direction = "tx" if normalized_direction == "rx" else "rx"
    observations: list[dict[str, Any]] = []
    for index, item in enumerate(captures):
        direction = str(_capture_value(item, "direction", "unknown")).strip().lower()
        endpoint_role = (
            "pms"
            if direction == normalized_direction
            else "pbx"
            if direction == pbx_direction
            else "unknown"
        )
        observation = _observation(
            capture_index=index,
            direction=direction,
            endpoint_role=endpoint_role,
            data=_capture_bytes(item),
        )
        if observation is not None:
            observations.append(observation)

    gi_events: list[dict[str, Any]] = []
    for position, item in enumerate(observations):
        if not (
            item["endpoint_role"] == "pms"
            and item["kind"] == "application"
            and item["record_code"] == "GI"
        ):
            continue

        response: dict[str, Any] | None = None
        for later in observations[position + 1 :]:
            # Never pair an ACK/NAK across a subsequent application record. That would
            # silently attribute a control response to the wrong transaction.
            if later["kind"] == "application":
                break
            if later["endpoint_role"] == "pbx" and later["kind"] == "control":
                response = later
                break

        gi_events.append(
            {
                "capture_index": item["capture_index"],
                "framing": item["framing"],
                "field_identifiers": item["field_identifiers"],
                "wire_length": item["wire_length"],
                "wire_sha256": item["wire_sha256"],
                "response_capture_index": response["capture_index"] if response else None,
                "response": response["control_code"] if response else None,
                "response_wire_sha256": response["wire_sha256"] if response else None,
                "source_shape_match": tuple(item["field_identifiers"])
                == _OBSERVED_GI_FIELD_IDENTIFIERS,
                "exact_candidate_ack": item["framing"] == "stx_etx"
                and response is not None
                and response["control_code"] == "ACK",
            }
        )

    exact_ack_events = [item for item in gi_events if item["exact_candidate_ack"]]
    nak_events = [item for item in gi_events if item["response"] == "NAK"]
    missing_response_events = [item for item in gi_events if item["response"] is None]
    wrong_framing_events = [item for item in gi_events if item["framing"] != "stx_etx"]

    findings: list[dict[str, str]] = []
    if exact_ack_events:
        findings.append(
            {
                "id": "matrix-fias-gi-ack-observed",
                "severity": "info",
                "confidence": "high",
                "summary": "A PMS-originated STX/ETX GI record was followed by a PBX ACK.",
                "corrective_action": (
                    "Treat this as transaction evidence only. Pin a real Matrix capture to the "
                    "current Emulator SHA before considering a PMS_TO_PBX matrix row."
                ),
            }
        )
    if nak_events:
        findings.append(
            {
                "id": "matrix-fias-gi-nak-observed",
                "severity": "warning",
                "confidence": "high",
                "summary": "A PMS-originated GI record was followed by a PBX NAK.",
                "corrective_action": (
                    "Verify framing, negotiated LR field declarations, endpoint direction, and the "
                    "site configuration. Do not infer checksum or field cause from NAK alone."
                ),
            }
        )
    if missing_response_events:
        findings.append(
            {
                "id": "matrix-fias-gi-response-missing",
                "severity": "warning",
                "confidence": "medium",
                "summary": (
                    "At least one PMS-originated GI record has no safely attributable PBX ACK/NAK."
                ),
                "corrective_action": (
                    "Capture through the next control response without interleaving another application "
                    "record; do not pair a later ACK across transaction boundaries."
                ),
            }
        )
    if wrong_framing_events:
        findings.append(
            {
                "id": "matrix-fias-gi-framing-mismatch",
                "severity": "warning",
                "confidence": "high",
                "summary": "A candidate GI record was not STX/ETX framed.",
                "corrective_action": (
                    "Use the Matrix MICROS Opera FIAS profile's evidence-backed STX/ETX application "
                    "framing before interpreting the peer response."
                ),
            }
        )

    return {
        "diagnostic_profile": "matrix_fias_pms_to_pbx_gi_candidate",
        "combination": {
            "pbx_family": "Matrix",
            "pbx_dialect": "MICROS Opera / FIAS",
            "transport": "tcp",
            "pms_family": "Oracle / MICROS Opera",
            "pms_protocol": "FIAS",
            "direction": "pms_to_pbx",
        },
        "matrix_claim": "candidate_only_not_registered",
        "transport": normalized_transport,
        "pms_capture_direction": normalized_direction,
        "pbx_capture_direction": pbx_direction,
        "evidence_class": normalized_evidence,
        "gi_event_count": len(gi_events),
        "exact_gi_ack_count": len(exact_ack_events),
        "gi_nak_count": len(nak_events),
        "gi_missing_response_count": len(missing_response_events),
        "gi_wrong_framing_count": len(wrong_framing_events),
        "gi_events": gi_events,
        "observed_historical_field_identifier_shape": list(_OBSERVED_GI_FIELD_IDENTIFIERS),
        "source_contract": {
            "historical_operator_observation": "STX/ETX GI followed by single-byte ACK",
            "historical_runtime_evidence_current_sha_qualified": False,
            "current_exact_sha_live_validation_required": True,
            "field_values_qualified": False,
            "site_port_qualified": False,
            "ack_timing_qualified": False,
            "retry_policy_qualified": False,
            "checksum_lrc_qualified": False,
            "other_application_records_qualified": False,
            "broader_matrix_models_qualified": False,
        },
        "findings": findings,
        "claim_policy": {
            "matrix_registration_authorized": False,
            "supported_promotion_authorized": False,
            "production_support_claim_authorized": False,
            "other_fias_events_inferred": False,
            "site_port_inferred": False,
            "ack_timing_inferred": False,
            "retry_policy_inferred": False,
            "checksum_lrc_inferred": False,
            "serial_behavior_inferred": False,
            "raw_payloads_embedded": False,
            "guest_pii_embedded": False,
            "series2_station_programming_in_scope": False,
        },
        "architectural_boundary": {
            "project": "InnAware PMS-PBX Emulator",
            "exchange_mode": "data_only",
            "runtime_dependency_on_ucp": False,
            "ucp_runtime_dependency_allowed": False,
        },
    }
