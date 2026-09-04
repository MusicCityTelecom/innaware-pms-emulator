from __future__ import annotations

import hashlib
from typing import Any, Iterable

STX = 0x02
ETX = 0x03

_EVIDENCE_CLASSES = {
    "packet_capture",
    "operator_confirmed",
    "legacy_source_profile",
    "simulator_characterization",
    "inference",
}
_LINK_CODES = {"LS", "LD", "LR", "LA"}


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


def _classify_fias_frame(data: bytes) -> tuple[str, str | None, str | None]:
    if len(data) >= 2 and data[0] == STX and data[-1] == ETX:
        framing = "stx_etx"
        payload = data[1:-1]
    elif data.endswith(b"\r\n"):
        framing = "crlf"
        payload = data[:-2]
    elif data.endswith(b"\r"):
        framing = "cr"
        payload = data[:-1]
    elif data.endswith(b"\n"):
        framing = "lf"
        payload = data[:-1]
    else:
        framing = "raw"
        payload = data

    text = payload.decode("latin-1", errors="replace").strip("\x00\r\n ")
    if len(text) < 2:
        return framing, None, None
    code = text[:2].upper()
    if code not in _LINK_CODES or (len(text) > 2 and text[2] != "|"):
        return framing, None, None

    record_type = None
    if code == "LR":
        for token in text.split("|")[1:]:
            if token.startswith("RT") and len(token) > 2:
                record_type = token[2:]
                break
    return framing, code, record_type


def analyze_matrix_fias_link_progression(
    captures: Iterable[object],
    *,
    transport: str,
    pbx_direction: str,
    evidence_class: str,
) -> dict[str, Any]:
    """Characterize a Matrix/FIAS link negotiation without widening support claims.

    The function is intentionally transport- and direction-gated. It recognizes the
    operator-observed FIAS link progression only: PBX-originated LS, PMS LS reply,
    PBX-originated LD/LR declarations, then PBX-originated LA. It does not infer
    guest-event support, a site TCP port, ENQ/ACK semantics, retry policy, or a
    compatibility promotion.
    """

    normalized_transport = transport.strip().lower()
    if normalized_transport != "tcp":
        raise ValueError("Matrix MICROS Opera link diagnostics are qualified only for TCP")

    normalized_direction = pbx_direction.strip().lower()
    if normalized_direction not in {"rx", "tx"}:
        raise ValueError("pbx_direction must be 'rx' or 'tx'")

    normalized_evidence = evidence_class.strip().lower()
    if normalized_evidence not in _EVIDENCE_CLASSES:
        raise ValueError("unsupported evidence_class")

    pms_direction = "tx" if normalized_direction == "rx" else "rx"
    observations: list[dict[str, Any]] = []

    for index, item in enumerate(captures):
        direction = str(_capture_value(item, "direction", "unknown")).strip().lower()
        data = _capture_bytes(item)
        framing, code, record_type = _classify_fias_frame(data)
        if code is None:
            continue
        observations.append(
            {
                "capture_index": index,
                "direction": direction,
                "endpoint_role": (
                    "pbx"
                    if direction == normalized_direction
                    else "pms"
                    if direction == pms_direction
                    else "unknown"
                ),
                "framing": framing,
                "record_code": code,
                "record_type": record_type,
                "wire_length": len(data),
                "wire_sha256": hashlib.sha256(data).hexdigest(),
            }
        )

    pbx_records = [item for item in observations if item["endpoint_role"] == "pbx"]
    pms_records = [item for item in observations if item["endpoint_role"] == "pms"]

    pbx_ls = [item for item in pbx_records if item["record_code"] == "LS"]
    pms_ls = [item for item in pms_records if item["record_code"] == "LS"]
    pbx_ld = [item for item in pbx_records if item["record_code"] == "LD"]
    pbx_lr = [item for item in pbx_records if item["record_code"] == "LR"]
    pbx_la = [item for item in pbx_records if item["record_code"] == "LA"]

    exact_progression = False
    progression_indexes: dict[str, Any] = {
        "pbx_ls": None,
        "pms_ls_reply": None,
        "pbx_ld": None,
        "pbx_lr": [],
        "pbx_la": None,
    }
    if pbx_ls:
        ls_index = pbx_ls[0]["capture_index"]
        progression_indexes["pbx_ls"] = ls_index
        reply = next(
            (item for item in pms_ls if item["capture_index"] > ls_index),
            None,
        )
        if reply is not None:
            reply_index = reply["capture_index"]
            progression_indexes["pms_ls_reply"] = reply_index
            ld = next(
                (item for item in pbx_ld if item["capture_index"] > reply_index),
                None,
            )
            if ld is not None:
                ld_index = ld["capture_index"]
                progression_indexes["pbx_ld"] = ld_index
                lr_items = [
                    item
                    for item in pbx_lr
                    if item["capture_index"] > ld_index
                ]
                progression_indexes["pbx_lr"] = [
                    item["capture_index"] for item in lr_items
                ]
                if lr_items:
                    last_lr_index = lr_items[-1]["capture_index"]
                    la = next(
                        (
                            item
                            for item in pbx_la
                            if item["capture_index"] > last_lr_index
                        ),
                        None,
                    )
                    if la is not None:
                        progression_indexes["pbx_la"] = la["capture_index"]
                        exact_progression = (
                            pbx_ls[0]["framing"] == "stx_etx"
                            and reply["framing"] == "stx_etx"
                            and ld["framing"] == "stx_etx"
                            and all(item["framing"] == "stx_etx" for item in lr_items)
                            and la["framing"] == "stx_etx"
                        )

    findings: list[dict[str, Any]] = []
    if exact_progression:
        findings.append(
            {
                "id": "matrix-fias-link-progression-observed",
                "severity": "info",
                "confidence": "high",
                "summary": (
                    "Observed the bounded Matrix/FIAS link progression: PBX LS, PMS LS reply, "
                    "PBX LD/LR declarations, then PBX LA using STX/ETX framing."
                ),
                "corrective_action": (
                    "Treat the FIAS link as having progressed beyond Link Start. If guest-event "
                    "testing still fails, preserve the LR declaration set and troubleshoot only "
                    "the specific event family instead of changing transport or LS framing."
                ),
            }
        )
    else:
        if pbx_ls and not pms_ls:
            findings.append(
                {
                    "id": "matrix-fias-ls-reply-missing",
                    "severity": "error",
                    "confidence": "high",
                    "summary": "The PBX sent FIAS LS but no PMS-originated LS reply was observed.",
                    "corrective_action": (
                        "Verify the Emulator is in the PMS role and returns LS with the same "
                        "STX/ETX framing before investigating guest records."
                    ),
                }
            )
        if len(pbx_ls) >= 2 and not pbx_la:
            findings.append(
                {
                    "id": "matrix-fias-link-start-retrying",
                    "severity": "warning",
                    "confidence": "medium",
                    "summary": "Multiple PBX-originated LS records were observed without PBX LA.",
                    "corrective_action": (
                        "Check the LS reply framing and capture subsequent LD/LR/LA traffic. "
                        "Do not infer a retry timer from this observation."
                    ),
                }
            )
        if pms_ls and any(item["framing"] != "stx_etx" for item in pms_ls):
            findings.append(
                {
                    "id": "matrix-fias-ls-reply-framing-mismatch",
                    "severity": "error",
                    "confidence": "high",
                    "summary": "A PMS LS reply was observed without STX/ETX framing.",
                    "corrective_action": (
                        "Use the field-observed Matrix MICROS Opera STX/ETX framing for LS replies."
                    ),
                }
            )
        if pbx_ld or pbx_lr:
            if not pbx_la:
                findings.append(
                    {
                        "id": "matrix-fias-link-negotiation-incomplete",
                        "severity": "warning",
                        "confidence": "high",
                        "summary": (
                            "PBX LD/LR link-description traffic was observed, but no PBX LA "
                            "was captured after it."
                        ),
                        "corrective_action": (
                            "Keep the connection open and capture through LA or link teardown. "
                            "Do not claim an active link from LD/LR alone."
                        ),
                    }
                )

    return {
        "diagnostic_profile": "matrix_sarvam_micros_opera_fias_link_progression",
        "combination": {
            "pbx_family": "Matrix",
            "pbx_dialect": "MICROS Opera / FIAS",
            "transport": "tcp",
            "pms_family": "Oracle / MICROS Opera",
            "pms_protocol": "FIAS",
            "direction": "pbx_to_pms",
        },
        "evidence_class": normalized_evidence,
        "pbx_capture_direction": normalized_direction,
        "pms_capture_direction": pms_direction,
        "qualified_scope": {
            "link_start": True,
            "link_description": True,
            "link_record_declarations": True,
            "link_alive": True,
            "guest_event_semantics": False,
            "site_port": False,
            "enq_ack": False,
            "retry_timing": False,
        },
        "observation_count": len(observations),
        "pbx_ls_count": len(pbx_ls),
        "pms_ls_reply_count": len(pms_ls),
        "pbx_ld_count": len(pbx_ld),
        "pbx_lr_count": len(pbx_lr),
        "pbx_la_count": len(pbx_la),
        "lr_record_types": [
            item["record_type"]
            for item in pbx_lr
            if item["record_type"] is not None
        ],
        "exact_progression_observed": exact_progression,
        "progression_capture_indexes": progression_indexes,
        "observations": observations,
        "findings": findings,
        "claim_policy": {
            "matrix_status_changed": False,
            "compatibility_promotion_authorized": False,
            "site_port_inferred": False,
            "enq_ack_inferred": False,
            "retry_policy_inferred": False,
            "guest_event_support_inferred": False,
            "raw_payloads_embedded": False,
            "series2_station_programming_in_scope": False,
        },
        "architectural_boundary": {
            "project": "InnAware PMS-PBX Emulator",
            "exchange_mode": "data_only",
            "runtime_dependency_on_ucp": False,
            "ucp_runtime_dependency_allowed": False,
        },
    }
