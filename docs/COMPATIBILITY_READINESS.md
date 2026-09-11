# Compatibility evidence readiness

`src/innaware_pms_emulator/compatibility_readiness.py` is the machine-readable evidence-gap companion to the six-dimensional compatibility matrix.

The matrix answers what is currently claimed for an exact PBX family, dialect, transport, PMS family, PMS protocol, and direction. Readiness answers what evidence is still missing before that exact row could be considered for promotion.

Readiness never promotes a compatibility row. Green software tests prove implementation behavior only; they do not strengthen packet, hardware, transport, or legacy-profile evidence by themselves.

## Contract

Every current `PARTIAL` or `PLANNED` row has explicit evidence gaps. `validate_readiness_registry()` detects missing and stale gap registrations. A `SUPPORTED` row must have no registered gaps. An unsupported lookup receives an `exact_row_missing` readiness gap rather than borrowing a nearby dialect, direction, or transport.

Transport remains independent from application personality. Serial parameters, TCP behavior, framing, timing, retries, checksums, and direction must be qualified by evidence for the exact row.

## Current priority gaps

Mitel TCP still needs broader model/firmware and field-variant evidence. Mitel serial remains direction-specific and still needs real-hardware serial characterization plus serial-specific timing evidence rather than TCP transposition.

PhoneSuite serial still needs hardware confirmation and PhoneSuite-specific serial-parameter evidence. The PMS-to-PBX row additionally retains explicit checksum-contract and retry-policy gaps.

Matrix MICROS Opera/FIAS TCP still needs post-`LS` progression, Matrix-specific timing, configured port context, handshake characterization, guest-event records, and reverse-direction evidence.

Hitachi/Epitome remains the fifth evidence-backed PBX family but is still `PLANNED`. `EPIT-HIT` requires the exact profile body to be characterized by source SHA-256, plus transport, framing/control, record-layout, checksum, and reverse-direction evidence. `EPIT-HIT2` has the same requirements plus a sanitized delta against `EPIT-HIT` and `Epitome` so the room/name-placement variant can be isolated without treating generic Voiceware settings as Hitachi truth.

## Acceptance evidence

A live result should record the exact emulator SHA, PBX model/firmware when known, exact personality and direction, explicit transport settings, the synthetic operation performed, and sanitized observed wire/control behavior. Legacy-profile characterization should also retain the source profile SHA-256.

For Hitachi, use the existing `characterize-legacy-profile.py` and `compare-legacy-profiles.py` workflow. A result may reduce a readiness gap only when it is tied to the exact tested emulator SHA and the exact source profile hash. Until transport is explicitly established by profile or wire evidence, the Hitachi rows must remain `transport=unknown`.
