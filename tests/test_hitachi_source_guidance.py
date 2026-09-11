from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

from innaware_pms_emulator.hitachi_source_guidance import (
    build_hitachi_source_guidance,
)


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "diagnose-hitachi-source-lineage.py"
EXACT_SHA = "a" * 40


def test_hitachi_source_guidance_preserves_unknown_transport_and_planned_status() -> None:
    report = build_hitachi_source_guidance(
        source_sha=EXACT_SHA,
        pms_protocol="EPIT-HIT",
        symptom="baseline",
        requested_transport="serial",
    )

    assert report["producer"]["source_sha"] == EXACT_SHA
    assert report["combination"] == {
        "pbx_family": "Hitachi",
        "pbx_dialect": "EPIT-HIT / Epitome Hitachi emulation",
        "transport": "unknown",
        "pms_family": "Epitome",
        "pms_protocol": "EPIT-HIT",
        "direction": "pms_to_pbx",
    }
    assert report["current_matrix"]["status"] == "planned"
    assert report["current_matrix"]["transport"] == "unknown"
    assert report["requested_transport"] == {
        "value": "serial",
        "concrete_transport_requested": True,
        "evidence_qualified": False,
    }
    assert report["source_contract"]["hitachi_transport_stated_by_source"] is False
    assert report["source_contract"]["neighboring_profile_transport_must_not_be_inherited"] is True
    assert report["source_profile_hint"]["profile"] == "EPIT-HIT"
    assert report["source_profile_hint"]["auto_profile_change_authorized"] is False

    policy = report["claim_policy"]
    assert policy["transport_inferred"] is False
    assert policy["framing_inferred"] is False
    assert policy["record_offsets_inferred"] is False
    assert policy["compatibility_promotion_authorized"] is False
    assert policy["runtime_profile_auto_change_authorized"] is False
    assert policy["ucp_runtime_dependency_allowed"] is False
    assert policy["series2_station_programming_in_scope"] is False


@pytest.mark.parametrize("symptom", ["checkin_failure", "room_name_mismatch"])
def test_epit_hit2_is_only_a_source_profile_hint_for_documented_failure_modes(
    symptom: str,
) -> None:
    report = build_hitachi_source_guidance(
        source_sha=EXACT_SHA,
        pms_protocol="EPIT-HIT2",
        symptom=symptom,
        requested_transport="unknown",
    )

    assert report["source_profile_hint"]["profile"] == "EPIT-HIT2"
    assert "corrective" in report["source_profile_hint"]["reason"].lower()
    assert report["source_profile_hint"]["auto_profile_change_authorized"] is False
    assert report["source_contract"]["exact_record_offsets_stated_by_source"] is False
    assert report["claim_policy"]["source_profile_hint_is_compatibility_claim"] is False


def test_unknown_symptom_does_not_guess_profile_selection() -> None:
    report = build_hitachi_source_guidance(
        source_sha=EXACT_SHA,
        pms_protocol="EPIT-HIT2",
    )

    assert report["symptom"] == "unknown"
    assert report["source_profile_hint"]["profile"] is None
    assert report["requested_transport"]["value"] == "unknown"
    assert report["requested_transport"]["evidence_qualified"] is False


@pytest.mark.parametrize("transport", ["tcp", "tcp_client", "tcp_server", "serial"])
def test_concrete_transport_never_resolves_hitachi_transport_from_setup_source(
    transport: str,
) -> None:
    report = build_hitachi_source_guidance(
        source_sha=EXACT_SHA,
        pms_protocol="EPIT-HIT",
        requested_transport=transport,
    )

    assert report["combination"]["transport"] == "unknown"
    assert report["requested_transport"]["value"] == transport
    assert report["requested_transport"]["evidence_qualified"] is False
    assert report["claim_policy"]["transport_inferred"] is False


def test_invalid_inputs_fail_closed() -> None:
    with pytest.raises(ValueError, match="40-character"):
        build_hitachi_source_guidance(
            source_sha="abc",
            pms_protocol="EPIT-HIT",
        )
    with pytest.raises(ValueError, match="EPIT-HIT or EPIT-HIT2"):
        build_hitachi_source_guidance(
            source_sha=EXACT_SHA,
            pms_protocol="FIAS",
        )
    with pytest.raises(ValueError, match="symptom must be one of"):
        build_hitachi_source_guidance(
            source_sha=EXACT_SHA,
            pms_protocol="EPIT-HIT",
            symptom="guess",
        )
    with pytest.raises(ValueError, match="requested_transport"):
        build_hitachi_source_guidance(
            source_sha=EXACT_SHA,
            pms_protocol="EPIT-HIT",
            requested_transport="udp",
        )


def test_cli_emits_deterministic_payload_safe_data_only_guidance(tmp_path: Path) -> None:
    output = tmp_path / "hitachi-source-guidance.json"
    command = [
        sys.executable,
        str(SCRIPT),
        "--source-sha",
        EXACT_SHA,
        "--pms-protocol",
        "EPIT-HIT2",
        "--symptom",
        "checkin_failure",
        "--requested-transport",
        "tcp",
        "--output",
        str(output),
    ]

    first = subprocess.run(command, check=False, capture_output=True, text=True)
    assert first.returncode == 0, first.stderr
    first_bytes = output.read_bytes()

    second = subprocess.run(command, check=False, capture_output=True, text=True)
    assert second.returncode == 0, second.stderr
    assert output.read_bytes() == first_bytes

    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["architectural_boundary"] == {
        "exchange_mode": "data_only",
        "runtime_dependency_on_emulator": False,
        "ucp_runtime_dependency_allowed": False,
    }
    assert report["source_profile_hint"]["profile"] == "EPIT-HIT2"
    assert report["requested_transport"]["evidence_qualified"] is False
    assert report["claim_policy"]["compatibility_promotion_authorized"] is False
    raw = json.dumps(report).lower()
    assert "raw_profile" not in raw
    assert "psip-pbx-protocol." in raw
    assert "/usr/local/" not in raw
