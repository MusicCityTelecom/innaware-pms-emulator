# Matrix FIAS PMS-to-PBX GI candidate diagnostics

This diagnostic belongs to the standalone **InnAware PMS-PBX Emulator** technician/support tool. It does not add a runtime dependency to the InnAware UCP Hospitality PMS Gateway and it does not transfer Emulator session, transport, UI, or deployment responsibilities into UCP.

## Evidence boundary

Project Sources contain a historical operator runtime log from a Matrix SARVAM UCS / MICROS Opera FIAS session. After link activation, that log shows one PMS-originated STX/ETX `GI` record followed by a single-byte PBX `ACK`. The same log contains real guest data, so its raw application payload is deliberately **not** committed. The committed fixture is a synthetic/redacted reproduction that preserves only wire semantics and field-identifier shape.

That historical runtime session predates the current Emulator exact SHA. Under the v0.4.0 evidence policy, it can guide a candidate diagnostic but **cannot register or promote** a `Matrix × MICROS Opera/FIAS × TCP × Oracle/MICROS Opera × FIAS × PMS_TO_PBX` compatibility row. Exact-SHA live validation is still required.

The historical observation qualifies only the following narrow candidate shape:

- transport under investigation: TCP;
- PMS-originated FIAS `GI` application record;
- STX/ETX framing;
- observed field identifiers `RN`, `G#`, `GN`, `GL`, `GV`, `CS`, `GA`, `GD`, `GS`;
- one following PBX single-byte `ACK` in the historical transaction.

It does **not** qualify field values, a universal site port, ACK latency, timeout/retry policy, checksum/LRC rules, reconnect policy, other FIAS application records, a serial variant, or broader Matrix models. A `NAK` is never labeled a checksum failure without separate evidence.

## Technician use

```bash
python scripts/diagnose-matrix-fias-pms-to-pbx.py \
  tests/fixtures/pbx/matrix_sarvam_fias_pms_to_pbx_gi_sanitized.json \
  --transport tcp \
  --pms-direction tx \
  --evidence-class operator_confirmed \
  --output /tmp/matrix-fias-pms-to-pbx.json
```

A synthetic fixture should produce `exact_gi_ack_count=1` while retaining `matrix_claim=candidate_only_not_registered` and `matrix_registration_authorized=false`. Reports store capture indexes, field identifiers, wire lengths, and SHA-256 digests rather than raw guest payloads.

## Exact-SHA live acceptance target for Codex

Pin the current feature SHA before testing. On an authorized Matrix SARVAM UCS, record the exact Matrix model/software revision, actual configured TCP endpoints, TCP initiator, which capture direction is PMS-originated, and a sanitized timestamped exchange. Start with a synthetic test guest/room and one `GI` after a completed link negotiation. Preserve the complete sanitized transaction through the PBX control response.

If the exact-SHA capture reproduces STX/ETX `GI -> ACK`, feed the sanitized capture through this diagnostic and then through the existing candidate-observation/admission workflow. Only a reviewed exact-SHA artifact should be considered for a new PARTIAL matrix row. Capture `RE`, `WR`, `GC`, `WC`, `GO`, or other record types separately; do not generalize them from the GI result.
