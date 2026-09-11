from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_REQUIRED_TEST_MATRIX = {
    ("ubuntu-latest", "3.11"),
    ("ubuntu-latest", "3.13"),
    ("windows-latest", "3.11"),
    ("windows-latest", "3.13"),
}


def _canonical_sha256(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _valid_sha256(value: Any) -> bool:
    return isinstance(value, str) and bool(_SHA256_RE.fullmatch(value.lower()))


def _valid_git_sha(value: Any) -> bool:
    return isinstance(value, str) and bool(_GIT_SHA_RE.fullmatch(value.lower()))


def _block(blockers: list[dict[str, str]], code: str, detail: str) -> None:
    blockers.append({"code": code, "detail": detail})


def _positive_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _nonnegative_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _classify_ci_acceptance(
    *,
    expected_source_sha: str,
    ci_acceptance: Mapping[str, Any],
    blockers: list[dict[str, str]],
) -> str:
    """Validate exact-head Actions evidence without treating missing execution as PASS."""

    infrastructure_blocked = False
    functional_failure = False

    ci_source = str(ci_acceptance.get("source_sha", "")).lower()
    if ci_source != expected_source_sha:
        _block(
            blockers,
            "ci-source-sha-mismatch",
            f"CI acceptance must be tied to exact Emulator SHA {expected_source_sha}.",
        )
        functional_failure = True

    test = ci_acceptance.get("test")
    if not isinstance(test, Mapping):
        _block(blockers, "ci-test-infrastructure-blocked", "Test workflow evidence is missing.")
        infrastructure_blocked = True
    else:
        runner_count = test.get("runner_job_count")
        zero_step_count = test.get("zero_step_job_count")
        if not _positive_int(runner_count):
            _block(
                blockers,
                "ci-test-infrastructure-blocked",
                "Test workflow must show at least one actual runner job; no-runner Actions are INFRASTRUCTURE_BLOCKED.",
            )
            infrastructure_blocked = True
        if not _nonnegative_int(zero_step_count) or zero_step_count != 0:
            _block(
                blockers,
                "ci-test-zero-step-infrastructure-blocked",
                "Test workflow must contain zero zero-step jobs; zero-step Actions are INFRASTRUCTURE_BLOCKED.",
            )
            infrastructure_blocked = True

        matrix = test.get("required_matrix")
        seen: set[tuple[str, str]] = set()
        if not isinstance(matrix, list):
            _block(
                blockers,
                "ci-test-matrix-infrastructure-blocked",
                "Test workflow evidence must enumerate the required OS/Python matrix.",
            )
            infrastructure_blocked = True
        else:
            for item in matrix:
                if not isinstance(item, Mapping):
                    continue
                key = (str(item.get("os", "")), str(item.get("python", "")))
                if key in _REQUIRED_TEST_MATRIX:
                    seen.add(key)
                    if item.get("test_step_executed") is not True:
                        _block(
                            blockers,
                            "ci-test-step-infrastructure-blocked",
                            f"Required Test step did not execute for {key[0]} / Python {key[1]}.",
                        )
                        infrastructure_blocked = True
                    elif str(item.get("result", "")).lower() != "pass":
                        _block(
                            blockers,
                            "ci-test-matrix-not-pass",
                            f"Required Test step did not PASS for {key[0]} / Python {key[1]}.",
                        )
                        functional_failure = True
            missing = sorted(_REQUIRED_TEST_MATRIX - seen)
            if missing:
                rendered = ", ".join(f"{os_name}/py{python}" for os_name, python in missing)
                _block(
                    blockers,
                    "ci-test-matrix-infrastructure-blocked",
                    f"Required Test matrix entries are missing: {rendered}.",
                )
                infrastructure_blocked = True

        if str(test.get("result", "")).lower() != "pass":
            _block(blockers, "ci-test-not-pass", "Exact-head Test workflow did not PASS.")
            functional_failure = True

    windows = ci_acceptance.get("windows_build")
    if not isinstance(windows, Mapping):
        _block(blockers, "ci-windows-build-infrastructure-blocked", "Windows Build workflow evidence is missing.")
        infrastructure_blocked = True
    else:
        runner_count = windows.get("runner_job_count")
        zero_step_count = windows.get("zero_step_job_count")
        if not _positive_int(runner_count):
            _block(
                blockers,
                "ci-windows-build-infrastructure-blocked",
                "Windows Build must show at least one actual runner job; no-runner Actions are INFRASTRUCTURE_BLOCKED.",
            )
            infrastructure_blocked = True
        if not _nonnegative_int(zero_step_count) or zero_step_count != 0:
            _block(
                blockers,
                "ci-windows-build-zero-step-infrastructure-blocked",
                "Windows Build must contain zero zero-step jobs; zero-step Actions are INFRASTRUCTURE_BLOCKED.",
            )
            infrastructure_blocked = True

        if str(windows.get("result", "")).lower() != "pass":
            _block(blockers, "ci-windows-build-not-pass", "Exact-head Windows Build workflow did not PASS.")
            functional_failure = True
        if windows.get("exact_source_checkout_verified") is not True:
            _block(
                blockers,
                "ci-windows-exact-source-checkout-required",
                "Windows Build must execute and pass its exact-source checkout verification.",
            )
            functional_failure = True
        if windows.get("build_step_executed") is not True:
            _block(
                blockers,
                "ci-windows-build-step-infrastructure-blocked",
                "Windows field-product build step must actually execute.",
            )
            infrastructure_blocked = True
        if windows.get("artifact_upload_executed") is not True:
            _block(
                blockers,
                "ci-windows-artifact-upload-infrastructure-blocked",
                "Windows artifact-upload step must actually execute.",
            )
            infrastructure_blocked = True

    if infrastructure_blocked:
        return "INFRASTRUCTURE_BLOCKED"
    if functional_failure:
        return "FAIL"
    return "PASS"


def build_field_candidate_closure(
    *,
    expected_source_sha: str,
    artifact_manifest: Mapping[str, Any],
    ci_acceptance: Mapping[str, Any],
    windows_acceptance: Mapping[str, Any],
    ucp_exchange: Mapping[str, Any],
) -> dict[str, Any]:
    """Build a fail-closed field-product candidate closure record.

    This function validates evidence only. It does not contact a PBX/PMS/UCP
    runtime, mutate a compatibility row, authorize production release, or create
    a runtime dependency between the Emulator and InnAware UCP.
    """

    blockers: list[dict[str, str]] = []
    expected = expected_source_sha.lower() if isinstance(expected_source_sha, str) else ""
    if not _valid_git_sha(expected):
        _block(blockers, "invalid-expected-source-sha", "Expected Emulator source SHA must be exactly 40 lowercase hexadecimal characters.")

    ci_classification = _classify_ci_acceptance(
        expected_source_sha=expected,
        ci_acceptance=ci_acceptance,
        blockers=blockers,
    )

    artifact_source = str(artifact_manifest.get("source_sha", "")).lower()
    windows_source = str(windows_acceptance.get("source_sha", "")).lower()
    exchange_source = str(ucp_exchange.get("emulator_source_sha", "")).lower()
    for label, value in (
        ("artifact-manifest", artifact_source),
        ("windows-acceptance", windows_source),
        ("ucp-exchange", exchange_source),
    ):
        if value != expected:
            _block(blockers, f"{label}-source-sha-mismatch", f"{label} must be tied to exact Emulator SHA {expected}.")

    required_artifacts = ("artifact_bundle", "field_executable", "installer", "interop_evidence_pack")
    artifacts = artifact_manifest.get("artifacts")
    if not isinstance(artifacts, Mapping):
        _block(blockers, "artifact-manifest-missing-artifacts", "Artifact manifest must contain an artifacts object.")
        artifacts = {}
    for key in required_artifacts:
        item = artifacts.get(key) if isinstance(artifacts, Mapping) else None
        if not isinstance(item, Mapping):
            _block(blockers, f"artifact-{key}-missing", f"Required candidate artifact entry {key} is missing.")
            continue
        if not str(item.get("name", "")).strip():
            _block(blockers, f"artifact-{key}-name-missing", f"Required candidate artifact {key} must record its filename/name.")
        if not _valid_sha256(item.get("sha256")):
            _block(blockers, f"artifact-{key}-sha256-invalid", f"Required candidate artifact {key} must record a SHA-256 digest.")

    exe_digest = ""
    field_executable = artifacts.get("field_executable") if isinstance(artifacts, Mapping) else None
    if isinstance(field_executable, Mapping):
        exe_digest = str(field_executable.get("sha256", "")).lower()
    accepted_exe_digest = str(windows_acceptance.get("executable_sha256", "")).lower()
    if not _valid_sha256(accepted_exe_digest):
        _block(blockers, "windows-executable-sha256-invalid", "Windows acceptance must record the tested executable SHA-256.")
    elif exe_digest and accepted_exe_digest != exe_digest:
        _block(blockers, "windows-executable-hash-mismatch", "Windows GUI/browser acceptance did not test the manifest field executable.")

    if windows_acceptance.get("disposable_data_dirs") is not True:
        _block(blockers, "windows-disposable-data-required", "Windows acceptance must use disposable data directories.")
    if windows_acceptance.get("telemetry_disabled") is not True:
        _block(blockers, "windows-telemetry-must-be-disabled", "Candidate acceptance must disable telemetry.")
    if windows_acceptance.get("update_checks_disabled") is not True:
        _block(blockers, "windows-update-checks-must-be-disabled", "Candidate acceptance must disable update checks.")
    if windows_acceptance.get("production_endpoints_used") is not False:
        _block(blockers, "windows-production-endpoint-prohibited", "Candidate acceptance must not use production endpoints.")
    if windows_acceptance.get("server5_used") is not False:
        _block(blockers, "server5-prohibited", "Server5 is quarantined and must not be used for candidate acceptance.")
    if windows_acceptance.get("child_processes_remaining") is not False:
        _block(blockers, "windows-clean-shutdown-required", "Candidate acceptance must prove no Emulator child process remains after shutdown.")

    for surface in ("native_gui", "browser"):
        evidence = windows_acceptance.get(surface)
        if not isinstance(evidence, Mapping):
            _block(blockers, f"windows-{surface}-missing", f"Windows {surface} acceptance evidence is required.")
            continue
        if str(evidence.get("result", "")).lower() != "pass":
            _block(blockers, f"windows-{surface}-not-pass", f"Windows {surface} acceptance must explicitly PASS.")
        if str(evidence.get("health_status", "")).lower() != "ok":
            _block(blockers, f"windows-{surface}-health-not-ok", f"Windows {surface} acceptance must observe health status ok.")
        if evidence.get("app_info_product") != "InnAware PMS Emulator":
            _block(blockers, f"windows-{surface}-wrong-product", f"Windows {surface} acceptance must identify InnAware PMS Emulator.")
        if not _valid_sha256(evidence.get("screenshot_sha256")):
            _block(blockers, f"windows-{surface}-screenshot-hash-invalid", f"Windows {surface} acceptance must include a screenshot SHA-256.")

    if str(ucp_exchange.get("result", "")).lower() != "pass":
        _block(blockers, "ucp-exchange-not-pass", "Synthetic Emulator↔UCP Gateway exchange must explicitly PASS.")
    ucp_sha = str(ucp_exchange.get("ucp_source_sha", "")).lower()
    if not _valid_git_sha(ucp_sha):
        _block(blockers, "ucp-source-sha-invalid", "UCP Gateway source SHA must be an exact 40-character Git SHA.")
    if ucp_exchange.get("independent_processes") is not True:
        _block(blockers, "ucp-independent-processes-required", "Emulator and UCP Gateway must run as independent processes/containers.")
    if ucp_exchange.get("loopback_or_disposable_private_network") is not True:
        _block(blockers, "ucp-isolated-network-required", "Synthetic exchange must use loopback or a disposable private network.")
    if ucp_exchange.get("synthetic_data") is not True:
        _block(blockers, "ucp-synthetic-data-required", "Synthetic room/guest identifiers are mandatory.")
    if ucp_exchange.get("production_pms_traffic") is not False:
        _block(blockers, "production-pms-traffic-prohibited", "Production PMS traffic is prohibited during candidate closure.")
    if ucp_exchange.get("production_pbx_traffic") is not False:
        _block(blockers, "production-pbx-traffic-prohibited", "Production PBX traffic is prohibited during candidate closure.")
    if ucp_exchange.get("guest_pii") is not False:
        _block(blockers, "guest-pii-prohibited", "Candidate closure evidence must not contain guest PII.")
    if ucp_exchange.get("server5_used") is not False:
        _block(blockers, "ucp-server5-prohibited", "Server5 is quarantined and must not be used for synthetic exchange acceptance.")
    if ucp_exchange.get("handshake_observed") is not True:
        _block(blockers, "ucp-handshake-required", "Synthetic exchange must observe the already-implemented protocol handshake.")
    if ucp_exchange.get("bounded_transaction_observed") is not True:
        _block(blockers, "ucp-bounded-transaction-required", "Synthetic exchange must observe one bounded semantic transaction.")
    if not _valid_sha256(ucp_exchange.get("transcript_sha256")):
        _block(blockers, "ucp-transcript-sha256-invalid", "Synthetic exchange must record a sanitized transcript SHA-256.")
    if ucp_exchange.get("emulator_runtime_dependency_on_ucp") is not False:
        _block(blockers, "emulator-runtime-coupling-prohibited", "The Emulator must not acquire a runtime dependency on UCP.")
    if ucp_exchange.get("ucp_runtime_dependency_on_emulator") is not False:
        _block(blockers, "ucp-runtime-coupling-prohibited", "UCP Gateway must not acquire a runtime dependency on the Emulator.")

    closure_ready = not blockers
    return {
        "schema": "innaware-pms-emulator-field-candidate-closure/v2",
        "producer": {
            "project": "InnAware PMS-PBX Emulator",
            "source_sha": expected,
        },
        "closure_ready": closure_ready,
        "ci_classification": ci_classification,
        "blockers": blockers,
        "evidence": {
            "artifact_manifest_sha256": _canonical_sha256(artifact_manifest),
            "ci_acceptance_sha256": _canonical_sha256(ci_acceptance),
            "windows_acceptance_sha256": _canonical_sha256(windows_acceptance),
            "ucp_exchange_sha256": _canonical_sha256(ucp_exchange),
            "ucp_source_sha": ucp_sha,
            "tested_executable_sha256": accepted_exe_digest,
        },
        "minimum_release_gates": {
            "exact_head_ci": ci_classification == "PASS",
            "exact_source_artifacts": all(not item["code"].startswith("artifact-") and "source-sha-mismatch" not in item["code"] for item in blockers),
            "native_gui_acceptance": not any(item["code"].startswith("windows-native_gui-") for item in blockers),
            "browser_acceptance": not any(item["code"].startswith("windows-browser-") for item in blockers),
            "clean_shutdown": not any(item["code"] == "windows-clean-shutdown-required" for item in blockers),
            "synthetic_ucp_gateway_exchange": not any(item["code"].startswith("ucp-") or item["code"].startswith("production-") or item["code"].endswith("coupling-prohibited") for item in blockers),
        },
        "claim_policy": {
            "candidate_closure_is_not_protocol_promotion": True,
            "compatibility_matrix_mutation_authorized": False,
            "production_release_authorized": False,
            "production_pms_or_pbx_traffic_authorized": False,
            "server5_use_authorized": False,
            "no_runner_or_zero_step_actions_can_pass": False,
        },
        "architectural_boundary": {
            "emulator_project": "standalone_support_tool",
            "ucp_gateway_project": "separate_production_runtime",
            "exchange_mode": "data_and_wire_evidence_only",
            "runtime_dependency_between_projects_allowed": False,
        },
    }
