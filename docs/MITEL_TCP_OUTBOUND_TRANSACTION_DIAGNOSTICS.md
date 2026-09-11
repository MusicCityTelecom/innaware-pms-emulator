# Mitel TCP outbound transaction diagnostics

## Scope

This document describes the evidence-qualified outbound transaction path used by the InnAware PMS Emulator when a configured Mitel-compatible TCP interface sends a PMS application record to its peer.

It applies to the characterized Mitel TCP half-duplex profile only. It does **not** redefine Mitel serial behavior, and it does not claim that every Mitel model or every PMS product uses identical timing or retry rules.

## Evidence boundary

The durable evidence index is GitHub issue #4.

Evidence classes used by this implementation:

- **packet capture verified**: TCP carries standalone ENQ/ACK/NAK controls and STX/ETX application frames; application frames may be fragmented or coalesced by TCP; reconnects occur; `AREYUTHERE`, `CHK1`, and `NAM2` are captured families;
- **vendor/public compatible specification**: ENQ is acknowledged before an application message, application frames receive ACK/NAK, the characterized default acknowledgement timeout is three seconds, and an initially rejected application message may be sent three additional times without another ENQ;
- **legacy simulator/source characterization**: `CHK0`, `CHK1`, `NAM1`, `NAM2`, `NAM3`, `NAM4`, `WKP`, `MW`, `RST`, `DPT`, `LOC`, and related Mitel-family messages are normal protocol elements in the corresponding characterized profiles;
- **inference not yet verified**: the exact meaning of a NAK returned directly to ENQ when simultaneous half-duplex contention or another busy condition is possible. The emulator therefore reports this condition without guessing the peer's internal reason.

## Runtime ordering

The outbound path is intentionally split between transaction logic and TCP stream/session logic:

```text
application record
    ↓
MitelTransactionSender
    ↓
ENQ
    ↓
TCP peer
    ↓
MitelTcpSessionStateMachine / TcpStreamDecoder
    ↓
standalone ACK or NAK only
    ↓
transaction response queue
    ↓
STX + application record + ETX
    ↓
standalone ACK/NAK
    ↓
complete or bounded message-only retry
```

`TcpStreamDecoder` is critical here. A byte with value `0x06` or `0x15` inside an STX/ETX application payload is application data, not an ACK/NAK transaction response. Only standalone decoded controls enter the outbound transaction response queue.

## Retry contract

The characterized defaults are:

- ACK/NAK timeout: **3 seconds**;
- ENQ acquisition attempts: separately bounded by `max_attempts`;
- application retries: `max_record_retries=3`, meaning the initial application frame plus at most three message-only retries;
- no second ENQ is sent between those application-frame retries.

A separately characterized profile may override the timing/retry values, but the emulator must not silently change them based on auto-detection.

## Structured failure diagnostics

Failed Mitel transactions now carry a `diagnostic` object in the normal transaction result. Because the existing interface transaction endpoint returns the stored transaction result, the structure is available to API/GUI consumers without parsing human log text.

The diagnostic fields are:

```text
code
severity
confidence
evidence_class
observed
expected
corrective_action
```

Current failure codes are:

- `mitel_transaction_enq_timeout`
- `mitel_transaction_enq_nak`
- `mitel_transaction_record_timeout_exhausted`
- `mitel_transaction_record_nak_exhausted`

The diagnostics deliberately distinguish what is known from what is inferred. In particular, an ENQ NAK is not labeled as a proven collision/busy state because that exact semantic remains an evidence gap.

## Field troubleshooting guidance

### ENQ timeout

Observed: no standalone ACK/NAK within the configured transaction timeout.

Check:

1. TCP connectivity and session direction;
2. selected Mitel-compatible personality rather than line-delimited FIAS/raw mode;
3. whether the peer expects the ENQ/ACK half-duplex handshake;
4. configured timeout/retry values before simply increasing them.

### ENQ NAK

Observed: peer returned NAK directly to ENQ.

Check endpoint role/profile and capture the surrounding exchange. Simultaneous half-duplex contention is a possible explanation but is not yet proven as the universal meaning, so the emulator must not auto-switch profiles or invent a peer state.

### Repeated application NAK

Observed: the application frame remained rejected through the configured bounded retry budget.

Check STX/ETX framing and the selected application dialect/field layout. Do not flag `CHK0`, `CHK1`, `NAM1`, `NAM2`, `NAM3`, or `NAM4` merely because of their status digits; those are normal characterized protocol elements.

### Application timeout

Observed: no standalone ACK/NAK after the application frame.

Check TCP stream health, framing, selected direction/personality, and timing. A timeout is ambiguous: it does not prove the peer applied the message and it does not prove the peer rejected it.

## Deterministic coverage

Repository tests exercise the actual `InterfaceManager` TCP-server path rather than only the transaction class. Coverage includes:

- ENQ → ACK → STX/ETX record → NAK → message-only retry → ACK;
- exactly one ENQ across the application retry;
- ACK-valued bytes inside an inbound STX/ETX payload not satisfying the outbound ACK wait;
- structured transaction diagnostics persisted in transaction history after a bounded NAK failure.

The tests use loopback addresses and synthetic guest/room-like values only. No live hotel endpoint, production credential, or captured guest PII is required.

## Remaining evidence gaps

- simultaneous ENQ collision/busy arbitration semantics;
- whether all Mitel TCP variants use the same keepalive cadence and reconnect timing;
- variant-specific application field validation beyond characterized fixtures;
- Mitel serial timing/handshake behavior beyond the separate legacy/profile evidence boundary.
