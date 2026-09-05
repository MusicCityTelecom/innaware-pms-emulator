# Hitachi / Epitome source-lineage guidance

This workflow belongs to the standalone **InnAware PMS-PBX Emulator** technician/support tool. It does not add runtime responsibilities to the separate InnAware UCP Hospitality PMS Gateway.

## Evidence boundary

The project Sources include legacy Voiceware PMS setup documentation that explicitly identifies:

- `EPIT-HIT` as the Epitome Hitachi-emulation interface; and
- `EPIT-HIT2` as the corrective Epitome/Hitachi variant to investigate when normal check-in fails because room-number and guest-name placement is not where the peer expects it.

That source is valuable evidence for the **existence and purpose of the fifth-family lineage**, but it does not state the Hitachi transport. Nearby profile descriptions separately label FIAS as TCP/IP and FOSSE/Galaxy/OnQ/Opera as serial; those neighboring transport statements are not evidence for EPIT-HIT or EPIT-HIT2.

Accordingly, the authoritative Hitachi rows remain:

```text
Hitachi
× EPIT-HIT / Epitome Hitachi emulation
× unknown
× Epitome
× EPIT-HIT
× PMS_TO_PBX
= PLANNED / LEGACY_SOURCE_PROFILE

Hitachi
× EPIT-HIT2 / Epitome Hitachi room-name layout variant
× unknown
× Epitome
× EPIT-HIT2
× PMS_TO_PBX
= PLANNED / LEGACY_SOURCE_PROFILE
```

The setup source also does **not** establish framing/control bytes, serial parameters, TCP roles/ports, checksum semantics, retry/timing behavior, exact record byte offsets, reverse-direction behavior, or real-hardware interoperability.

## Technician CLI

Pin the exact Emulator SHA and request a source-bounded guidance report:

```bash
SHA="$(git rev-parse HEAD)"

python scripts/diagnose-hitachi-source-lineage.py \
  --source-sha "$SHA" \
  --pms-protocol EPIT-HIT2 \
  --symptom checkin_failure \
  --requested-transport serial \
  --output /tmp/hitachi-source-guidance.json
```

Valid symptoms are:

- `baseline` — the source-backed profile hint is EPIT-HIT;
- `checkin_failure` — the source-backed corrective-profile hint is EPIT-HIT2;
- `room_name_mismatch` — the source-backed corrective-profile hint is EPIT-HIT2;
- `unknown` — no profile-selection hint is emitted.

A hint is **not** authorization to change a live PMS/PBX profile. The report always emits `auto_profile_change_authorized=false` and `compatibility_promotion_authorized=false`.

If `--requested-transport serial`, `tcp`, `tcp_client`, or `tcp_server` is supplied, the report retains that requested value only as the technician's hypothesis. It still reports the matrix transport as `unknown` and `evidence_qualified=false`.

## Next evidence step

Acquire these exact legacy profiles read-only:

```text
psip-pbx-protocol.Epitome
psip-pbx-protocol.EPIT-HIT
psip-pbx-protocol.EPIT-HIT2
```

Do not commit the original vendor profile bodies. SHA-256 the originals, then use the existing sanitized workflow:

```bash
python scripts/build-hitachi-profile-evidence.py \
  --epitome /secure/path/psip-pbx-protocol.Epitome \
  --epit-hit /secure/path/psip-pbx-protocol.EPIT-HIT \
  --epit-hit2 /secure/path/psip-pbx-protocol.EPIT-HIT2 \
  --source-sha "$(git rev-parse HEAD)" \
  --output /tmp/hitachi-profile-evidence.json

python scripts/admit-hitachi-profile-evidence.py \
  --bundle /tmp/hitachi-profile-evidence.json \
  --expected-source-sha "$(git rev-parse HEAD)" \
  --output /tmp/hitachi-profile-admission.json
```

Only an explicit transport declaration in the exact profile evidence, or a sanitized real endpoint/wire observation, can justify a transport-specific matrix proposal. Even then, the admission workflow does not automatically promote compatibility.

For EPIT-HIT2, compare the sanitized `EPIT-HIT -> EPIT-HIT2` record-layout delta. The legacy setup source explains *why* the variant exists, while the exact profile bodies are the stronger evidence needed to determine the actual layout difference without guessing byte offsets.

## Source isolation

Do not borrow unrelated protocol facts to fill Hitachi gaps. In particular:

- a generic Voiceware serial/TCP configuration option does not prove Hitachi transport;
- PhoneSuite PMS-interface ENQ/ACK/NAK timing does not prove Hitachi session behavior;
- HOBIS call-accounting framing/checksum rules do not prove PBX↔PMS behavior;
- Mitel TCP or serial timing/retry behavior does not prove Hitachi behavior;
- Matrix/FIAS TCP behavior does not prove Hitachi behavior;
- Series2 TDMoE/PRI/Q.921/Q.931/D-channel/`0x0E` station programming is not a PBX↔PMS application protocol.

Transport and application personality remain separate evidence dimensions.

## Codex / Server3 acceptance

Validate only an exact feature SHA:

```bash
cd /opt/innaware/innaware-pms-emulator

git fetch origin \
  main \
  feature/pbx-emulation-v0.4.0 \
  codex/pbx-emulation-fixtures-v0.4.0

git checkout feature/pbx-emulation-v0.4.0

SHA="$(git rev-parse HEAD)"

python -m pytest -q \
  tests/test_hitachi_source_guidance.py \
  tests/test_hitachi_profile_evidence.py \
  tests/test_hitachi_evidence_admission.py \
  tests/test_hitachi_evidence_admission_cli.py \
  tests/test_compatibility_matrix.py \
  tests/test_transport_evidence_boundaries.py

python scripts/diagnose-hitachi-source-lineage.py \
  --source-sha "$SHA" \
  --pms-protocol EPIT-HIT2 \
  --symptom room_name_mismatch \
  --requested-transport tcp \
  --output /tmp/hitachi-source-guidance.json
```

Expected policy boundaries include:

```text
combination.transport = unknown
current_matrix.status = planned
requested_transport.evidence_qualified = false
claim_policy.transport_inferred = false
claim_policy.record_offsets_inferred = false
claim_policy.compatibility_promotion_authorized = false
claim_policy.runtime_profile_auto_change_authorized = false
architectural_boundary.exchange_mode = data_only
```

No live PBX is needed to accept this source-guidance slice. Live Hitachi/Epitome validation should wait for the exact profile bodies or an authorized sanitized wire capture tied to the exact Emulator SHA.

## Cross-project evidence handoff

The separate UCP Hospitality PMS Gateway may consume the generated JSON as **data/test knowledge**: six-dimensional coordinates, legacy evidence class, the documented EPIT-HIT/EPIT-HIT2 purpose distinction, unresolved transport status, and technician evidence actions.

It must not import the Emulator runtime, FastAPI/operator console, simulator/session orchestration, transport lifecycle, capture store, Windows launcher, or Emulator release/deployment lifecycle. This report is an evidence handoff, not shared runtime code.
