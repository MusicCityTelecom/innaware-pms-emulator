# Hitachi legacy profile intake

The InnAware PMS-PBX Emulator has a fifth-family evidence track for the legacy Epitome/Hitachi profiles `EPIT-HIT` and `EPIT-HIT2`. The authoritative matrix intentionally keeps both rows at `transport=unknown` until direct evidence establishes a transport. Generic Voiceware support for serial or TCP/IP, and neighboring profile descriptions such as FIAS or FOSSE, are not enough to assign a Hitachi transport.

`inspect-hitachi-profile-set.py` is the read-only intake step for a system where the exact legacy profile files are available. It reads the three required files in place:

- `psip-pbx-protocol.Epitome`
- `psip-pbx-protocol.EPIT-HIT`
- `psip-pbx-protocol.EPIT-HIT2`

The command does not copy or modify those files. The JSON output contains only sanitized characterization facts, exact source-file SHA-256 values, the deterministic evidence-bundle digest, and the existing fail-closed admission result for both Hitachi rows. It deliberately omits the local source-directory path and all raw profile bodies.

## Exact-SHA technician / Codex workflow

Run this only on an authorized copy of the Voiceware profile directory. Keep the vendor profile bodies outside Git.

```bash
cd /opt/innaware/innaware-pms-emulator

git fetch origin \
  main \
  feature/pbx-emulation-v0.4.0 \
  codex/pbx-emulation-fixtures-v0.4.0

git checkout feature/pbx-emulation-v0.4.0
SHA="$(git rev-parse HEAD)"

test "${#SHA}" -eq 40

python scripts/inspect-hitachi-profile-set.py \
  --source-sha "$SHA" \
  --profile-dir /usr/local/etc/psip-pms \
  --output /tmp/hitachi-profile-intake.json
```

The output is suitable for protocol review because it is data-only and SHA-pinned. It is **not** a production compatibility claim and it does not mutate `compatibility_matrix.py`.

## Interpreting the result

If `observed_concrete_transports` is empty, the exact profiles did not contain a recognized explicit transport key. Keep the matrix rows at `transport=unknown`; do not inherit serial or TCP from generic Voiceware settings or neighboring profiles.

If an exact profile explicitly declares `serial`, `tcp`, `tcp_client`, or `tcp_server`, the corresponding admission reports `matrix_change_required=true` and the protocol appears in `matrix_change_candidates`. This only means the source profile can close the transport-evidence gap strongly enough for human review. It does **not** authorize an automatic matrix edit, a `PARTIAL`/`SUPPORTED` promotion, serial defaults, timing/retry behavior, checksum behavior, reverse direction, or real-hardware interoperability.

The intake also reports whether the existing characterizer found the known control-byte names and safe CHK/NAM-related layout keys. Unrecognized profile values remain omitted so site secrets and unrelated configuration do not leak into reusable evidence.

## Architectural boundary

This workflow belongs to the standalone InnAware PMS-PBX Emulator support tool. The InnAware UCP Hospitality PMS Gateway is a separate production runtime and must not import the Emulator runtime, FastAPI/operator UI, session orchestration, Windows launcher, or deployment lifecycle.

A UCP test effort may reuse the resulting **data-only** facts—profile digests, exact six-dimensional coordinates, sanitized layout facts, admission gaps, and later sanitized wire evidence—without coupling the two codebases.

## What this still does not prove

Even a clean profile intake does not establish real endpoint interoperability. Before registering a transport-specific Hitachi row, review the exact profile evidence and, where practical, obtain an authorized sanitized wire capture tied to the exact Emulator SHA. Timing, retries, checksum behavior, endpoint role/port, and reverse direction each require their own evidence.
