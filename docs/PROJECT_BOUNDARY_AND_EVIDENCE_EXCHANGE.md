# Project Boundary and Interoperability Evidence Exchange

## Architectural boundary

**InnAware PMS-PBX Emulator is a standalone technician/installer support product.** It exists to simulate, test, characterize, and diagnose PMS-to-PBX and PBX-to-PMS integrations. Its responsibilities include lab/runtime emulation, transport testing, framing and handshake characterization, deterministic replay, capture analysis, compatibility evidence, and technician-facing diagnostics.

**InnAware UCP Hospitality PMS Gateway/Module is a separate production runtime.** It owns production hospitality integration behavior inside InnAware UCP. The emulator does not become that runtime, and the UCP gateway must not depend on the emulator application, UI, service process, Python package, storage model, or support-tool lifecycle.

The projects may share **data and knowledge**, not runtime ownership.

## Allowed cross-project reuse

The following artifacts are intentionally reusable by a separate production project such as the InnAware UCP Hospitality PMS Gateway:

- sanitized deterministic fixture documents;
- the explicit PBX-family × dialect × transport × PMS-family × PMS-protocol × direction compatibility matrix;
- evidence class and evidence-readiness metadata;
- clean-room wire observations and expected transaction outcomes;
- protocol/profile test expectations and diagnostic knowledge;
- source SHA and fixture SHA-256 provenance needed to reproduce a claim.

The following are deliberately **not** cross-project runtime dependencies:

- `innaware_pms_emulator` Python modules;
- the emulator FastAPI service, operator console, Windows launcher, or service lifecycle;
- emulator property/session storage or technician workflow state;
- simulator orchestration and field-support UI behavior;
- opaque vendor executables, proprietary profile bodies/manuals, original customer captures, credentials, or guest PII.

A downstream project may copy a sanitized fixture into its own test resources or ingest a generated evidence pack during development/CI. It should implement and own its production adapter/runtime behavior in its own repository and lifecycle.

## Consumer-neutral evidence pack

The feature branch provides a deterministic data-only exchange contract in:

- `src/innaware_pms_emulator/interop_evidence_pack.py`
- `scripts/build-interop-evidence-pack.py`

Build a pack from an exact checked-out emulator revision:

```bash
git rev-parse HEAD
python scripts/build-interop-evidence-pack.py \
  --source-sha "$(git rev-parse HEAD)" \
  --output /tmp/innaware-pms-pbx-interop-evidence.json
```

On PowerShell:

```powershell
$sha = (git rev-parse HEAD).Trim()
python scripts/build-interop-evidence-pack.py `
  --source-sha $sha `
  --output "$env:TEMP\innaware-pms-pbx-interop-evidence.json"
```

The builder requires a full 40-character Git SHA. Abbreviated or unpinned source revisions are rejected so evidence cannot silently lose provenance.

The generated JSON contains:

- producer project/repository and exact source SHA;
- the architectural boundary and data-only exchange rule;
- evidence ranking in the project-required order;
- every current compatibility row with readiness gaps;
- only explicitly registered, sanitized JSON fixtures;
- a SHA-256 digest for each exported fixture document;
- production-claim policy that keeps `PARTIAL`, `PLANNED`, and unknown combinations from becoming production support claims.

The output is deterministic for a given repository state and `source_sha`; it intentionally contains no generation timestamp.

## Shareable fixture registry

The export registry is intentionally small and explicit. A fixture is not exported merely because it exists under `tests/`.

Current reusable evidence documents include:

| PBX family | Direction | Transport | Evidence class | Fixture |
| --- | --- | --- | --- | --- |
| Mitel iPocket-characterized | bidirectional | TCP | packet capture | `tests/data/emulation/mitel_ipocket_tcp.json` |
| Mitel legacy MTL-compatible | PMS → PBX | serial | simulator characterization | `tests/data/emulation/mitel_serial_pms_to_pbx.json` |
| PhoneSuite MITEL-1-compatible | PBX → PMS | serial | simulator characterization | `tests/fixtures/pbx/phonesuite_serial_characterization.json` |
| Matrix SARVAM MICROS Opera/FIAS | PBX → PMS | TCP | operator confirmed | `tests/fixtures/pbx/matrix_sarvam_micros_opera_characterization.json` |

This registry is not a statement that those rows are fully supported. It preserves the existing evidence class and matrix status exactly.

## Promotion and production-consumption rules

The evidence pack is deliberately conservative:

1. An exact six-dimensional row must exist; nearby transports or personalities are not substitutes.
2. `PLANNED` rows are evidence lineage only and are not runtime compatibility claims.
3. `PARTIAL` rows are useful for development, diagnostics, and regression testing but are not automatically production-ready.
4. A `SUPPORTED` row must have deterministic tests and a registered shareable sanitized fixture before the export registry will validate.
5. Unsupported combinations continue to fail closed rather than borrowing a neighboring row.
6. Evidence ranking remains: packet capture > operator-confirmed behavior > legacy source/profile > simulator characterization > inference.

At the current v0.4.0 feature state, there are no rows promoted to `SUPPORTED`. A downstream UCP implementation should therefore treat the exported material as qualified development/test evidence unless and until the exact row is promoted by stronger evidence and deterministic coverage.

## Recommended UCP consumption pattern

A clean downstream workflow is:

```text
InnAware PMS-PBX Emulator repository at exact SHA
        |
        | build data-only evidence pack
        v
pinned JSON pack + sanitized fixtures
        |
        | ingest in UCP development/CI or copy selected fixtures
        v
InnAware UCP Hospitality PMS Gateway repository
        |
        | independent production adapter implementation and tests
        v
UCP release lifecycle
```

The UCP project should record the emulator source SHA and individual fixture SHA-256 values when it imports evidence. This creates a reviewable evidence lineage without making either repository a runtime dependency of the other.

If the UCP implementation later produces new clean-room captures or corrected fixtures, those facts can be contributed back to the emulator as evidence after sanitization and review. The exchange remains artifact/evidence based in both directions.

## Validation

Repository tests enforce the exchange boundary:

```bash
python -m pytest -q tests/test_interop_evidence_pack.py
```

The validation checks that:

- registered reusable fixtures map to an exact compatibility row;
- fixture evidence class matches the matrix evidence class;
- only JSON documents explicitly marked sanitized are embedded;
- a production `SUPPORTED` row cannot lack a shareable fixture;
- source provenance is a full Git SHA;
- the pack remains deterministic and data-only;
- the CLI builder works cross-platform using the same contract.

This exchange mechanism intentionally does not alter any transport, framing, session, or application-protocol implementation and does not promote any compatibility row.
