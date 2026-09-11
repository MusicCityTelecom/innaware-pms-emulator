# Mitel half-duplex transaction timing and retry boundary

This document records the evidence-qualified transaction behavior implemented by `MitelTransactionSender` for the Mitel-compatible hotel PMS profile.

## Evidence classification

The following behavior is based on the Mitel-compatible section of the public 3CX PMS Protocol Specifications indexed in GitHub issue #4:

- the link is half-duplex;
- a sender opens a transaction with `ENQ`;
- the peer responds to `ENQ` with `ACK` or `NAK` within three seconds;
- after `ACK`, the sender transmits one `STX + application message + ETX` frame;
- the peer responds to the completed application frame with `ACK` or `NAK` within three seconds;
- if the application frame is rejected or otherwise not acknowledged, the PMS may retransmit the framed message three additional times without another `ENQ`.

The three-second timing and the three message-only retries are profile evidence, not a universal assertion about every Mitel model, firmware generation, transport, or vendor-derived compatibility mode. Separately characterized variants may override timing/retry values.

Project-source simulator logs independently show repeated `ENQ -> ACK -> application record -> ACK/NAK` sequences for normal Mitel-family commands including `CHK`, `NAM`, `WKP`, `MW`, `RST`, `DPT`, and `LOC`. A `NAK` therefore describes the disposition of a specific transaction/profile/field layout; it is not proof that the command family itself is anomalous.

## Runtime contract

`MitelTransactionSender` keeps ENQ acquisition and application-frame retries separate:

- `max_attempts` bounds ENQ attempts;
- `max_record_retries` bounds retries *after* the initial application-frame transmission;
- the evidence-backed default is three record retries, yielding four total record transmissions;
- record retries do not send another ENQ;
- the default ACK timeout remains three seconds.

This is intentionally different from generic call-accounting transaction behavior.

## TCP and serial separation

This transaction policy is application/session behavior only. It does not make Mitel TCP and Mitel serial the same transport profile.

Mitel TCP must continue to handle arbitrary TCP stream fragmentation/coalescing and reconnect state. Mitel serial must use separately verified serial settings, control/framing behavior, and line discipline. Shared application semantics do not justify sharing unverified transport assumptions.

## Diagnostics

A diagnostic layer may use this profile to identify likely faults such as:

- peer does not answer ENQ within the selected three-second compatibility window;
- application frame is repeatedly NAKed;
- sender incorrectly repeats ENQ before every record retry;
- peer expects a different framing/profile or message layout;
- retry count/timing differs from the selected Mitel-compatible profile.

Diagnostics should state the observed sequence, expected sequence, evidence source, confidence, and corrective action. They must not silently switch the configured profile.
