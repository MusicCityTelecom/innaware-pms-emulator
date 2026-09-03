import hashlib

import pytest

from innaware_pms_emulator.legacy_profile_evidence import (
    MAX_PROFILE_BYTES,
    characterize_legacy_profile_bytes,
)


SYNTHETIC_HITACHI_PROFILE = b"""[pbx-protocol]\ndescription=Synthetic Epitome Hitachi characterization\nprotocol=EPIT-HIT\nfamily=HITACHI\nenq=5\nstx=0x02\netx=3\nack=6\nack2=6\nnak=21\nchecksum=0\nnameorder=FIRST_LAST\nCHK=CHK{status}{room}\nNAM=NAM{name}{room}\nsite_secret=must-not-leak\n\n[pbx-masks]\nchkdelim=11 20 MASK_LITERAL /\nnamdelim=6 20 MASK_LITERAL /\nnameindex0=2\nswapnames=false\nsite_secret=must-not-leak-either\n"""


def test_characterizer_extracts_only_evidence_whitelist_by_default():
    evidence = characterize_legacy_profile_bytes(
        SYNTHETIC_HITACHI_PROFILE,
        source_name="/authorized/lab/psip-pbx-protocol.EPIT-HIT",
    )
    payload = evidence.as_dict()

    assert evidence.source_name == "psip-pbx-protocol.EPIT-HIT"
    assert evidence.sha256 == hashlib.sha256(SYNTHETIC_HITACHI_PROFILE).hexdigest()
    assert evidence.evidence_class == "legacy_source_profile"
    assert evidence.profile_section == "pbx-protocol"
    assert evidence.mask_section == "pbx-masks"
    assert evidence.profile_identity["protocol"] == "EPIT-HIT"
    assert evidence.profile_identity["family"] == "HITACHI"
    assert evidence.control_bytes == {
        "enq": 5,
        "stx": 2,
        "etx": 3,
        "ack": 6,
        "ack2": 6,
        "nak": 21,
    }
    assert evidence.record_keys == ("CHK", "NAM")
    assert evidence.record_layouts == {}
    assert evidence.record_mask_keys == ("CHKDELIM", "NAMDELIM", "NAMEINDEX0", "SWAPNAMES")
    assert evidence.record_mask_layouts == {}
    assert evidence.unknown_key_count == 1
    assert evidence.unknown_mask_key_count == 1
    assert "site_secret" not in repr(payload)
    assert "must-not-leak" not in repr(payload)
    assert "must-not-leak-either" not in repr(payload)


def test_characterizer_does_not_infer_transport_or_generic_serial_defaults():
    evidence = characterize_legacy_profile_bytes(SYNTHETIC_HITACHI_PROFILE)

    assert evidence.transport == "unknown"
    assert evidence.transport_source == "none"
    assert evidence.serial_parameters == {}
    assert any("transport remains unqualified" in warning for warning in evidence.warnings)
    assert any("do not inherit generic serial defaults" in warning for warning in evidence.warnings)


def test_characterizer_accepts_only_explicit_transport_and_serial_values():
    evidence = characterize_legacy_profile_bytes(
        b"""[pbx-protocol]\nprotocol=SYNTHETIC\ntransport=RS-232\nbaud=9600\ndatabits=7\nparity=E\nstopbits=2\nflowcontrol=none\n"""
    )

    assert evidence.transport == "serial"
    assert evidence.transport_source == "explicit_profile_key"
    assert evidence.serial_parameters == {
        "baud_rate": 9600,
        "data_bits": 7,
        "parity": "E",
        "stop_bits": 2,
        "flow_control": "none",
    }


def test_record_layout_values_require_explicit_opt_in():
    evidence = characterize_legacy_profile_bytes(
        SYNTHETIC_HITACHI_PROFILE,
        include_record_layouts=True,
    )

    assert evidence.record_layouts == {
        "CHK": "CHK{status}{room}",
        "NAM": "NAM{name}{room}",
    }
    assert evidence.record_mask_layouts == {
        "CHKDELIM": "11 20 MASK_LITERAL /",
        "NAMEINDEX0": "2",
        "NAMDELIM": "6 20 MASK_LITERAL /",
        "SWAPNAMES": "false",
    }
    assert "site_secret" not in evidence.record_layouts
    assert "site_secret" not in evidence.record_mask_layouts


def test_pbx_mask_layouts_are_collected_from_their_own_section():
    evidence = characterize_legacy_profile_bytes(
        b"""[pbx-protocol]\nprotocol=EPIT-HIT2\n[pbx-masks]\nchkroom=4 3 MASK_NUMBER\nnamroom=8 3 MASK_NUMBER\nnamname=11 20 MASK_LITERAL\nunrelated_secret=redacted\n""",
        include_record_layouts=True,
    )

    assert evidence.profile_identity["protocol"] == "EPIT-HIT2"
    assert evidence.record_keys == ()
    assert evidence.record_mask_keys == ("CHKROOM", "NAMNAME", "NAMROOM")
    assert evidence.record_mask_layouts == {
        "CHKROOM": "4 3 MASK_NUMBER",
        "NAMNAME": "11 20 MASK_LITERAL",
        "NAMROOM": "8 3 MASK_NUMBER",
    }
    assert evidence.unknown_mask_key_count == 1
    assert "redacted" not in repr(evidence.as_dict())


def test_unrecognized_transport_fails_closed():
    evidence = characterize_legacy_profile_bytes(
        b"[pbx-protocol]\nprotocol=SYNTHETIC\ntransport=mystery-bus\n"
    )

    assert evidence.transport == "unknown"
    assert evidence.transport_source == "none"
    assert any("not recognized" in warning for warning in evidence.warnings)


def test_binary_and_oversized_inputs_are_rejected():
    with pytest.raises(ValueError, match="NUL"):
        characterize_legacy_profile_bytes(b"[pbx-protocol]\x00protocol=X")

    with pytest.raises(ValueError, match="safety limit"):
        characterize_legacy_profile_bytes(b"x" * (MAX_PROFILE_BYTES + 1))
