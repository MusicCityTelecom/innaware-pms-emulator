from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

from innaware_pms_emulator.compatibility_matrix import (
    COMPATIBILITY_MATRIX,
    Direction,
    SupportStatus,
)
from innaware_pms_emulator.interop_evidence_pack import EVIDENCE_RANK
from innaware_pms_emulator.technician_acceptance import build_technician_acceptance_plan


REPO_ROOT = Path(__file__).resolve().parents[1]
EXACT_SHA = "a" * 40


def _row_by(plan: dict, *, pbx_family: str, transport: str, direction: str) -> dict:
    matches = [
        row
        for row in plan["rows"]
        if row["combination"]["pbx_family"] == pbx_family
        and row["combination"]["transport"] == transport
        and row["combination"]["direction"] == direction
    ]
    assert len(matches) == 1
    return matches[0]


def test_default_plan_is_deterministic_data_only_and_matrix_complete() -> None:
    first = build_technician_acceptance_plan(source_sha=EXACT_SHA)
    second = build_technician_acceptance_plan(source_sha=EXACT_SHA)

    assert first == second
    assert first["producer"] == {
        "project": "InnAware PMS-PBX Emulator",
        "repository": "MusicCityTelecom/innaware-pms-emulator",
        "source_sha": EXACT_SHA,
    }
    assert first["architectural_boundary"]["exchange_mode"] == "data_only"
    assert first["architectural_boundary"]["runtime_dependency_on_emulator"] is False
    assert first["evidence_rank"] == [item.value for item in EVIDENCE_RANK]
    assert len(first["rows"]) == len(COMPATIBILITY_MATRIX)

    expected = {
        (
            entry.pbx_family,
            entry.pbx_dialect,
            entry.transport,
            entry.pms_family,
            entry.pms_protocol,
            entry.direction.value,
        )
        for entry in COMPATIBILITY_MATRIX
    }
    actual = {
        (
            row["combination"]["pbx_family"],
            row["combination"]["pbx_dialect"],
            row["combination"]["transport"],
            row["combination"]["pms_family"],
            row["combination"]["pms_protocol"],
            row["combination"]["direction"],
        )
        for row in first["rows"]
    }
    assert actual == expected
    assert all(
        row["acceptance"]["compatibility_promotion_authorized"] is False
        for row in first["rows"]
    )


def test_serial_acceptance_requires_explicit_transport_facts_without_defaults() -> None:
    plan = build_technician_acceptance_plan(
        source_sha=EXACT_SHA,
        pbx_family="Mitel",
        transport="serial",
    )
    assert len(plan["rows"]) == 2

    required = {
        "serial_device_or_adapter",
        "baud_rate",
        "data_bits",
        "parity",
        "stop_bits",
        "flow_control",
    }
    for row in plan["rows"]:
        transport = row["acceptance"]["transport"]
        assert transport["wire_test_permitted"] is True
        assert set(transport["configuration_facts_to_record"]) == required
        joined = " ".join(transport["rules"]).casefold()
        assert "supplies no baud/parity/flow defaults" in joined
        assert "do not import tcp" in joined


def test_tcp_acceptance_keeps_endpoint_role_and_site_port_separate() -> None:
    plan = build_technician_acceptance_plan(
        source_sha=EXACT_SHA,
        transport="tcp",
    )
    assert plan["rows"]
    for row in plan["rows"]:
        transport = row["acceptance"]["transport"]
        assert transport["wire_test_permitted"] is True
        facts = set(transport["configuration_facts_to_record"])
        assert {"local_endpoint_role", "remote_endpoint_role"} <= facts
        assert {"local_address_and_port", "remote_address_and_port"} <= facts
        joined = " ".join(transport["rules"]).casefold()
        assert "site tcp port" in joined
        assert "do not transpose serial" in joined


def test_hitachi_unknown_transport_is_evidence_acquisition_only() -> None:
    plan = build_technician_acceptance_plan(
        source_sha=EXACT_SHA,
        pbx_family="Hitachi",
        statuses=(SupportStatus.PLANNED,),
    )
    assert len(plan["rows"]) == 2
    assert plan["global_rules"]["unknown_transport_wire_testing_allowed"] is False

    for row in plan["rows"]:
        assert row["combination"]["transport"] == "unknown"
        assert row["current_claim"]["status"] == SupportStatus.PLANNED.value
        assert row["acceptance"]["mode"] == "transport_evidence_acquisition_only"
        transport = row["acceptance"]["transport"]
        assert transport["wire_test_permitted"] is False
        assert transport["configuration_facts_to_record"] == ["transport_evidence_source"]
        assert "transport" in {gap["code"] for gap in row["evidence_gaps"]}
        assert row["acceptance"]["compatibility_promotion_authorized"] is False


def test_mitel_serial_directions_remain_distinct() -> None:
    plan = build_technician_acceptance_plan(
        source_sha=EXACT_SHA,
        pbx_family="Mitel",
        transport="serial",
    )
    outbound = _row_by(
        plan,
        pbx_family="Mitel",
        transport="serial",
        direction=Direction.PBX_TO_PMS.value,
    )
    inbound = _row_by(
        plan,
        pbx_family="Mitel",
        transport="serial",
        direction=Direction.PMS_TO_PBX.value,
    )
    assert outbound["current_claim"]["evidence_class"] != inbound["current_claim"]["evidence_class"]
    assert not any(
        row["combination"]["direction"] == Direction.BIDIRECTIONAL.value
        for row in plan["rows"]
    )
    for row in (outbound, inbound):
        joined = " ".join(row["acceptance"]["direction"]["rules"]).casefold()
        assert "do not manufacture the reverse direction" in joined


def test_nonexistent_exact_transport_filter_fails_closed() -> None:
    with pytest.raises(ValueError, match="no exact compatibility rows"):
        build_technician_acceptance_plan(
            source_sha=EXACT_SHA,
            pbx_family="Hitachi",
            transport="serial",
            pms_protocol="EPIT-HIT",
            direction=Direction.PMS_TO_PBX,
        )


def test_plan_rejects_unpinned_or_abbreviated_sha() -> None:
    for source_sha in ("", "abc1234", "not-a-sha", "a" * 39, "a" * 41):
        with pytest.raises(ValueError, match="exact 40-character Git commit SHA"):
            build_technician_acceptance_plan(source_sha=source_sha)


def test_cli_matches_library_and_is_byte_deterministic(tmp_path: Path) -> None:
    script = REPO_ROOT / "scripts" / "build-technician-acceptance-plan.py"
    output1 = tmp_path / "hitachi-acceptance-1.json"
    output2 = tmp_path / "hitachi-acceptance-2.json"
    argv = [
        sys.executable,
        str(script),
        "--source-sha",
        EXACT_SHA,
        "--pbx-family",
        "Hitachi",
        "--status",
        SupportStatus.PLANNED.value,
    ]

    for output in (output1, output2):
        result = subprocess.run(
            [*argv, "--output", str(output)],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr

    assert output1.read_bytes() == output2.read_bytes()
    cli_plan = json.loads(output1.read_text(encoding="utf-8"))
    direct_plan = build_technician_acceptance_plan(
        source_sha=EXACT_SHA,
        pbx_family="Hitachi",
        statuses=(SupportStatus.PLANNED,),
    )
    assert cli_plan == direct_plan


def test_cli_unmatched_filter_fails_without_creating_output(tmp_path: Path) -> None:
    script = REPO_ROOT / "scripts" / "build-technician-acceptance-plan.py"
    output = tmp_path / "must-not-exist.json"
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--source-sha",
            EXACT_SHA,
            "--pbx-family",
            "Hitachi",
            "--transport",
            "serial",
            "--pms-protocol",
            "EPIT-HIT",
            "--direction",
            Direction.PMS_TO_PBX.value,
            "--output",
            str(output),
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "no exact compatibility rows" in result.stderr
    assert not output.exists()
