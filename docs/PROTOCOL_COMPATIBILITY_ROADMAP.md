# Protocol compatibility roadmap

This roadmap records functional interoperability requirements that have been identified from historical deployments and reference material. An entry in this document is **not** a claim that the corresponding vendor or protocol is currently certified or fully implemented.

The implementation rule is to preserve functional facts and independently implement them behind protocol/profile adapters. Do not copy vendor manuals, third-party source code, screenshots or distinctive documentation into the emulator repository.

## Maturity vocabulary

- **stateful** - adapter plus meaningful protocol/session state machine is implemented.
- **transactional** - call-accounting handshake/retry behavior is implemented.
- **encoder** - message generation exists, but full profile/session behavior is not yet certified.
- **planned** - requirement identified; implementation is intentionally withheld until fixtures/behavior are sufficiently verified.

## PMS families

### FIAS / Oracle / MICROS

Current generic FIAS work includes check-in/out, guest-name change, room move, wakeup set/cancel, link-state handling, posting acknowledgement and property-backed database resync.

Additional verified edge requirements to implement/test:

- costed postings must be serialized so a later posting does not overtake one awaiting PMS acknowledgement;
- an unacknowledged cost posting must not be blindly re-sent in a way that can double-bill a guest;
- when modeling an offline posting queue, charges may be held with strict age/count limits while stale room-state/check-in/DND/MWI events must not be replayed later;
- posting identifiers must remain positive and avoid malformed zero/leading-zero behavior where the target FIAS profile requires that;
- charge descriptions must obey profile field-length limits;
- wake-up results must preserve the request date/time identity needed to reconcile a result with the request;
- link-end handshake and link-alive cadence need profile-specific tests;
- Hilton PEP/FIAS has a resynchronization variant and combined guest-name semantics.

### OnQ

`ONQ` currently has encoder-level support. A legacy `ONQ2` profile existed specifically to correct guest-name/change-name records whose field length differed from the default profile. The emulator should represent this as profile behavior, not a copy/paste protocol implementation.

### Opera legacy

`OPERA_LEGACY` currently has encoder-level support. Historical profiles distinguish serial Opera, Opera-over-IP, and an `OPERA2` correction for longer guest-name/change-name records. Oracle/MICROS FIAS-family testing should remain separate from these legacy profiles.

### Choice Advantage / SkyTalk

Choice Advantage-style support exists at encoder level. Historical deployments describe SkyTalk as the hosted Choice Advantage variant. Profile-level framing/name-field differences still require fixtures before declaring stateful support.

### FOSSE / GALAXY / RDP / COMTROL / others

Historical profiles include FOSSE/FOSSE2, GALAXY/GALAXY2, RDP, COMTROL UHLL and other specialty interfaces. Several `*2` variants exist specifically because change-name or check-in field lengths differ from their original profiles. These should be added only from independently verified fixtures.

## Call-accounting families

### HOBIS / HOBIS-A / Holidex

`HOBIS`, `HOBIS_A`, and `HOLIDEX` now use a verified HOBIS-A 54-character fixed-field layout with transactional ENQ/ACK behavior and recommended STX/ETX/XOR-BCC record framing. The three names are compatibility aliases for the same currently verified byte layout; they are not a claim that every historical product using those labels was byte-identical.

The formatter keeps InnForm XL separate rather than inheriting the InnForm-specific `001A TEL ...` representation. HOBIS-A uses the documented four-digit counter, `PST` property code, fixed extension/time/duration/cost/number positions, and final description/type field.

### HOBIS2

Verified requirement: HOBIS2 adjusts the normal HOBIS layout for **five-digit extension numbers**. Do not implement it merely by truncating a five-digit room into the existing four-character field.

### InnForm XL

Current `INNFORM_XL` support uses the `TEL` property code and the same transaction engine. It intentionally remains a separate formatter from HOBIS-A because existing field-tested InnForm traffic uses the `001A TEL ...` family. Continue testing fixed positions, duration representation, cost rounding and sequence behavior against independent fixtures.

### MICROS call accounting

Historical deployments identify a MICROS-specific HOBIS-A variant. Keep it planned until byte-position fixtures establish how it differs from base HOBIS.

### RoomKey

Verified differences from normal HOBIS:

- extension field begins one position earlier;
- call duration is represented as `MMSS` instead of the normal HOBIS minute field.

This should become a distinct adapter/profile with exact regression fixtures.

### RDP

Historical RDP ACK/NAK call-accounting formatting is identified as a distinct compatibility profile and was later considered deprecated in favor of HOBIS on some systems. Keep a separate adapter if field deployments still require it.

### ProfitWatch

Verified behavior is raw SMDR-style output containing the calling room, called number and call length; the external system applies its own billing/cost tables. This belongs in the blind/raw family rather than the ACK/NAK transaction family.

### LegacyRaw / REMCO / ValuePlace / RAWPS / Navy

These are blind/raw specialty families and must not be silently mapped to HOBIS merely because they are call-accounting interfaces. Each needs its own fixture before being marked implemented.

## Session/framing edge cases

The emulator framework must continue to support profile-selectable behavior for:

- ENQ before record vs no ENQ;
- ACK/NAK as binary control bytes or profile-specific ASCII responses;
- raw CR/LF vs STX/ETX;
- XOR BCC/checksum variants;
- immediate ACK timing when required to avoid sender retransmit/backlog storms;
- TCP client/server reconnect behavior;
- serial line settings;
- bounded timeout/retry behavior;
- intentionally malformed/late/dropped traffic for fault-injection tests.

## Windows field-tool requirements carried forward

The earlier native Windows prototype identified several technician-facing requirements that remain valid even though the project now uses a shared Python core:

- multiple simultaneous endpoints/listeners;
- saved profiles;
- framing/checksum controls;
- ACK/NAK visibility;
- serial port selection;
- start/stop/restart/status per interface;
- raw/decoded traffic logging;
- simple field deployment with no Python installation required in the packaged build.

These features should continue to be implemented in the shared API/operator console so Windows and Debian behavior cannot drift.
