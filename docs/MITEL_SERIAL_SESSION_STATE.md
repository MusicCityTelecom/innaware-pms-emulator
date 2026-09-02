# Mitel serial session state boundary

This document records the clean-room serial-session boundary implemented for the Mitel 1 / Mitel 2 compatibility profiles.

## Evidence level

The serial transport implementation is **partially characterized**. It is based on the durable evidence index in issue #4 and intentionally does not claim that every Mitel PBX uses these settings or byte-level rules.

Evidence classes used by the implementation:

- `operator_confirmed_behavior`: CHK0/CHK1 and related CHK/NAM family members are normal protocol elements, not anomalies.
- `legacy_source_profile_verified`: the legacy MTL reference profile defines ENQ `0x05`, STX `0x02`, ETX `0x03`, ACK `0x06`, NAK `0x15`, checksum disabled, and the Mitel-family application vocabulary.
- `legacy_simulator_characterized`: NAM1/NAM2/NAM3/NAM4 behavior is characterized by historical simulator evidence.
- `inference_not_yet_verified`: repeated-ENQ/collision interpretation remains deliberately non-authoritative.

Packet-capture evidence for the current iPocket work is primarily a **TCP** evidence source and is not promoted to serial truth merely because the control bytes look similar.

## Built-in legacy serial profile

The default serial state-machine metadata reflects the existing technician profile:

- 1200 baud
- 8 data bits
- no parity
- 1 stop bit
- XON/XOFF flow control
- STX/ETX application framing
- ENQ/ACK/NAK half-duplex control

All line settings remain configuration data; the emulator must allow technicians to change them for the PBX actually under test.

## Receive state

The serial session has its own lifecycle and does not instantiate the Mitel TCP state machine.

```text
closed
  -> open
  -> idle
  -> ENQ received
  -> peer_granted
  -> STX ... ETX application record
  -> ACK and idle
```

A rejected application record opens a bounded message-retry window. A frame received without an ENQ grant is rejected when strict half-duplex mode is enabled.

Serial driver reads are treated as arbitrary byte chunks. Controls and STX/ETX application records may be fragmented or coalesced across reads. A partial application record is discarded when the serial session closes so stale bytes cannot leak into a later port-open generation.

## Diagnostics

The serial state machine emits structured diagnostics for:

- application frame received without ENQ;
- unexpected bytes outside STX/ETX framing;
- incomplete frame when the port closes;
- invalid CHK status;
- uncharacterized NAM status;
- uncharacterized application family;
- repeated ENQ while a prior transaction remains open.

Framing diagnostics explicitly direct the field technician to check serial-vs-TCP profile selection and baud/data/parity/stop settings. Auto-detection must never silently switch the configured profile.

## Architectural boundary

`MitelSerialSessionStateMachine` is transport/session code only. It does not contain vendor executables, guest data, TDMoE, Q.921/Q.931, PRI D-channel logic, or PhoneSuite Series2 station-programming behavior.

The current implementation is a serial state-machine foundation. Runtime wiring to the pyserial interface loop and PTY/loopback validation are the next required steps before any serial combination can be promoted from partially characterized to supported.
