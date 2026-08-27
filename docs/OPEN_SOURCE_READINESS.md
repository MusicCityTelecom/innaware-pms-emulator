# Open-source readiness and provenance

The InnAware PMS Emulator is intended to become a freely available interoperability and field-test tool, but the repository should not be made public until the release boundary is deliberately reviewed.

## Clean implementation rule

This repository should contain original emulator code, original documentation, factual protocol behavior needed for interoperability, and properly licensed dependencies. Historical PBX modules, vendor manuals, screenshots, proprietary sample source, firmware, logos, or distinctive vendor documentation must not be copied into this repository merely because they were useful as research references.

When a legacy implementation or third-party document teaches a required behavior, record the functional requirement and implement the behavior independently. Preserve test evidence that demonstrates interoperability without reproducing protected expression.

## Compatibility names

Names such as Hilton, PEP, OnQ, Oracle, Opera, Choice Advantage, HotelKey, TelElectronics, InnForm, HOBIS and Holidex are compatibility targets or protocol/profile descriptions. Their presence must not imply sponsorship, certification, partnership, ownership, or endorsement.

Before public release, review product names and README language for accurate nominative/descriptive use. Do not add third-party logos unless there is a separately established right or reason to do so.

## License decision is intentionally pending

No public-source license is selected by this document. Before changing the repository from private to public, explicitly choose and add a `LICENSE` file. The choice should reflect the intended contribution/reuse model and should be reviewed together with the licenses of redistributed dependencies and any bundled assets.

Do not assume that choosing a permissive or copyleft license changes obligations attached to third-party software.

## Required pre-publication gate

Before making the repository public:

1. Run the Linux and Windows CI matrix successfully.
2. Build and smoke-test the Windows EXE on an actual Windows host.
3. Verify every protocol adapter against independently documented expected behavior and regression fixtures.
4. Review repository history for accidentally committed credentials, private keys, customer/property data, proprietary documents, screenshots, or vendor source code.
5. Produce a dependency/SBOM inventory and review dependency licenses.
6. Add the chosen project `LICENSE` and appropriate third-party notices.
7. Review all compatibility names and disclaimers.
8. Confirm that generated Windows packages contain only intended runtime files.
9. Preserve source tags, build hashes, CI artifacts and release notes for each public release.
10. Consider a fresh public-history repository or history sanitization if the private history ever contained material that should not be published.

## Security boundary

The emulator is a laboratory instrument. It can intentionally generate check-ins, check-outs, wakeups, call-accounting records, control bytes and malformed/failure traffic as development expands. The management UI should remain bound to `127.0.0.1` by default. Binding it to a LAN address should be an explicit operator decision.

Do not connect it to a production PMS, billing endpoint or customer environment unless test traffic is explicitly authorized.

## Release evidence worth preserving

For each release retain:

- Git commit and tag.
- Test results from Linux and Windows.
- Windows EXE SHA-256.
- Source archive SHA-256.
- Dependency/SBOM output.
- Protocol compatibility matrix and maturity status.
- Human smoke-test notes for TCP and serial operation.
- Any independent interoperability fixture provenance notes.
