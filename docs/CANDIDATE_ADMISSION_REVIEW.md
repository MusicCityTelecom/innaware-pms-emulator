# Candidate Admission Review

The Emulator has two deliberately different evidence paths:

1. **Registered compatibility rows** use the technician acceptance/result workflow.
2. **Unregistered combinations** use `record-candidate-observation.py` and remain pre-admission evidence only.

`review-candidate-admission.py` adds a fail-closed human-review gate between those paths. It does **not** register a compatibility row, promote support, mutate the matrix, or send traffic.

This exists for cases such as the current 3CX Hotel Module / Mitel SX2000-compatible TCP `PBX_TO_PMS` direction: source material can justify a bounded diagnostic target, while real exact-SHA wire evidence is still required before a narrowly scoped matrix claim should even be considered.

## Evidence ranking

The project continues to rank evidence as:

1. packet capture / direct wire evidence;
2. operator-confirmed behavior;
3. legacy source/profile evidence;
4. simulator characterization;
5. inference.

The candidate recorder already refuses inference-only reusable evidence. The admission reviewer is stricter: a candidate is `manual_review_ready=true` only when it has a direct packet/wire capture, real endpoint provenance, an affirmative application-record observation, a sanitized wire-artifact digest, and a payload-safe bounded diagnostic digest.

`manual_review_ready=true` means only that the evidence packet is coherent enough for a human protocol review. It does **not** mean `PARTIAL`, `SUPPORTED`, production-qualified, or merge/release-ready.

## Exact-SHA protection

The reviewer requires `--expected-source-sha` and compares it to the exact 40-character Emulator SHA recorded in the candidate artifact. A stale or abbreviated SHA fails closed.

It also rechecks the **current** compatibility registry. If the candidate combination has since gained an exact or covering bidirectional row, the pre-admission review is rejected and the registered technician acceptance/result workflow must be used instead. This prevents a stale candidate artifact from bypassing a newer matrix claim.

## Review blockers

The generated JSON reports deterministic blocker codes rather than guessing protocol behavior:

- `affirmative_observation_missing` — the result is rejected or inconclusive rather than an affirmative observation;
- `packet_capture_missing` — evidence is source/operator/simulator-derived rather than direct wire evidence;
- `real_endpoint_provenance_missing` — only synthetic/emulator evidence is present;
- `wire_observation_missing` — no normalized wire-byte observation is recorded;
- `application_record_observation_missing` — transport evidence exists but no application record was observed for the exact direction;
- `payload_safe_diagnostic_missing` — no bounded diagnostic report digest is attached.

These blockers are generic admission-quality checks. They do not invent handshake, checksum, retry, timing, field-layout, port, or serial-parameter requirements for a protocol that has not established them.

## Usage

After producing a candidate artifact at the exact Emulator SHA:

```bash
SHA="$(git rev-parse HEAD)"

python scripts/review-candidate-admission.py \
  /tmp/candidate-observation.json \
  --expected-source-sha "$SHA" \
  --output /tmp/candidate-admission-review.json
```

Inspect the gate without exposing raw wire bytes:

```bash
python - <<'PY'
import json
from pathlib import Path

p = json.loads(
    Path("/tmp/candidate-admission-review.json").read_text(encoding="utf-8")
)

print("manual_review_ready=", p["review_gate"]["manual_review_ready"])
for blocker in p["review_gate"]["blocking_requirements"]:
    print(blocker["code"], "-", blocker["action"])
PY
```

The review output intentionally retains only candidate dimensions, evidence class/rank, evidence origin, normalized observation codes, and SHA-256 references to sanitized wire/diagnostic artifacts. It does not repeat endpoint addresses, endpoint versions, or raw application payloads.

## 3CX reverse-direction acceptance scenario for Codex

For the current unregistered candidate:

```text
3CX
× Hotel Module / Mitel SX2000-compatible
× tcp
× legacy-hotel-pms
× mitel-hospitality
× PBX_TO_PMS
```

Codex should first pin the exact Emulator SHA and run the bounded reverse-direction diagnostic. A real authorized lab capture should use synthetic guest/room data, record the exact 3CX version/build and actual configured Hotel Services endpoint, and retain a sanitized timestamped wire artifact outside Git.

Record the candidate with `record-candidate-observation.py` using `packet_capture` evidence and real endpoint provenance. Then run `review-candidate-admission.py` at the **same SHA**. A review-ready result still requires a human to inspect framing, direction, record layout, control sequence/timing, model/version scope, and any reconnect behavior before adding a narrowly scoped `PARTIAL` row.

If the evidence does justify a row, add only the exact six-dimensional claim supported by that evidence and add deterministic synthetic/redacted regression coverage. Do not infer the opposite direction, another transport, a universal site port, a checksum contract, or `SUPPORTED` status.

## UCP boundary

Candidate admission artifacts are data-only interoperability evidence. The separate InnAware UCP Hospitality PMS Gateway may consume the compatibility dimensions, evidence metadata, normalized findings, and sanitized artifact digests for independent tests/research.

It must not import the Emulator runtime, FastAPI/operator console, simulator/session orchestration, capture store, Windows launcher, or deployment/release lifecycle. Candidate evidence remains outside the normal interop fixture pack until a matrix row is explicitly reviewed and registered.

Series2 TDMoE/PRI/Q.921/Q.931/D-channel/`0x0E` station programming remains outside PBX↔PMS application-protocol scope.
