# Technician Evidence Results

## Purpose

InnAware PMS-PBX Emulator is a standalone technician/installer interoperability and diagnostic product. It is not the InnAware UCP Hospitality PMS Gateway runtime. This workflow turns an exact-row technician acceptance plan into a deterministic evidence-result JSON artifact without sending traffic, changing the compatibility matrix, promoting support status, or creating a runtime dependency between the two products.

The intended flow is:

1. Build an acceptance plan for exactly one registered six-dimensional compatibility row.
2. Run the declared deterministic regressions and verify the exact-head GitHub Test matrix and Windows Build are green.
3. Exercise only that row's registered direction on operator-authorized lab/test equipment using synthetic or redacted wire data.
4. Hash the sanitized wire artifact; do not embed the capture, vendor profile, credentials, or guest PII in the result JSON.
5. Record normalized observations and every transport fact required by the acceptance plan.
6. Retain the deterministic result with the exact Emulator SHA for later evidence review or data-only downstream testing.

A passing result is evidence, not a compatibility promotion. `partial` and `planned` rows remain non-production claims until a separate reviewed repository change changes the matrix.

## Exact-row and transport boundaries

`record-technician-evidence-result.py` accepts only an acceptance plan containing exactly one compatibility row. This prevents a single observation from being applied to multiple personalities, transports, or directions.

For serial rows, the acceptance plan requires the explicit adapter/device identity, baud rate, data bits, parity, stop bits, and flow control. The result recorder supplies no serial defaults. Mitel TCP reconnect/timing evidence must not be copied into Mitel serial, PhoneSuite serial, or another serial personality.

For TCP rows, the plan requires local and remote endpoint roles separately from the observed address/port pairs. A site port remains installation evidence rather than a universal protocol constant.

Rows whose transport is still `unknown`, including the current Hitachi `EPIT-HIT` and `EPIT-HIT2` rows, cannot produce a wire-test result. The transport must first be established by separately reviewed profile/capture evidence and represented by an exact transport-specific matrix row.

Series2 TDMoE/PRI/Q.921/Q.931/D-channel/`0x0E` station programming is outside this workflow. It must never be used as PBX-PMS application-protocol evidence.

## Normalized observation codes

The result artifact intentionally avoids arbitrary technician free text so reusable evidence does not become a convenient place to leak guest or site-specific narrative data. Supported observation codes are:

- `transport_opened`
- `transport_open_failed`
- `handshake_success`
- `handshake_timeout`
- `frame_acknowledged`
- `frame_rejected`
- `application_record_accepted`
- `application_record_rejected`
- `reconnect_observed`
- `unexpected_wire_bytes`
- `no_wire_response`

A `pass` requires all of the following: the row's declared deterministic tests passed, the exact-head Test matrix is green, the exact-head Windows Build is green, at least one protocol-level success observation is present, and no failure observation is present. A `fail` requires at least one failure observation. `inconclusive` may be used when the observation is insufficient to call either outcome.

## Example: distinct Mitel serial PMS-to-PBX result

First build a single-row plan at the exact revision under test:

```bash
SHA="$(git rev-parse HEAD)"

python scripts/build-technician-acceptance-plan.py \
  --source-sha "$SHA" \
  --pbx-family Mitel \
  --transport serial \
  --pms-protocol mitel-hospitality \
  --direction pms_to_pbx \
  --status partial \
  --output /tmp/mitel-serial-pms-to-pbx-plan.json
```

After the exact-head CI/build gate is green and the authorized synthetic/redacted lab observation is complete, hash the sanitized artifact and record the result. The serial values below are examples only; use the values actually configured for the test endpoint.

```bash
WIRE_SHA256="$(sha256sum /tmp/sanitized-mitel-serial-wire.json | awk '{print $1}')"

python scripts/record-technician-evidence-result.py \
  --source-sha "$SHA" \
  --plan /tmp/mitel-serial-pms-to-pbx-plan.json \
  --result pass \
  --transport-fact serial_device_or_adapter=lab-usb-serial-01 \
  --transport-fact baud_rate=9600 \
  --transport-fact data_bits=8 \
  --transport-fact parity=none \
  --transport-fact stop_bits=1 \
  --transport-fact flow_control=xon/xoff \
  --observation transport_opened \
  --observation handshake_success \
  --observation frame_acknowledged \
  --wire-artifact-sha256 "$WIRE_SHA256" \
  --deterministic-tests-passed \
  --exact-head-test-matrix-green \
  --exact-head-windows-build-green \
  --operator-authorized \
  --synthetic-or-redacted-wire-bytes \
  --no-guest-pii \
  --output /tmp/mitel-serial-pms-to-pbx-result.json
```

The example does **not** assert that `9600 8N1 XON/XOFF` is a universal Mitel serial default. Those values are retained as explicit facts for that one observation only.

## Fail-closed examples

The result recorder rejects:

- an abbreviated or different producer SHA;
- a plan containing zero or multiple compatibility rows;
- a plan that permits compatibility promotion or violates the data-only project boundary;
- a wire result for a row with evidence-unqualified transport;
- missing or extra transport facts;
- an unknown observation code;
- an invalid or absent sanitized artifact SHA-256;
- a passing result when deterministic tests, exact-head Test, or Windows Build are red;
- a passing result that contains a failure observation or lacks protocol-level success;
- reusable evidence not explicitly marked operator-authorized and synthetic/redacted;
- reusable evidence marked as containing guest PII.

Failure observations produce bounded technician diagnostics. For example, a handshake timeout directs the technician to verify direction, handshake expectations, and exact transport facts without borrowing timing from another transport; a frame rejection directs comparison against the exact dialect framing/checksum evidence before changing field layout or retry behavior.

## Determinism and provenance

The result contains:

- exact 40-character Emulator source SHA;
- SHA-256 of the canonical acceptance plan;
- exact PBX family, dialect, transport, PMS family, PMS protocol, and direction;
- the current matrix status/evidence class without changing it;
- normalized explicit transport facts;
- normalized observation codes;
- SHA-256 digests of sanitized wire artifacts only;
- deterministic-test and exact-head CI/build gate booleans;
- fail-closed claim policy and technician diagnostics.

No timestamp is inserted by the recorder, so identical reviewed inputs produce byte-identical JSON when serialized by the CLI.

## Reuse by InnAware UCP Hospitality PMS Gateway

The UCP Hospitality PMS Gateway is a separate codebase, product, runtime, deployment, and release lifecycle. It may consume a reviewed technician result as **data or test evidence only**. For example, a UCP development test may use the exact combination metadata, observation codes, source SHA, and referenced sanitized fixture digest to decide which independent adapter regression to run.

UCP must not import `innaware_pms_emulator`, the Emulator FastAPI application, technician console, session/simulator orchestration, Windows launcher, storage model, or field-support lifecycle. The result contract explicitly states `runtime_dependency_on_emulator=false` and `ucp_runtime_dependency_allowed=false`.

Raw packet captures, raw vendor profile bodies, credentials, and guest PII are not part of this exchange. If UCP needs a reusable wire fixture, use a separately reviewed synthetic/redacted fixture whose digest matches the result rather than copying an original customer capture.

## Hitachi next step

The current `EPIT-HIT` and `EPIT-HIT2` matrix rows retain `transport=unknown`, so this result workflow correctly refuses a Hitachi wire result today. The next evidence step remains read-only acquisition of the historical `Epitome`, `EPIT-HIT`, and `EPIT-HIT2` textual profiles, followed by the existing sanitized profile evidence bundle and admission workflow. If those exact artifacts establish transport, a separate reviewed transport-specific matrix row is required before a technician wire result can be recorded.
