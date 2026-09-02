# PBX↔PMS compatibility claim matrix

`src/innaware_pms_emulator/compatibility_matrix.py` is the machine-readable compatibility claim surface for v0.4.x.

Each row is keyed by all six required dimensions:

`PBX family × PBX dialect × transport × PMS family × PMS protocol × direction`

The matrix is deliberately fail-closed. An exact combination that is not explicitly registered is returned as `unsupported`; the emulator must not silently substitute a nearby personality or transport.

## Status rules

- `supported`: may be used only when the exact row has deterministic test/fixture coverage and evidence stronger than inference.
- `partial`: meaningful implementation and evidence exist, but one or more runtime, fixture, direction, transport, or model-specific boundaries remain open.
- `planned`: evidence or product need identifies the combination, but implementation/coverage is not yet sufficient.
- `unsupported`: no verified exact row exists. This is the default for an unlisted combination.

The initial registry intentionally does **not** promote any new combination to `supported`. Mitel TCP remains capture-backed but model/profile-qualified; Mitel serial remains separate and only partially characterized until the serial state machine is wired through the live pyserial runtime and PTY/runtime tested. PhoneSuite remains planned pending clean-room simulator fixtures. Matrix/FIAS remains partial based on field observation plus existing FIAS tests. Hitachi is retained as the fifth PBX-family candidate without a wire-level claim.

## Evidence ranking

Rows use the project evidence order:

1. packet capture
2. operator-confirmed behavior
3. legacy source/profile
4. simulator characterization
5. inference

Inference alone can never satisfy a `supported` claim.

## Test contract

A `supported` row must list deterministic test paths. Unit tests enforce this contract and also verify that unknown combinations fail closed. This makes the compatibility matrix suitable for later CLI/API/GUI presentation without turning auto-detection into auto-configuration.
