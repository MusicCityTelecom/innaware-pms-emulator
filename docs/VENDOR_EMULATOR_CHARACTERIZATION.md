# Vendor Emulator Behavioral Characterization

## Purpose

Third-party PBX/PMS emulator applications can be valuable interoperability references when characterizing how real hotel integrations behave. They must be used as **behavioral references only**.

The InnAware PMS Emulator project may derive original interoperability knowledge from observable behavior such as:

- protocol selection choices;
- transport defaults;
- serial settings;
- TCP client/server direction;
- framing;
- ENQ/ACK/NAK sequencing;
- link-establishment behavior;
- timers and retries;
- check-in/check-out behavior;
- guest-name updates;
- wake-up requests/results;
- room/housekeeping status;
- message/MWI state;
- restrictions/COS;
- call posting;
- synchronization requests;
- raw wire bytes generated from synthetic test cases.

## Do not copy proprietary implementation material

Do not commit or reproduce:

- vendor executables/installers;
- proprietary source code;
- decompiled source trees;
- copied manuals or help files;
- proprietary images/resources;
- private customer/property data;
- credentials, serial numbers, license keys, registration data, or customer identifiers;
- large verbatim string/resource dumps.

If binary inspection is useful, retain only the minimum original observations needed to understand behavior. Prefer black-box execution, packet capture, virtual serial capture, API/UI observation, and synthetic test cases over implementation extraction.

## Sanitized evidence

Permanent fixtures must be newly authored and sanitized.

Use values such as:

```text
Room:       101
Guest:      TEST / GUEST
Number:     15555550100
IP:         192.0.2.10
Date/time:  synthetic/fixed test value
```

Never preserve a real hotel's room/guest data merely because it appeared in a field capture.

## Recommended characterization matrix

For each vendor emulator/system, exercise the same semantic operations and record the resulting wire behavior:

1. startup/link establishment;
2. link alive/keepalive;
3. check in;
4. check out;
5. guest-name update;
6. room move;
7. wake-up set;
8. wake-up cancel;
9. room/housekeeping status;
10. DND;
11. restriction/COS;
12. language;
13. message/MWI;
14. synchronization request/response;
15. call posting where supported;
16. disconnect/reconnect;
17. negative/invalid transaction behavior.

Capture for each operation:

- direction;
- raw bytes/hex;
- decoded semantic event;
- framing;
- transport;
- control bytes;
- ACK/NAK requirements;
- timing/retry behavior;
- resulting emulator state.

## Mitel reference emulator

Use the Mitel Windows emulator to establish reference behavior for the Mitel-derived hospitality family, especially where our current `Mitel 1` and `Mitel 2` fixtures are incomplete.

Important targets include:

- exact room/name field order;
- fixed vs variable field widths;
- ENQ/ACK sequence;
- STX/ETX framing;
- whether CR/LF occurs inside or outside frames;
- transaction timing;
- retry behavior;
- PBX-originated events;
- serial defaults and any TCP-wrapper behavior offered by the emulator.

Do not assume a behavior is universal across SX-200 and MiVoice merely because one emulator exhibits it; qualify fixtures by product/profile when possible.

## PhoneSuite reference emulator

Use the PhoneSuite Windows emulator to characterize both its Mitel-derived baseline and any distinct PhoneSuite/Voiceware compatibility modes.

Important targets include:

- Mitel 1/Mitel 2 compatibility behavior;
- OperaIP/Voiceware-era ENQ/ACK plus STX/ETX behavior where exposed;
- supported PMS-originated commands;
- PBX-originated status/posting records;
- synchronization behavior;
- timers/retries;
- transport choices.

PhoneSuite remains one technician-facing PBX brand. `Voiceware`/`OperaIP` behavior should be represented as a PhoneSuite profile/mode where applicable, not as a separate manufacturer.

## Output

Characterization work should produce only:

- original sanitized fixture files;
- original regression tests;
- concise behavioral notes;
- compatibility/profile metadata;
- ambiguities that require real-device capture.

Each behavioral claim should be tagged by confidence/maturity such as:

- emulator-observed;
- field-observed;
- fixture-backed;
- partially characterized;
- capture-only.
