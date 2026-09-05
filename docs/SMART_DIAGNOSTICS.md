# Smart Interoperability Diagnostics

## Objective

InnAware should explain *why* an integration is failing, not merely show bytes. The diagnostic engine observes both directions of a live or replayed session, compares the observed wire behavior with the configured protocol/personality, and emits evidence-backed findings with severity, confidence, and corrective actions.

A technician should be able to reach a conclusion such as:

> The peer is sending FIAS `LS` inside STX/ETX framing, but this endpoint is configured for CRLF and is replying with a bare CRLF `LS`. The application record is correct, but the wire framing is incompatible. Set framing to STX/ETX and repeat link negotiation before testing guest events.

That conclusion must be generated from the capture itself rather than from a hard-coded vendor assumption.

## Diagnostic layers

Diagnostics should run from the bottom of the stack upward so a lower-layer fault is not mistaken for an application problem.

### 1. Transport

Detect and report:

- listener not bound;
- client unable to connect;
- connection established but no application traffic;
- repeated connect/disconnect loops;
- multiple clients where a transactional profile requires exactly one;
- TCP peer changes during a transaction;
- serial device unavailable;
- serial parameter mismatch candidates;
- HTTP method/status problems where applicable.

### 2. Stream and framing

Detect:

- raw vs CR vs LF vs CRLF;
- STX/ETX;
- STX/ETX/BCC;
- peer framing different from configured framing;
- outbound framing different from inbound peer framing;
- malformed or incomplete frames;
- multiple frames coalesced into one TCP read;
- one frame split across multiple TCP reads;
- control byte plus frame coalescing;
- unexpected CR/LF inside an STX/ETX payload;
- checksum/BCC mismatch;
- framing changes during one session.

### 3. Control-byte transaction behavior

Detect:

- ENQ without ACK;
- ACK without an outstanding transaction;
- NAK and the exact preceding TX record;
- delayed ACK beyond configured timeout;
- retransmission loops;
- retry exhaustion;
- duplicate transactions caused by lost acknowledgements;
- wrong ACK type, such as ASCII response vs control-byte ACK where applicable.

### 4. Session/link state

For FIAS-family sessions, detect:

- repeated `LS` without progress;
- `LS` response framing mismatch;
- missing or unexpected `LD`, `LR`, `LA`, `LE` sequence;
- guest records sent before link activation;
- keepalive interval failures;
- database synchronization requested but not answered;
- database synchronization started but not completed.

Equivalent state-machine diagnostics should exist for Mitel, OperaIP, call-accounting transaction families, and future protocols.

### 5. Protocol identification and mismatch

Analyze payload structure independently from the configured protocol.

Examples:

- observed FIAS `LS|...|` while interface is configured as `OPERA_LEGACY`;
- observed Voiceware-style `CHK/NAM/WKP` while configured as generic FIAS;
- observed Mitel fixed-field traffic while configured for a line-oriented protocol;
- observed HOBIS BCC framing while configured as blind SMDR.

The diagnostic should say what was *observed* and what was *configured* rather than silently changing the protocol.

### 6. Personality fingerprinting

Known field observations and sanitized fixtures can provide candidate personalities.

Example field signature:

```text
PBX -> PMS
<STX>LS|...|<ETX>
```

This is consistent with the observed Matrix SARVAM UCS `Micros Opera` behavior. It is not globally unique, so a diagnostic should report:

- candidate personality;
- confidence;
- evidence;
- why the match is not conclusive.

A personality fingerprint must never be treated as proof of a vendor/model unless the operator selected that system or stronger evidence exists.

### 7. Record semantics

Detect likely field-level problems after transport/framing/session health is acceptable:

- unknown record type;
- missing required room number;
- invalid room width for a fixed-field protocol;
- name field overflow shifting a later field;
- unsupported guest event for the selected personality;
- invalid date/time format;
- invalid status/restriction code;
- unexpected direction for a record type;
- posting request without a posting response;
- room move missing old/new room relationship.

#### PhoneSuite PMS→PBX source-backed format diagnostics

The PhoneSuite PMS policy has a dedicated format-diagnostic layer for the command subset explicitly described by historical PhoneSuite/Voiceware PMS-interface documentation. It is intentionally separate from the simulator-characterized PhoneSuite PBX→PMS row and from physical serial configuration.

Current deterministic checks include:

- `CHK0`/`CHK1`: command separation, 3- or 4-digit extension syntax, and the documented 20-character maximum for an optional `CHK1` guest name;
- `LMT`: extension syntax and the documented decimal credit-limit shape through `999.99`, with optional `$`;
- `DND0`/`DND1`: documented status and extension shape;
- `GRP`: extension syntax plus the documented letters/numbers group-code field and 10-character boundary;
- `LNG`: exactly two lowercase language-code letters immediately after `LNG`, followed directly by a 3- or 4-digit extension;
- `MW 0`/`MW 1`: status validation and the explicitly documented requirement for exactly one space between `MW` and the status digit;
- `RSTn`: restriction code adjacency and extension syntax;
- `NAM1` through `NAM4`: immediate numeric index, required name/extension placement, and the documented 20-character name limit;
- `AREYUTHERE`, `GRS`, and `END`: exact application-control records without appended arguments.

These findings use `legacy_source_profile` provenance and describe the observed field, expected source-backed shape, and a corrective action. A syntactically valid three- or four-digit extension is **not** treated as proof that the extension exists at the property; property membership is a separate state/configuration check.

The format helper deliberately returns no directional-format finding for `MOV`, `MSGn`, `STSn`, `RQINZ`, or unknown commands because their PMS→PhoneSuite direction is not qualified by the current source boundary. It also does not select a transport, supply baud/parity/data/stop defaults, add a checksum, invent a retry policy, or silently switch profiles. Format errors are application-layer findings and must not be “fixed” by changing serial/TCP transport settings.

### 8. Property/state divergence

When bound to the property-state model, compare wire traffic with expected state:

- check-in acknowledged but room state did not change;
- checkout received for a room already vacant;
- wake-up set on the wire but not reflected in state;
- PBX reports room status inconsistent with expected PMS state;
- repeated duplicate events;
- synchronization result differs from local property state.

This is how InnAware can distinguish "wire protocol succeeded" from "business state actually changed".

### 9. Timing and reliability

Track monotonic timings for:

- ACK latency;
- link-start response latency;
- posting response latency;
- keepalive spacing;
- reconnect interval;
- transaction duration;
- retry counts.

Diagnostics should compare observed timings with profile/personality tolerances and identify slow-but-successful behavior separately from hard failures.

## Finding structure

Every finding should contain:

```text
id
severity        info | warning | error | critical
confidence      low | medium | high
title
summary
evidence[]
suggested_actions[]
tags[]
```

Findings should be deterministic enough for regression tests and readable enough for field technicians.

## Root-cause ranking

When several findings are related, InnAware should rank the lowest-layer likely root cause first.

Example:

```text
CRITICAL  FIAS Link Start reply uses wrong framing
ERROR     Peer framing differs from configured framing
ERROR     TX framing differs from RX framing
WARNING   Peer keeps retrying Link Start
INFO      Traffic resembles Matrix SARVAM MICROS Opera field profile
```

The UI should visually group the retry as a *symptom* of the framing problem rather than five unrelated errors.

Future implementation should add `root_cause_id` / `caused_by` relationships between findings.

## Passive and active diagnostics

### Passive

Passive mode never transmits extra traffic. It analyzes:

- live captures;
- session state;
- transaction history;
- configuration;
- property-state effects.

This should be the default on active hotel systems.

### Active probe

An explicit technician-controlled probe mode may perform safe protocol-specific tests, for example:

- TCP connect test;
- ENQ/ACK handshake;
- FIAS link-start negotiation;
- keepalive exchange;
- known-safe synthetic room event against a designated test room;
- posting request/response test;
- controlled disconnect/reconnect.

Active probes must never run automatically against a live endpoint. The UI must identify exactly what will be transmitted.

## Known-good comparison

A support bundle or capture should be comparable against a sanitized known-good fixture for the selected personality.

The comparison should answer:

- where the first byte-level divergence occurs;
- whether control sequence differs;
- whether framing differs;
- whether required fields are missing;
- whether timing is outside tolerance;
- whether the peer stopped progressing at a specific state.

This is more useful than a generic packet diff because it understands the protocol structure.

## Capture learning

Capture/Learn mode should produce a characterization summary such as:

```text
Observed role:       PBX-side candidate
Transport:           TCP client -> emulator listener
Dominant framing:    STX/ETX
Protocol candidate:  FIAS
Observed records:    LS, LA, ...
Controls:            none observed
Keepalive:           approximately 30 seconds
Candidate profile:   Matrix SARVAM MICROS Opera
Confidence:          medium
Unknown behavior:    record ACK policy, posting behavior
```

A technician can then save sanitized observations as a development fixture without copying customer data.

## Initial implemented rules

The diagnostics surface on the v0.4.0 feature branch now includes:

- FIAS traffic with a non-FIAS configured adapter;
- configured framing vs observed peer framing mismatch;
- inbound/outbound framing asymmetry;
- FIAS `LS` response framing mismatch;
- repeated `LS` without progress;
- unanswered ENQ;
- inbound NAK;
- invalid XOR BCC;
- CRLF embedded inside framed FIAS when the peer does not use it;
- TCP coalescing evidence;
- field-observed Matrix SARVAM MICROS Opera signature candidate;
- PhoneSuite PMS→PBX source-backed receive-timing findings;
- PhoneSuite PMS→PBX source-backed command-format findings for the qualified application subset.

These rules are only the foundation. The intended product is a layered troubleshooting engine that explains transport, framing, handshake, protocol, personality, timing, and property-state behavior together.
