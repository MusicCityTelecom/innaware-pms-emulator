from __future__ import annotations

import pytest

from innaware_pms_emulator.capture_diagnostics import diagnose_capture_interface
from innaware_pms_emulator.phonesuite_pms_source_extensions import (
    assess_phonesuite_pms_source_extension,
    diagnose_phonesuite_pms_source_extension_format,
)


@pytest.mark.parametrize(
    ("payload", "family"),
    [
        (b"MSG0 101", "MSG"),
        (b"MSG9 1001", "MSG"),
        (b"DID1 101 1234", "DID"),
        (b"DID0 1001", "DID"),
        (b"VIP1 101", "VIP"),
        (b"VIP0 1001", "VIP"),
        (b"WKP0705 101", "WKP"),
        (b"WKP1430 1001", "WKP"),
        (b"WKP9999 101", "WKP"),
        (b"WKP 1001", "WKP"),
    ],
)
def test_direct_manual_pms_to_phonesuite_families_are_direction_qualified(
    payload: bytes,
    family: str,
) -> None:
    assessment = assess_phonesuite_pms_source_extension(payload)
    assert assessment.qualified is True
    assert assessment.family == family
    assert assessment.direction == "pms_to_pbx"
    assert assessment.evidence_class == "legacy_source_profile"
    assert assessment.expected_format
    assert diagnose_phonesuite_pms_source_extension_format(payload) == []


@pytest.mark.parametrize(
    ("payload", "code"),
    [
        (b"MSG10 101", "phonesuite_pms_msg_format_invalid"),
        (b"MSG1 XX", "phonesuite_pms_extension_format_invalid"),
        (b"MSG2 101 1", "phonesuite_pms_msg_format_invalid"),
        (b"DID2 101", "phonesuite_pms_did_status_invalid"),
        (b"DID1 101 12345", "phonesuite_pms_did_number_invalid"),
        (b"DID0 101 1234", "phonesuite_pms_did_format_invalid"),
        (b"DID1 XX 1234", "phonesuite_pms_extension_format_invalid"),
        (b"VIP2 101", "phonesuite_pms_vip_status_invalid"),
        (b"VIP1 XX", "phonesuite_pms_extension_format_invalid"),
        (b"WKP2500 101", "phonesuite_pms_wkp_time_invalid"),
        (b"WKP1260 101", "phonesuite_pms_wkp_time_invalid"),
        (b"WKP0705 XX", "phonesuite_pms_extension_format_invalid"),
        (b"WKP07:05 101", "phonesuite_pms_wkp_format_invalid"),
    ],
)
def test_direct_manual_source_extensions_emit_actionable_format_diagnostics(
    payload: bytes,
    code: str,
) -> None:
    findings = diagnose_phonesuite_pms_source_extension_format(payload)
    assert code in {finding.code for finding in findings}
    assert all(finding.confidence == "high" for finding in findings)
    assert all(finding.evidence_class == "legacy_source_profile" for finding in findings)
    assert all(finding.corrective_action for finding in findings)


def test_unrelated_or_reverse_only_families_are_not_promoted_by_extension_policy() -> None:
    for payload in (b"STS2 101", b"RQINZ", b"MOV 101 102", b"UNKNOWN 101"):
        assessment = assess_phonesuite_pms_source_extension(payload)
        assert assessment.qualified is False
        assert diagnose_phonesuite_pms_source_extension_format(payload) == []


def _frame(direction: str, text: str) -> dict:
    return {
        "direction": direction,
        "data": b"\x02" + text.encode("latin-1") + b"\x03",
        "peer": "synthetic-lab-peer",
    }


def _phonesuite_ids(report) -> set[str]:
    return {finding.id for finding in report.findings if finding.id.startswith("phonesuite_pms_")}


def test_capture_overlay_applies_new_families_only_in_proven_pms_to_phonesuite_direction() -> None:
    config = {
        "name": "phonesuite-pbx",
        "protocol": "MITEL 1",
        "transport": "serial",
        "emulation_role": "pbx",
        "personality_id": "pbx-phonesuite",
        "options": {"framing": "stx_etx"},
    }

    valid = diagnose_capture_interface(
        config,
        [
            _frame("rx", "MSG1 101"),
            _frame("rx", "DID1 101 1234"),
            _frame("rx", "VIP1 101"),
            _frame("rx", "WKP0705 101"),
        ],
    )
    assert _phonesuite_ids(valid) == set()

    malformed = diagnose_capture_interface(config, [_frame("rx", "MSG2 101 1")])
    assert _phonesuite_ids(malformed) == {"phonesuite_pms_msg_format_invalid"}

    # The direct manual separately documents PhoneSuite-originated MSG2
    # voicemail-status records. The PMS->PBX formatter must never inspect the
    # reverse capture direction merely because the same MSG family name appears.
    reverse = diagnose_capture_interface(config, [_frame("tx", "MSG2 101 1")])
    assert _phonesuite_ids(reverse) == set()


def test_direct_did_diagnostic_does_not_depend_on_generic_legacy_prefix_classification() -> None:
    report = diagnose_capture_interface(
        {
            "name": "phonesuite-pbx",
            "protocol": "MITEL 1",
            "transport": "serial",
            "emulation_role": "pbx",
            "personality_id": "pbx-phonesuite",
            "options": {"framing": "stx_etx"},
        },
        [_frame("rx", "DID1 101 12345")],
    )

    assert _phonesuite_ids(report) == {"phonesuite_pms_did_number_invalid"}


def test_matrix_personality_never_inherits_direct_phonesuite_command_policy() -> None:
    report = diagnose_capture_interface(
        {
            "name": "matrix-negative",
            "protocol": "FIAS",
            "transport": "tcp_server",
            "emulation_role": "pms",
            "peer_personality_id": "pbx-matrix",
            "options": {"framing": "stx_etx"},
        },
        [_frame("tx", "DID1 101 12345"), _frame("tx", "MSG2 101 1")],
    )

    assert _phonesuite_ids(report) == set()
