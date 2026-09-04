# Hitachi / Epitome Profile Evidence Bundle

This workflow advances the fifth-family Hitachi/Epitome evidence surface without guessing transport or committing vendor profile bodies.

The current compatibility rows remain `PLANNED / LEGACY_SOURCE_PROFILE / transport=unknown` until direct profile or wire evidence resolves individual dimensions. Generating a bundle is evidence collection only; it does not promote a row.

## What the bundle does

`scripts/build-hitachi-profile-evidence.py` reads exactly these authorized textual files:

- `psip-pbx-protocol.Epitome`
- `psip-pbx-protocol.EPIT-HIT`
- `psip-pbx-protocol.EPIT-HIT2`

The builder refuses renamed inputs so one vendor profile cannot be silently relabeled as another. It uses the existing fail-closed legacy-profile characterizer with recognized record-layout opt-in and creates three sanitized comparisons:

1. Epitome → EPIT-HIT
2. EPIT-HIT → EPIT-HIT2
3. Epitome → EPIT-HIT2

The output retains source basenames, full source SHA-256 values, recognized identity/control/serial fields, recognized record and `[pbx-masks]` layout facts, warnings, and sanitized deltas. Unknown profile and mask values are never emitted. Raw profile bodies are never embedded.

The producer emulator revision must be supplied as an exact 40-character Git SHA. The JSON is deterministic and contains no timestamp, so a reviewed derived evidence document can be pinned by content digest and producer SHA.

## Evidence boundaries

The bundle intentionally states all of the following:

- profile facts do not prove real-hardware interoperability;
- a room/name layout delta does not qualify serial or TCP transport;
- transport is accepted only when the profile explicitly declares it or separate sanitized wire evidence establishes it;
- reverse direction needs separate evidence;
- timing and retry behavior need separate evidence;
- generating a bundle does not change compatibility status.

This keeps transport separate from application personality and prevents generic Voiceware serial guidance from becoming a Hitachi default.

## Safe exact-SHA collection procedure

On the reviewed emulator checkout:

```bash
cd /opt/innaware/innaware-pms-emulator

git fetch origin \
  main \
  feature/pbx-emulation-v0.4.0 \
  codex/pbx-emulation-fixtures-v0.4.0

git checkout feature/pbx-emulation-v0.4.0
SHA="$(git rev-parse HEAD)"

git diff --check
python -m pytest -q \
  tests/test_hitachi_profile_evidence.py \
  tests/test_legacy_profile_evidence.py \
  tests/test_legacy_profile_compare.py \
  tests/test_compatibility_readiness.py \
  tests/test_compatibility_matrix.py
```

On an authorized Voiceware system, locate the three profiles read-only. A historical deployment may expose them in the container at `/usr/local/etc/psip-pms`; some deployments bind that directory from a host path such as `/data/psip/configs`. Verify the actual deployment rather than assuming a host path.

Keep the raw files outside Git. From a machine that has temporary read-only access to the three profile files, run:

```bash
python scripts/build-hitachi-profile-evidence.py \
  --source-sha "$SHA" \
  --epitome /read-only/path/psip-pbx-protocol.Epitome \
  --epit-hit /read-only/path/psip-pbx-protocol.EPIT-HIT \
  --epit-hit2 /read-only/path/psip-pbx-protocol.EPIT-HIT2 \
  --output /tmp/hitachi-profile-evidence.json
```

The CLI prints a deterministic bundle SHA-256. Record that digest with the exact emulator SHA and the three source SHA-256 values already present inside the output.

Before sharing the derived JSON, review it for scope and confirm:

```bash
python - <<'PY'
import json
from pathlib import Path

p = json.loads(Path('/tmp/hitachi-profile-evidence.json').read_text())
assert p['sanitized'] is True
assert p['raw_profiles_embedded'] is False
assert p['claim_policy']['layout_delta_does_not_qualify_transport'] is True
assert p['claim_policy']['compatibility_status_is_not_promoted_by_bundle_generation'] is True
assert set(p['profiles']) == {'epitome', 'epit_hit', 'epit_hit2'}
print('Hitachi derived evidence bundle: PASS')
PY
```

Do not commit the raw profiles. Do not commit an unreviewed derived bundle merely because the characterizer marks it sanitized. Promote only the minimum facts needed for deterministic synthetic fixtures and compatibility claims.

## How this can be reused by the UCP Hospitality PMS Gateway

The InnAware PMS-PBX Emulator and the InnAware UCP Hospitality PMS Gateway remain separate products and codebases.

A reviewed Hitachi evidence bundle may be supplied to the UCP project as **data/test evidence** together with its exact emulator producer SHA and bundle/source digests. The UCP project may use those facts to create its own independent production adapter tests or copy a synthetic fixture into its own test resources. It must not import `innaware_pms_emulator`, the emulator API/UI, simulator orchestration, or technician-support runtime.

This is the same artifact/evidence exchange boundary used by the consumer-neutral interoperability evidence pack: evidence can cross repositories; runtime ownership does not.

## Promotion path after real evidence arrives

A useful real bundle can close readiness gaps one at a time:

- an explicit transport key may resolve the transport gap;
- exact ENQ/STX/ETX/ACK/NAK or checksum fields may resolve framing/control or checksum gaps;
- recognized CHK/NAM and `[pbx-masks]` differences may resolve the EPIT-HIT2 room/name-layout delta;
- absent fields stay unknown rather than being inherited from another profile.

Even a complete profile bundle does not establish reverse-direction behavior, timing/retry semantics, or successful hardware interoperability. Those require separate evidence before any corresponding matrix promotion.
