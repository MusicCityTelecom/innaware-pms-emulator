import pytest

from innaware_pms_emulator.phonesuite_pms_policy import (
    PHONESUITE_PMS_MAX_GAP_SECONDS,
    assess_phonesuite_pms_record,
    diagnose_phonesuite_pms_receive_timing,
)


def test_phonesuite_vendor_boundary_qualifies_chk0_and_chk1_pms_to_pbx() -> None:
    for payload, opcode in ((b"CHK1 101", "CHK1"), (b"CHK0 101", "CHK0")):
        assessment = assess_phonesuite_pms_record(payload)
        assert assessment.qualified is True
        assert assessment.opcode == opcode
        assert assessment.family == "CHK"
        assert assessment.expected_format == "CHK1 EEEE [Name] or CHK0 EEEE"
        assert assessment.direction == "pms_to_pbx"
        assert assessment.evidence_class == "legacy_source_profile"


@pytest.mark.parametrize(
    ("payload", "family", "opcode"),
    [
        (b"LMT 101 25.00", "LMT", "LMT"),
        (b"DND1 101", "DND", "DND1"),
        (b"DND0 101", "DND", "DND0"),
        (b"GRP 101 GOLD", "GRP", "GRP"),
        (b"LNGen101", "LNG", "LNGen"),
        (b"MW 1 101", "MW", "MW1"),
        (b"MW 0 101", "MW", "MW0"),
        (b"RST2 101", "RST", "RST2"),
        (b"AREYUTHERE", "AREYUTHERE", "AREYUTHERE"),
        (b"GRS", "GRS", "GRS"),
        (b"END", "END", "END"),
        (b"NAM1 TEST,GUEST 101", "NAM", "NAM1"),
        (b"NAM2 TEST,GUEST 101", "NAM", "NAM2"),
        (b"NAM3 TEST,GUEST 101", "NAM", "NAM3"),
        (b"NAM4 TEST,GUEST 101", "NAM", "NAM4"),
    ],
)
def test_phonesuite_vendor_boundary_qualifies_documented_pms_command_families(
    payload: bytes,
    family: str,
    opcode: str,
) -> None:
    assessment = assess_phonesuite_pms_record(payload)
    assert assessment.qualified is True
    assert assessment.family == family
    assert assessment.opcode == opcode
    assert assessment.expected_format
    assert assessment.direction == "pms_to_pbx"
    assert assessment.evidence_class == "legacy_source_profile"


def test_phonesuite_vendor_boundary_preserves_source_format_hints() -> None:
    language = assess_phonesuite_pms_record(b"LNGen101")
    assert "lowercase two-letter ISO 639-1" in (language.expected_format or "")

    message_waiting = assess_phonesuite_pms_record(b"MW 1 101")
    assert "exactly one space" in (message_waiting.expected_format or "")

    guest_name = assess_phonesuite_pms_record(b"NAM2 TEST,GUEST 101")
    assert "n is 1-4" in (guest_name.expected_format or "")


def test_phonesuite_vendor_boundary_does_not_promote_ambiguous_or_reverse_direction_records() -> None:
    for payload in (
        b"MOV 101 102",
        b"MSG1 101",
        b"STS2 101",
        b"RQINZ",
        b"UNKNOWN 101",
    ):
        assessment = assess_phonesuite_pms_record(payload)
        assert assessment.qualified is False
        assert assessment.expected_format is None


def test_phonesuite_pms_start_and_interbyte_deadlines_are_one_tenth_second() -> None:
    assert PHONESUITE_PMS_MAX_GAP_SECONDS == pytest.approx(0.1)

    acceptable = diagnose_phonesuite_pms_receive_timing(
        enq_ack_to_stx_seconds=0.1,
        max_inter_byte_gap_seconds=0.1,
    )
    assert acceptable == []

    late = diagnose_phonesuite_pms_receive_timing(
        enq_ack_to_stx_seconds=0.101,
        max_inter_byte_gap_seconds=0.125,
    )
    assert [item.code for item in late] == [
        "phonesuite_pms_stx_deadline_exceeded",
        "phonesuite_pms_interbyte_deadline_exceeded",
    ]
    assert all(item.evidence_class == "legacy_source_profile" for item in late)
    assert "3-second" in late[0].corrective_action
    assert "operator-configured" in late[1].corrective_action


def test_phonesuite_pms_incomplete_frame_and_late_data_are_actionable() -> None:
    findings = diagnose_phonesuite_pms_receive_timing(
        complete_etx=False,
        late_data_after_timeout=True,
    )
    assert [item.code for item in findings] == [
        "phonesuite_pms_etx_deadline_missing",
        "phonesuite_pms_late_data_after_timeout",
    ]
    assert "continuous transaction" in findings[0].corrective_action
    assert "Restart the transaction with ENQ" in findings[1].corrective_action
    assert "automatic profile switch" in findings[1].corrective_action


def test_phonesuite_pms_timing_rejects_negative_observations() -> None:
    with pytest.raises(ValueError, match="enq_ack_to_stx_seconds"):
        diagnose_phonesuite_pms_receive_timing(enq_ack_to_stx_seconds=-0.001)
    with pytest.raises(ValueError, match="max_inter_byte_gap_seconds"):
        diagnose_phonesuite_pms_receive_timing(max_inter_byte_gap_seconds=-0.001)
