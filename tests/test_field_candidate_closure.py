from innaware_pms_emulator.field_candidate_closure import build_field_candidate_closure

EMU_SHA = "5" * 40
UCP_SHA = "a" * 40
HASH_A = "1" * 64
HASH_B = "2" * 64
HASH_C = "3" * 64
HASH_D = "4" * 64
HASH_E = "5" * 64
HASH_F = "6" * 64
HASH_G = "7" * 64


def artifact_manifest():
    return {
        "source_sha": EMU_SHA,
        "artifacts": {
            "artifact_bundle": {"name": "candidate.zip", "sha256": HASH_A},
            "field_executable": {"name": "InnAware-PMS-Emulator.exe", "sha256": HASH_B},
            "installer": {"name": "InnAware-PMS-Emulator-Setup.exe", "sha256": HASH_C},
            "interop_evidence_pack": {"name": f"InnAware-PMS-Interop-Evidence-{EMU_SHA}.json", "sha256": HASH_D},
        },
    }


def windows_acceptance():
    return {
        "source_sha": EMU_SHA,
        "executable_sha256": HASH_B,
        "disposable_data_dirs": True,
        "telemetry_disabled": True,
        "update_checks_disabled": True,
        "production_endpoints_used": False,
        "server5_used": False,
        "child_processes_remaining": False,
        "native_gui": {
            "result": "pass",
            "health_status": "ok",
            "app_info_product": "InnAware PMS Emulator",
            "screenshot_sha256": HASH_E,
        },
        "browser": {
            "result": "pass",
            "health_status": "ok",
            "app_info_product": "InnAware PMS Emulator",
            "screenshot_sha256": HASH_F,
        },
    }


def ucp_exchange():
    return {
        "result": "pass",
        "emulator_source_sha": EMU_SHA,
        "ucp_source_sha": UCP_SHA,
        "independent_processes": True,
        "loopback_or_disposable_private_network": True,
        "synthetic_data": True,
        "production_pms_traffic": False,
        "production_pbx_traffic": False,
        "guest_pii": False,
        "server5_used": False,
        "handshake_observed": True,
        "bounded_transaction_observed": True,
        "transcript_sha256": HASH_G,
        "emulator_runtime_dependency_on_ucp": False,
        "ucp_runtime_dependency_on_emulator": False,
    }


def test_complete_candidate_evidence_is_ready_without_authorizing_release_or_promotion():
    result = build_field_candidate_closure(
        expected_source_sha=EMU_SHA,
        artifact_manifest=artifact_manifest(),
        windows_acceptance=windows_acceptance(),
        ucp_exchange=ucp_exchange(),
    )
    assert result["closure_ready"] is True
    assert result["blockers"] == []
    assert all(result["minimum_release_gates"].values())
    assert result["claim_policy"]["production_release_authorized"] is False
    assert result["claim_policy"]["compatibility_matrix_mutation_authorized"] is False
    assert result["architectural_boundary"]["runtime_dependency_between_projects_allowed"] is False


def test_wrong_exact_emulator_sha_fails_closed():
    windows = windows_acceptance()
    windows["source_sha"] = "b" * 40
    result = build_field_candidate_closure(
        expected_source_sha=EMU_SHA,
        artifact_manifest=artifact_manifest(),
        windows_acceptance=windows,
        ucp_exchange=ucp_exchange(),
    )
    codes = {item["code"] for item in result["blockers"]}
    assert result["closure_ready"] is False
    assert "windows-acceptance-source-sha-mismatch" in codes


def test_windows_evidence_must_match_exact_executable_and_visual_surfaces():
    windows = windows_acceptance()
    windows["executable_sha256"] = "8" * 64
    windows["browser"]["screenshot_sha256"] = ""
    result = build_field_candidate_closure(
        expected_source_sha=EMU_SHA,
        artifact_manifest=artifact_manifest(),
        windows_acceptance=windows,
        ucp_exchange=ucp_exchange(),
    )
    codes = {item["code"] for item in result["blockers"]}
    assert "windows-executable-hash-mismatch" in codes
    assert "windows-browser-screenshot-hash-invalid" in codes


def test_production_or_server5_use_is_rejected():
    exchange = ucp_exchange()
    exchange["production_pms_traffic"] = True
    exchange["server5_used"] = True
    result = build_field_candidate_closure(
        expected_source_sha=EMU_SHA,
        artifact_manifest=artifact_manifest(),
        windows_acceptance=windows_acceptance(),
        ucp_exchange=exchange,
    )
    codes = {item["code"] for item in result["blockers"]}
    assert "production-pms-traffic-prohibited" in codes
    assert "ucp-server5-prohibited" in codes


def test_cross_project_runtime_coupling_is_rejected():
    exchange = ucp_exchange()
    exchange["ucp_runtime_dependency_on_emulator"] = True
    result = build_field_candidate_closure(
        expected_source_sha=EMU_SHA,
        artifact_manifest=artifact_manifest(),
        windows_acceptance=windows_acceptance(),
        ucp_exchange=exchange,
    )
    codes = {item["code"] for item in result["blockers"]}
    assert "ucp-runtime-coupling-prohibited" in codes
