from innaware_pms_emulator.personalities import (
    PERSONALITIES,
    get_personality,
    personality_catalog,
)


def _pbx_items():
    return [item for item in personality_catalog() if item["role"] == "pbx"]


def test_canonical_pbx_brand_catalog_contains_required_brands():
    names = {item["name"] for item in _pbx_items()}
    assert {
        "Mitel SX-200",
        "Mitel MiVoice",
        "PhoneSuite",
        "Matrix",
        "Hitachi",
        "InnAware UCP",
    } <= names


def test_mitel_wire_variants_are_not_exposed_as_pbx_brands():
    ids = {item["id"] for item in _pbx_items()}
    names = {item["name"] for item in _pbx_items()}
    assert "pbx-mitel-1" not in ids
    assert "pbx-mitel-2" not in ids
    assert "Mitel PBX - Type 1" not in names
    assert "Mitel PBX - Type 2" not in names


def test_mitel_family_lineage_is_explicit_for_non_hitachi_brands():
    for personality_id in (
        "pbx-mitel-sx200",
        "pbx-mitel-mivoice",
        "pbx-phonesuite",
        "pbx-matrix",
        "pbx-innaware-ucp",
    ):
        assert PERSONALITIES[personality_id].compatibility_family == "mitel_hospitality"

    assert PERSONALITIES["pbx-hitachi"].compatibility_family == "hitachi"


def test_phonesuite_retains_voiceware_operaip_as_profile_variant():
    phonesuite = PERSONALITIES["pbx-phonesuite"]
    assert "MITEL 1" in phonesuite.protocols
    assert "MITEL 2" in phonesuite.protocols
    assert "OPERAIP_FIAS" in phonesuite.protocols


def test_matrix_exposes_mitel_and_matrix_specific_modes():
    matrix = PERSONALITIES["pbx-matrix"]
    assert {"MITEL 1", "MITEL 2", "FIAS"} <= set(matrix.protocols)
    assert "MATRIX_TYPE1" in matrix.protocols
    assert "MATRIX_EXTENDED_STARLIGHT" in matrix.protocols


def test_hitachi_is_evidence_indexed_without_mitel_or_wire_assumptions():
    hitachi = PERSONALITIES["pbx-hitachi"]
    assert hitachi.maturity == "evidence-indexed"
    assert hitachi.protocols == ("EPIT-HIT", "EPIT-HIT2")
    assert "MITEL 1" not in hitachi.protocols
    assert "MITEL 2" not in hitachi.protocols
    assert hitachi.recommended_profile is None
    assert "byte-level wire behavior is not yet qualified" in hitachi.description
    assert any("do not infer framing" in note for note in hitachi.notes)


def test_development_aliases_resolve_to_normalized_brands():
    assert get_personality("pbx-mitel-1").id == "pbx-mitel-sx200"
    assert get_personality("pbx-mitel-2").id == "pbx-mitel-mivoice"
    assert get_personality("pbx-voiceware-operaip").id == "pbx-phonesuite"
    assert get_personality("pbx-matrix-sarvam-opera").id == "pbx-matrix"
    assert get_personality("pbx-matrix-type2").id == "pbx-matrix"
