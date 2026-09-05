# PhoneSuite PMS-to-PBX Serial Diagnostics

This diagnostic belongs to **InnAware PMS-PBX Emulator**, the standalone
technician/installer interoperability and support tool. It is not a production
hospitality runtime and it does not add any dependency on InnAware UCP
Hospitality PMS Gateway.

## Evidence boundary

The diagnostic is intentionally restricted to the currently registered
six-dimensional combination:

| Dimension | Value |
| --- | --- |
| PBX family | PhoneSuite |
| PBX dialect | MITEL 1-compatible |
| Transport | serial |
| PMS family | legacy-hotel-pms |
| PMS protocol | mitel-hospitality |
| Direction | PMS_TO_PBX |

The direct PhoneSuite/Voiceware PMS-interface documentation states that either
side can act as sender in the Enquire/Acknowledge exchange. For PMS-originated
traffic received by PhoneSuite, the documented application sequence is:

```text
PMS                    PhoneSuite
 | ----- ENQ ---------> |
 | <---- ACK ---------- |
 | -- STX message ETX ->|
 | <---- ACK or NAK --- |
```

The same source states that PhoneSuite must receive STX within **0.100 second**
after its ACK to the PMS ENQ and that an in-message character gap greater than
**0.100 second** causes the receive transaction to time out. The documentation
also describes an optional checksum, but the current project evidence does not
qualify a universal checksum algorithm, byte coverage, placement, or validation
rule for this compatibility row.

Those facts are application/session evidence. They do not establish a universal
PhoneSuite baud rate, parity, data bits, stop bits, flow control, TCP behavior,
retry policy, or a Series2 TDMoE/PRI station-programming behavior.

## Why capture direction is mandatory

Several record names are direction-sensitive. In particular, `MSG` has
different meanings depending on whether the PMS or PhoneSuite originated the
record. The analyzer therefore requires `--pms-direction rx|tx`; it will not
guess the PMS side from a record name.

Use:

- `rx` when local capture `rx` is independently known to be PMS -> PhoneSuite.
- `tx` when local capture `tx` is independently known to be PMS -> PhoneSuite.

The capture role/personality, wiring, endpoint identity, or a separately
reviewed trace must establish that fact.

## CLI

```bash
python scripts/diagnose-phonesuite-pms-to-pbx.py \
  /tmp/phonesuite-pms-capture.json \
  --transport serial \
  --pms-direction tx \
  --evidence-class legacy_source_profile \
  --output /tmp/phonesuite-pms-report.json
```

Input is either a JSON list of capture items or an object containing a
`captures` list. A capture item can provide raw bytes as `hex`, and may include
an ISO-8601 `timestamp`.

The analyzer rejects `tcp` and `unknown` transport values for this diagnostic.
That is not a statement that no PhoneSuite TCP implementation can exist. It is
a fail-closed boundary around the currently registered serial matrix row.

## What the report can establish

For a strict adjacent sequence, the report can retain:

- PMS ENQ;
- PhoneSuite ACK;
- a source-qualified PMS-to-PhoneSuite STX/ETX application record;
- PhoneSuite terminal ACK or NAK;
- application family/opcode and the source-backed expected format;
- format-diagnostic codes without copying the observed application text;
- exact wire-byte SHA-256 and byte length;
- capture indexes and normalized endpoint side;
- when compatible timestamps are present, the elapsed time from the PhoneSuite
  ACK observation to the following PMS STX-framed observation.

A transaction can be marked `qualified_success=true` only when PhoneSuite
returned ACK, the source-qualified record has no documented format problem, and
any assessed ACK-to-STX capture interval is not over 0.100 second.

A missing timestamp does not manufacture a timing claim. Aggregate frame
timestamps also cannot prove the separate 0.100-second **between-character**
rule; that requires byte-level or otherwise sufficiently granular evidence.

## Source-qualified PMS-originated records

The analyzer reuses the project's direct/manual-backed PhoneSuite application
policy rather than maintaining a second opcode table. This currently includes
the base PMS-to-PBX commands and separately reviewed manual extensions such as
drop-message (`MSGn`), DID, VIP, and wakeup (`WKP`) commands.

A recognizable application frame that is outside the current source-qualified
set is retained only as a new evidence candidate. It does not become supported
because another PBX family or the opposite PhoneSuite direction uses a similar
opcode.

## Checksum handling

The source permits an optional checksum, but that statement alone does not
identify its algorithm or wire contract. A capture classified as STX/ETX plus a
trailing byte is therefore reported as a `checksum_variant_candidate`.

The generic capture parser may calculate whether that byte happens to satisfy
its generic XOR-BCC classifier. This PhoneSuite diagnostic intentionally does
**not** promote that generic result into a PhoneSuite checksum claim.

Likewise, a terminal NAK is rejection evidence. It is not proof of checksum
failure. Investigate role/direction, framing, field format, receive timing,
serial settings, and the site's actual checksum configuration before assigning
a cause.

## Payload and PII safety

Reusable report JSON never embeds the raw application payload. It stores
digests and protocol metadata only. This matters for `NAM`, check-in, message,
DID, and other records that can contain guest- or room-related data.

Any retained fixture must be synthetic or redacted while preserving the wire
semantics required by the test. Do not commit hotel captures containing guest
PII, and do not commit vendor executables or proprietary raw profile files.

## Technician workflow

1. Confirm the exact Emulator Git SHA and keep the exact-head Test matrix and
   Windows Build green.
2. Confirm PhoneSuite model/firmware and PMS product/version when real endpoints
   are involved.
3. Confirm which capture direction is PMS-originated.
4. Record the actual serial adapter/device, baud, data bits, parity, stop bits,
   and flow control. The diagnostic does not supply defaults.
5. Run the CLI against a synthetic/redacted capture.
6. If timestamps are trustworthy, review the ACK-to-STX observation interval.
7. If NAK is returned, preserve a sanitized digest/capture and diagnose the
   transaction without assuming checksum failure or changing personality.
8. Feed a reviewed result into the exact-SHA technician evidence-result
   workflow; do not mutate the compatibility matrix automatically.

## UCP Hospitality PMS Gateway evidence handoff

The separate InnAware UCP Hospitality PMS Gateway may reuse **data-only**
artifacts from this work: synthetic/redacted fixtures, exact wire digests,
source-backed application formats, timing facts, six-dimensional compatibility
coordinates, and reviewed diagnostic results.

It must not import the Emulator package, API/operator UI, simulation/session
orchestration, capture store, Windows launcher, or Emulator deployment
lifecycle. Evidence and compatibility knowledge can be shared without coupling
the two products.

## Non-claims

This diagnostic does not:

- promote the PhoneSuite row from `PARTIAL` to `SUPPORTED`;
- qualify a PhoneSuite TCP row;
- qualify universal serial defaults;
- establish checksum algorithm/coverage/placement;
- establish a retry count or retry timer;
- transfer PMS-to-PBX evidence into PBX-to-PMS;
- infer another PBX personality from shared framing;
- infer Series2 TDMoE/PRI/Q.921/Q.931/D-channel/`0x0E` behavior.

Compatibility promotion remains a separate evidence review against the
authoritative six-dimensional matrix and readiness registry.
