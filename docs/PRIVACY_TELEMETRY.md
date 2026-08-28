# Privacy and Anonymous Usage Telemetry

InnAware PMS Emulator includes a small, auditable telemetry feature intended only to measure aggregate installation and usage counts.

## Default and control

Telemetry is enabled by default. It can be disabled at any time from **Update Center > Preferences** by clearing **Send anonymous usage statistics** and saving settings.

When disabled, the emulator makes no telemetry requests. The emulator remains fully functional offline and telemetry failures never block startup or normal operation.

## Endpoint

Telemetry is sent with HTTPS POST requests to:

```text
https://telemetry.innawareucp.com/pms-telemetry-ingest.php
```

Normal TLS certificate validation remains enabled.

## Installation identifier

On the first telemetry-enabled run, the emulator generates a random UUID-v4 and stores it in the normal application data directory. The UUID is not derived from hardware, Windows, network, account, or user identifiers.

The installation UUID is visible in the Update Center for troubleshooting.

If the local telemetry state is deleted or becomes unreadable, a new random UUID may be generated.

## Events

On the first telemetry-enabled run, the emulator attempts one `install` event and one `run` event. The install event is marked delivered only after the endpoint returns a successful acknowledgement. If delivery fails, the install event is retried on later telemetry-enabled launches until acknowledged.

Every later telemetry-enabled application run attempts one `run` event.

All requests are best-effort, short-timeout background operations. DNS failure, TLS failure, endpoint failure, or lack of Internet access is silently tolerated except for low-severity debug logging.

## Exact outbound JSON fields

The telemetry JSON body contains only these fields:

```text
event
version
platform
architecture
protocol_pack_version
install_id
```

Example:

```json
{
  "event": "run",
  "version": "0.3.7",
  "platform": "windows",
  "architecture": "x64",
  "protocol_pack_version": "2026.08.27.1",
  "install_id": "random-uuid-v4"
}
```

The application version comes from the package's canonical version metadata. The protocol-pack version comes from the active installed protocol-pack manifest, or the bundled canonical protocol-pack manifest when no independent pack is active.

## Data that is not sent

The telemetry implementation does not put any of the following into the telemetry JSON body:

- IP address
- hostname or computer name
- Windows username
- email address
- MAC address
- Windows SID
- Windows machine GUID
- disk, CPU, motherboard, or other hardware identifiers
- hotel/property identity
- PMS credentials
- PMS traffic or message content
- guest or room data
- telephone numbers
- call records
- network configuration
- license keys
- filesystem paths

The server receiving an HTTPS request may inherently observe normal network-layer information such as the source IP needed to establish the connection, but the emulator does not include an IP address or any other network identity field in the telemetry payload.

## Source code

Telemetry is intentionally implemented in the dedicated, readable module:

```text
src/innaware_pms_emulator/telemetry.py
```

It is not hidden or obfuscated. Changes to the outbound field set should be reviewed explicitly before release.

## Support

Email: support@innawareucp.com  
Website: https://support.innawareucp.com
