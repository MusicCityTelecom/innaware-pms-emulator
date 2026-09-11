# Bidirectional PMS / PBX Emulation Architecture

## Goal

InnAware PMS Emulator must be able to emulate either side of a hospitality integration so a technician can isolate whether a fault belongs to the PMS, PBX, transport, framing, session handshake, or application payload.

A technician should be able to select combinations such as:

- PMS: Oracle / MICROS Opera FIAS -> PBX under test
- PMS: Hilton / PEP FIAS -> PBX under test
- PBX: Matrix SARVAM UCS -> PMS under test
- PBX: Mitel 1 / Mitel 2 -> PMS under test
- PBX: Voiceware OperaIP -> PMS under test
- PBX: InnAware UCP -> PMS under test

The emulator must not conflate a wire protocol with a product personality.

## Separation of concerns

The model has four independent dimensions:

1. **Domain** - PMS integration or call accounting.
2. **Emulated endpoint role** - PMS, PBX, call-accounting system, or PBX call-accounting output.
3. **Personality** - the product/system behavior being emulated (for example Opera, Matrix, Mitel, Voiceware, InnAware).
4. **Wire profile** - protocol, transport, framing, control bytes, handshake, timers, retries, and field semantics.

For example, FIAS is a wire/application protocol family. `Oracle / MICROS Opera` is a PMS personality. `Matrix SARVAM UCS - MICROS Opera` is a PBX personality. The same FIAS parser can be reused by both endpoints while role-specific state machines determine which side initiates link negotiation, which records are legal in each direction, and how acknowledgements are generated.

## Proposed interface model

Existing saved interfaces remain valid. New fields are additive and optional until migration is complete.

```text
name
purpose                 pms | call_accounting
emulation_role          pms | pbx | call_accounting_system | pbx_call_accounting_output
personality_id          optional product personality identifier
protocol                existing protocol adapter identifier
transport               tcp_server | tcp_client | serial | http_server
framing                 raw | cr | lf | crlf | stx_etx | stx_etx_bcc
session options          ENQ/ACK, ACK-record, retries, timers, checksum, initiator behavior
property_id              optional property state binding
```

`purpose` continues to describe the traffic domain. `emulation_role` describes which endpoint InnAware is pretending to be.

## Personality catalog

A personality is declarative metadata plus optional role-specific behavior. It should not duplicate protocol encoders unless the wire format actually differs.

Initial target personalities:

### PMS personalities

- `pms-opera-fias` - Oracle / MICROS Opera FIAS
- `pms-hilton-pep-fias` - Hilton / PEP FIAS
- `pms-onq` - Hilton OnQ compatibility family
- `pms-choice-advantage` - Choice Advantage compatibility family
- `pms-generic-fias` - generic FIAS endpoint

### PBX personalities

- `pbx-matrix-sarvam-opera` - Matrix SARVAM UCS MICROS Opera mode
- `pbx-matrix-type1` - Matrix Type 1 (capture/fixture maturity until fully characterized)
- `pbx-matrix-type2` - Matrix Type 2 / Mitel compatibility path
- `pbx-matrix-extended-starlight` - Matrix Extended Starlight
- `pbx-mitel-1` - Mitel 1 hotel PMS personality
- `pbx-mitel-2` - Mitel 2 hotel PMS personality
- `pbx-voiceware-operaip` - Voiceware-era OperaIP behavior
- `pbx-innaware-ucp` - InnAware UCP hospitality PMS endpoint
- `pbx-generic-fias` - generic PBX-side FIAS endpoint

## Matrix SARVAM UCS field observation

A live Matrix SARVAM UCS configured for `Micros Opera` was observed connecting as a TCP client to the PMS server and sending FIAS `LS` inside STX/ETX framing:

```text
02 4c 53 7c ... 7c 03
<STX>LS|...|<ETX>
```

This is distinct from the current built-in generic CRLF FIAS profile. A dedicated Matrix/Opera profile must therefore use FIAS record semantics with STX/ETX wire framing and Matrix-observed session behavior.

The current observation should be treated as field evidence, not a claim that every Matrix firmware/model uses identical behavior.

## Session responsibilities

The protocol adapter owns record encode/decode only.

The endpoint personality/session layer owns:

- which side initiates the session;
- client/server direction defaults;
- ENQ/ACK/NAK behavior;
- link-start/link-description/link-result/link-alive sequencing;
- record acknowledgements;
- retry and acknowledgement timers;
- keepalive generation;
- synchronization behavior;
- allowed record masks/directions;
- product-specific quirks discovered from fixtures or field captures.

The transport layer remains product-agnostic.

## Diagnostic modes

Each emulated endpoint should support:

- **Strict** - behave as closely as possible to the selected personality and reject invalid sequencing/records.
- **Permissive** - accept compatible variants while logging deviations.
- **Capture / Learn** - record bytes and decoded candidates without automatically mutating property state.
- **Fault injection** - optional delayed ACK, dropped ACK, NAK, malformed frame, disconnect, retry exhaustion, and keepalive loss for troubleshooting.

## UI direction

The operator flow should become:

```text
Create Endpoint
  Domain: PMS Integration
  Emulate: PMS | PBX
  System: Oracle/MICROS Opera | Hilton/PEP | Matrix SARVAM UCS | Mitel | Voiceware | InnAware UCP | Generic
  Interface/Profile: compatible choices for the selected system
  Transport: recommended default, overridable
  Advanced: framing/session/timers/controls
```

The UI should show two independent labels:

```text
Emulating: Matrix SARVAM UCS PBX
Wire profile: MICROS Opera FIAS / STX-ETX / TCP client-side behavior
```

This prevents product identity from being confused with protocol identity.

## Diagnostic matrix concept

A future `Integration Lab` view should permit two local endpoints to be connected internally or through loopback TCP/virtual serial so both halves can be proven without external equipment.

Examples:

```text
Opera PMS personality <-> Matrix PBX personality
Hilton/PEP PMS personality <-> Mitel PBX personality
Opera PMS personality <-> Voiceware PBX personality
Opera PMS personality <-> InnAware UCP PBX personality
```

The lab should report independently:

- transport state;
- framing validity;
- handshake state;
- decoded records;
- state changes;
- ACK/NAK timing;
- retries;
- protocol deviations;
- raw wire capture.

## Compatibility and release approach

- Do not break existing 0.3.x saved interfaces.
- Add fields with backward-compatible defaults.
- Do not change `v0.3.7`; this work belongs to the next feature release.
- Keep vendor manuals/proprietary source outside the repository. Store only original code, sanitized behavioral fixtures, factual interoperability observations, and compatibility labels required to identify protocols/products.
- Every field-observed personality must have sanitized fixtures and regression tests before being marked field-observed or higher maturity.
