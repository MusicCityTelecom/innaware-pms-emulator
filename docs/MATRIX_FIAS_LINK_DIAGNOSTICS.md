# Matrix SARVAM UCS MICROS Opera / FIAS Link Diagnostics

This diagnostic belongs to the standalone **InnAware PMS-PBX Emulator** technician/support tool. It does not move Matrix/FIAS behavior into the InnAware UCP Hospitality PMS Gateway runtime and it creates no runtime dependency between the two projects.

## Evidence boundary

Project evidence contains an operator-observed Matrix SARVAM UCS MICROS Opera/FIAS TCP session that progressed beyond the previously retained Link Start (`LS`) sample. The session showed this bounded application-layer progression:

1. Matrix/PBX originated `LS` using STX/ETX framing.
2. The PMS endpoint replied with `LS` using STX/ETX framing.
3. Matrix/PBX then sent `LD`.
4. Matrix/PBX sent multiple `LR` record declarations, including `RTGI`, `RTGO`, and `RTRE` among the observed declarations.
5. Matrix/PBX sent `LA`, indicating that the observed link negotiation progressed beyond Link Start.

The committed fixture is synthetic/redacted. Date/time values are synthetic and guest records are deliberately omitted. The diagnostic report stores record codes, LR record-type identifiers, wire lengths, capture indexes, and SHA-256 digests rather than raw application payloads.

The accepted progression is deliberately bounded. Only `LR` declarations that occur after the selected `LD` and before the first following `LA` belong to that completed link attempt. Later `LR` traffic is still reported as observed evidence, but it does not invalidate a previously completed progression or silently widen the declaration set attributed to that progression. Likewise, an `LA` observed before the selected `LD` cannot satisfy that later link attempt.

This evidence does **not** qualify a universal Matrix TCP port, ENQ/ACK behavior, retry timing, guest-event field semantics, broader Matrix model coverage, or a production interoperability claim. The existing compatibility row therefore remains `PARTIAL / OPERATOR_CONFIRMED / TCP / PBX_TO_PMS`.

## Technician use

```bash
python scripts/diagnose-matrix-fias-link.py \
  tests/fixtures/pbx/matrix_sarvam_fias_link_progression_sanitized.json \
  --transport tcp \
  --pbx-direction rx \
  --evidence-class operator_confirmed \
  --output /tmp/matrix-fias-link-report.json
```

A healthy bounded observation reports `exact_progression_observed=true` and the finding `matrix-fias-link-progression-observed`. `lr_record_types` contains only declarations inside the selected `LD ... LA` progression; `observed_lr_record_types` retains all recognized PBX-originated LR declarations in the capture for technician context.

If `LS` is observed but no PMS `LS` reply follows, fix the PMS role/listener behavior before troubleshooting room-event records. If the PMS `LS` reply is CR/LF-framed rather than STX/ETX-framed, use the Matrix MICROS Opera profile's field-observed STX/ETX framing. If `LD`/`LR` arrive but no later `LA` completes that same attempt, keep the capture running through the end of link negotiation and do not call the link active from `LD`/`LR` alone.

## Codex / live validation

For a live Matrix validation, pin the Emulator to the exact SHA being tested and record:

- Matrix product/model and software revision;
- the actual site-configured TCP endpoint and which side initiated the connection;
- which local capture direction corresponds to the Matrix/PBX;
- the complete sanitized `LS -> LS -> LD/LR... -> LA` exchange with timestamps;
- any later guest-event record separately, with synthetic guest/room identifiers.

Do not commit raw guest PII. A real capture may justify stronger evidence provenance for the exact row, but it must not automatically promote `PARTIAL` to `SUPPORTED`.

## UCP evidence handoff

The separate UCP Hospitality PMS Gateway may reuse the sanitized fixture shape, exact wire digests, six-dimensional compatibility coordinates, and LR declaration knowledge as data/test evidence. It must not import the Emulator runtime, simulation/session orchestration, diagnostics engine, Windows field tool, or release lifecycle.
