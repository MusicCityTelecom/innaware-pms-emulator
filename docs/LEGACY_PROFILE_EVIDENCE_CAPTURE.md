# Legacy PBX Profile Evidence Capture

This workflow exists to turn an authorized historical Voiceware/PSIP textual PBX profile into a **sanitized interoperability summary** without copying the vendor profile into this repository.

It is intended for evidence gaps such as the Epitome `EPIT-HIT` / `EPIT-HIT2` Hitachi-emulation profiles. The current project evidence establishes that those profile names existed and describes their purpose, but does not yet qualify their transport, control bytes, record layouts, checksum behavior, or serial parameters.

## Evidence boundary

The characterizer is deliberately fail-closed:

- it computes SHA-256 over the complete source file so the observation can be tied to an exact artifact;
- it reports only the source basename, never the source directory;
- it recognizes explicit protocol identity fields, control-byte fields, serial-parameter fields, and a bounded set of hotel-PMS record keys;
- it separately recognizes the Voiceware `[pbx-masks]` section used for room/name parsing overrides, but emits only a bounded set of structural mask keys;
- it never infers `serial` or `tcp` from a filename, PBX family, generic Voiceware defaults, or nearby documentation;
- it does not emit values from unknown keys in either `[pbx-protocol]` or `[pbx-masks]`;
- exact record-layout and recognized PBX-mask values are omitted unless `--include-record-layouts` is explicitly requested;
- binary/NUL-containing and unexpectedly large inputs are rejected.

A characterization result is **legacy source/profile evidence**, not packet-capture evidence and not proof of successful operation against real PBX hardware.

## Why `[pbx-masks]` is separate

Project Sources document that Voiceware uses `[pbx-masks]` for structural parsing overrides such as `chkdelim`, `namdelim`, `swapnames`, and `nameindex0`. That section can therefore contain exactly the room/name-placement differences that distinguish a compatibility variant such as `EPIT-HIT2` from its base profile. The characterizer reports recognized PBX-mask key names by default, but keeps their values private until the explicit layout opt-in is used. Unrecognized mask values are never emitted.

This distinction matters for evidence promotion: a difference in `[pbx-masks]` can qualify a layout variant, but it does not by itself qualify transport, framing, timing, reverse direction, or real-hardware interoperability.

## Safe Codex / Server3 acceptance

First prove the emulator checkout is the exact reviewed head before collecting evidence:

```bash
cd /opt/innaware/innaware-pms-emulator

git fetch origin main feature/pbx-emulation-v0.4.0 codex/pbx-emulation-fixtures-v0.4.0
git checkout feature/pbx-emulation-v0.4.0

git diff --check
python -m pytest -q tests/test_legacy_profile_evidence.py tests/test_compatibility_matrix.py
```

On an authorized historical Voiceware host, inspect the source files read-only. Do not copy executables, credentials, property configuration, or logs into the repository. Record file hashes alongside the emulator SHA:

```bash
sha256sum \
  /usr/local/etc/psip-pms/psip-pbx-protocol.Epitome \
  /usr/local/etc/psip-pms/psip-pbx-protocol.EPIT-HIT \
  /usr/local/etc/psip-pms/psip-pbx-protocol.EPIT-HIT2
```

Run the characterizer against local read-only copies or paths. The default mode does **not** emit record-mask values:

```bash
python scripts/characterize-legacy-profile.py \
  /path/to/psip-pbx-protocol.Epitome \
  /path/to/psip-pbx-protocol.EPIT-HIT \
  /path/to/psip-pbx-protocol.EPIT-HIT2 \
  > /tmp/hitachi-profile-evidence.json
```

Review that JSON before sharing it. If exact recognized CHK/NAM/RST/WKP/MW/etc. layouts or bounded `[pbx-masks]` room/name-placement values are required to build a synthetic fixture, repeat locally with the explicit opt-in:

```bash
python scripts/characterize-legacy-profile.py \
  --include-record-layouts \
  /path/to/psip-pbx-protocol.EPIT-HIT \
  /path/to/psip-pbx-protocol.EPIT-HIT2 \
  > /tmp/hitachi-profile-layout-evidence.json
```

Do **not** commit either raw profile file or an unreviewed characterization dump. Translate only the minimum interoperability facts needed for a synthetic/redacted fixture and document their source SHA-256 and evidence class in issue #4.

## Promotion rule

The Hitachi compatibility rows must stay `PLANNED` with `transport=unknown` until the profile evidence explicitly resolves those dimensions. A profile that explicitly declares transport/control/layout facts can justify a narrower `PARTIAL` claim and deterministic synthetic fixture. A `[pbx-masks]` difference alone can justify a narrower layout-variant characterization but must not be treated as transport evidence. None of these source-profile facts justify reverse-direction behavior, timing/retry semantics, or hardware interoperability unless those are separately evidenced.
