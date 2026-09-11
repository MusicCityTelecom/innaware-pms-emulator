# Matrix MICROS Opera / FIAS Characterization

## Scope

This document records the qualified Matrix SARVAM UCS interoperability boundary used by InnAware PMS Emulator v0.4.0 development. It is intentionally narrower than a general Matrix protocol specification.

The field observation is:

- PBX family: Matrix
- observed product: SARVAM UCS
- configured PBX mode: MICROS Opera
- application family: FIAS
- transport: TCP, with the Matrix acting as the client toward the PMS endpoint
- observed application record: `LS` (FIAS Link Start)
- observed framing: STX/ETX
- direction qualified by the observation: PBX to PMS

The permanent regression fixture uses synthetic date/time values and preserves only those wire semantics. It does not contain customer, guest, property, credential, or vendor-binary data.

Evidence class: **operator-confirmed field observation**. The sanitized regression fixture is implementation evidence derived from that observation; it does not upgrade the evidence class or broaden the claim.

## Important framing result

An earlier InnAware interoperability attempt returned valid FIAS `LS` text using CRLF framing. The Matrix remained in link-start negotiation because the observed peer used STX/ETX framing. This is the principal behavior this slice makes deterministic.

The built-in profile `matrix-micros-opera-fias-tcp-server` therefore keeps the layers explicit:

```text
Matrix PBX personality
    -> MICROS Opera / FIAS application dialect
        -> FIAS link state
            -> STX/ETX framing
                -> TCP server endpoint on InnAware
```

The profile does **not** enable ENQ/ACK controls. No Matrix MICROS Opera ENQ/ACK behavior has been qualified for this observation.

Port `5001` is the InnAware laboratory default and is not asserted as a Matrix vendor default. Technicians must set the port to the deployed site configuration.

## Link-state boundary

A successful TCP connection is only transport connectivity. Receiving the observed Matrix `LS` causes the PMS-side FIAS engine to enter `negotiating` and produce an `LS` reply using the configured STX/ETX framing. InnAware must not treat TCP-connected or first-LS-received as proof that the FIAS session is active.

Do not send guest transactions merely because the socket is open. Link progression beyond the observed `LS` remains qualified by generic FIAS implementation behavior until Matrix-specific evidence establishes the exact SARVAM progression.

### Project-source boundary review

Project Sources contain generic/vendor FIAS references that demonstrate common `LS`, `LD`, `LR`, and `LA` link-control records and legacy runtime logs that exercised a generic FIAS negotiation sequence. Those sources are useful for understanding the FIAS family, but they are **not Matrix SARVAM evidence**. No Matrix-specific sanitized source currently qualifies the exact post-`LS` order, retry timing, record-set negotiation, or activation transition.

Accordingly, generic FIAS `LD/LR/LA` behavior must not be promoted into the Matrix compatibility row. The next evidence gain must come from a Matrix-tied capture or operator-confirmed Matrix runtime observation associated with an exact InnAware commit SHA.

## Technician diagnostics

The smart diagnostic layer already distinguishes application records from framing. For this profile, a capture containing inbound STX/ETX `LS` and outbound CRLF `LS` should raise the framing findings:

- `configured-framing-mismatch`
- `wire-framing-asymmetry`
- `fias-link-start-framing-mismatch`

The corrective action is to select the Matrix MICROS Opera profile or explicitly configure STX/ETX framing, then retest link negotiation before troubleshooting room/guest payloads.

Remediation also preserves endpoint identity. On a PMS-side InnAware interface, Matrix is the **remote peer**, so a Matrix recommendation sets `peer_personality_id=pbx-matrix`; it must not rewrite InnAware's own `personality_id` to a PBX identity. If FIAS plus STX/ETX is already selected, observing the Matrix-like `LS` fingerprint alone does not justify another personality rewrite.

## Explicitly unqualified behavior

This characterization does not claim any of the following:

- Matrix vendor-default TCP port
- Matrix retry interval or timeout values
- ENQ/ACK/NAK control behavior for MICROS Opera mode
- full LD/LR/LA negotiation order for this Matrix model/firmware
- guest-event directionality or exact GI/GO/GC/WR field requirements
- Matrix Type 1 behavior
- Matrix Type 2 byte layout
- Matrix Extended Starlight behavior
- behavior of Matrix models or firmware other than the qualified SARVAM observation

Those items require new sanitized evidence before the compatibility matrix is expanded.

## Deterministic regression coverage

`tests/test_matrix_sarvam_characterization.py` verifies:

1. the permanent fixture is sanitized and only records the qualified inbound STX/ETX `LS` observation;
2. the Matrix profile selects FIAS over TCP with STX/ETX and does not invent ENQ/ACK settings;
3. the FIAS engine replies to the observed frame using STX/ETX and remains in negotiation rather than claiming an active session;
4. the diagnostic engine detects the known CRLF-vs-STX/ETX failure mode;
5. the dedicated profile removes that known framing mismatch.

`tests/test_diagnostic_recommendations.py` additionally verifies that Matrix remediation identifies the remote PBX through `peer_personality_id`, never overwrites InnAware's own endpoint personality, and does not produce a redundant Matrix-personality recommendation when the dedicated FIAS/STX-ETX wire profile is already selected.

The six-dimensional compatibility row remains **PARTIAL**.

## Safe live acceptance procedure

For a candidate feature-branch SHA, validate the exact checkout before collecting runtime evidence:

```bash
git fetch origin main feature/pbx-emulation-v0.4.0
git checkout feature/pbx-emulation-v0.4.0
git status --short --branch
git rev-parse HEAD
git diff --check
python -m pytest -q tests/test_matrix_sarvam_characterization.py tests/test_diagnostic_recommendations.py tests/test_compatibility_matrix.py tests/test_diagnostics.py tests/test_protocols.py
```

For Server3 isolation, use the repository verifier rather than reusing a production interface:

```bash
INNAWARE_PMS_REPO_DIR=/opt/innaware/innaware-pms-emulator bash scripts/verify-server3.sh
```

If a real Matrix is available, create a temporary PMS interface from `matrix-micros-opera-fias-tcp-server`, override the listen port to the site's configured value, and use synthetic room/guest actions only after link negotiation is demonstrably active. Preserve the exact commit SHA, interface configuration, and sanitized wire bytes with any new evidence. Never commit live guest data, credentials, customer addresses, or proprietary vendor files.

For the next Matrix evidence capture, stop after the protocol link exchange if possible: record the Matrix-originated bytes immediately after the STX/ETX `LS`, the InnAware response bytes, connection direction, and any subsequent Matrix link-control records. Do not enable ENQ/ACK or synthesize generic `LD/LR/LA` traffic merely to make the session advance; the purpose of this capture is to discover the Matrix-specific progression, not to force a generic FIAS model onto it.
