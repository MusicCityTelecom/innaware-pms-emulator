# InnAware PMS Emulator 0.3.6

**Author:** Tommy Heggie  
**Status:** field-beta development release

## Highlights

0.3.6 adds transparent, opt-out anonymous usage telemetry and improves the Update Center/support experience without changing PMS, PBX, call-accounting, or protocol behavior.

### Anonymous usage telemetry

- production HTTPS endpoint: `https://telemetry.innawareucp.com/pms-telemetry.php`
- random UUID-v4 installation identifier stored in the normal application data directory
- first telemetry-enabled run attempts one `install` event and one `run` event
- later telemetry-enabled runs attempt one `run` event only
- telemetry is enabled by default and can be disabled in the Update Center
- no telemetry request is made when disabled
- network activity is best-effort, background, short-timeout, and never blocks application startup
- normal TLS verification remains enabled
- the installation UUID is visible in the Update Center for troubleshooting

The outbound JSON field set is intentionally limited to:

```text
event
version
platform
architecture
protocol_pack_version
install_id
```

No PMS data, guest/room information, credentials, network configuration, hardware identifier, hostname, username, telephone number, call record, or license key is included in the telemetry payload.

### Protocol-pack reporting

Telemetry reports the canonical currently-loaded protocol-pack version. An independently installed active protocol pack takes precedence over the bundled protocol-pack manifest, so the next application run reports a newly updated protocol-pack version without requiring an application update.

### Update Center and support improvements

- refreshed Update Center layout
- visible anonymous-usage setting and explanation
- visible installation UUID and protocol-pack version
- one-click UUID copy action
- support email: `support@innawareucp.com`
- support website: `https://support.innawareucp.com`
- direct link to the telemetry/privacy documentation

### Packaging

- Windows frozen builds embed the canonical `protocol-pack.json` so telemetry can report the built-in protocol-pack version
- the Windows build smoke test disables telemetry before launching the frozen EXE, preventing build/test systems from polluting production usage counts
- packaged installer and portable ZIP include the telemetry/privacy document
- installer support metadata points to `https://support.innawareucp.com`
- application version now comes from installed package metadata rather than a second hard-coded runtime version string

## Verification gates

The 0.3.6 test suite covers:

- first-run install + run behavior
- UUID persistence across later runs and application upgrades
- run-only behavior after the first launch
- telemetry disabled
- endpoint, DNS, TLS, and offline failures
- corrupt/missing telemetry state recovery
- exact outbound JSON field allowlist
- canonical active protocol-pack version reporting
- settings persistence
- frozen Windows EXE telemetry status with telemetry disabled during smoke testing

A Windows release should still be considered unverified until the normal local Windows build, frozen-EXE smoke test, installer build, installation/launch test, and final SHA-256 artifact generation complete successfully.

See `docs/PRIVACY_TELEMETRY.md` for the complete privacy contract.
