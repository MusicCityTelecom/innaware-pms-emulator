# PMS Emulator field-candidate closure gate

This gate belongs only to **MusicCityTelecom/innaware-pms-emulator**. It is release/acceptance tooling for the standalone technician support product; it does not add protocol behavior and does not turn the Emulator into the InnAware UCP Hospitality PMS Gateway.

Feature breadth is frozen while field-product acceptance is incomplete. The closure gate therefore validates evidence instead of widening the compatibility matrix.

## Required evidence

Run all acceptance work in disposable environments and tie every result to the exact Emulator Git SHA being reviewed.

The closure builder requires four JSON inputs:

1. `artifact-manifest.json` — exact Emulator source SHA plus SHA-256/name entries for the hosted artifact bundle, field executable, installer, and exact-SHA interoperability evidence pack.
2. `ci-acceptance.json` — exact-head hosted Test and Windows Build execution evidence. PASS requires actual runner jobs and executed steps. A no-runner or zero-step Action is classified `INFRASTRUCTURE_BLOCKED` and can never satisfy the CI gate.
3. `windows-acceptance.json` — the exact executable SHA-256 plus separate native GUI and browser PASS results. Each surface must report health `ok`, product `InnAware PMS Emulator`, and the SHA-256 of a captured screenshot. Acceptance must use disposable data directories, disable telemetry/update checks, use no production endpoint or Server5, and leave no Emulator child process running after shutdown.
4. `ucp-exchange.json` — one synthetic end-to-end transaction between independent Emulator and UCP Hospitality Gateway processes/containers. It must record both exact Git SHAs, use loopback or a disposable private network, contain synthetic data and no guest PII, observe the already-implemented handshake and one bounded semantic transaction, and record the SHA-256 of the sanitized transcript.

The UCP side remains a separate production project. The exchange may share wire evidence and fixtures only; neither project may acquire a runtime dependency on the other.

## Build the exact artifact manifest first

Do not hand-transcribe candidate hashes. Build the artifact input directly from the exact hosted Windows artifact ZIP. The builder reads and hashes the archive without executing the EXE or installer, verifies the candidate release remains unpublished/prerelease, verifies the expected 0.4.x release identity carried by the archive, and requires the interoperability evidence producer SHA to equal the exact Emulator SHA.

```bash
python scripts/build-field-artifact-manifest.py \
  --source-sha "$EMU_SHA" \
  --artifact-zip /tmp/innaware-pms-emulator-windows-candidate.zip \
  --output /tmp/artifact-manifest.json
```

The generated manifest includes SHA-256 and byte size for the hosted artifact bundle, field EXE, installer, Windows ZIP, source ZIP, exact-SHA interop evidence JSON, protocol pack, and release manifest. This step is hash/provenance admission only; it does not execute or visually accept the Windows product.

## Build the closure manifest

```bash
python scripts/build-field-candidate-closure.py \
  --source-sha "$EMU_SHA" \
  --artifact-manifest /tmp/artifact-manifest.json \
  --ci-acceptance /tmp/ci-acceptance.json \
  --windows-acceptance /tmp/windows-acceptance.json \
  --ucp-exchange /tmp/ucp-exchange.json \
  --output /tmp/field-candidate-closure.json
```

Exit code `0` means all minimum candidate-closure evidence is coherent. Exit code `2` means at least one gate is blocked. `closure_ready=true` still does **not** authorize a production release or compatibility-matrix promotion; signing/public-release decisions remain separate.

## Exact-head CI evidence shape

```json
{
  "source_sha": "<exact Emulator SHA>",
  "test": {
    "workflow": "Test",
    "result": "pass",
    "runner_job_count": 4,
    "zero_step_job_count": 0,
    "required_matrix": [
      {"os": "ubuntu-latest", "python": "3.11", "result": "pass", "test_step_executed": true},
      {"os": "ubuntu-latest", "python": "3.13", "result": "pass", "test_step_executed": true},
      {"os": "windows-latest", "python": "3.11", "result": "pass", "test_step_executed": true},
      {"os": "windows-latest", "python": "3.13", "result": "pass", "test_step_executed": true}
    ]
  },
  "windows_build": {
    "workflow": "Windows Build",
    "result": "pass",
    "runner_job_count": 1,
    "zero_step_job_count": 0,
    "exact_source_checkout_verified": true,
    "build_step_executed": true,
    "artifact_upload_executed": true
  }
}
```

`ci_classification` has only three meanings:

- `PASS` — both workflows are tied to the exact source SHA, actual runners executed all required test/build/upload gates, and those gates passed.
- `FAIL` — required execution occurred but an exact-head test/build/provenance condition failed.
- `INFRASTRUCTURE_BLOCKED` — required runner or step execution is absent or incomplete. This state is never treated as PASS.

## Codex-safe Windows evidence shape

```json
{
  "source_sha": "<exact Emulator SHA>",
  "executable_sha256": "<64 hex>",
  "disposable_data_dirs": true,
  "telemetry_disabled": true,
  "update_checks_disabled": true,
  "production_endpoints_used": false,
  "server5_used": false,
  "child_processes_remaining": false,
  "native_gui": {
    "result": "pass",
    "health_status": "ok",
    "app_info_product": "InnAware PMS Emulator",
    "screenshot_sha256": "<64 hex>"
  },
  "browser": {
    "result": "pass",
    "health_status": "ok",
    "app_info_product": "InnAware PMS Emulator",
    "screenshot_sha256": "<64 hex>"
  }
}
```

## Codex-safe synthetic UCP exchange shape

```json
{
  "result": "pass",
  "emulator_source_sha": "<exact Emulator SHA>",
  "ucp_source_sha": "<exact UCP Gateway SHA>",
  "independent_processes": true,
  "loopback_or_disposable_private_network": true,
  "synthetic_data": true,
  "production_pms_traffic": false,
  "production_pbx_traffic": false,
  "guest_pii": false,
  "server5_used": false,
  "handshake_observed": true,
  "bounded_transaction_observed": true,
  "transcript_sha256": "<64 hex>",
  "emulator_runtime_dependency_on_ucp": false,
  "ucp_runtime_dependency_on_emulator": false
}
```

Use only an already-implemented common protocol path for the synthetic exchange. This closure task must not add a new protocol, transport, matrix row, or production behavior.
