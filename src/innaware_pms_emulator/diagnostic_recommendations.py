from __future__ import annotations

from typing import Any

from .diagnostics import DiagnosticReport


def remediation_plan(report: DiagnosticReport) -> list[dict[str, Any]]:
    """Translate evidence-backed findings into explicit, reviewable config suggestions.

    These are suggestions only. The emulator must never apply them automatically to a
    live endpoint. The UI can later offer an operator-confirmed Apply action for low-risk
    configuration changes.
    """

    by_id = {item.id: item for item in report.findings}
    plan: list[dict[str, Any]] = []
    rx_framing = report.observations.get("dominant_rx_framing")

    if rx_framing and (
        "configured-framing-mismatch" in by_id
        or "wire-framing-asymmetry" in by_id
        or "fias-link-start-framing-mismatch" in by_id
    ):
        plan.append({
            "id": "match-peer-framing",
            "title": f"Change outbound framing to {str(rx_framing).upper()}",
            "reason": "The peer's recognized application records consistently use a different framing mode.",
            "risk": "low",
            "requires_operator_confirmation": True,
            "requires_reconnect": True,
            "configuration_patch": {
                "options": {"framing": rx_framing},
            },
            "validate_after": [
                "Reconnect the endpoint.",
                "Verify RX and TX use the same framing.",
                "Verify link negotiation progresses beyond Link Start.",
            ],
        })

    if "protocol-observation-mismatch" in by_id:
        plan.append({
            "id": "select-observed-fias-protocol",
            "title": "Use FIAS wire semantics for the observed FIAS traffic",
            "reason": "The capture contains recognized FIAS records while the selected adapter belongs to another command family.",
            "risk": "medium",
            "requires_operator_confirmation": True,
            "requires_reconnect": True,
            "configuration_patch": {"protocol": "FIAS"},
            "validate_after": [
                "Verify Link Start is decoded as FIAS.",
                "Verify outbound records use the peer's framing before sending guest events.",
            ],
        })

    # Matrix is the remote PBX for the dedicated PMS-side profile. Do not rewrite
    # InnAware's `personality_id` to a PBX identity: endpoint identity and wire
    # protocol are separate dimensions. If the interface already uses the known
    # FIAS + STX/ETX wire boundary, no additional Matrix-profile remediation is
    # needed solely because the fingerprint detector also recognized the LS frame.
    matrix_wire_already_selected = (
        report.protocol == "FIAS"
        and report.configured_framing == "stx_etx"
    )
    if "matrix-sarvam-opera-signature" in by_id and not matrix_wire_already_selected:
        plan.append({
            "id": "consider-matrix-sarvam-personality",
            "title": "Consider the Matrix SARVAM MICROS Opera peer profile",
            "reason": "The capture matches the field-observed PBX-to-PMS STX/ETX FIAS Link Start signature.",
            "risk": "medium",
            "requires_operator_confirmation": True,
            "requires_reconnect": True,
            "configuration_patch": {
                "protocol": "FIAS",
                "peer_personality_id": "pbx-matrix",
                "options": {"framing": "stx_etx"},
            },
            "caveat": (
                "The wire signature is not globally unique. Confirm the connected product before applying "
                "a remote PBX personality. This patch identifies the peer; it does not change what InnAware is emulating."
            ),
            "validate_after": [
                "Confirm the remote PBX is Matrix SARVAM UCS in MICROS Opera mode.",
                "Capture the next Matrix-originated link records after LS; do not assume a generic FIAS LD/LR/LA order until Matrix-specific evidence is observed.",
            ],
        })

    if "unanswered-enq" in by_id:
        plan.append({
            "id": "enable-enq-ack",
            "title": "Enable ENQ acknowledgement behavior",
            "reason": "The peer sent more ENQ controls than InnAware answered with ACK.",
            "risk": "medium",
            "requires_operator_confirmation": True,
            "requires_reconnect": False,
            "configuration_patch": {
                "options": {"auto_ack": True, "ack_enq": True},
            },
            "validate_after": [
                "Verify each inbound ENQ receives the personality-appropriate ACK within its timeout.",
            ],
        })

    if "embedded-line-ending-in-stx-etx-fias" in by_id:
        plan.append({
            "id": "strip-inner-fias-line-ending",
            "title": "Strip CR/LF before applying STX/ETX framing",
            "reason": "The peer terminates its FIAS payload at ETX while InnAware is placing CR/LF inside the frame.",
            "risk": "low",
            "requires_operator_confirmation": True,
            "requires_reconnect": False,
            "configuration_patch": {
                "options": {"strip_line_endings_before_frame": True},
            },
            "implementation_note": "This option is a v0.4.0 target and must be implemented in the framing/send path before the UI offers Apply.",
            "validate_after": [
                "Confirm TX bytes end with the final FIAS field delimiter followed immediately by ETX.",
            ],
        })

    return plan


def report_with_remediation(report: DiagnosticReport) -> dict[str, Any]:
    result = report.as_dict()
    result["remediation_plan"] = remediation_plan(report)
    return result
