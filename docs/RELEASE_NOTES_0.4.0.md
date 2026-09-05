# InnAware PMS Emulator 0.4.0

## Field-candidate release notes

0.4.0 is the candidate line for the standalone InnAware PMS-PBX Emulator technician and installer support tool. It remains separate from the InnAware UCP Hospitality PMS Gateway production runtime. This candidate is intentionally not configured for automatic publication while exact-head field-product acceptance is still open.

### Candidate scope

- preserves the Windows-first, cross-platform Emulator product and its standalone lifecycle;
- keeps transport independent from application personality, including distinct Mitel TCP and Mitel serial behavior;
- carries evidence-backed PhoneSuite serial and Matrix FIAS/TCP characterization plus bounded fifth-family evidence handling;
- uses an explicit PBX-family × dialect × transport × PMS-family × PMS-protocol × direction compatibility registry;
- provides deterministic synthetic or redacted fixtures and technician-oriented diagnostics without committing guest data or vendor executables;
- preserves Windows/PyInstaller packaging and Debian compatibility.

### Evidence and compatibility policy

Compatibility status remains evidence-driven. `PARTIAL` and `PLANNED` rows are not production-support declarations, and a green software build does not promote a protocol combination. Every future `SUPPORTED` combination must have deterministic fixture coverage and the required evidence for that exact six-dimensional row.

Series2 TDMoE/PRI/Q.921/Q.931/D-channel station programming remains outside PBX↔PMS application-protocol scope.

### Field-product closure

Before this candidate is eligible for a release decision, closure evidence must be tied to one exact Emulator SHA and must include:

1. real cross-platform Test execution and a real Windows packaging run;
2. an exact artifact manifest and hashes;
3. disposable Windows native-GUI and browser-console acceptance using the same executable hash;
4. an isolated synthetic end-to-end exchange with the separate UCP Hospitality PMS Gateway, with exact SHAs for both projects and a sanitized transcript hash.

A no-runner or zero-step CI execution is infrastructure-blocked and cannot satisfy a release gate.

### Release metadata

- Application version: `0.4.0`
- Candidate tag identity: `v0.4.0`
- Protocol-pack version: `2026.08.27.1`
- Primary field platform: Windows 10/11 x64
- Release channel: field beta
- Automatic publication: disabled for candidate qualification

### Boundary with UCP Hospitality PMS Gateway

The separate UCP Hospitality PMS Gateway may reuse sanitized fixtures, wire evidence, compatibility coordinates, and test knowledge. It must not import the Emulator runtime or adopt the Emulator's UI, session orchestration, storage, packaging, or release lifecycle.

For the candidate gate, see `docs/FIELD_CANDIDATE_CLOSURE.md`. For operating instructions, see `docs/WINDOWS_QUICK_START.md`.
