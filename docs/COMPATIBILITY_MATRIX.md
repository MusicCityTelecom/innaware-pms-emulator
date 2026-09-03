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

The current registry intentionally does **not** promote any v0.4.0 row to `supported` merely because software coverage exists. Evidence maturity and the exact transport/model boundary remain part of the claim.

## Current row boundaries

### Mitel TCP

Mitel `MITEL 1 / iPocket-characterized` over TCP remains `partial` and packet-capture-backed. Deterministic tests cover stream replay, session state, live TCP runtime behavior, and outbound transaction handling. Capture observations remain qualified to the characterized product/profile and are not promoted into universal Mitel behavior.

### Mitel serial

Mitel `legacy MTL-compatible` serial remains a distinct `partial` row using legacy source/profile evidence. It has a separate serial state machine, live pyserial routing, Linux POSIX PTY framing/reopen coverage, and outbound ENQ/ACK/NAK transaction tests. The row remains partial because real-PBX model coverage and broader timing evidence are incomplete. TCP capture facts are not used as proof of serial behavior.

### PhoneSuite serial

PhoneSuite `MITEL 1-compatible` serial remains `partial` using simulator characterization. Its clean-room fixture, dedicated session adapter, live serial selector, and Linux POSIX PTY tests cover characterized ENQ/ACK plus STX/ETX `CHK0`, `CHK1`, and `NAM2` behavior, fragmented/coalesced reads, close/reopen reset, and peer ACK/NAK control routing.

PhoneSuite-specific baud/data/parity/stop defaults are **not** claimed. Runtime serial parameters remain operator-configured until stronger PhoneSuite-specific evidence qualifies defaults. Linux PTY validation is test infrastructure, not a new protocol-evidence class. Series2/Voiceware TDMoE, PRI, Q.921/Q.931, D-channel, or `0x0E` station-programming observations must not be treated as PhoneSuite PBX↔PMS serial/application evidence.

### Matrix FIAS

Matrix `MICROS Opera / FIAS` over TCP remains `partial` based on operator-confirmed field behavior. A dedicated sanitized Matrix SARVAM fixture, profile, and deterministic diagnostic tests now preserve the observed PBX→PMS STX/ETX-framed `LS` behavior and the known CRLF-reply framing failure. Matrix-specific post-`LS` progression, retry timing, site port, ENQ/ACK behavior, guest-event semantics, PMS→PBX application direction, and broader Matrix modes/models remain unqualified. Generic FIAS `LD`/`LR`/`LA` knowledge must not be promoted into Matrix-specific truth without Matrix evidence.

### Fifth PBX family: Hitachi / Epitome

Hitachi is evidence-indexed rather than an evidence-free placeholder. Legacy PhoneSuite/Voiceware documentation explicitly identifies two Epitome-to-Hitachi profile variants:

- `Hitachi × EPIT-HIT / Epitome Hitachi emulation × unknown transport × Epitome × EPIT-HIT × PMS_TO_PBX = planned / legacy_source_profile`
- `Hitachi × EPIT-HIT2 / Epitome Hitachi room-name layout variant × unknown transport × Epitome × EPIT-HIT2 × PMS_TO_PBX = planned / legacy_source_profile`

`EPIT-HIT` is documented as the default Epitome Hitachi-emulation interface used in Navy NGIS/Navy Lodge deployments. `EPIT-HIT2` is separately documented as the variant to use when normal check-ins fail because the room number and guest name do not appear where expected. Keeping these as separate matrix rows matters because `EPIT-HIT2` is an evidence-backed dialect/profile choice rather than an informal note attached to `EPIT-HIT`.

Both rows deliberately retain `transport=unknown`. The general Voiceware setup material discusses serial PBX-interface configuration, but the available `EPIT-HIT`/`EPIT-HIT2` descriptions do not themselves bind either profile to a transport or serial settings. Neither row therefore qualifies framing, control bytes, baud/data/parity/stop values, byte-level record layout, checksum/BCC, or reverse-direction behavior. Guessed `serial` and `tcp` combinations fail closed as `unsupported`.

## Evidence ranking

Rows use the project evidence order:

1. packet capture
2. operator-confirmed behavior
3. legacy source/profile
4. simulator characterization
5. inference

Inference alone can never satisfy a `supported` claim. Test harnesses such as loopback sockets and POSIX PTYs validate implementation behavior but do not upgrade the underlying protocol evidence class.

## Test contract

A `supported` row must list deterministic test paths. Unit tests enforce this contract and also verify that unknown combinations fail closed. This makes the compatibility matrix suitable for later CLI/API/GUI presentation without turning auto-detection into auto-configuration.

For `partial` rows, deterministic test paths should still be recorded as coverage is added so the matrix documents what software behavior has actually been exercised without overstating evidence maturity.

For `planned` evidence-indexed rows such as Hitachi/Epitome, deterministic tests may validate the claim boundary itself while wire-level tests remain absent. The absence of a wire fixture must remain visible and must not be converted into an inferred transport or framing choice.

## Live/Codex acceptance rule

Runtime or field observations may tighten a row only when the result records the exact tested Git SHA, configured personality, application protocol, transport, direction, serial/TCP settings, synthetic test operation, and observed wire/control behavior. A result from an unspecified or older SHA is not sufficient to promote the current branch. Vendor binaries, credentials, customer/property identifiers, and real guest data must not be committed with the evidence.