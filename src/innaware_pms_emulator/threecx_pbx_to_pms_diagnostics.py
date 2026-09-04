from __future__ import annotations

from hashlib import sha256
import re
from typing import Any, Iterable

from .diagnostics import observe_capture


_ALLOWED_EVIDENCE_CLASSES = {
    "packet_capture",
    "operator_confirmed",
    "legacy_source_profile",
    "simulator_characterization",
    "inference",
}
_PBX_DIRECTIONS = {"rx", "tx"}
_SOURCE_QUALIFIED_PBX_RECORD_CODES = {"MSG", "STS"}
_MAID_STATUS = {
    "1": "maid_present",
    "2": "clean",
    "3": "not_clean",
    "4": "out_of_service",
    "5": "to_be_inspected",
    "6": "occupied_clean",
    "7": "occupied_not_clean",
    "8": "vacant_clean",
    "9": "vacant_not_clean",
}
_MAID_RE = re.compile(r"^STS([1-9]) +([0-9]{1,5})$")
_MESSAGE_REGISTRATION_FEE_STATUS_WIDTH_BYTES = 4
_SOURCE_BIDIRECTIONAL_LINK_PATTERN = "ENQ/ACK/STX-text-ETX/ACK"


def _normalize_choice(value: str, *, name: str, allowed: set[str]) -> str:
    normalized = str(value).strip().lower()
    if normalized not in allowed:
        raise ValueError(f"{name} must be one of: {', '.join(sorted(allowed))}")
    return normalized


def _safe_observation(index: int, item: Any, *, endpoint_side: str) -> dict[str, Any]:
    observation = observe_capture(item)
    return {
        "capture_index": index,
        "endpoint_side": endpoint_side,
        "direction": observation.direction,
        "sha256": sha256(observation.data).hexdigest(),
        "wire_length": len(observation.data),
        "framing": observation.framing,
        "control": observation.control,
        "record_family": observation.record_family,
        "record_code": observation.record_code,
    }


def analyze_3cx_pbx_to_pms_observations(
    captures: Iterable[Any],
    *,
    transport: str,
    evidence_class: str,
    pbx_direction: str,
) -> dict[str, Any]:
    """Characterize source-documented 3CX system-to-PMS record candidates.

    The current public 3CX PMS specification explicitly documents two records sent
    by the system to the PMS: Message Registration (MSG) and Maid Status (STS).
    It also describes the PMS/System link as bidirectional and identifies the
    ENQ/ACK/STX-text-ETX/ACK link pattern. This analyzer preserves those source facts
    without inventing a reverse transaction state machine. In particular, it does not
    infer system-originated timing/retry semantics, a checksum contract, universal
    TCP port, or compatibility promotion from the presence of those source facts.
    """

    normalized_transport = _normalize_choice(
        transport, name="transport", allowed={"tcp"}
    )
    normalized_evidence = _normalize_choice(
        evidence_class,
        name="evidence_class",
        allowed=_ALLOWED_EVIDENCE_CLASSES,
    )
    normalized_pbx_direction = _normalize_choice(
        pbx_direction,
        name="pbx_direction",
        allowed=_PBX_DIRECTIONS,
    )
    pms_direction = "rx" if normalized_pbx_direction == "tx" else "tx"

    source_records: list[dict[str, Any]] = []
    exact_maid_status_records: list[dict[str, Any]] = []
    message_registration_candidates: list[dict[str, Any]] = []
    framing_candidates: list[dict[str, Any]] = []
    other_pbx_application_candidates: list[dict[str, Any]] = []
    peer_controls: list[dict[str, Any]] = []
    pbx_controls: list[dict[str, Any]] = []

    for index, item in enumerate(captures):
        observation = observe_capture(item)
        if observation.direction == normalized_pbx_direction:
            endpoint_side = "pbx"
        elif observation.direction == pms_direction:
            endpoint_side = "pms"
        else:
            endpoint_side = "unknown"
        summary = _safe_observation(index, item, endpoint_side=endpoint_side)

        if observation.control:
            if endpoint_side == "pbx":
                pbx_controls.append(summary)
            elif endpoint_side == "pms":
                peer_controls.append(summary)
            continue

        if endpoint_side != "pbx" or observation.record_family != "legacy_hotel":
            continue

        if observation.record_code not in _SOURCE_QUALIFIED_PBX_RECORD_CODES:
            other_pbx_application_candidates.append(summary)
            continue

        source_record = dict(summary)
        source_record["source_direction_qualified"] = True
        source_record["field_layout_qualified"] = False
        source_records.append(source_record)

        if observation.record_code == "STS":
            text = observation.payload.decode("latin-1", errors="replace")
            match = _MAID_RE.fullmatch(text)
            if observation.framing == "stx_etx" and match:
                maid = dict(source_record)
                maid["field_layout_qualified"] = True
                maid["maid_status_code"] = f"STS{match.group(1)}"
                maid["maid_status_meaning"] = _MAID_STATUS[match.group(1)]
                maid["station_digit_count"] = len(match.group(2))
                exact_maid_status_records.append(maid)
            else:
                framing_candidates.append(source_record)
        else:
            # The source establishes MSG direction/semantics and that its fee/status
            # field is four bytes, but the retrievable field-layout diagram does not
            # justify exact offsets. Preserve the known scalar without inventing a
            # parser contract.
            message = dict(source_record)
            message["fee_status_width_bytes"] = _MESSAGE_REGISTRATION_FEE_STATUS_WIDTH_BYTES
            message["fee_status_width_source_qualified"] = True
            message_registration_candidates.append(message)

    findings: list[dict[str, Any]] = []
    if exact_maid_status_records:
        findings.append(
            {
                "id": "3cx-pbx-to-pms-maid-status-source-match",
                "severity": "info",
                "confidence": "high",
                "summary": (
                    "A PBX-originated STX/ETX Maid Status record matches the source-documented "
                    "STS1..STS9 plus station-number shape. This is record/direction evidence only; "
                    "it does not establish a direction-specific reverse transaction state machine."
                ),
                "record_count": len(exact_maid_status_records),
            }
        )
    if message_registration_candidates:
        findings.append(
            {
                "id": "3cx-pbx-to-pms-message-registration-layout-unqualified",
                "severity": "warning",
                "confidence": "high",
                "summary": (
                    "A PBX-originated MSG record matches the source-documented Message Registration "
                    "family. The source qualifies a four-byte fee/status field, but exact field offsets/layout "
                    "remain unqualified. Retain the wire digest and obtain sanitized field evidence before implementing a formatter/parser contract."
                ),
                "record_count": len(message_registration_candidates),
                "fee_status_width_bytes": _MESSAGE_REGISTRATION_FEE_STATUS_WIDTH_BYTES,
            }
        )
    if framing_candidates:
        findings.append(
            {
                "id": "3cx-pbx-to-pms-source-record-framing-deviation",
                "severity": "warning",
                "confidence": "high",
                "summary": (
                    "A source-documented PBX-to-PMS record family was observed outside the exact "
                    "STX/ETX Maid Status shape. Preserve it as evidence; do not normalize framing automatically."
                ),
                "record_count": len(framing_candidates),
            }
        )
    if other_pbx_application_candidates:
        findings.append(
            {
                "id": "3cx-pbx-to-pms-record-outside-source-qualified-set",
                "severity": "warning",
                "confidence": "high",
                "summary": (
                    "A recognizable PBX-originated legacy-hotel record is outside the current source-qualified "
                    "3CX system-to-PMS MSG/STS set. Retain it as evidence; do not widen the direction claim automatically."
                ),
                "record_count": len(other_pbx_application_candidates),
            }
        )
    if peer_controls or pbx_controls:
        findings.append(
            {
                "id": "3cx-pbx-to-pms-control-bytes-not-transaction-correlated",
                "severity": "info",
                "confidence": "high",
                "summary": (
                    "ENQ/ACK/NAK control bytes were observed. The source qualifies the link as bidirectional "
                    "and identifies the ENQ/ACK/STX-text-ETX/ACK pattern, but this analyzer does not correlate "
                    "observed controls into a direction-specific 3CX-originated transaction state machine. "
                    "Capture timing/order must be reviewed before claiming reverse timing or retry behavior."
                ),
                "pbx_control_count": len(pbx_controls),
                "pms_control_count": len(peer_controls),
            }
        )

    return {
        "schema_version": "1.1",
        "diagnostic_profile": "3cx_mitel_sx2000_pbx_to_pms_source_candidate",
        "combination_candidate": {
            "pbx_family": "3CX",
            "pbx_dialect": "Hotel Module / Mitel SX2000-compatible",
            "transport": "tcp",
            "pms_family": "legacy-hotel-pms",
            "pms_protocol": "mitel-hospitality",
            "direction": "pbx_to_pms",
        },
        "matrix_claim": "candidate_only_not_registered",
        "transport": normalized_transport,
        "evidence_class": normalized_evidence,
        "capture_pbx_direction": normalized_pbx_direction,
        "reference_contract": {
            "source_qualified_pbx_record_codes": sorted(_SOURCE_QUALIFIED_PBX_RECORD_CODES),
            "application_framing": "STX/message/ETX",
            "source_bidirectional_link_control_pattern": _SOURCE_BIDIRECTIONAL_LINK_PATTERN,
            "source_bidirectional_link_control_pattern_qualified": True,
            "maid_status_codes": {f"STS{key}": value for key, value in _MAID_STATUS.items()},
            "maid_status_station_digits_max": 5,
            "message_registration_direction": "system_to_pms",
            "message_registration_semantics": (
                "Outside-call registration/counting using meter-pulse-derived status; the status/fee field is documented as four bytes."
            ),
            "message_registration_fee_status_width_bytes": _MESSAGE_REGISTRATION_FEE_STATUS_WIDTH_BYTES,
            "message_registration_fee_status_width_qualified": True,
            "message_registration_field_layout_qualified": False,
            "pbx_to_pms_transaction_correlation_qualified": False,
            "pbx_to_pms_timing_qualified": False,
            "pbx_to_pms_retry_policy_qualified": False,
            "pbx_to_pms_checksum_contract_qualified": False,
            "site_port_is_configured_not_universal": True,
            "separate_3cx_billing_cdr_interface_not_inferred": True,
        },
        "claim_policy": {
            "3cx_identity_preserved": True,
            "transport_inferred": False,
            "site_port_inferred": False,
            "bidirectional_link_pattern_does_not_infer_direction_specific_timing_or_retries": True,
            "pbx_to_pms_transaction_state_machine_inferred": False,
            "pbx_to_pms_retry_policy_inferred": False,
            "message_registration_layout_inferred": False,
            "billing_or_cdr_transport_inferred": False,
            "matrix_registration_authorized": False,
            "compatibility_promotion_authorized": False,
            "raw_payloads_embedded": False,
            "series2_station_programming_in_scope": False,
        },
        "source_direction_qualified_record_count": len(source_records),
        "source_direction_qualified_records": source_records,
        "exact_maid_status_record_count": len(exact_maid_status_records),
        "exact_maid_status_records": exact_maid_status_records,
        "message_registration_candidate_count": len(message_registration_candidates),
        "message_registration_candidates": message_registration_candidates,
        "framing_candidate_count": len(framing_candidates),
        "framing_candidates": framing_candidates,
        "other_pbx_application_candidate_count": len(other_pbx_application_candidates),
        "other_pbx_application_candidates": other_pbx_application_candidates,
        "pbx_controls": pbx_controls,
        "pms_controls": peer_controls,
        "findings": findings,
        "technician_actions": [
            "Record the exact 3CX version/build and confirm Hotel Services is configured for Mitel SX2000 before collecting live evidence.",
            "Record the actual Hotel Services address and site-configured TCP port; never promote one installation value into a protocol default.",
            "Explicitly identify which capture direction is 3CX-originated; do not infer endpoint roles from MSG or STS text alone.",
            "Trigger Maid Status with a synthetic room and preserve an STS1..STS9 frame plus exact wire SHA-256; do not retain guest PII.",
            "If Message Registration is exercised, preserve a sanitized MSG frame; the source qualifies a four-byte fee/status field but not its exact offsets.",
            "Capture any surrounding ENQ/ACK/NAK bytes and timestamps. The source qualifies the bidirectional link pattern, but direction-specific timing/retry behavior still requires reviewed evidence.",
            "Keep the separate 3CX CDR/billing interface outside this PMS application-protocol diagnostic.",
            "Do not register or promote a PBX-to-PMS matrix row from this source-derived report alone; tie any field/runtime expansion to an exact Emulator SHA.",
        ],
    }
