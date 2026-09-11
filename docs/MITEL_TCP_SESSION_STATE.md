# Mitel TCP Session State Boundary

This document records the v0.4 clean-room Mitel-compatible TCP receive-session behavior implemented by `MitelTcpSessionStateMachine`.

## Evidence provenance

The implementation intentionally separates evidence classes.

### Packet-capture verified

The sanitized iPocket evidence indexed in GitHub issue #4 establishes all of the following on a TCP session:

- one-byte `ENQ` (`0x05`), `ACK` (`0x06`) and observed `NAK` (`0x15`) controls;
- `STX` (`0x02`) / `ETX` (`0x03`) application framing;
- `AREYUTHERE` as a normal framed keepalive/control message;
- normal `CHK*` and `NAM*` application families, including captured `CHK1` and `NAM2` examples;
- repeated control/application exchanges across a persistent connection;
- TCP reconnects;
- arbitrary TCP read fragmentation/coalescing must not define record boundaries.

The implementation does not assign protocol roles from the captured lab IP addresses.

### Vendor/public Mitel-compatible specification evidence

The Mitel-compatible half-duplex profile documented in issue #4 establishes:

```text
ENQ -> ACK/NAK -> STX + application message + ETX -> ACK/NAK
```

with a three-second response bound and up to three message-only retries following a rejected application frame. The sender does not send another ENQ before those message retries.

`CHK1` and `CHK0` are valid check-in/check-out status forms. An invalid status such as `CHK3` is NAK-worthy in that profile.

### Legacy source/profile and simulator characterization

Legacy HotelPMS/profile material expands the characterized application-family set (`WKP`, `RST`, `DND`, `MW`, `LNG`, `LMT`, `DPT`, `LOC`, `VIP`, `SDD`, `STE`, `MOV`, `EDT`, `STS`, `MSG`, `GRS`, `END`, `RQINZ`). Legacy simulator logs also exercise `NAM1` through `NAM4`.

Those families are not promoted to packet-capture-verified merely because legacy material recognizes them.

## State model

The TCP session state machine has four externally visible receive states:

- `disconnected`
- `idle`
- `peer_granted`
- `peer_retry_window`

A new TCP connection always starts a fresh protocol session. Reconnect discards any previous ENQ grant, application retry window and partial TCP frame. An incomplete STX/ETX frame at disconnect produces a structured diagnostic before the buffer is discarded.

### Incoming ENQ

When ENQ is received, the receiver opens a peer transaction and, when automatic responses are enabled, returns ACK. A repeated ENQ while a transaction remains open is observable as an informational diagnostic; it is not used to silently switch profiles.

### Incoming application frame

`TcpStreamDecoder` separates one-byte controls from STX/ETX frames before the session state machine sees them. This is important because bytes with the numerical values of ACK/NAK may legally occur inside an application payload and must not be mistaken for standalone transaction responses.

With strict half-duplex enforcement, a complete application frame arriving without an ENQ grant or message-retry window is NAKed and reported as `mitel_tcp_frame_without_enq`.

A valid characterized frame consumes the receive grant and is ACKed. `AREYUTHERE` is counted separately as normal keepalive traffic.

A rejected application frame opens a bounded message-only retry window. The initial frame plus three retries are permitted by the evidence-qualified profile. After the fourth rejected frame the retry window closes and the diagnostic output tells the operator to correct the message rather than continuing to replay it.

## Structured diagnostics

Session findings include:

- stable diagnostic code;
- severity;
- confidence;
- provenance/evidence class;
- what was observed;
- what the selected Mitel-compatible profile expected;
- exact corrective action.

Current session-level findings cover:

- frame without ENQ;
- malformed STX/ETX stream bytes;
- partial frame lost at disconnect;
- repeated ENQ while a transaction is open;
- invalid `CHK` status;
- uncharacterized `NAM` status;
- uncharacterized application family;
- exhausted message-only retry budget.

Auto-detection is deliberately not performed by this state machine. Diagnostics may recommend verifying a competing profile, but configuration remains operator-controlled.

## Transport boundary

This state machine is **Mitel TCP only**. Mitel serial remains a separate transport profile. Application-family knowledge may be shared where evidence supports it, but TCP reconnect/session semantics must not be copied into the serial transport or vice versa.

## Compatibility matrix impact

This slice upgrades the following dimension from stream-only characterization to deterministic session-state coverage:

| PBX family | Dialect | Transport | Direction | Maturity | Deterministic coverage |
|---|---|---|---|---|---|
| Mitel-compatible | legacy hotel / iPocket-characterized | TCP | peer -> emulator | partially characterized | ENQ grant, ACK/NAK controls, STX/ETX fragmentation/coalescing, CHK/NAM/AREYUTHERE classification, message-only retry window, reconnect reset |

It does **not** claim all Mitel TCP x PMS-family combinations supported. Application field layouts outside the evidence-backed checks remain profile-specific and must be covered by deterministic fixtures before being promoted.

## Remaining evidence gaps

The highest-value remaining gaps are:

1. wire this state machine into the live `InterfaceManager` Mitel TCP reader path so standalone control bytes are routed to outbound transaction waiters only after stream decoding;
2. characterize collision/busy behavior when both ends attempt ENQ concurrently;
3. derive capture-supported keepalive cadence and timeout/reconnect timing without assuming one observed lab interval is universal;
4. add explicit profile-specific field validation for additional message families as evidence permits;
5. implement Mitel serial as a separate handshake/framing/settings adapter using serial-specific evidence.
