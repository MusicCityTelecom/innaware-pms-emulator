import json
from pathlib import Path

from innaware_pms_emulator.personalities import PERSONALITIES


DATA = Path(__file__).parent / "data" / "emulation" / "compatibility_matrix.json"
ALLOWED = {"supported", "partially_characterized", "capture_only", "incompatible"}


def test_compatibility_matrix_uses_explicit_non_overclaiming_statuses():
    matrix = json.loads(DATA.read_text(encoding="utf-8"))
    assert len(matrix) == 6
    assert {item["status"] for item in matrix} <= ALLOWED
    assert all(item["basis"] for item in matrix)
    assert any(item["status"] == "incompatible" for item in matrix)
    assert any(item["status"] == "capture_only" for item in matrix)


def test_requested_compatibility_combinations_are_present():
    matrix = json.loads(DATA.read_text(encoding="utf-8"))
    pairs = {(item["pms"], item["pbx"]) for item in matrix}
    assert {
        ("Opera FIAS", "Matrix SARVAM Opera"),
        ("Hilton/PEP", "Generic compatible FIAS PBX"),
        ("Mitel-compatible PMS", "Matrix Type 2"),
        ("OperaIP", "Voiceware"),
        ("PMS", "InnAware UCP"),
    } <= pairs


def test_capture_only_personalities_do_not_gain_false_protocol_support():
    assert PERSONALITIES["pbx-matrix-type1"].maturity == "capture"
    assert PERSONALITIES["pbx-matrix-extended-starlight"].maturity == "capture"
    assert PERSONALITIES["pbx-innaware-ucp"].maturity == "planned"
