# Pre-admission candidate observation results

## Purpose

`record-candidate-observation.py` records deterministic, payload-safe evidence for an **exact six-dimensional PBX/PMS combination that is not yet registered in the compatibility matrix**.

This fills the gap between two existing states:

1. a combination has source or lab evidence worth retaining; and
2. a reviewed exact matrix row exists and can use the normal technician acceptance/result workflow.

The candidate workflow is intentionally incapable of producing a `pass`, registering a matrix row, or promoting compatibility. Its result statuses are only:

- `observed`
- `rejected`
- `inconclusive`

Every result remains `matrix_state.status=unsupported` until a separate manual evidence review justifies a narrowly scoped row.

## Architectural boundary

InnAware PMS-PBX Emulator remains the standalone technician/installer interoperability, simulation, capture-analysis, and diagnostic support tool.

InnAware UCP Hospitality PMS Gateway remains a separate production codebase/runtime. Candidate artifacts may be exchanged as **pre-admission data/test evidence only**. UCP must not import the Emulator Python package, FastAPI/operator UI, transport/session orchestration, capture store, Windows launcher, or Emulator deployment lifecycle.

The candidate document therefore declares:

- `exchange_mode=data_only`
- `runtime_dependency_on_emulator=false`
- `candidate_is_not_a_compatibility_claim=true`
- `ucp_runtime_dependency_allowed=false`

Candidate artifacts are not included in the normal interoperability fixture pack until an exact matrix row has been separately reviewed and registered.

## Fail-closed rules

A reusable candidate result requires all of the following:

- exact 40-character Emulator Git SHA;
- exact PBX family, dialect, transport, PMS family, PMS protocol, and direction;
- an **unregistered** exact/direction combination;
- an explicit `tcp` or `serial` transport — `unknown` cannot be used for wire evidence;
- the complete transport-fact set for that transport;
- evidence stronger than inference;
- explicit endpoint provenance;
- at least one SHA-256 of synthetic/redacted wire evidence;
- deterministic candidate diagnostic tests passing;
- green exact-head Test matrix and green exact-head Windows Build;
- explicit operator authorization;
- synthetic/redacted reusable bytes only; and
- no guest PII.

If an exact row already exists, or a registered `bidirectional` row already covers the requested direction, the command refuses the candidate and directs the operator to the normal technician acceptance/result workflow.

### TCP facts

TCP candidate evidence requires exactly:

- `local_endpoint_role`
- `remote_endpoint_role`
- `local_address_and_port`
- `remote_address_and_port`

No site port is inferred from application personality.

### Serial facts

Serial candidate evidence requires exactly:

- `serial_device_or_adapter`
- `baud_rate`
- `data_bits`
- `parity`
- `stop_bits`
- `flow_control`

No generic Voiceware/PhoneSuite/Mitel serial setting becomes a family-specific default merely because the field exists in a legacy configuration UI.

## 3CX PBX-to-PMS candidate

The current 3CX reverse direction is the primary reason for this workflow. Source evidence establishes system-originated `MSG` and `STS` behavior, and the bounded reverse analyzer can retain candidate observations, but the exact combination remains intentionally unregistered pending endpoint/capture evidence:

```text
3CX
× Hotel Module / Mitel SX2000-compatible
× tcp
× legacy-hotel-pms
× mitel-hospitality
× PBX_TO_PMS
= UNSUPPORTED candidate
```

The already-registered neighboring `PMS_TO_PBX` row remains a separate `PARTIAL / LEGACY_SOURCE_PROFILE` claim. Candidate recording must never transfer that row's direction, transaction behavior, or evidence strength into the reverse direction.

## Software-only acceptance

Pin the exact feature SHA first:

```bash
cd /opt/innaware/innaware-pms-emulator

git fetch origin \
  main \
  feature/pbx-emulation-v0.4.0 \
  codex/pbx-emulation-fixtures-v0.4.0

git checkout feature/pbx-emulation-v0.4.0
SHA="$(git rev-parse HEAD)"
test "${#SHA}" -eq 40

git diff --check
python -m pytest -q \
  tests/test_candidate_observation_result.py \
  tests/test_3cx_pbx_to_pms_diagnostics.py \
  tests/test_compatibility_matrix.py \
  tests/test_compatibility_readiness.py \
  tests/test_interop_evidence_pack.py \
  tests/test_transport_evidence_boundaries.py
```

Build the existing payload-safe 3CX reverse diagnostic from the synthetic candidate fixture:

```bash
python scripts/diagnose-3cx-pbx-to-pms.py \
  tests/fixtures/pbx/3cx_mitel_sx2000_pbx_to_pms_source_candidate.json \
  --transport tcp \
  --pbx-direction rx \
  --evidence-class legacy_source_profile \
  --output /tmp/3cx-reverse-diagnostic.json

WIRE_SHA256="$(sha256sum tests/fixtures/pbx/3cx_mitel_sx2000_pbx_to_pms_source_candidate.json | awk '{print $1}')"
DIAG_SHA256="$(sha256sum /tmp/3cx-reverse-diagnostic.json | awk '{print $1}')"
```

Record the synthetic pre-admission artifact:

```bash
python scripts/record-candidate-observation.py \
  --source-sha "$SHA" \
  --pbx-family "3CX" \
  --pbx-dialect "Hotel Module / Mitel SX2000-compatible" \
  --transport tcp \
  --pms-family "legacy-hotel-pms" \
  --pms-protocol "mitel-hospitality" \
  --direction pbx_to_pms \
  --result observed \
  --evidence-class legacy_source_profile \
  --transport-fact local_endpoint_role=emulator-pms-client \
  --transport-fact remote_endpoint_role=3cx-hotel-services-server \
  --transport-fact local_address_and_port=192.0.2.10:49152 \
  --transport-fact remote_address_and_port=192.0.2.20:5010 \
  --evidence-origin synthetic_replay \
  --observation transport_opened \
  --observation wire_bytes_observed \
  --observation application_record_observed \
  --wire-artifact-sha256 "$WIRE_SHA256" \
  --diagnostic-report-sha256 "$DIAG_SHA256" \
  --candidate-diagnostics-tests-passed \
  --exact-head-test-matrix-green \
  --exact-head-windows-build-green \
  --operator-authorized \
  --synthetic-or-redacted-wire-bytes \
  --no-guest-pii \
  --output /tmp/3cx-reverse-candidate-result.json
```

Verify the non-promotion boundary:

```bash
python - <<'PY'
import json
from pathlib import Path

p = json.loads(Path('/tmp/3cx-reverse-candidate-result.json').read_text())
assert p['combination']['direction'] == 'pbx_to_pms'
assert p['matrix_state']['status'] == 'unsupported'
assert p['matrix_state']['registered_exact_or_covering_row'] is False
assert p['result']['status'] == 'observed'
assert p['claim_policy']['matrix_registration_authorized'] is False
assert p['claim_policy']['compatibility_promotion_authorized'] is False
assert p['claim_policy']['candidate_must_not_enter_normal_interop_fixture_pack'] is True
assert p['consumer_exchange']['ucp_runtime_dependency_allowed'] is False
assert p['consumer_exchange']['candidate_is_not_a_compatibility_claim'] is True
print('candidate observation result: PASS')
PY
```

This software-only replay proves the evidence-result workflow, not 3CX reverse-direction interoperability.

## Authorized live 3CX acceptance for Codex

Live validation must be a separately authorized Codex/manual lab action; scheduled automation must not send traffic to a hotel PBX/PMS.

Pin the exact Emulator SHA and record:

- exact 3CX version/build;
- actual Hotel Services listener address and configured site port;
- local Emulator/PMS-side endpoint and role;
- which capture direction is 3CX-originated;
- synthetic test room/data only;
- a sanitized complete wire capture with timestamps; and
- SHA-256 of both the sanitized capture and payload-safe diagnostic report.

Recommended sequence:

1. trigger one Maid Status operation for a synthetic test room and capture the full system-to-PMS exchange;
2. run `diagnose-3cx-pbx-to-pms.py` against the sanitized capture;
3. record the candidate with `--evidence-class packet_capture`, `--evidence-origin real_pbx_lab`, the actual `--pbx-model` and `--pbx-firmware`, and the actual TCP transport facts;
4. separately trigger a synthetic outside-call scenario to capture `MSG` if authorized;
5. preserve surrounding ENQ/ACK/NAK/timing exactly rather than inferring a reverse state machine; and
6. review the resulting evidence manually before adding any exact PBX-to-PMS matrix row.

A source-backed `MSG` observation still does not qualify its complete field layout, reverse handshake timing, retry policy, checksum contract, TCP reconnect policy, or broad 3CX version/model scope unless the capture and endpoint evidence establish those facts.

## Hitachi boundary

The same candidate mechanism can retain a future **transport-specific** Hitachi/Epitome wire observation, but it must not be used to guess the transport. Current `EPIT-HIT` and `EPIT-HIT2` registry rows remain `transport=unknown` and `PLANNED` until the actual profile bodies or sanitized wire evidence establish transport/framing/layout facts.

A candidate result using `transport=serial` or `transport=tcp` is appropriate only after the evidence being referenced actually establishes that transport. Generic serial settings from the legacy Voiceware configuration UI are not Hitachi defaults.

## UCP evidence reuse

The separate UCP Hospitality PMS Gateway may consume a candidate JSON and its referenced sanitized evidence digests as research/test knowledge. It must treat `matrix_state.status=unsupported` and `candidate_is_not_a_compatibility_claim=true` as authoritative.

Once manual review creates an exact Emulator compatibility row, sanitized deterministic fixtures may enter the normal exact-SHA interoperability evidence pack and be copied into independent UCP tests. That promotion is a data-review step, not a runtime dependency between the two products.
