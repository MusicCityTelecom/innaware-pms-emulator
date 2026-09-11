# PhoneSuite Serial Transaction Diagnostics

## Scope

This diagnostic belongs to the standalone InnAware PMS-PBX Emulator technician/support product. It characterizes one already-registered compatibility row only:

- PBX family: `PhoneSuite`
- PBX dialect: `MITEL 1-compatible`
- transport: `serial`
- PMS family: `legacy-hotel-pms`
- PMS protocol: `mitel-hospitality`
- direction: `PBX_TO_PMS`
- current status: `PARTIAL`
- current evidence class: `SIMULATOR_CHARACTERIZATION`

It is not an InnAware UCP Hospitality PMS Gateway runtime component and must not be imported into that product as a runtime dependency.

## Evidence boundary

The existing sanitized clean-room PhoneSuite serial fixture preserves three characterized PBX-to-emulator transactions:

1. `ENQ -> ACK -> STX CHK1 ... ETX -> ACK`
2. `ENQ -> ACK -> STX NAM2 ... ETX -> ACK`
3. `ENQ -> ACK -> STX CHK0 ... ETX -> ACK`

The diagnostic therefore treats only `CHK0`, `CHK1`, and `NAM2` as simulator-qualified opcodes for this exact directional row. Additional recognizable legacy-hotel records are retained as evidence candidates, not silently promoted to PhoneSuite PBX-to-PMS support.

The broader PhoneSuite PMS-to-PBX row has separate legacy-source evidence and remains a separate six-dimensional claim. This diagnostic does not transfer that stronger reverse-direction evidence into the simulator-derived PBX-to-PMS row.

## What the analyzer does

`src/innaware_pms_emulator/phonesuite_serial_diagnostics.py` accepts an ordered capture and correlates only a strict adjacent transaction:

```text
PBX -> emulator    ENQ
emulator -> PBX    ACK
PBX -> emulator    STX + CHK0|CHK1|NAM2 + ETX
emulator -> PBX    ACK or NAK
```

A strict transaction that ends in `ACK` is retained as accepted. A strict transaction that ends in `NAK` is retained as rejection evidence and produces an actionable finding, but a NAK is not interpreted as proof of checksum failure.

The analyzer also reports:

- characterized frames seen outside the exact ENQ/ACK transaction;
- qualified record opcodes seen with non-STX/ETX framing;
- ENQ answered with NAK;
- recognizable legacy-hotel opcodes outside the simulator-qualified `CHK0`/`CHK1`/`NAM2` set.

Reusable reports omit raw application payloads. They retain indexes, normalized direction, framing/control classification, record family/code/opcode, exact wire length, and SHA-256 of the observed wire bytes.

## Claims deliberately not made

This diagnostic does not qualify or infer:

- PhoneSuite-specific baud rate, data bits, parity, stop bits, or flow control;
- optional checksum algorithm, byte coverage, placement, or validation behavior;
- retry count or retry timing;
- a PhoneSuite TCP transport;
- Mitel TCP reconnect or timing behavior;
- support for additional PBX-to-PMS opcodes merely because another direction or family documents them;
- reverse-direction compatibility;
- real PhoneSuite hardware compatibility;
- compatibility promotion from `PARTIAL` to `SUPPORTED`.

Series2 TDMoE/PRI/Q.921/Q.931/D-channel/`0x0E` station programming is explicitly outside this PMS application-protocol diagnostic.

## CLI

Use a synthetic, redacted, or otherwise authorized capture:

```bash
python scripts/diagnose-phonesuite-serial.py \
  /tmp/phonesuite-serial-capture.json \
  --transport serial \
  --evidence-class simulator_characterization \
  --output /tmp/phonesuite-serial-report.json
```

Capture JSON may be a list or an object containing a `captures` list. Each entry may use `hex`, `text`, or byte-backed data accepted by the shared capture observer. `rx` is interpreted as PBX-to-emulator and `tx` as emulator-to-PBX for technician captures; the fixture-native `pbx_to_emulator` and `emulator_to_pbx` names are also accepted.

`--transport tcp` and `--transport unknown` fail closed. The present compatibility claim is serial; application framing is not permission to invent another transport.

## Technician interpretation

Before treating a result as field evidence, record the exact Emulator Git SHA and actual endpoint provenance. For a physical serial test also record the adapter/device plus baud, data bits, parity, stop bits, and flow control. Those settings are site observations until PhoneSuite-specific evidence qualifies broader defaults.

If the PBX-originated frame receives NAK, first preserve the exact sanitized frame and verify role/direction, ENQ/ACK sequencing, STX/ETX framing, and field layout. Do not label the result a checksum failure without independent evidence establishing the checksum contract.

If an opcode outside `CHK0`, `CHK1`, or `NAM2` appears, retain the report and sanitized wire evidence for review. A source-backed opcode in the separate PMS-to-PBX policy does not automatically establish the same opcode in PBX-to-PMS direction.

## Deterministic acceptance

The repository regression test consumes the existing sanitized fixture and requires all three characterized transactions to remain exact, accepted, payload-safe, and non-promoting. It also verifies NAK handling, framing mismatch diagnostics, uncharacterized-record handling, fail-closed transport selection, deterministic CLI output, and source-path privacy on read failure.

A safe Codex/Server3 software acceptance at an exact checked-out SHA is:

```bash
python -m pytest -q \
  tests/test_phonesuite_serial_diagnostics.py \
  tests/test_phonesuite_serial_characterization.py \
  tests/test_phonesuite_serial_session.py \
  tests/test_phonesuite_serial_runtime_integration.py \
  tests/test_phonesuite_serial_pty_integration.py \
  tests/test_compatibility_matrix.py \
  tests/test_transport_evidence_boundaries.py
```

No physical PBX or PMS is required to accept this software slice. A real hardware result must be tied to the exact SHA, endpoint model/version, explicit serial settings, authorization, direction, and a sanitized wire artifact before it is considered for compatibility review.

## UCP Hospitality PMS Gateway handoff

The separate InnAware UCP Hospitality PMS Gateway may reuse the sanitized fixture, the report schema, exact wire SHA-256 values, six-dimensional compatibility knowledge, and technician findings as data/test evidence. It must not import the Emulator package, FastAPI/operator console, session orchestration, storage, Windows launcher, or field-support lifecycle.

Evidence and fixtures may cross the project boundary; runtime responsibilities and release lifecycle do not.
