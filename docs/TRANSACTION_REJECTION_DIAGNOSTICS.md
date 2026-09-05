# Transaction rejection diagnostics

`diagnose-peer-naks.py` is a technician-facing diagnostic utility for PBX↔PMS interoperability work. It correlates an inbound protocol `NAK` with the nearest defensible outbound transaction while deliberately refusing to infer transport, switch personalities, or promote a compatibility claim.

## Why this exists

A peer `NAK` is strong evidence that the peer rejected a transaction, but it is not by itself proof of a checksum fault, a serial-setting mismatch, a TCP-port problem, or the wrong PBX/PMS personality. Troubleshooting is more reliable when the rejected outbound element is identified first and only then compared against the evidence-qualified profile.

The correlator therefore fails closed at transaction boundaries. It will not attribute a `NAK` to an older outbound frame if a new inbound control or application record occurred in between.

## Transport remains explicit

The caller must select `tcp`, `serial`, or `unknown`. The tool never determines transport from application bytes.

For serial evidence, the technician must separately retain the actual adapter/device, baud, data bits, parity, stop bits, and flow control. For TCP evidence, retain endpoint roles and the site port separately. A received `NAK` does not establish universal serial defaults or make a site TCP port a protocol constant.

Series2 TDMoE/PRI/Q.921/Q.931/D-channel/`0x0E` station programming is outside this diagnostic surface and must not be treated as PBX↔PMS application-protocol evidence.

## Evidence provenance

Every run requires an evidence class:

- `packet_capture`
- `operator_confirmed`
- `legacy_source_profile`
- `simulator_characterization`
- `inference`

The class is recorded in the deterministic output; it does not change parser behavior or authorize promotion.

## Payload safety

The reusable report does **not** embed raw application payloads. For a correlated outbound element it records only:

- capture indexes;
- confidence;
- SHA-256 of the exact outbound bytes;
- byte length;
- parsed framing;
- parsed record family/code or control byte classification;
- corrective actions.

This allows a technician or downstream test consumer to prove which transaction was analyzed without copying guest names or other raw payload data into the report. Inputs still must be synthetic/redacted before any fixture is committed to the repository.

## CLI example

```bash
python scripts/diagnose-peer-naks.py \
  /tmp/synthetic-capture.json \
  --transport serial \
  --evidence-class simulator_characterization \
  --output /tmp/peer-nak-report.json
```

The capture JSON may be either a list of capture objects or an object containing a `captures` list. Capture objects use the same `direction` plus `hex`/`text`/`data` semantics as the existing diagnostic parser; JSON inputs normally use `hex`.

## Interpreting confidence

`high` means the rejected TX element immediately preceded the inbound `NAK`. `medium` means a defensible TX element was found with non-transaction observations between it and the `NAK`. `low` means no TX element could be safely correlated without crossing a new inbound transaction boundary.

A low-confidence result is still useful: it tells the technician to improve the capture before making configuration changes.

## Compatibility and UCP boundary

The report always declares:

- `transport_inferred=false`;
- `personality_switch_authorized=false`;
- `compatibility_promotion_authorized=false`;
- `raw_payloads_embedded=false`;
- `series2_station_programming_in_scope=false`.

The InnAware PMS-PBX Emulator remains a standalone technician/installer support project. A sanitized report may be supplied to the separate InnAware UCP Hospitality PMS Gateway as data/test evidence, but UCP must not import the Emulator runtime, API/UI, session orchestration, Windows launcher, storage model, or deployment lifecycle.

## Recommended technician sequence

1. Capture the actual rejection transaction with explicit direction.
2. Run this diagnostic with the independently known transport and correct evidence class.
3. If a TX frame is correlated, compare that exact frame's framing, record type, field layout, and documented checksum behavior with the selected personality.
4. Change one variable at a time and replay using synthetic/redacted data.
5. Record the resulting wire artifact digest and exact Emulator Git SHA in the existing technician evidence-result workflow.
6. Treat any compatibility-matrix change as a separate reviewed decision.
