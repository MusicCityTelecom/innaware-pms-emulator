# PhoneSuite capture diagnostics

InnAware exposes capture-level interoperability analysis at:

```text
GET /api/v1/interfaces/{name}/capture-diagnostics
```

This report is separate from `GET /api/v1/interfaces/{name}/diagnostics`, which remains the bounded stream of live transport/session-state-machine diagnostics.

## Evidence boundary

PhoneSuite application-format findings are derived from the legacy PhoneSuite/Voiceware PMS-interface documentation already indexed for v0.4.0. They identify documented PMS-to-PBX field-shape problems such as malformed `CHK`, `LMT`, `DND`, `GRP`, `LNG`, `MW`, `RST`, `NAM`, `AREYUTHERE`, `GRS`, and `END` records.

The capture integration deliberately fails closed unless endpoint identity establishes the direction unambiguously:

- InnAware emulating the PhoneSuite PBX: `emulation_role=pbx` and `personality_id=pbx-phonesuite`; PMS-to-PBX traffic is RX.
- InnAware emulating a PMS against a real PhoneSuite peer: `emulation_role=pms` and `peer_personality_id=pbx-phonesuite`; PMS-to-PBX traffic is TX.
- Missing role metadata, reverse PBX-to-PMS traffic, Matrix, Mitel, unknown PBX personalities, and unrelated records do not inherit PhoneSuite PMS-format rules.

This is an application-level diagnostic overlay. It does **not** select or change a profile, infer that serial or TCP is supported, supply baud/parity/data/stop/flow-control defaults, add checksum behavior, define retries, or promote a compatibility-matrix row.

## Technician use

A malformed synthetic record such as:

```text
MW1 101
```

can produce a `phonesuite_pms_mw_spacing_invalid` finding when it is observed in the qualified PMS-to-PhoneSuite direction. The finding explains that the documented application form uses a space between `MW` and the status digit. The corrective action is confined to the application record; it must not suggest changing transport settings to compensate for a field-format error.

Likewise, a malformed synthetic name record such as:

```text
NAM0 TEST,GUEST 101
```

can produce `phonesuite_pms_nam_index_invalid` only in the qualified PMS-to-PBX direction. An identical record observed in the reverse direction is not enough evidence to assign PhoneSuite PMS-to-PBX semantics.

## Analyze Capture technician view

The operator console links to a dedicated read-only page at:

```text
GET /capture-diagnostics
```

The **Analyze Capture** view lets a technician choose an existing interface and a bounded capture window, then renders the existing capture-diagnostic report as endpoint context, observations, evidence/confidence, findings, and corrective actions. The browser only performs GET requests against the interface list and `capture-diagnostics` report endpoint.

The page intentionally cannot start or stop an interface, send traffic, instantiate or switch a profile, change a serial/TCP transport, or write configuration. It also does not consume the live `/diagnostics` session stream. That separation is deliberate: capture analysis explains bounded observed wire evidence, while live diagnostics report transport/session-state-machine events.

An empty finding list means only that no configured diagnostic rule fired in the selected window. It must not be presented as proof that a PBX/PMS combination is supported, and it does not alter any compatibility-matrix status.

## Safety

Use synthetic or redacted room/name values in deterministic fixtures and shared support material. A capture report may reflect live traffic supplied by the operator, so normal support-bundle and evidence-handling practices still apply. Never turn a diagnostic match into an automatic personality switch.
