# PhoneSuite serial receive-fault diagnostics

This diagnostic is part of the standalone **InnAware PMS-PBX Emulator** technician/support tool. It does not add runtime responsibilities to the separate InnAware UCP Hospitality PMS Gateway.

## Evidence boundary

The direct PhoneSuite/Voiceware PMS Interface manual documents the PBX-interface ENQ/ACK transaction sequence for either sender role and, for PMS-originated traffic, several receive-side failure behaviors:

- after PhoneSuite ACKs a PMS ENQ, PhoneSuite waits up to **0.100 second** for additional data;
- if no data arrives in that interval, the transaction times out silently;
- if data other than a new ENQ arrives after that timeout, PhoneSuite documents a **NAK** response;
- an unterminated message without ETX within the documented receive interval is a NAK condition;
- any between-character delay greater than 0.100 second is a timeout/NAK condition;
- the CHK, DND, and MW command notes explicitly document NAK for an invalid extension number.

These are PhoneSuite application/session facts. They do **not** establish a universal serial baud rate, parity, stop-bit setting, flow-control setting, checksum algorithm, checksum coverage, retry policy, or PhoneSuite TCP compatibility row.

The analyzer intentionally distinguishes what an aggregate capture can prove from what requires byte-level timestamps. An STX observation with no ETX followed by NAK is only *consistent with* the documented missing-ETX condition unless byte-level timing proves the receive deadline.

## CLI

```bash
python scripts/diagnose-phonesuite-receive-faults.py \
  /tmp/phonesuite-capture.json \
  --transport serial \
  --pms-direction tx \
  --evidence-class packet_capture \
  --output /tmp/phonesuite-receive-faults.json
```

`--pms-direction` is mandatory because local `rx`/`tx` is capture-point-specific. The tool never infers PMS/PBX role from a command name.

The report is payload-safe: it records capture indexes, framing/control classification, record family/code where available, exact wire length, and SHA-256 of observed wire bytes. It does not copy application payloads, room numbers, guest names, messages, or vendor binaries into reusable output.

## Technician interpretation

A `phonesuite-late-data-nak-source-consistent` finding means trustworthy capture timestamps show PMS data more than 0.100 second after PhoneSuite's grant ACK and the directly adjacent PhoneSuite response is NAK. This is strong evidence that the observed exchange matches the documented timeout behavior, but it does not prove why the PMS transmitted late.

A `phonesuite-late-data-ack-source-deviation` finding means an ACK was captured where the source describes NAK for late non-ENQ data. Verify timestamp semantics, serial buffering, capture point, endpoint roles, and device/version provenance before treating it as a PhoneSuite implementation deviation.

A `phonesuite-incomplete-frame-nak-source-consistent` finding means an STX-started observation lacked recognized ETX termination and was followed by NAK. Without byte-level timestamps the analyzer deliberately does not claim the 0.100-second missing-ETX or inter-character rule was proven.

A `phonesuite-invalid-extension-nak-source-consistent` finding is limited to CHK, DND, or MW when the source-backed format checker finds a syntactically invalid 3/4-digit extension and the next PhoneSuite control response is NAK. The property still must be checked separately to determine whether a syntactically valid extension actually exists.

A NAK is never automatically labeled a checksum failure. The PhoneSuite documentation permits an optional checksum, but the current evidence surface does not establish a universal checksum algorithm, byte coverage, placement, or verification policy.

## Codex / Server3 acceptance

Pin the exact Emulator SHA first, then run:

```bash
python -m pytest -q \
  tests/test_phonesuite_receive_fault_diagnostics.py \
  tests/test_phonesuite_pms_to_pbx_diagnostics.py \
  tests/test_phonesuite_pms_policy.py \
  tests/test_transport_evidence_boundaries.py
```

Safe synthetic timeout acceptance:

```bash
cat >/tmp/phonesuite-late-data.json <<'JSON'
[
  {"direction":"tx","hex":"05","timestamp":"2026-09-04T10:00:00.000Z"},
  {"direction":"rx","hex":"06","timestamp":"2026-09-04T10:00:00.010Z"},
  {"direction":"tx","hex":"0243484b302039303103","timestamp":"2026-09-04T10:00:00.150Z"},
  {"direction":"rx","hex":"15","timestamp":"2026-09-04T10:00:00.160Z"}
]
JSON

python scripts/diagnose-phonesuite-receive-faults.py \
  /tmp/phonesuite-late-data.json \
  --transport serial \
  --pms-direction tx \
  --evidence-class packet_capture \
  --output /tmp/phonesuite-late-data-result.json
```

For live qualification, record the exact Emulator SHA, PhoneSuite model/version, PMS product/version, serial adapter/device, baud, data bits, parity, stop bits, flow control, capture point, and which local direction is PMS-originated. Use synthetic/redacted room and guest data. Preserve the original wire artifact outside Git and retain only sanitized fixtures/digests in the repository.

## Cross-project evidence handoff

The separate UCP Hospitality PMS Gateway may reuse this diagnostic's source facts, synthetic/redacted fixtures, wire digests, and normalized finding codes as independent test evidence. It must not import the Emulator runtime, FastAPI/operator console, transport/session orchestration, Windows launcher, capture store, or Emulator release lifecycle. Evidence can cross the boundary; runtime ownership does not.
