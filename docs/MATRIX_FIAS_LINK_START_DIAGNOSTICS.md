# Matrix MICROS Opera / FIAS Link-Start Diagnostics

This diagnostic is part of the standalone **InnAware PMS-PBX Emulator** technician/support tool. It characterizes PBX↔PMS interoperability evidence; it is not the InnAware UCP Hospitality PMS Gateway runtime and does not make UCP a dependency of the Emulator (or vice versa).

## Evidence boundary

The current Matrix claim is intentionally narrow and follows the project compatibility matrix:

- PBX family: `Matrix`
- PBX dialect/personality: `MICROS Opera / FIAS`
- transport: `tcp`
- PMS family: `Oracle/MICROS Opera`
- PMS protocol: `FIAS`
- direction: `PBX_TO_PMS`
- status: `PARTIAL`
- evidence class: `OPERATOR_CONFIRMED`

The qualified field observation is that a Matrix SARVAM UCS PBX initiated TCP toward the PMS and delivered a FIAS `LS` record using STX/ETX framing. The existing sanitized fixture deliberately does **not** claim a universal TCP port, post-`LS` progression, retry timing, ENQ/ACK behavior, guest-event support, or reverse-direction support.

Transport and application personality remain separate dimensions. STX/ETX-framed FIAS does not imply that a serial Matrix variant exists, and this diagnostic refuses `serial` or `unknown` for the current evidence-qualified row. Series2 TDMoE/PRI/Q.921/Q.931/D-channel/`0x0E` station programming is outside this diagnostic and outside PBX↔PMS application-protocol evidence.

## What the analyzer does

Run:

```bash
python scripts/diagnose-matrix-fias-link.py \
  /path/to/sanitized-capture.json \
  --transport tcp \
  --evidence-class operator_confirmed \
  --output /tmp/matrix-fias-link-report.json
```

Input may be a JSON list of capture records or an object containing a `captures` list. Capture items can use the same `direction` plus `hex`, `data`, or `text` forms accepted by the shared diagnostic observer.

The report can identify:

1. inbound and outbound FIAS `LS` records;
2. strict adjacent `RX STX/ETX LS -> TX STX/ETX LS` pairs;
3. `LS` framing deviations such as a CR/LF reply where the qualified Matrix observation requires STX/ETX;
4. ENQ/ACK/NAK control bytes observed after link start as **new evidence candidates**, not assumed Matrix handshake semantics;
5. recognizable post-`LS` FIAS records as **new evidence candidates**;
6. `GI`, `GO`, and `GC` after `LS` as guest-event evidence candidates without claiming guest-event compatibility.

Reusable output contains only indexes, direction, wire SHA-256, wire length, framing, record family/code, confidence, findings, and technician actions. Application payload bytes are not embedded. Sanitized/redacted captures should still be used before retaining or sharing any report.

## Fail-closed rules

The analyzer does not:

- infer a serial Matrix transport;
- infer a protocol-standard Matrix TCP port;
- infer ENQ/ACK/NAK handshake semantics from observing control bytes;
- infer guest-event support merely because a recognizable FIAS guest record appears;
- infer PMS→PBX support from the current PBX→PMS row;
- switch personalities;
- modify the compatibility matrix;
- authorize compatibility promotion;
- embed raw application payloads;
- treat Series2 station programming as PMS application behavior.

A new post-`LS` record is evidence to review, not permission to widen the matrix. Any promoted or new row must still be explicit across PBX family × dialect × transport × PMS family × PMS protocol × direction, must carry the appropriate evidence class, and must satisfy the project readiness/fixture rules.

## Technician workflow

For an authorized live Matrix session, record the exact Emulator Git SHA and the exact PBX/PMS endpoint provenance. For TCP, record which endpoint initiated the connection, both endpoint addresses, and the actual site port. The site port is evidence for that deployment only unless stronger source evidence establishes otherwise.

Use synthetic guest names/room numbers when generating test traffic. For an existing field capture, redact guest-identifying values while preserving control bytes, framing, record codes, field ordering, lengths where relevant, and transaction ordering. Retain the original only in the authorized evidence location; do not commit it.

When `LS` succeeds but the link does not progress, capture enough timestamped traffic after `LS` to determine whether the peer sends another FIAS record, an ENQ/ACK/NAK control byte, closes TCP, or remains idle. The diagnostic report should be tied to the exact Emulator SHA plus the endpoint/product versions before it is considered for compatibility evidence expansion.

## Safe synthetic acceptance

This exercises the diagnostic without touching a PBX or PMS:

```bash
cat >/tmp/matrix-fias-link.json <<'JSON'
[
  {"direction":"rx","hex":"024c537c44413030303130317c54493030303030307c03"},
  {"direction":"tx","hex":"024c537c44413030303130317c54493030303030317c03"}
]
JSON

python scripts/diagnose-matrix-fias-link.py \
  /tmp/matrix-fias-link.json \
  --transport tcp \
  --evidence-class operator_confirmed \
  --output /tmp/matrix-fias-link-report.json
```

Expected boundaries include one exact link-start pair, STX/ETX framing in both directions, no raw `DA`/`TI` values in the output, and `compatibility_promotion_authorized=false`.

The following must fail closed because no evidence-qualified Matrix serial row exists:

```bash
python scripts/diagnose-matrix-fias-link.py \
  /tmp/matrix-fias-link.json \
  --transport serial \
  --evidence-class operator_confirmed
```

## Sharing with the UCP Hospitality PMS Gateway

The separate UCP Hospitality PMS Gateway may reuse the resulting **data-only knowledge** in its own tests: the six-dimensional combination, framing/record classifications, wire digests, observed sequence boundaries, and technician findings. It may also copy an explicitly sanitized synthetic fixture into its own test resources.

It should not import the Emulator Python package, FastAPI application, technician console, session/simulator orchestration, Windows launcher, Emulator storage, or deployment lifecycle. Evidence can cross the project boundary; runtime responsibilities do not.

## Evidence needed to widen Matrix support

The highest-value next Matrix evidence is a sanitized, timestamped session that continues beyond the known `LS`, tied to exact Emulator SHA and exact Matrix/PMS product versions. Useful observations include the next FIAS records, any control-character exchange, connection close/reopen behavior, retry timing, and guest-event transactions. Those observations should be admitted only for the exact direction and transport actually observed.
