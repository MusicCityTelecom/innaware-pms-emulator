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


def ci_acceptance():
    return {
        "source_sha": EMU_SHA,
        "test": {
            "workflow": "Test",
            "result": "pass",
            "runner_job_count": 4,
            "zero_step_job_count": 0,
            "required_matrix": [
                {"os": "ubuntu-latest", "python": "3.11", "result": "pass", "test_step_executed": True},
                {"os": "ubuntu-latest", "python": "3.13", "result": "pass", "test_step_executed": True},
                {"os": "windows-latest", "python": "3.11", "result": "pass", "test_step_executed": True},
                {"os": "windows-latest", "python": "3.13", "result": "pass", "test_step_executed": True},
            ],
        },
        "windows_build": {
            "workflow": "Windows Build",
            "result": "pass",
            "runner_job_count": 1,
            "zero_step_job_count": 0,
            "exact_source_checkout_verified": True,
            "build_step_executed": True,
            "artifact_upload_executed": True,
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


def build(*, ci=None, windows=None, exchange=None):
    return build_field_candidate_closure(
        expected_source_sha=EMU_SHA,
        artifact_manifest=artifact_manifest(),
        ci_acceptance=ci_acceptance() if ci is None else ci,
        windows_acceptance=windows_acceptance() if windows is None else windows,
        ucp_exchange=ucp_exchange() if exchange is None else exchange,
    )


def test_complete_candidate_evidence_is_ready_without_authorizing_release_or_promotion():
    result = build()
    assert result["closure_ready"] is True
    assert result["ci_classification"] == "PASS"
    assert result["blockers"] == []
    assert all(result["minimum_release_gates"].values())
    assert result["claim_policy"]["production_release_authorized"] is False
    assert result["claim_policy"]["compatibility_matrix_mutation_authorized"] is False
    assert result["claim_policy"]["no_runner_or_zero_step_actions_can_pass"] is False
    assert result["architectural_boundary"]["runtime_dependency_between_projects_allowed"] is False


def test_wrong_exact_emulator_sha_fails_closed():
    windows = windows_acceptance()
    windows["source_sha"] = "b" * 40
    result = build(windows=windows)
    codes = {item["code"] for item in result["blockers"]}
    assert result["closure_ready"] is False
    assert "windows-acceptance-source-sha-mismatch" in codes


def test_windows_evidence_must_match_exact_executable_and_visual_surfaces():
    windows = windows_acceptance()
    windows["executable_sha256"] = "8" * 64
    windows["browser"]["screenshot_sha256"] = ""
    result = build(windows=windows)
    codes = {item["code"] for item in result["blockers"]}
    assert "windows-executable-hash-mismatch" in codes
    assert "windows-browser-screenshot-hash-invalid" in codes


def test_production_or_server5_use_is_rejected():
    exchange = ucp_exchange()
    exchange["production_pms_traffic"] = True
    exchange["server5_used"] = True
    result = build(exchange=exchange)
    codes = {item["code"] for item in result["blockers"]}
    assert "production-pms-traffic-prohibited" in codes
    assert "ucp-server5-prohibited" in codes


def test_cross_project_runtime_coupling_is_rejected():
    exchange = ucp_exchange()
    exchange["ucp_runtime_dependency_on_emulator"] = True
    result = build(exchange=exchange)
    codes = {item["code"] for item in result["blockers"]}
    assert "ucp-runtime-coupling-prohibited" in codes


def test_no_runner_test_workflow_is_infrastructure_blocked_never_pass():
    ci = ci_acceptance()
    ci["test"]["runner_job_count"] = 0
    ci["test"]["required_matrix"] = []
    result = build(ci=ci)
    assert result["closure_ready"] is False
    assert result["ci_classification"] == "INFRASTRUCTURE_BLOCKED"
    assert result["minimum_release_gates"]["exact_head_ci"] is False
    codes = {item["code"] for item in result["blockers"]}
    assert "ci-test-infrastructure-blocked" in codes
    assert "ci-test-matrix-infrastructure-blocked" in codes


def test_zero_step_windows_build_is_infrastructure_blocked_never_pass():
    ci = ci_acceptance()
    ci["windows_build"]["zero_step_job_count"] = 1
    result = build(ci=ci)
    assert result["closure_ready"] is False
    assert result["ci_classification"] == "INFRASTRUCTURE_BLOCKED"
    codes = {item["code"] for item in result["blockers"]}
    assert "ci-windows-build-zero-step-infrastructure-blocked" in codes


def test_unexecuted_required_test_step_is_infrastructure_blocked():
    ci = ci_acceptance()
    ci["test"]["required_matrix"][2]["test_step_executed"] = False
    result = build(ci=ci)
    assert result["ci_classification"] == "INFRASTRUCTURE_BLOCKED"
    codes = {item["code"] for item in result["blockers"]}
    assert "ci-test-step-infrastructure-blocked" in codes


def test_executed_test_failure_is_fail_not_infrastructure_blocked():
    ci = ci_acceptance()
    ci["test"]["result"] = "fail"
    ci["test"]["required_matrix"][1]["result"] = "fail"
    result = build(ci=ci)
    assert result["closure_ready"] is False
    assert result["ci_classification"] == "FAIL"
    codes = {item["code"] for item in result["blockers"]}
    assert "ci-test-not-pass" in codes
    assert "ci-test-matrix-not-pass" in codes


def test_ci_source_mismatch_is_fail_not_pass():
    ci = ci_acceptance()
    ci["source_sha"] = "c" * 40
    result = build(ci=ci)
    assert result["ci_classification"] == "FAIL"
    assert "ci-source-sha-mismatch" in {item["code"] for item in result["blockers"]}
