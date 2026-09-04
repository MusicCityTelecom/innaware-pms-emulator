# Matrix FIAS live-capture acceptance gate

This gate belongs only to the standalone **InnAware PMS-PBX Emulator** support tool. It prepares exact-SHA Matrix SARVAM UCS / MICROS Opera FIAS evidence for human review; it does not implement or own the InnAware UCP Hospitality PMS Gateway runtime.

## Purpose

The existing bounded Matrix diagnostic recognizes the operator-observed TCP application progression `PBX LS -> PMS LS -> PBX LD/LR... -> PBX LA`. A synthetic/redacted replay is sufficient to regression-test that analyzer, but it is not sufficient to claim a real Matrix endpoint behaved that way.

`review-matrix-fias-live-capture.py` closes that evidence-lifecycle gap. It requires an exact 40-character Emulator Git SHA, explicit Matrix model/version, actual endpoint identifiers, TCP initiator role, capture direction, authorization/sanitization declarations, and direct packet-capture provenance before it can report `manual_review_ready=true`.

Even then, the artifact remains non-promoting. `manual_review_ready` means a human has a coherent evidence packet to review. It does **not** mean `SUPPORTED`, production-qualified, or release-ready.

## Safe synthetic check

```bash
SHA="$(git rev-parse HEAD)"
python scripts/review-matrix-fias-live-capture.py \
  tests/fixtures/pbx/matrix_sarvam_fias_link_progression_sanitized.json \
  --source-sha "$SHA" \
  --transport tcp \
  --pbx-direction rx \
  --evidence-class operator_confirmed \
  --evidence-origin synthetic_replay \
  --matrix-model "SARVAM UCS" \
  --matrix-version synthetic-test \
  --local-endpoint 192.0.2.10:50000 \
  --remote-endpoint 192.0.2.20:5010 \
  --tcp-initiator pbx \
  --operator-authorized \
  --synthetic-or-redacted \
  --no-guest-pii \
  --source-material-synthetic \
  --output /tmp/matrix-fias-synthetic-review.json
```

That replay should stay `manual_review_ready=false` with blockers for direct packet capture, real endpoint provenance, and synthetic source material. This is expected.

## Codex / real endpoint acceptance

For an authorized real Matrix validation, pin Codex/Server3 to the exact feature SHA. Record the Matrix model and software revision, actual TCP endpoints, which side initiated TCP, which local capture direction is Matrix-originated, and a sanitized timestamped `LS -> LS -> LD/LR... -> LA` exchange. Use `--evidence-class packet_capture` and `--evidence-origin real_pbx_lab` (or `authorized_field_capture`) only for genuinely direct endpoint evidence. Do not mark source material non-synthetic unless the bytes came from that authorized real endpoint session.

Guest-event traffic should be captured separately with synthetic/redacted room and guest values. This gate does not infer guest-event semantics, site port defaults, ENQ/ACK behavior, retry timing, or a production support claim.

## UCP handoff boundary

The separate UCP Hospitality PMS Gateway may consume the resulting JSON as data/test evidence: exact six-dimensional coordinates, producer SHA, endpoint provenance, bounded link counts, LR record-type declarations, and report digests. It must not import the Emulator runtime, simulator orchestration, technician UI, capture storage, Windows field-tool lifecycle, or deployment responsibilities.
