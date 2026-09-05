# Technician Acceptance Plans

InnAware PMS-PBX Emulator is a standalone technician/installer interoperability and diagnostic tool. It is not the InnAware UCP Hospitality PMS Gateway runtime. This document describes a deterministic acceptance-plan artifact that can guide lab validation without turning test results into compatibility claims or coupling the two products.

## Purpose

`scripts/build-technician-acceptance-plan.py` projects the authoritative six-dimensional compatibility matrix and readiness registry into an exact-SHA technician acceptance plan. The plan tells a technician or Codex what can safely be tested, what transport facts must be recorded, which deterministic repository tests already support the row, and which evidence gaps remain open.

The plan does **not**:

- send traffic;
- open a serial port or TCP socket;
- select or change an interface personality;
- infer a transport from an application profile;
- promote a `PARTIAL` or `PLANNED` row;
- manufacture a reverse direction or bidirectional claim;
- make the Emulator a runtime dependency of the UCP Hospitality PMS Gateway.

Every generated plan sets `compatibility_promotion_authorized=false`. Compatibility promotion remains a separate reviewed repository change tied to evidence.

## Exact revision pinning

Always build a plan from the exact Emulator revision being validated:

```bash
SHA="$(git rev-parse HEAD)"

python scripts/build-technician-acceptance-plan.py \
  --source-sha "$SHA" \
  --output /tmp/pms-pbx-acceptance.json
```

The CLI rejects abbreviated or malformed Git SHAs. Store the exact SHA with any resulting lab observation so later work cannot confuse evidence collected against one revision with another.

## Filters

Plans may be narrowed by exact matrix dimensions exposed by the CLI:

```bash
python scripts/build-technician-acceptance-plan.py \
  --source-sha "$(git rev-parse HEAD)" \
  --pbx-family Mitel \
  --transport serial \
  --status partial \
  --output /tmp/mitel-serial-acceptance.json
```

For the current fifth-family evidence work:

```bash
python scripts/build-technician-acceptance-plan.py \
  --source-sha "$(git rev-parse HEAD)" \
  --pbx-family Hitachi \
  --status planned \
  --output /tmp/hitachi-evidence-acceptance.json
```

Filters are fail-closed. Asking for a combination with no exact matrix row, such as a guessed `Hitachi × serial × EPIT-HIT × PMS_TO_PBX` row while Hitachi transport is still unknown, produces an error rather than borrowing the `transport=unknown` profile lineage.

## Transport boundary

Transport is recorded separately from application personality.

For an exact `serial` row, the plan requires the technician to record the serial device/adapter identity, baud rate, data bits, parity, stop bits, and flow control. The plan intentionally supplies no serial defaults. Site settings or direct transport evidence must provide them. Mitel TCP reconnect/timing behavior must not be transplanted into Mitel serial, and generic Voiceware serial guidance must not become a PhoneSuite or Hitachi default.

For an exact `tcp` row, the plan records local and remote endpoint roles separately from local and remote addresses/ports. A site TCP port is installation evidence, not a universal protocol constant. Serial flow-control or framing assumptions must not leak into TCP.

For `transport=unknown`, `wire_test_permitted=false`. The only safe action is transport evidence acquisition: inspect an authorized exact profile or obtain a sanitized wire capture. Do not start a serial or TCP session merely because a neighboring Voiceware profile or another PBX family uses that transport.

## Direction boundary

Directional rows remain directional. A PMS-to-PBX test result does not create a PBX-to-PMS claim, and two independent directional rows do not automatically become a `BIDIRECTIONAL` row. A registered bidirectional row should still exercise and record both directions independently.

This is particularly important for Mitel serial and PhoneSuite, whose current directions have different evidence provenance.

## Safe lab evidence

Reusable observations must use synthetic or redacted room, guest, extension, DID, and status values while preserving the relevant wire semantics. Record, when applicable:

- exact Emulator source SHA;
- PBX model and firmware;
- PMS product and version;
- explicit transport configuration;
- direction;
- synthetic/redacted wire bytes and control sequence;
- observed diagnostic result;
- any evidence source digest used for comparison.

Use only operator-authorized lab or test hardware. The scheduled interoperability worker must not connect to live hotel systems.

Series2 TDMoE/PRI, Q.921/Q.931, D-channel signaling, B-channel bearer allocation, and `0x0E` station programming remain outside PBX-PMS application-protocol acceptance. They may be useful separate deployment evidence but are not a substitute for PMS-interface wire evidence.

## Evidence ranking and claim handling

Generated plans preserve the project evidence ranking:

1. packet capture;
2. operator-confirmed behavior;
3. legacy source/profile;
4. simulator characterization;
5. inference;
6. no evidence.

A passing deterministic test proves that the Emulator preserves the behavior encoded by that test. A passing live lab observation strengthens the evidence only when it is retained with exact provenance. Neither event changes the compatibility matrix automatically.

## UCP Hospitality PMS Gateway handoff

The generated JSON is safe to use as **data/test knowledge** for the separate InnAware UCP Hospitality PMS Gateway. A downstream test or release process may parse the plan to understand Emulator evidence boundaries, deterministic test lineage, and unresolved gaps.

It must not import `innaware_pms_emulator` as a production runtime dependency or move Emulator UI, simulator orchestration, capture-analysis, Windows field-tool, or technician-support responsibilities into UCP. Protocol evidence and synthetic fixtures may be shared; product code and lifecycle remain separate.

## Codex acceptance pattern

Codex should first pin the exact requested feature SHA and run the deterministic tests declared by the relevant rows. For a serial row, it should additionally record all serial parameters from the authorized lab setup. For a TCP row, it should record endpoint roles separately from addresses and ports. For a Hitachi `transport=unknown` row, it should **not** attempt a wire session; it should collect the exact Epitome/EPIT-HIT/EPIT-HIT2 profile evidence read-only, produce the sanitized profile bundle/admission report, and return that evidence for separate matrix review.

A useful final acceptance record states the exact Emulator SHA, exact matrix row, deterministic tests run, hardware/runtime evidence collected, remaining readiness gap codes, and whether a separate matrix change is required. It must never state that compatibility was promoted merely because the plan or tests passed.
