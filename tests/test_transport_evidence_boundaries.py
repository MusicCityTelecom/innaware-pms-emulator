from innaware_pms_emulator.compatibility_matrix import (
    Direction,
    EvidenceClass,
    SupportStatus,
    find_compatibility,
)


def test_hitachi_serial_near_miss_keeps_transport_unqualified() -> None:
    entry = find_compatibility(
        pbx_family="Hitachi",
        pbx_dialect="EPIT-HIT / Epitome Hitachi emulation",
        transport="serial",
        pms_family="Epitome",
        pms_protocol="EPIT-HIT",
        direction=Direction.PMS_TO_PBX,
    )

    assert entry.status is SupportStatus.UNSUPPORTED
    assert entry.evidence_class is EvidenceClass.NONE
    assert "transport remains evidence-unqualified" in entry.notes
    assert "Requested transport 'serial' is not verified" in entry.notes
    assert "Do not inherit generic serial/TCP settings" in entry.notes


def test_hitachi_tcp_near_miss_does_not_promote_profile_lineage() -> None:
    entry = find_compatibility(
        pbx_family="Hitachi",
        pbx_dialect="EPIT-HIT2 / Epitome Hitachi room-name layout variant",
        transport="tcp",
        pms_family="Epitome",
        pms_protocol="EPIT-HIT2",
        direction=Direction.PMS_TO_PBX,
    )

    assert entry.status is SupportStatus.UNSUPPORTED
    assert entry.evidence_class is EvidenceClass.NONE
    assert "Requested transport 'tcp' is not verified" in entry.notes
    assert "profile-bound transport evidence" in entry.notes


def test_matrix_serial_near_miss_reports_tcp_as_only_evidence_indexed_transport() -> None:
    entry = find_compatibility(
        pbx_family="Matrix",
        pbx_dialect="MICROS Opera / FIAS",
        transport="serial",
        pms_family="Oracle / MICROS Opera",
        pms_protocol="FIAS",
        direction=Direction.PBX_TO_PMS,
    )

    assert entry.status is SupportStatus.UNSUPPORTED
    assert entry.evidence_class is EvidenceClass.NONE
    assert "transport(s): tcp" in entry.notes
    assert "Requested transport 'serial' has no exact row" in entry.notes
    assert "Transport is a separate compatibility dimension" in entry.notes


def test_phonesuite_tcp_near_miss_does_not_inherit_serial_characterization() -> None:
    entry = find_compatibility(
        pbx_family="PhoneSuite",
        pbx_dialect="MITEL 1-compatible",
        transport="tcp",
        pms_family="legacy-hotel-pms",
        pms_protocol="mitel-hospitality",
        direction=Direction.PBX_TO_PMS,
    )

    assert entry.status is SupportStatus.UNSUPPORTED
    assert entry.evidence_class is EvidenceClass.NONE
    assert "transport(s): serial" in entry.notes
    assert "do not transpose framing, timing, handshake, or application behavior" in entry.notes


def test_unrelated_unknown_combination_keeps_generic_fail_closed_message() -> None:
    entry = find_compatibility(
        pbx_family="Unknown PBX",
        pbx_dialect="unknown",
        transport="tcp",
        pms_family="Unknown PMS",
        pms_protocol="unknown",
        direction=Direction.BIDIRECTIONAL,
    )

    assert entry.status is SupportStatus.UNSUPPORTED
    assert entry.evidence_class is EvidenceClass.NONE
    assert entry.notes == (
        "No verified compatibility row exists for this exact combination. "
        "Do not auto-select or infer a different profile."
    )
