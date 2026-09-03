from innaware_pms_emulator.legacy_profile_compare import compare_legacy_profile_evidence
from innaware_pms_emulator.legacy_profile_evidence import characterize_legacy_profile_bytes


BASE_PROFILE = b"""[pbx-protocol]\nprotocol=EPIT-HIT\nfamily=HITACHI\nenq=5\nstx=2\netx=3\nack=6\nCHK=CHK{status}{room}\nNAM=NAM{name}{room}\nsite_secret=never-emit-base\n\n[pbx-masks]\nchkroom=4 3 MASK_NUMBER\nnamroom=8 3 MASK_NUMBER\nnamname=11 20 MASK_LITERAL\nnameindex0=1\nsite_secret=never-emit-mask-base\n"""

VARIANT_PROFILE = b"""[pbx-protocol]\nprotocol=EPIT-HIT2\nfamily=HITACHI\nenq=5\nstx=2\netx=3\nack=6\nCHK=CHK{status}{room}\nNAM=NAM{name}{room}\nsite_secret=never-emit-variant\n\n[pbx-masks]\nchkroom=4 3 MASK_NUMBER\nnamroom=4 3 MASK_NUMBER\nnamname=7 20 MASK_LITERAL\nnameindex0=2\nswapnames=true\nsite_secret=never-emit-mask-variant\n"""


def _characterize(data: bytes, name: str, *, layouts: bool = False):
    return characterize_legacy_profile_bytes(
        data,
        source_name=name,
        include_record_layouts=layouts,
    )


def test_default_delta_compares_safe_keys_without_claiming_layout_values():
    baseline = _characterize(BASE_PROFILE, "/lab/psip-pbx-protocol.EPIT-HIT")
    candidate = _characterize(VARIANT_PROFILE, "/lab/psip-pbx-protocol.EPIT-HIT2")

    delta = compare_legacy_profile_evidence(baseline, candidate)
    payload = delta.as_dict()

    assert delta.baseline_source_name == "psip-pbx-protocol.EPIT-HIT"
    assert delta.candidate_source_name == "psip-pbx-protocol.EPIT-HIT2"
    assert delta.baseline_sha256 == baseline.sha256
    assert delta.candidate_sha256 == candidate.sha256
    assert delta.evidence_class == "legacy_source_profile_delta"
    assert delta.profile_identity_changes["protocol"] == {
        "baseline": "EPIT-HIT",
        "candidate": "EPIT-HIT2",
    }
    assert delta.transport_change is None
    assert delta.control_byte_changes == {}
    assert delta.serial_parameter_changes == {}
    assert delta.record_keys_added == ()
    assert delta.record_keys_removed == ()
    assert delta.record_layout_changes == {}
    assert delta.record_mask_keys_added == ("SWAPNAMES",)
    assert delta.record_mask_keys_removed == ()
    assert delta.record_mask_layout_changes == {}
    assert any("record layout values were not compared" in item for item in delta.warnings)
    assert any("PBX mask layout values were not compared" in item for item in delta.warnings)
    assert "never-emit" not in repr(payload)


def test_opt_in_delta_isolates_sanitized_hitachi_mask_layout_changes():
    baseline = _characterize(
        BASE_PROFILE,
        "psip-pbx-protocol.EPIT-HIT",
        layouts=True,
    )
    candidate = _characterize(
        VARIANT_PROFILE,
        "psip-pbx-protocol.EPIT-HIT2",
        layouts=True,
    )

    delta = compare_legacy_profile_evidence(baseline, candidate)

    assert delta.record_layout_changes == {}
    assert delta.record_mask_layout_changes == {
        "NAMEINDEX0": {"baseline": "1", "candidate": "2"},
        "NAMNAME": {
            "baseline": "11 20 MASK_LITERAL",
            "candidate": "7 20 MASK_LITERAL",
        },
        "NAMROOM": {
            "baseline": "8 3 MASK_NUMBER",
            "candidate": "4 3 MASK_NUMBER",
        },
        "SWAPNAMES": {"baseline": None, "candidate": "true"},
    }
    assert not any("not compared" in item for item in delta.warnings)
    assert "never-emit" not in repr(delta.as_dict())


def test_transport_changes_require_explicit_profile_evidence():
    baseline = characterize_legacy_profile_bytes(
        b"[pbx-protocol]\nprotocol=BASE\ntransport=RS-232\nbaud=9600\n",
        source_name="base",
    )
    candidate = characterize_legacy_profile_bytes(
        b"[pbx-protocol]\nprotocol=VARIANT\ntransport=TCP client\n",
        source_name="variant",
    )

    delta = compare_legacy_profile_evidence(baseline, candidate)

    assert delta.transport_change == {
        "baseline": "serial",
        "candidate": "tcp_client",
        "baseline_source": "explicit_profile_key",
        "candidate_source": "explicit_profile_key",
    }
    assert delta.serial_parameter_changes == {
        "baud_rate": {"baseline": 9600, "candidate": None}
    }


def test_key_membership_delta_is_available_without_exposing_values():
    baseline = characterize_legacy_profile_bytes(
        b"[pbx-protocol]\nprotocol=BASE\nCHK=x\nNAM=y\n[pbx-masks]\nchkroom=a\n",
        source_name="base",
    )
    candidate = characterize_legacy_profile_bytes(
        b"[pbx-protocol]\nprotocol=VARIANT\nCHK=x\nRST=z\n[pbx-masks]\nnamroom=b\n",
        source_name="variant",
    )

    delta = compare_legacy_profile_evidence(baseline, candidate)

    assert delta.record_keys_added == ("RST",)
    assert delta.record_keys_removed == ("NAM",)
    assert delta.record_mask_keys_added == ("NAMROOM",)
    assert delta.record_mask_keys_removed == ("CHKROOM",)
    assert delta.record_layout_changes == {}
    assert delta.record_mask_layout_changes == {}
