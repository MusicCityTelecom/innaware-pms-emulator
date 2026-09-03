# Mitel serial PMS→PBX simulator replay evidence

This note records the evidence boundary for the deterministic serial replay fixture in `tests/data/emulation/mitel_serial_pms_to_pbx.json`.

## Evidence provenance

The source characterization is a clean-room PBX simulator transcript captured in the project Sources. The simulator was explicitly configured for a lab serial link at **9600 baud, 8 data bits, no parity, 1 stop bit, XON/XOFF flow control**. It observed PMS-originated transactions with these wire-level elements:

- `ENQ` (`0x05`) received by the PBX simulator;
- `ACK` (`0x06`) returned by the PBX simulator;
- `STX + CHK1   <room> + ETX` received, followed by `ACK`;
- a new `ENQ -> ACK` transaction;
- `STX + CHK0   <room> + ETX` received, followed by `ACK`.

This is **simulator characterization**, not packet-capture evidence from a production Mitel PBX and not proof that every Mitel-family serial interface uses 9600 baud. The compatibility matrix therefore keeps the serial PMS→PBX row `partial / simulator_characterization` and keeps the opposite serial direction under its separate legacy-source provenance.

## Fixture construction

The permanent fixture replaces the observed room with synthetic room `901` while preserving the characterized control bytes, STX/ETX framing, command/status bytes, and spacing. It contains no COM-port name, workstation path, hotel/property identifier, guest name, IP address, or vendor executable.

`ReplayFixture.environment` records the observed lab transport parameters separately from application replay steps. Existing replay fixtures that do not declare an environment continue to load with an empty environment mapping. This separation is intentional: a captured or simulated application sequence must not silently become a universal serial preset.

`tests/test_mitel_serial_replay_fixture.py` loads the fixture, verifies the privacy/provenance boundary, instantiates the independent Mitel serial state machine from the fixture's scoped environment metadata, and replays both transactions. The expected result is two accepted records (`CHK1`, `CHK0`) and four generated ACK controls: one for each ENQ and one for each framed application record.

## What this fixture does not establish

The fixture does not qualify a universal Mitel baud rate, parity, data-bit, stop-bit, or flow-control setting. It does not import Mitel TCP reconnect behavior, packet timing, endpoint addresses, or capture-derived field variants into serial. It does not make the serial row `SUPPORTED`, does not create an aggregate serial `BIDIRECTIONAL` claim, and does not establish real-hardware behavior for a specific Mitel model or firmware release.

Public Mitel-compatible application documentation about ENQ/ACK transaction timing and retry limits remains a separate application-protocol evidence source. Physical transport parameters and application transaction policy must continue to be qualified independently.

## Safe live validation

For a real serial PBX validation, record the exact emulator Git SHA, PBX model/firmware, explicitly configured serial parameters, direction, and synthetic bytes. Use synthetic room/name values only. A real-hardware observation may tighten a matrix row only when that evidence is tied to the exact tested SHA and transport configuration; it must not be generalized to other Mitel models or transports without additional evidence.
