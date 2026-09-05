# Mitel-compatible half-duplex sequence diagnostics

`mitel_half_duplex_diagnostics.py` is a technician/support diagnostic for characterizing the application-session sequence used by the evidence-qualified Mitel-compatible hotel PMS profile. It is not a new PBX runtime personality and it does not collapse Mitel TCP and Mitel serial into one transport definition.

## Evidence boundary

Project issue #4 and `MITEL_HALF_DUPLEX_TRANSACTION_TIMING.md` record the current reference behavior from the public Mitel-compatible PMS specification evidence:

1. sender transmits `ENQ`;
2. receiver answers `ACK` or `NAK`;
3. after `ACK`, sender transmits one `STX + application record + ETX` frame;
4. receiver answers the completed frame with `ACK` or `NAK`;
5. after an application-frame rejection/non-acknowledgement, the PMS may retransmit the framed record three additional times without another `ENQ`.

The same source gives a three-second ACK/NAK response window. The diagnostic reports that value as reference metadata but deliberately sets `timing_assessed_by_this_analyzer=false`. A timestamped capture and exact endpoint qualification are required before making a timing conclusion.

These values are scoped to the selected Mitel-compatible application/session profile. They are **not** universal assertions about every Mitel model, firmware generation, serial implementation, TCP implementation, or third-party compatibility mode.

## What the diagnostic identifies

The analyzer intentionally uses strict, fail-closed correlation:

- an exact adjacent `TX ENQ -> RX ACK -> TX framed-record -> RX ACK` is counted as a high-confidence successful reference transaction;
- a `RX NAK` immediately after a transmitted application frame opens a possible record-retry chain;
- an identical framed record retransmitted after that NAK, with no intervening `ENQ`, is counted as a frame-only retry;
- retries one through three are inside the selected reference limit;
- a fourth retry (fifth total transmission of the same framed record) is reported as exceeding that reference limit;
- a new `ENQ` after a frame NAK is reported as a sequence deviation from the selected frame-only retry behavior, not as proof that the transport is wrong;
- a different frame after a NAK without a new ENQ is treated as ambiguous and requires capture-boundary review;
- a NAK immediately following `ENQ` is kept separate from an application-frame NAK.

The analyzer does not reconstruct missing packets or infer transaction success across unrelated capture elements. Its successful-transaction count is therefore a high-confidence lower bound.

## Payload and privacy handling

Reusable output does not embed the raw application record. A transmitted frame is represented by:

- capture index;
- SHA-256 of exact wire bytes;
- wire-byte length;
- observed framing classification;
- parser-recognized record family/code when available.

Technicians should still use synthetic or redacted captures for reusable artifacts. Guest names, room-associated PII, credentials, proprietary profile bodies, and vendor executables must not be committed.

## Transport remains separate

The CLI requires an explicit transport dimension: `tcp`, `serial`, or `unknown`.

For `serial`, the report tells the technician to record the actual adapter/device, baud, data bits, parity, stop bits, and flow control. It supplies no serial defaults and does not import TCP reconnect behavior.

For `tcp`, the report tells the technician to record endpoint roles, addresses, and the actual site port. A site port is not promoted into a universal protocol constant, and TCP stream fragmentation/coalescing/reconnect behavior remains a separate diagnostic concern.

For `unknown`, the report explicitly requires independent transport evidence. The application sequence alone cannot prove TCP or serial.

Series2 TDMoE/PRI/Q.921/Q.931/D-channel/`0x0E` station programming remains outside this PBX↔PMS application-protocol diagnostic.

## CLI

Use a synthetic/redacted JSON capture list or an object with a `captures` list:

```bash
python scripts/diagnose-mitel-half-duplex.py \
  /tmp/synthetic-capture.json \
  --transport serial \
  --evidence-class simulator_characterization \
  --output /tmp/mitel-half-duplex-report.json
```

The report is deterministic for identical input and options. Supported evidence classes preserve the project ranking vocabulary: `packet_capture`, `operator_confirmed`, `legacy_source_profile`, `simulator_characterization`, and `inference`.

## Interpreting findings

`record-retry-limit-exceeded` means the observed identical-frame rejection chain exceeded the selected reference of initial transmission plus three frame-only retries. It does **not** prove the peer is defective and does not authorize changing personality or transport.

`enq-reissued-before-record-retry` means the capture re-opened acquisition with `ENQ` after an application-frame NAK rather than immediately retransmitting the rejected frame. Compare the exact configured session policy and endpoint expectations before changing anything.

`frame-changed-after-nak-without-enq` is intentionally medium-confidence. It may indicate a changed transaction, incomplete capture, queue behavior, or a profile mismatch. The tool does not guess which explanation is correct.

A NAK proves rejection of a transaction, not its cause. Framing, record layout, checksum behavior, sequencing, and endpoint-specific policy must be tested independently and one variable at a time.

## Standalone Emulator / UCP boundary

This diagnostic belongs to the standalone InnAware PMS-PBX Emulator technician/support product. It does not become part of the InnAware UCP Hospitality PMS Gateway runtime.

A separate UCP project may consume the sanitized deterministic JSON report, frame SHA-256 values, six-dimensional compatibility dimensions, and evidence conclusions as test/diagnostic knowledge. It must not import the Emulator package, API/UI, session orchestration, storage, Windows launcher, or deployment lifecycle. Compatibility promotion remains a separate evidence review in each product.

## Safe Codex / Server3 acceptance

Pin the exact Emulator SHA under review, run the targeted regression suite plus the normal Server3 verifier, then execute only synthetic input unless a live test is separately authorized:

```bash
SHA="$(git rev-parse HEAD)"

test "$SHA" = "<expected-exact-40-character-sha>"

python -m pytest -q \
  tests/test_mitel_half_duplex_diagnostics.py \
  tests/test_transaction_rejection_diagnostics.py \
  tests/test_mitel_tcp_outbound_transaction_integration.py \
  tests/test_mitel_serial_session.py \
  tests/test_transport_evidence_boundaries.py

INNAWARE_PMS_REPO_DIR=/opt/innaware/innaware-pms-emulator \
  bash scripts/verify-server3.sh
```

A real PBX/PMS capture can strengthen evidence only when the result is tied to the exact Emulator SHA, endpoint model/firmware or PMS product/version, explicit transport settings/endpoints, direction, authorization, and a synthetic/redacted reusable wire artifact. Passing this diagnostic alone never changes a compatibility-matrix row to `SUPPORTED`.
