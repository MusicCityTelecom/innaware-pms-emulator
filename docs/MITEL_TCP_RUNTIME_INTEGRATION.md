# Mitel TCP Runtime Integration

## Scope

This boundary connects the evidence-qualified `MitelTcpSessionStateMachine` to the normal TCP interface runtime. It applies only to PMS interfaces using the explicit Mitel TCP protocol names (`MITEL 1`, `MITEL 2`, `MITEL_1`, `MITEL_2`) over `tcp_server` or `tcp_client` transports.

Mitel serial is intentionally excluded. Serial transport settings, line discipline, and serial-specific handshake behavior remain a separate profile even where application-family semantics overlap.

## Why the generic reader loop was unsafe

The older runtime inspected every raw byte in each TCP read and pushed any `0x06` or `0x15` byte into the outbound transaction-response queue. TCP is a byte stream, not a record transport, so a single read may contain controls, complete frames, partial frames, or several of those at once. A byte equal to ACK or NAK inside an STX/ETX application payload is application data and must not be treated as a standalone transaction response.

The runtime now delegates Mitel TCP stream interpretation to `MitelTcpSessionStateMachine`, which itself uses the bounded `TcpStreamDecoder`. Only standalone decoded ACK/NAK controls reach the transaction sender queue.

## Receive flow

For an explicit Mitel TCP interface:

1. establish the TCP connection;
2. create a new Mitel session state machine and call `connect()`;
3. capture each raw read for diagnostics;
4. feed the read to the stream/session decoder;
5. route standalone ACK/NAK controls to the outbound transaction queue;
6. transmit state-machine ACK/NAK actions without applying a second framing layer;
7. retain structured session diagnostics and current transport-session status;
8. on disconnect, call `disconnect()` so incomplete STX/ETX frames are diagnosed and partial state is discarded.

A reconnect therefore begins with a clean framing buffer and no inherited ENQ grant or message-retry window.

## Evidence boundary

The runtime integration inherits the evidence classifications from the session state machine:

- ENQ/ACK/NAK, STX/ETX, `AREYUTHERE`, captured CHK/NAM traffic, fragmentation/coalescing, and reconnects: **packet-capture verified**;
- three-second ACK timing and initial frame plus three message-only retries: **vendor/public Mitel-compatible specification evidence**;
- additional normal Mitel-family message names and NAM variants: **legacy source/profile or legacy simulator characterization** as labeled by the state machine.

These facts characterize the Mitel-compatible profile and the observed iPocket session. They are not universal claims for every Mitel model or serial implementation.

## Diagnostics exposed by the interface runtime

`InterfaceManager.diagnostics()` returns bounded structured session diagnostics containing timestamp, peer, configured protocol, diagnostic code, severity, confidence, evidence class, observed behavior, expected behavior, and corrective action.

`InterfaceRuntime.status()` exposes the latest `transport_session` snapshot and a `session_diagnostic_count`. Auto-detection may use these observations to rank candidate profiles, but this integration never changes the configured personality automatically.

## Transaction sender interaction

Outbound Mitel PMS transactions continue to use `MitelTransactionSender`. `max_attempts` bounds ENQ acquisition attempts, while `max_record_retries` independently bounds application-frame retries after ENQ has been granted. Incoming standalone ACK/NAK controls are supplied by the stream-aware session decoder.

## Regression expectations

Loopback coverage must preserve all of the following:

- ENQ and a complete STX/ETX frame may arrive coalesced in one TCP read;
- a frame may be arbitrarily fragmented across TCP reads;
- standalone ACK/NAK controls may be coalesced with each other or with framed data;
- ACK/NAK-valued bytes inside an STX/ETX payload never become transaction responses;
- a frame without the expected ENQ grant is rejected and produces a structured diagnostic;
- a disconnect with a partial frame produces an incomplete-frame diagnostic;
- reconnect starts with an empty stream buffer and no stale transaction grant;
- Mitel serial never enters this TCP-specific state machine.

## Remaining evidence gaps

This integration does not invent simultaneous-ENQ collision rules, universal keepalive cadence, or universal reconnect timing. Those remain evidence gaps. Additional capture-derived timing should be added only when supported by issue #4 or verified project-source evidence.
