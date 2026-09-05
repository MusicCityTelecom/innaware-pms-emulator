# 3CX Hotel Module / Mitel SX2000 Interoperability

This work belongs to **InnAware PMS-PBX Emulator**, the standalone technician and installer interoperability/support tool. It does not add 3CX behavior to InnAware UCP Hospitality PMS Gateway and it does not make the Emulator a production hotel-PBX runtime.

## Evidence boundary

The project now registers one exact six-dimensional 3CX combination:

| Dimension | Value |
| --- | --- |
| PBX family | 3CX |
| PBX dialect | Hotel Module / Mitel SX2000-compatible |
| Transport | TCP |
| PMS family | legacy-hotel-pms |
| PMS protocol | mitel-hospitality |
| Direction | PMS_TO_PBX |
| Status | PARTIAL |
| Evidence class | LEGACY_SOURCE_PROFILE |

`LEGACY_SOURCE_PROFILE` is the project's conservative source/documentation evidence bucket. This row is based on the direct 3CX PMS protocol specification retained in project Sources together with current 3CX Hotel Services documentation. It is not packet-capture or real-endpoint evidence and therefore is not `SUPPORTED`.

Current 3CX documentation states that, in the Mitel SX2000 PMS integration, the **3CX Hotel Module acts as the server** and the PMS sends messages to it. The operator configures the local PMS address and a port that must match the PMS configuration. The built-in Emulator profile therefore models the Emulator as a PMS-side TCP client connecting to the real 3CX Hotel Services endpoint. No universal 3CX PMS port is supplied or claimed.

The direct 3CX PMS protocol specification documents the Mitel-compatible application/session sequence:

```text
PMS                         3CX Hotel Module
 | -------- ENQ ----------> |
 | <----- ACK or NAK ------ |
 | -- STX application ETX ->|
 | <----- ACK or NAK ------ |
```

The source documents a three-second response window and permits the PMS to resend only the framed message up to three additional times after a rejected application frame, without another ENQ. The built-in profile therefore sets `ack_timeout=3.0` and `max_record_retries=3`.

The source excerpt does not establish a PMS ENQ-acquisition retry count. The 3CX profile deliberately sets `max_attempts=1` rather than borrowing the generic Mitel sender's configurable acquisition retry budget and presenting it as 3CX truth.

## Identity and transport separation

3CX is a separate PBX family in the technician catalog. Its use of a Mitel SX2000-compatible application protocol does **not** make 3CX a Mitel PBX.

Likewise, application framing and physical/session transport remain separate facts:

- `ENQ`, `ACK`, `NAK`, `STX`, and `ETX` are application/session control and framing bytes.
- the registered 3CX Hotel Services mode is a network server reached by the PMS through a configured endpoint;
- the exact site port is configuration evidence, not a protocol constant;
- the 3CX Fidelio/FIAS integration is a different application/profile mode and is not selected by this profile;
- CDR/billing output is a separate 3CX interface and is not carried by this Mitel-SX2000 PMS row.

Series2 TDMoE/PRI/Q.921/Q.931/D-channel/`0x0E` station programming is not part of this PMS application protocol and must not be used to infer anything about this row.

## Built-in profile

Use `3cx-mitel-sx2000-tcp-client` when the Emulator is acting as the PMS against a 3CX Hotel Module configured for Mitel SX2000 integration.

The profile intentionally leaves `host` and `port` unset. Enter the actual lab/site endpoint before starting it. It also leaves automatic ACK of 3CX-originated application traffic disabled because the reverse PBX-to-PMS direction is not registered by this slice.

The profile reuses the existing `MitelTransactionSender` and Mitel TCP session machinery because the source-backed application handshake is Mitel-compatible. This is code reuse beneath a distinct 3CX personality, not identity conflation.

## Synthetic fixture

`tests/fixtures/pbx/3cx_mitel_sx2000_pms_to_pbx.json` contains one synthetic source-derived check-in transaction:

```text
PMS ENQ
3CX ACK
PMS STX CHK1 <synthetic room> ETX
3CX ACK
```

The committed fixture contains no guest name, vendor executable, proprietary raw profile body, or hotel production capture. Reusable diagnostics emit SHA-256, length, framing, record family/code, indexes, and evidence metadata rather than raw application payloads.

A source-derived synthetic fixture proves deterministic software behavior. It does **not** prove compatibility with a particular 3CX release or hotel deployment.

## Diagnostic CLI

```bash
python scripts/diagnose-3cx-mitel-sx2000.py \
  /tmp/3cx-pms-capture.json \
  --transport tcp \
  --pms-direction tx \
  --evidence-class legacy_source_profile \
  --output /tmp/3cx-pms-report.json
```

`--pms-direction` is mandatory because captures can be taken from either endpoint. Use `tx` only when local capture TX is independently known to be PMS -> 3CX; use `rx` when local capture RX is PMS -> 3CX. The analyzer does not infer endpoint role from an opcode.

The strict source-qualified PMS record set currently retained by this diagnostic is:

- `CHK` — check-in/check-out;
- `NAM` — guest-name operation;
- `MW` — wake-up form shown by the 3CX specification;
- `DND` — do-not-disturb;
- `RST` — station restriction.

An acknowledged Mitel-compatible record outside that list is retained as an **evidence candidate**, not automatically promoted into the 3CX row.

A NAK proves rejection. It does not by itself establish whether the cause was framing, function/status code, field layout, timing, endpoint state, or some other validation rule.

## Compatibility readiness gaps

The row remains `PARTIAL` until at least these registered gaps are addressed:

1. **real_3cx_endpoint** — validate against a real 3CX Hotel Services endpoint and record exact 3CX version/build;
2. **site_endpoint** — retain the actual endpoint address and configured TCP port as test evidence without universalizing the port;
3. **pms_record_scope** — capture sanitized CHK/NAM/MW/DND/RST variants against real 3CX;
4. **tcp_reconnect_scope** — characterize real 3CX disconnect/reconnect behavior separately from the application transaction timing;
5. **reverse_direction** — obtain 3CX-to-PMS evidence, including maid-status behavior where applicable, before adding PBX_TO_PMS or BIDIRECTIONAL claims.

No green software test automatically closes those field-evidence gaps or authorizes matrix promotion.

## Codex / live acceptance

Codex should pin the exact feature SHA before any runtime observation:

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
  tests/test_3cx_mitel_sx2000.py \
  tests/test_mitel_half_duplex_diagnostics.py \
  tests/test_compatibility_matrix.py \
  tests/test_compatibility_readiness.py \
  tests/test_transport_evidence_boundaries.py

INNAWARE_PMS_REPO_DIR=/opt/innaware/innaware-pms-emulator \
  bash scripts/verify-server3.sh
```

For a **software-only** acceptance, run the committed synthetic fixture:

```bash
python scripts/diagnose-3cx-mitel-sx2000.py \
  tests/fixtures/pbx/3cx_mitel_sx2000_pms_to_pbx.json \
  --transport tcp \
  --pms-direction tx \
  --evidence-class legacy_source_profile \
  --output /tmp/3cx-mitel-source-derived.json

python - <<'PY'
import json
from pathlib import Path

p = json.loads(Path('/tmp/3cx-mitel-source-derived.json').read_text())
assert p['source_qualified_success_count'] == 1
assert p['combination']['pbx_family'] == '3CX'
assert p['combination']['transport'] == 'tcp'
assert p['combination']['direction'] == 'pms_to_pbx'
assert p['reference_contract']['response_window_seconds'] == 3
assert p['reference_contract']['max_frame_only_retries_after_initial'] == 3
assert p['reference_contract']['site_port_is_configured_not_universal'] is True
assert p['claim_policy']['3cx_identity_preserved'] is True
assert p['claim_policy']['site_port_inferred'] is False
assert p['claim_policy']['pbx_to_pms_support_inferred'] is False
assert p['claim_policy']['compatibility_promotion_authorized'] is False
assert p['claim_policy']['raw_payloads_embedded'] is False
print('3CX Mitel-SX2000 source-derived diagnostic: PASS')
PY
```

That validates the implementation only. It must be recorded as source-derived/synthetic evidence, not a real 3CX pass.

For **live 3CX acceptance**, use an authorized lab or maintenance window and synthetic guest data. Before sending anything, record:

- exact Emulator SHA;
- exact 3CX version/build;
- 3CX Hotel Services integration type (`Mitel SX2000`);
- actual endpoint address and configured site port;
- which capture direction is PMS-originated;
- authorization and property/lab context;
- a sanitized wire artifact or digest with no guest PII.

Start with one CHK transaction. If it succeeds, exercise the other source-qualified PMS-to-3CX forms one at a time. If a NAK occurs, retain the rejected frame digest and investigate one variable at a time. Do not switch personality, transport, or framing automatically.

Capture any 3CX-originated record separately. It may become evidence for the currently missing PBX_TO_PMS row, but this profile must not manufacture that claim.

## UCP Hospitality PMS Gateway evidence handoff

The separate UCP Hospitality PMS Gateway may reuse **data-only** artifacts from this work:

- the exact six-dimensional matrix coordinates;
- the synthetic/redacted fixture;
- source-backed transaction/timing facts;
- exact wire SHA-256 values;
- sanitized live evidence after review;
- readiness gaps and diagnostic findings.

UCP must not import `innaware_pms_emulator`, the Emulator FastAPI/operator console, simulator/session orchestration, capture store, Windows launcher, or Emulator deployment/release lifecycle. The two products can share interoperability evidence without sharing runtime responsibility.

## Sources

Project Sources include `3CX PMS Protocol Specifications.pdf` (3CX PMS protocol specification, last-updated date shown by the source as 18 July 2022). Current 3CX documentation is also available at:

- `https://www.3cx.com/docs/3cx-pms-protocol/`
- `https://www.3cx.com/docs/pms-integration/`

The current integration documentation was updated 04 June 2026 when this slice was reviewed. If 3CX changes that deployment model, re-review the transport/server-role claim before widening or retaining it.
