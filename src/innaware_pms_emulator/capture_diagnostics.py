from __future__ import annotations

from typing import Any, Iterable

from .diagnostics import DiagnosticFinding, DiagnosticReport, WireObservation, diagnose_interface, observe_capture
from .phonesuite_pms_policy import diagnose_phonesuite_pms_record_format
from .phonesuite_pms_source_extensions import diagnose_phonesuite_pms_source_extension_format


_PHONESUITE_PERSONALITY = "pbx-phonesuite"


def _value(config: Any, name: str, default: Any = None) -> Any:
    if isinstance(config, dict):
        return config.get(name, default)
    return getattr(config, name, default)


def _normalized(value: Any) -> str:
    return str(value or "").strip().lower()


def _emulation_role(config: Any) -> str:
    role = _value(config, "emulation_role")
    return _normalized(getattr(role, "value", role))


def phonesuite_pms_to_pbx_capture_direction(config: Any) -> str | None:
    """Return the local capture direction that represents PMS -> PhoneSuite.

    Direction is only qualified when endpoint identity is explicit. A local PBX
    personality receives PMS application records on RX; a local PMS endpoint
    connected to a real PhoneSuite peer transmits those records on TX. Missing
    or contradictory role/personality metadata deliberately fails closed.
    """

    role = _emulation_role(config)
    local_personality = _normalized(_value(config, "personality_id"))
    peer_personality = _normalized(_value(config, "peer_personality_id"))

    if role == "pbx" and local_personality == _PHONESUITE_PERSONALITY:
        return "rx"
    if role == "pms" and peer_personality == _PHONESUITE_PERSONALITY:
        return "tx"
    return None


def _phonesuite_pms_format_findings(
    config: Any,
    observations: Iterable[WireObservation],
) -> list[DiagnosticFinding]:
    capture_direction = phonesuite_pms_to_pbx_capture_direction(config)
    if capture_direction is None:
        return []

    findings: list[DiagnosticFinding] = []
    for observation in observations:
        if observation.direction != capture_direction:
            continue
        if observation.record_family != "legacy_hotel" or not observation.payload:
            continue

        diagnostics = [
            *diagnose_phonesuite_pms_record_format(observation.payload),
            *diagnose_phonesuite_pms_source_extension_format(observation.payload),
        ]
        for diagnostic in diagnostics:
            findings.append(
                DiagnosticFinding(
                    id=diagnostic.code,
                    severity=diagnostic.severity,
                    confidence=diagnostic.confidence,
                    title="PhoneSuite PMS-to-PBX application record has a documented format problem",
                    summary=f"{diagnostic.observed}. Expected: {diagnostic.expected}.",
                    evidence=[observation.evidence()],
                    suggested_actions=[diagnostic.corrective_action],
                    tags=[
                        "phonesuite",
                        "application-format",
                        "pms-to-pbx",
                        diagnostic.evidence_class,
                    ],
                )
            )
    return findings


def diagnose_capture_interface(config: Any, captures: Iterable[Any]) -> DiagnosticReport:
    """Build the generic capture report plus strictly gated vendor overlays.

    The generic diagnostics remain transport/application neutral. PhoneSuite
    PMS record-format findings are added only when endpoint identity makes the
    PMS->PBX direction unambiguous. The overlay does not select a profile,
    infer serial settings, qualify another transport, or alter compatibility
    status.
    """

    raw_captures = list(captures)
    report = diagnose_interface(config, raw_captures)
    observations = [observe_capture(item) for item in raw_captures]
    phone_findings = _phonesuite_pms_format_findings(config, observations)
    report.findings.extend(phone_findings)
    report.observations["phonesuite_pms_format_findings"] = len(phone_findings)
    report.observations["phonesuite_pms_to_pbx_capture_direction"] = (
        phonesuite_pms_to_pbx_capture_direction(config)
    )
    return report
