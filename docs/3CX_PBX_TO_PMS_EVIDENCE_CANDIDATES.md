# 3CX Mitel-SX2000 PBX-to-PMS evidence candidates

## Scope

This document belongs only to **InnAware PMS-PBX Emulator**, the standalone technician/installer PMS↔PBX interoperability and support tool. It does not add a production PMS runtime to InnAware UCP and does not authorize UCP to import Emulator code. Sanitized fixtures, exact wire digests, compatibility knowledge, and reviewed test evidence may be copied into the separate UCP Hospitality PMS Gateway's own tests as data only.

The existing registered 3CX compatibility row remains **PMS_TO_PBX / TCP / PARTIAL**. This slice does **not** register or promote a `PBX_TO_PMS` row. It adds a bounded diagnostic so a technician or Codex can collect the exact reverse-direction evidence needed for a later matrix decision.

## Source-backed facts

The public 3CX PMS protocol specification describes the Mitel-style PMS/System link as bidirectional and documents two application record families that the **system sends to the PMS**:

- **Message Registration (`MSG`)** — emitted when a hotel extension makes a trunk call so the PMS can update the room's outside-call count. The documentation states that its status/fee field is four bytes. The retrievable text does not expose enough of the rendered format diagram to justify exact field offsets, so the Emulator does not invent them.
- **Maid Status (`STS1` through `STS9`)** — generated from a room feature-code action. The documented meanings are Maid Present, Clean, Not Clean, Out of Service, To be Inspected, Occupied/Clean, Occupied/Not Clean, Vacant/Clean, and Vacant/Not Clean. The documented wire shape is STX + `STS` + status digit + space + station number (up to five digits) + ETX.

The same specification documents the PMS-to-system ENQ/ACK/STX-text-ETX/ACK sequence in detail. It does **not** provide enough direction-specific material in the retrievable text to justify implementing a 3CX-originated transaction state machine, retry budget, checksum contract, or timing contract from this reverse-direction slice. Control bytes observed around a reverse-direction record are therefore retained only as evidence candidates until a live capture establishes the order and timing.

The 3CX Hotel Services endpoint remains TCP and site-configured. One observed/configured port must never become a universal protocol default. The separate 3CX billing/CDR interface also remains outside this PMS application-protocol diagnostic; Message Registration is not permission to conflate those interfaces.

## Diagnostic

Use:

```bash
python scripts/diagnose-3cx-pbx-to-pms.py \
  /path/to/sanitized-capture.json \
  --transport tcp \
  --pbx-direction rx \
  --evidence-class packet_capture \
  --output /tmp/3cx-pbx-to-pms.json
```

`--pbx-direction` is mandatory because capture direction depends on where the capture was taken. The analyzer never decides endpoint role from an `MSG` or `STS` prefix.

Reusable JSON contains only capture indexes, endpoint-side classification, framing/control metadata, record family/code, exact wire length, SHA-256, bounded source qualification, findings, and technician actions. It does not copy the raw application payload.

The synthetic fixture:

```text
tests/fixtures/pbx/3cx_mitel_sx2000_pbx_to_pms_source_candidate.json
```

contains only the source-documented STX/ETX `STS2` (Clean) plus a synthetic station number. It is marked `candidate_only`, synthetic, guest-PII-free, and vendor-material-free. It is intentionally **not** in the consumer-neutral interop evidence pack yet because no exact PBX_TO_PMS matrix row exists.

## Fail-closed boundaries

The diagnostic intentionally keeps all of these false:

- transport inference;
- universal site-port inference;
- reverse handshake inference;
- reverse retry-policy inference;
- Message Registration field-layout inference;
- billing/CDR transport inference;
- automatic matrix registration;
- compatibility promotion;
- raw-payload embedding;
- Series2 TDMoE/PRI/Q.921/Q.931/D-channel/`0x0E` station-programming scope.

Mitel-compatible application syntax does not turn 3CX into a Mitel PBX. TCP remains separate from any serial evidence. Series2 station programming remains a separate PBX/signaling concern and is not PMS application protocol.

## Exact-SHA live acceptance for Codex

Codex should pin the exact Emulator SHA under test, then use an authorized lab/property endpoint and synthetic room data. Record the exact 3CX version/build, configured Hotel Services address/port, capture point, which direction is 3CX-originated, and any surrounding control bytes with timestamps.

A safe Maid Status acceptance sequence is:

1. Confirm Hotel Services is configured for Mitel SX2000 at the recorded TCP endpoint.
2. Use a synthetic test room/extension.
3. Trigger one documented maid status code, preferably `STS2` (Clean).
4. Capture the complete application exchange and preserve a sanitized copy.
5. Run the diagnostic with the correct `--pbx-direction`.
6. Require one `exact_maid_status_record` with matching SHA-256 and no raw payload in the report.
7. Retain surrounding ENQ/ACK/NAK/timing separately; do not convert those bytes into a reverse state-machine claim until reviewed.

For Message Registration, make a synthetic/authorized trunk call from the test room and retain a sanitized `MSG` frame. The current tool should classify it as source-direction-qualified while leaving `field_layout_qualified=false`. That capture is the evidence needed to define exact offsets without guessing from the omitted source diagram.

## Promotion decision

A future PBX_TO_PMS row should be considered only after exact-SHA live evidence establishes at least:

- real 3CX version/build and Hotel Services endpoint;
- actual system-originated STS and/or MSG wire bytes with synthetic/redacted data;
- exact application framing;
- endpoint direction;
- surrounding control-byte order and timing if a reverse transaction state machine will be implemented;
- reconnect behavior separately from application framing;
- Message Registration field layout before implementing MSG parsing/formatting beyond family recognition.

Until then, the authoritative matrix stays unchanged and the reverse direction remains unsupported by default.
