from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

from innaware_pms_emulator.compatibility_matrix import Direction, SupportStatus
from innaware_pms_emulator.technician_acceptance import build_technician_acceptance_plan
from innaware_pms_emulator.technician_evidence_result import (
    AcceptanceResultStatus,
    build_technician_evidence_result,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
EXACT_SHA = "a" * 40
ARTIFACT_SHA = "b" * 64


def _mitel_serial_plan() -> dict:
    return build_technician_acceptance_plan(
        source_sha=EXACT_SHA,
        pbx_family="Mitel",
        transport="serial",
        pms_protocol="mitel-hospitality",
        direction=Direction.PMS_TO_PBX,
        statuses=(SupportStatus.PARTIAL,),
    )


def _serial_facts() -> dict[str, str]:
    return {
        "serial_device_or_adapter": "lab-usb-serial-01",
        "baud_rate": "9600",
        "data_bits": "8",
        "parity": "none",
        "stop_bits": "1",
        "flow_control": "xon/xoff",
    }


def _pass_result(**overrides) -> dict:
    kwargs = {
        "source_sha": EXACT_SHA,
        "acceptance_plan": _mitel_serial_plan(),
        "result_status": AcceptanceResultStatus.PASS,
        "transport_facts": _serial_facts(),
        "observation_codes": [
            "transport_opened",
            "handshake_success",
            "frame_acknowledged",
        ],
        "wire_artifact_sha256s": [ARTIFACT_SHA],
        "deterministic_tests_passed": True,
        "exact_head_test_matrix_green": True,
        "exact_head_windows_build_green": True,
        "operator_authorized": True,
        "synthetic_or_redacted_wire_bytes": True,
        "guest_pii_present": False,
    }
    kwargs.update(overrides)
    return build_technician_evidence_result(**kwargs)


def test_pass_result_is_deterministic_exact_row_data_only_and_non_promoting() -> None:
    first = _pass_result()
    second = _pass_result()

    assert first == second
    assert first["producer"]["source_sha"] == EXACT_SHA
    assert len(first["acceptance_plan_sha256"]) == 64
    assert first["combination"] == _mitel_serial_plan()["rows"][0]["combination"]
    assert first["combination"]["direction"] == Direction.PMS_TO_PBX.value
    assert first["current_claim"]["status"] == SupportStatus.PARTIAL.value
    assert first["result"]["status"] == AcceptanceResultStatus.PASS.value
    assert first["result"]["wire_artifact_sha256s"] == [ARTIFACT_SHA]
    assert first["architectural_boundary"]["exchange_mode"] == "data_only"
    assert first["architectural_boundary"]["runtime_dependency_on_emulator"] is False
    assert first["claim_policy"]["compatibility_promotion_authorized"] is False
    assert first["claim_policy"]["matrix_mutation_authorized"] is False
    assert first["claim_policy"]["partial_or_planned_pass_is_not_production_support"] is True
    assert first["claim_policy"]["raw_capture_or_vendor_profile_embedded"] is False
    assert first["claim_policy"]["series2_tdmoe_pri_station_programming_in_scope"] is False
    assert first["consumer_exchange"]["ucp_runtime_dependency_allowed"] is False
    assert first["consumer_exchange"]["artifact_payload_is_digest_only"] is True


def test_serial_result_requires_exact_transport_fact_set_without_defaults() -> None:
    facts = _serial_facts()
    facts.pop("flow_control")
    with pytest.raises(ValueError, match="transport facts must match"):
        _pass_result(transport_facts=facts)

    facts = _serial_facts()
    facts["tcp_port"] = "5001"
    with pytest.raises(ValueError, match="transport facts must match"):
        _pass_result(transport_facts=facts)


def test_tcp_result_requires_endpoint_roles_and_site_addresses_separately() -> None:
    plan = build_technician_acceptance_plan(
        source_sha=EXACT_SHA,
        pbx_family="Matrix",
        transport="tcp",
        pms_protocol="FIAS",
        direction=Direction.PBX_TO_PMS,
        statuses=(SupportStatus.PARTIAL,),
    )
    result = build_technician_evidence_result(
        source_sha=EXACT_SHA,
        acceptance_plan=plan,
        result_status=AcceptanceResultStatus.PASS,
        transport_facts={
            "local_endpoint_role": "emulated-pms-listener",
            "remote_endpoint_role": "matrix-pbx-client",
            "local_address_and_port": "192.0.2.10:5001",
            "remote_address_and_port": "192.0.2.20:49152",
        },
        observation_codes=["transport_opened", "application_record_accepted"],
        wire_artifact_sha256s=[ARTIFACT_SHA],
        deterministic_tests_passed=True,
        exact_head_test_matrix_green=True,
        exact_head_windows_build_green=True,
        operator_authorized=True,
        synthetic_or_redacted_wire_bytes=True,
        guest_pii_present=False,
    )
    assert result["combination"]["transport"] == "tcp"
    assert set(result["result"]["transport_facts"]) == {
        "local_endpoint_role",
        "remote_endpoint_role",
        "local_address_and_port",
        "remote_address_and_port",
    }


def test_unknown_transport_hitachi_plan_cannot_record_wire_result() -> None:
    plan = build_technician_acceptance_plan(
        source_sha=EXACT_SHA,
        pbx_family="Hitachi",
        pms_protocol="EPIT-HIT",
        direction=Direction.PMS_TO_PBX,
        statuses=(SupportStatus.PLANNED,),
    )
    with pytest.raises(ValueError, match="evidence-unqualified transport"):
        build_technician_evidence_result(
            source_sha=EXACT_SHA,
            acceptance_plan=plan,
            result_status=AcceptanceResultStatus.INCONCLUSIVE,
            transport_facts={"transport_evidence_source": "profile-sha256"},
            observation_codes=["no_wire_response"],
            wire_artifact_sha256s=[ARTIFACT_SHA],
            deterministic_tests_passed=False,
            exact_head_test_matrix_green=True,
            exact_head_windows_build_green=True,
            operator_authorized=True,
            synthetic_or_redacted_wire_bytes=True,
            guest_pii_present=False,
        )


def test_result_requires_exactly_one_matrix_row() -> None:
    plan = build_technician_acceptance_plan(
        source_sha=EXACT_SHA,
        pbx_family="Mitel",
        transport="serial",
    )
    with pytest.raises(ValueError, match="exactly one compatibility row"):
        _pass_result(acceptance_plan=plan)


def test_pass_requires_green_exact_head_and_protocol_success_without_failure_codes() -> None:
    with pytest.raises(ValueError, match="green exact-head"):
        _pass_result(exact_head_windows_build_green=False)
    with pytest.raises(ValueError, match="protocol-level success"):
        _pass_result(observation_codes=["transport_opened", "reconnect_observed"])
    with pytest.raises(ValueError, match="cannot contain failure"):
        _pass_result(observation_codes=["handshake_success", "frame_rejected"])


def test_fail_requires_failure_observation_and_yields_actionable_diagnostic() -> None:
    with pytest.raises(ValueError, match="fail requires"):
        _pass_result(
            result_status=AcceptanceResultStatus.FAIL,
            deterministic_tests_passed=False,
            observation_codes=["transport_opened"],
        )

    result = _pass_result(
        result_status=AcceptanceResultStatus.FAIL,
        deterministic_tests_passed=False,
        observation_codes=["transport_opened", "handshake_timeout"],
    )
    assert result["result"]["status"] == "fail"
    joined = " ".join(result["technician_diagnostics"]).casefold()
    assert "direction" in joined
    assert "do not borrow timing" in joined


def test_result_rejects_unredacted_pii_unpinned_source_or_bad_artifact_hash() -> None:
    with pytest.raises(ValueError, match="guest PII"):
        _pass_result(guest_pii_present=True)
    with pytest.raises(ValueError, match="synthetic_or_redacted"):
        _pass_result(synthetic_or_redacted_wire_bytes=False)
    with pytest.raises(ValueError, match="operator_authorized"):
        _pass_result(operator_authorized=False)
    with pytest.raises(ValueError, match="exact 40-character"):
        _pass_result(source_sha="abc1234")
    with pytest.raises(ValueError, match="64-character SHA-256"):
        _pass_result(wire_artifact_sha256s=["bad-digest"])


def test_cli_is_byte_deterministic_and_matches_library(tmp_path: Path) -> None:
    plan = _mitel_serial_plan()
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    script = REPO_ROOT / "scripts" / "record-technician-evidence-result.py"
    output1 = tmp_path / "result-1.json"
    output2 = tmp_path / "result-2.json"

    argv = [
        sys.executable,
        str(script),
        "--source-sha",
        EXACT_SHA,
        "--plan",
        str(plan_path),
        "--result",
        "pass",
        "--transport-fact",
        "serial_device_or_adapter=lab-usb-serial-01",
        "--transport-fact",
        "baud_rate=9600",
        "--transport-fact",
        "data_bits=8",
        "--transport-fact",
        "parity=none",
        "--transport-fact",
        "stop_bits=1",
        "--transport-fact",
        "flow_control=xon/xoff",
        "--observation",
        "transport_opened",
        "--observation",
        "handshake_success",
        "--wire-artifact-sha256",
        ARTIFACT_SHA,
        "--deterministic-tests-passed",
        "--exact-head-test-matrix-green",
        "--exact-head-windows-build-green",
        "--operator-authorized",
        "--synthetic-or-redacted-wire-bytes",
        "--no-guest-pii",
    ]

    for output in (output1, output2):
        completed = subprocess.run(
            [*argv, "--output", str(output)],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        assert completed.returncode == 0, completed.stderr

    assert output1.read_bytes() == output2.read_bytes()
    cli_result = json.loads(output1.read_text(encoding="utf-8"))
    direct_result = _pass_result(
        observation_codes=["transport_opened", "handshake_success"],
    )
    assert cli_result == direct_result


def test_cli_wrong_source_sha_fails_without_creating_output(tmp_path: Path) -> None:
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(_mitel_serial_plan()), encoding="utf-8")
    output = tmp_path / "must-not-exist.json"
    script = REPO_ROOT / "scripts" / "record-technician-evidence-result.py"
    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            "--source-sha",
            "c" * 40,
            "--plan",
            str(plan_path),
            "--result",
            "inconclusive",
            "--output",
            str(output),
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 2
    assert "producer SHA does not match" in completed.stderr
    assert not output.exists()
