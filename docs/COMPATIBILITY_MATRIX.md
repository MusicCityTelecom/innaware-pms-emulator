# PBX↔PMS compatibility claim matrix

`src/innaware_pms_emulator/compatibility_matrix.py` is the machine-readable compatibility claim surface for v0.4.x.

Each row is keyed by all six required dimensions:

`PBX family × PBX dialect × transport × PMS family × PMS protocol × direction`

The matrix is deliberately fail-closed. An exact combination that is not explicitly registered is returned as `unsupported`; the emulator must not silently substitute a nearby personality or transport.

When the only difference from an evidence-indexed row is transport, the failed lookup now explains that boundary instead of returning an opaque generic failure. If the known row itself has `transport=unknown` (for example the current Hitachi/Epitome lineage), a requested serial or TCP transport remains `unsupported` and is explicitly identified as evidence-unqualified. If evidence exists only on another concrete transport, the diagnostic names that transport and warns not to transpose framing, timing, handshake, or application behavior. These messages are technician guidance only; they do not create a new compatibility row or promote evidence.

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

PhoneSuite serial now has **separate directional rows** instead of an aggregate bidirectional claim, because the available evidence has different provenance in each direction.

`PhoneSuite × MITEL 1-compatible × serial × legacy-hotel-pms × mitel-hospitality × PBX_TO_PMS` remains `partial / simulator_characterization`. Its clean-room fixture, dedicated session adapter, live serial selector, and Linux POSIX PTY tests cover characterized ENQ/ACK plus STX/ETX `CHK0`, `CHK1`, and `NAM2` behavior, fragmented/coalesced reads, close/reopen reset, and peer ACK/NAK control routing.

`PhoneSuite × MITEL 1-compatible × serial × legacy-hotel-pms × mitel-hospitality × PMS_TO_PBX` is separately registered as `partial / legacy_source_profile`. Historical PhoneSuite/Voiceware PMS-interface documentation explicitly states that either PhoneSuite or the PMS can be the sender for the ENQ/ACK/STX-message-ETX exchange. The same source qualifies a broader PMS-originated application subset than the initial CHK-only policy: `CHK0`/`CHK1`, `LMT`, `DND0`/`DND1`, `GRP`, `LNG`, `MW 0`/`MW 1`, `RSTn`, `AREYUTHERE`, database-dump boundary controls `GRS`/`END`, and guest-name commands `NAM1` through `NAM4`. `phonesuite_pms_policy.py` exposes these source-backed command families with technician-facing expected-format hints while deliberately leaving ambiguous or reverse-direction families such as `MOV`, `MSGn`, `STSn`, and `RQINZ` outside this PMS→PBX qualification boundary.

The same documentation qualifies PhoneSuite's receive-side timing: after PhoneSuite ACKs a PMS ENQ, STX must arrive within **0.100 second**; between-character delay greater than **0.100 second** times out the transaction; ETX must terminate the message inside that receive window; and late non-ENQ data after the timed-out transaction is answered with NAK. `phonesuite_pms_policy.py` preserves these facts as deterministic technician diagnostics rather than importing the Mitel-compatible three-second timer or Mitel frame-only retry count.

PhoneSuite-specific baud/data/parity/stop/flow defaults are still **not** claimed. Voiceware setup documentation allows serial and TCP/IP methods and gives general serial configuration guidance, while the existing serial characterization/runtime proves the emulator's serial path. Those facts do not establish a universal PhoneSuite serial parameter set. The PhoneSuite PBX-interface documentation says the application text may carry an optional checksum, but the currently indexed section does not qualify a PhoneSuite checksum algorithm/placement contract strongly enough to implement one here. Retry policy also remains unqualified. Linux PTY validation is test infrastructure, not a new protocol-evidence class. Series2/Voiceware TDMoE, PRI, Q.921/Q.931, D-channel, or `0x0E` station-programming observations must not be treated as PhoneSuite PBX↔PMS serial/application evidence.

An aggregate `BIDIRECTIONAL` PhoneSuite row intentionally remains absent. Consumers must query the exact direction so the simulator-characterized PBX→PMS evidence is not silently promoted to the stronger legacy-source class used for the PMS→PBX subset.

### Matrix FIAS

Matrix `MICROS Opera / FIAS` over TCP remains `partial` based on operator-confirmed field behavior. A dedicated sanitized Matrix SARVAM fixture, profile, and deterministic diagnostic tests now preserve the observed PBX→PMS STX/ETX-framed `LS` behavior and the known CRLF-reply framing failure. Matrix-specific post-`LS` progression, retry timing, site port, ENQ/ACK behavior, guest-event semantics, PMS→PBX application direction, and broader Matrix modes/models remain unqualified. Generic FIAS `LD`/`LR`/`LA` knowledge must not be promoted into Matrix-specific truth without Matrix evidence.

### Fifth PBX family: Hitachi / Epitome

Hitachi is evidence-indexed rather than an evidence-free placeholder. Legacy PhoneSuite/Voiceware documentation explicitly identifies two Epitome-to-Hitachi profile variants:

- `Hitachi × EPIT-HIT / Epitome Hitachi emulation × unknown transport × Epitome × EPIT-HIT × PMS_TO_PBX = planned / legacy_source_profile`
- `Hitachi × EPIT-HIT2 / Epitome Hitachi room-name layout variant × unknown transport × Epitome × EPIT-HIT2 × PMS_TO_PBX = planned / legacy_source_profile`

`EPIT-HIT` is documented as the default Epitome Hitachi-emulation interface used in Navy NGIS/Navy Lodge deployments. `EPIT-HIT2` is separately documented as the variant to use when normal check-ins fail because the room number and guest name do not appear where expected. Keeping these as separate matrix rows matters because `EPIT-HIT2` is an evidence-backed dialect/profile choice rather than an informal note attached to `EPIT-HIT`.

Both rows deliberately retain `transport=unknown`. The general Voiceware setup material discusses serial PBX-interface configuration, but the available `EPIT-HIT`/`EPIT-HIT2` descriptions do not themselves bind either profile to a transport or serial settings. Neither row therefore qualifies framing, control bytes, baud/data/parity/stop values, byte-level record layout, checksum/BCC, or reverse-direction behavior. Guessed `serial` and `tcp` combinations fail closed as `unsupported`. Those transport-only near misses now produce an actionable explanation that the Hitachi lineage is real but the selected transport is not yet evidence-qualified.

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
