# InnAware Hospitality Interoperability Findings

## Purpose

This is the living engineering record for hospitality PMS/PBX interoperability findings that must carry forward from the InnAware PMS Emulator into the final InnAware UCP product.

The emulator is the characterization and troubleshooting laboratory. InnAware UCP is the production PBX. Protocol behavior proven here should be implemented from the same clean-room behavioral model so the emulator can later validate UCP from the opposite endpoint.

Claims in this document are intentionally qualified by evidence level. Do not silently promote field knowledge, one-device captures, or legacy compatibility observations into universal vendor specifications.

## Evidence levels

| Level | Meaning |
| --- | --- |
| `field-observed` | Captured from an actual deployed PBX/PMS integration. |
| `operator-field-knowledge` | Repeated field knowledge supplied by the project owner/technician, but not yet represented by a sanitized capture in the repository. |
| `emulator-observed` | Observed from a third-party vendor emulator using synthetic data. |
| `fixture-backed` | Represented by sanitized regression fixtures/tests in this project. |
| `legacy-profile-reference` | Derived from historical compatibility profile behavior supplied for interoperability work. |
| `inferred` | Engineering inference that still needs characterization. |
| `unknown` | Explicitly not yet characterized. |

## Canonical PBX brands

The technician-facing PBX brand catalog for the emulator and final UCP interoperability tooling is:

| PBX | Compatibility organization | Notes |
| --- | --- | --- |
| Mitel SX-200 | Mitel-derived hospitality family | Primary historical reference family. |
| Mitel MiVoice | Mitel-derived hospitality family | Later Mitel generation; transport deployment may differ from SX-200. |
| PhoneSuite | Mitel-derived hospitality family | Includes PhoneSuite/Voiceware-era compatibility modes where applicable. |
| Matrix | Mitel-derived hospitality family plus Matrix-specific modes | Matrix also exposes modes such as MICROS Opera/FIAS, Type 1, Type 2, and Extended Starlight. |
| Hitachi | Separate Hitachi family | Do not force Hitachi through a Mitel adapter. |
| InnAware UCP | Mitel-derived compatibility plus InnAware-supported modern profiles | UCP must intentionally support the compatibility profiles we choose to ship. |

`Mitel 1`, `Mitel 2`, `FIAS`, `OperaIP`, `Hitachi`, etc. are protocol/profile choices underneath a PBX identity, not manufacturer names.

Evidence: `operator-field-knowledge`, plus existing field and legacy profile observations.

## Mitel family lineage

The project owner reports that the hotel PMS interfaces used by Mitel SX-200, later Mitel systems, PhoneSuite, Matrix compatibility modes, and the planned InnAware compatibility layer are historically based on the Mitel hotel interface family. Hitachi is the important exception in the current target set.

Treat this as a compatibility lineage, not a claim that every product emits identical bytes for every mode. Product/firmware/profile quirks still require fixtures.

Evidence: `operator-field-knowledge`.

## Mitel 1 versus Mitel 2

The primary practical distinction reported from field use is the guest-name (`NAM`) compatibility behavior/length. The `#2`/extended variant exists primarily to accommodate a longer or alternate guest-name message used by some PMS implementations.

The current InnAware development adapter historically modeled Mitel 2 as a fundamentally different room/name ordering. That model is now considered **provisional**. It must not be treated as authoritative until the Mitel and PhoneSuite reference emulators and/or sanitized captures establish the exact byte layouts.

Legacy compatibility profile findings supplied to the project support the broader pattern that `DEFAULT2` and similar `#2` variants are compatibility corrections around the guest-name message rather than entirely different hotel protocols.

Implementation requirement for both emulator and UCP:

- keep Mitel 1 and Mitel 2 selectable;
- share the common transaction/session implementation;
- isolate the `NAM` layout/length as profile data wherever possible;
- do not duplicate the entire protocol engine for a name-field compatibility variant;
- diagnostics should recognize a probable Mitel profile mismatch when room/name parsing fails or guest names arrive blank.

Evidence: `operator-field-knowledge`, `legacy-profile-reference`; exact lengths remain `unknown` until characterized.

## Hitachi variants

Hitachi is not part of the Mitel-derived family for this project. Supplied legacy profile references include `EPIT-HIT` and `EPIT-HIT2`. The `#2` Hitachi variant appears to address room/name positioning rather than merely the Mitel-style extended-name compatibility issue.

Implementation requirement:

- maintain an independent Hitachi adapter/profile family;
- support explicit standard/alternate layout profiles only after sanitized fixture characterization;
- do not alias Hitachi to Mitel 1 or Mitel 2.

Evidence: `legacy-profile-reference`; detailed wire format still requires sanitized fixtures.

## Serial is the native transport for many legacy hotel interfaces

Most of the historical Mitel-derived and vendor compatibility profiles supplied for this work were primarily designed for serial communications. The application protocol, serial transport, framing, and handshake must remain separate layers.

A profile can therefore be modeled as:

```text
PBX personality
    -> protocol/profile
        -> session/handshake
            -> framing
                -> transport
```

This permits the same Mitel application/session behavior to be carried over native serial or through a network serial bridge without falsely defining a new PMS protocol.

Evidence: `operator-field-knowledge`, `legacy-profile-reference`.

## Later Mitel deployments using iPocket serial adapters over Telnet

The project owner reports that later Mitel systems are commonly encountered connecting to iPocket serial adapters using a Telnet client connection. This is operationally important for both InnAware UCP and the emulator.

The likely architecture is conceptually:

```text
Mitel hotel PMS application protocol
        -> Mitel serial-style framing/session
        -> TCP/Telnet terminal-server session
        -> iPocket serial adapter
        -> serial endpoint
```

The key engineering rule is that **Telnet/iPocket is a transport/session wrapper around the serial-oriented Mitel hotel protocol, not a new PMS application protocol**.

InnAware should therefore plan transport capabilities that distinguish at least:

| Transport/session mode | Purpose |
| --- | --- |
| Direct serial | Native RS-232/serial PMS interface. |
| Raw TCP client/server | Carry an application protocol directly over TCP where the peer expects raw TCP. |
| Telnet client/server wrapper | Support terminal-server deployments that expect Telnet semantics. |
| Serial-device-server profile | Product/profile metadata for devices such as iPocket without baking the device brand into the PMS protocol. |

Open characterization item: determine whether the deployed iPocket path uses plain Telnet negotiation, transparent/raw TCP exposed as a Telnet service, RFC2217, or another serial-server mode. Do not implement RFC2217 assumptions without a real capture/configuration proving it.

Evidence: `operator-field-knowledge`; Telnet negotiation details are `unknown`.

## IP-oriented PMS integrations

The project owner's experience is that many later IP PMS interfaces are FIAS-based, especially MICROS/Opera-family deployments. This is broadly consistent with the current project observations, but **IP does not imply FIAS**.

Known architectural categories include:

| Category | Examples / notes |
| --- | --- |
| FIAS over TCP/IP | Generic FIAS, Hilton/PEP FIAS-family, Matrix MICROS Opera observation. |
| Product-specific TCP protocol | PhoneSuite/Voiceware OperaIP fixed-command behavior. |
| Serial protocol through TCP/Telnet wrapper | Later Mitel + iPocket deployment pattern. |
| HTTP/API | HotelKey-style integrations and future API-native PMS integrations. |

Therefore transport auto-detection and diagnostics must inspect actual wire behavior rather than classify every TCP socket as FIAS.

Evidence: `operator-field-knowledge`, `field-observed`.

## Matrix SARVAM UCS MICROS Opera observation

A live Matrix SARVAM UCS deployment configured for `Micros Opera` was observed acting as a TCP client toward the PMS endpoint and transmitting a FIAS `LS` record inside STX/ETX framing:

```text
<STX>LS|DA...|TI...|<ETX>
```

The initial InnAware test replied with valid FIAS `LS` text but CRLF framing. This exposed a critical diagnostic case: application payload semantics can be correct while wire framing is wrong, causing the PBX to remain in link-start negotiation.

Implementation requirements:

- Matrix MICROS Opera profile must support FIAS record semantics with the Matrix-observed STX/ETX framing behavior;
- the diagnostic engine must compare observed inbound framing with configured/generated outbound framing;
- link status must distinguish TCP connected from protocol/session active;
- do not send guest transactions merely because the socket is connected.

Evidence: `field-observed`.

## PhoneSuite / Voiceware OperaIP

The existing project has field-observed PhoneSuite/Voiceware-era OperaIP behavior using fixed hotel commands such as `CHK`, `NAM`, `MOV`, `WKP` and transactional control behavior involving ENQ/ACK and STX/ETX.

This must remain a selectable PhoneSuite profile/mode rather than being conflated with generic FIAS merely because it uses IP transport.

Evidence: `field-observed`.

## Dual-endpoint troubleshooting requirement

The emulator must be able to test either side of a production integration.

### Test a PBX

InnAware emulates the PMS and connects to the real PBX. The technician can generate PMS-originated actions such as check-in, checkout, guest name, room move, wakeup, restrictions, DND, messages, and synchronization, while decoding PBX-originated room status, posting, call, message, wakeup-result, synchronization, and control behavior.

### Test a PMS

InnAware emulates the PBX and connects to the real PMS. It receives PMS-originated check-in/out/name/wakeup/restriction commands, applies them to emulated PBX/property state, and can originate PBX-side room status, posting, call, wakeup result, message status, synchronization requests, ACK/NAK, and link behavior.

The saved interface must record both identities:

```text
personality_id       = what InnAware is pretending to be
peer_personality_id  = the real/remote system under test
```

This same dual-endpoint architecture should inform future UCP diagnostics/support tooling.

Evidence: project design requirement.

## Diagnostic requirements

Diagnostics must reason across transport, terminal-server/Telnet wrapper, framing, session controls, application record, product profile, and state transition independently.

A successful TCP/Telnet connection is not sufficient proof of a working PMS integration.

The diagnostic pipeline should independently evaluate:

| Layer | Example findings |
| --- | --- |
| Transport | unreachable host/port, serial device unavailable, disconnect/reconnect loop. |
| Telnet/terminal-server wrapper | negotiation mismatch, unexpected Telnet control bytes, raw-vs-Telnet mismatch. |
| Serial settings | baud/data/parity/stop/flow mismatch when direct serial is used. |
| Framing | CRLF vs STX/ETX vs STX/ETX+BCC mismatch. |
| Session controls | unanswered ENQ, missing ACK, NAK, timeout, retry exhaustion. |
| Protocol family | FIAS traffic while configured for fixed-command OperaIP, or vice versa. |
| Profile/layout | probable Mitel 1 vs Mitel 2 NAM mismatch; Hitachi standard vs alternate positioning. |
| Link state | repeated LS without LD/LR/LA progression; socket connected but session not active. |
| Semantic state | check-in transmitted but peer/property state did not change. |

Every finding should expose evidence, severity, confidence, probable cause, and suggested corrective action. Suggested fixes may be machine-readable for a future `Apply suggested fix` workflow, but production/live interfaces must never be silently changed.

## InnAware UCP production requirements derived from emulator work

InnAware UCP should eventually consume the same clean-room protocol/profile definitions and sanitized regression fixtures used by the emulator rather than implementing a separate, drifting interpretation of hospitality protocols.

The UCP hospitality subsystem should preserve these boundaries:

```text
semantic hotel event
        -> vendor/profile codec
        -> endpoint/session state machine
        -> framing/checksum
        -> transport wrapper (serial/raw TCP/Telnet/HTTP)
        -> physical/network endpoint
```

That separation is especially important for later Mitel/iPocket deployments: changing from direct serial to Telnet-terminal-server transport must not require rewriting the Mitel `CHK/NAM/WKP/RST` application logic.

## Characterization backlog

The following items remain important before profiles are promoted to production maturity:

| Item | Current state |
| --- | --- |
| Exact Mitel 1 vs Mitel 2 `NAM` lengths/layouts | Needs vendor-emulator/capture characterization. |
| Mitel SX-200 vs MiVoice application-level differences | Partially characterized / needs qualified fixtures. |
| iPocket Telnet negotiation mode | Unknown; capture/config needed. |
| PhoneSuite Mitel compatibility byte-for-byte comparison | Needs vendor emulator characterization. |
| Matrix Type 1 | Capture-only. |
| Matrix Type 2 exact Mitel variant | Partially characterized. |
| Matrix Extended Starlight | Capture-only. |
| Hitachi standard/alternate exact layouts | Needs sanitized fixtures. |
| InnAware UCP production personality | Planned; should be validated by the emulator from both directions. |

## Repository hygiene

Third-party executables, original vendor protocol profile files, proprietary manuals, credentials, and customer data are behavioral/reference material only and must not be published in the public InnAware repository.

Permanent repository artifacts should be original code, sanitized fixtures, concise behavioral observations, and regression tests.