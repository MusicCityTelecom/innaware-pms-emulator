from __future__ import annotations

from hashlib import sha256
import json
import re
from typing import Any, Iterable

from .matrix_fias_link_diagnostics import analyze_matrix_fias_link_progression

_SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")
_REAL_CAPTURE_ORIGINS = {"real_pbx_lab", "authorized_field_capture"}


def _text(value: str, *, name: str) -> str:
    normalized = str(value).strip()
    if not normalized:
        raise ValueError(f"{name} must be non-empty")
    return normalized


def _digest_json(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return sha256(raw).hexdigest()


def build_matrix_fias_live_acceptance(
    captures: Iterable[object],
    *,
    source_sha: str,
    transport: str,
    pbx_direction: str,
    evidence_class: str,
    evidence_origin: str,
    matrix_model: str,
    matrix_version: str,
    local_endpoint: str,
    remote_endpoint: str,
    tcp_initiator: str,
    operator_authorized: bool,
    synthetic_or_redacted: bool,
    no_guest_pii: bool,
    source_material_synthetic: bool,
) -> dict[str, Any]:
    """Evaluate whether a Matrix/FIAS capture packet is ready for human evidence review.

    This is a review/readiness artifact for the standalone Emulator. It does not mutate
    the compatibility matrix and it never converts a green capture into SUPPORTED.
    """

    if not _SHA_RE.fullmatch(source_sha):
        raise ValueError("source_sha must be an exact 40-character Git commit SHA")

    normalized_origin = str(evidence_origin).strip().lower()
    normalized_evidence = str(evidence_class).strip().lower()
    normalized_initiator = str(tcp_initiator).strip().lower()
    if normalized_initiator not in {"pbx", "pms"}:
        raise ValueError("tcp_initiator must be 'pbx' or 'pms'")

    diagnostic = analyze_matrix_fias_link_progression(
        captures,
        transport=transport,
        pbx_direction=pbx_direction,
        evidence_class=evidence_class,
    )

    blockers: list[dict[str, str]] = []

    def block(code: str, detail: str) -> None:
        blockers.append({"code": code, "detail": detail})

    if normalized_evidence != "packet_capture":
        block(
            "packet-capture-evidence-required",
            "Live admission requires direct packet-capture evidence; source/operator/simulator evidence remains useful but non-admitting.",
        )
    if normalized_origin not in _REAL_CAPTURE_ORIGINS:
        block(
            "real-endpoint-provenance-required",
            "Evidence origin must identify an authorized real PBX lab or authorized field capture.",
        )
    if source_material_synthetic:
        block(
            "synthetic-source-material",
            "Synthetic/reconstructed frames may test the analyzer but cannot establish real endpoint interoperability.",
        )
    if not diagnostic.get("exact_progression_observed"):
        block(
            "bounded-link-progression-not-observed",
            "Capture must contain the bounded STX/ETX LS -> LS -> LD/LR... -> LA progression before review.",
        )
    if not operator_authorized:
        block("operator-authorization-required", "The capture must be explicitly authorized by the operator/site owner.")
    if not synthetic_or_redacted:
        block("sanitization-required", "Reusable evidence must be synthetic or redacted before it leaves the capture workspace.")
    if not no_guest_pii:
        block("guest-pii-present", "Guest PII must be removed before the evidence artifact can be reused.")

    model = _text(matrix_model, name="matrix_model")
    version = _text(matrix_version, name="matrix_version")
    local = _text(local_endpoint, name="local_endpoint")
    remote = _text(remote_endpoint, name="remote_endpoint")

    report = {
        "schema_version": "1.0",
        "producer": {
            "project": "InnAware PMS-PBX Emulator",
            "repository": "MusicCityTelecom/innaware-pms-emulator",
            "source_sha": source_sha.casefold(),
        },
        "combination": diagnostic["combination"],
        "endpoint_provenance": {
            "matrix_model": model,
            "matrix_version": version,
            "local_endpoint": local,
            "remote_endpoint": remote,
            "tcp_initiator": normalized_initiator,
            "pbx_capture_direction": diagnostic["pbx_capture_direction"],
            "evidence_origin": normalized_origin,
        },
        "evidence": {
            "evidence_class": normalized_evidence,
            "operator_authorized": bool(operator_authorized),
            "synthetic_or_redacted": bool(synthetic_or_redacted),
            "no_guest_pii": bool(no_guest_pii),
            "source_material_synthetic": bool(source_material_synthetic),
            "diagnostic_report_sha256": _digest_json(diagnostic),
        },
        "bounded_observation": {
            "exact_progression_observed": bool(diagnostic.get("exact_progression_observed")),
            "pbx_ls_count": diagnostic.get("pbx_ls_count", 0),
            "pms_ls_reply_count": diagnostic.get("pms_ls_reply_count", 0),
            "pbx_ld_count": diagnostic.get("pbx_ld_count", 0),
            "pbx_lr_count": diagnostic.get("pbx_lr_count", 0),
            "pbx_la_count": diagnostic.get("pbx_la_count", 0),
            "lr_record_types": list(diagnostic.get("lr_record_types", [])),
        },
        "manual_review_ready": not blockers,
        "blockers": blockers,
        "claim_policy": {
            "matrix_status_changed": False,
            "compatibility_promotion_authorized": False,
            "production_support_claim_authorized": False,
            "automated_matrix_mutation_allowed": False,
            "guest_event_support_inferred": False,
            "site_port_inferred": False,
            "retry_timing_inferred": False,
            "enq_ack_inferred": False,
            "series2_station_programming_in_scope": False,
            "manual_review_ready_does_not_equal_supported": True,
        },
        "architectural_boundary": {
            "emulator_role": "standalone technician/installer interoperability and diagnostic support tool",
            "ucp_role": "separate production hospitality PMS gateway/runtime",
            "exchange_mode": "data_only",
            "runtime_dependency_on_emulator": False,
            "ucp_runtime_dependency_allowed": False,
        },
    }
    report["artifact_sha256"] = _digest_json(report)
    return report
