# InnAware PMS Emulator 0.3.7

## Corrective telemetry release

0.3.7 corrects the production telemetry path discovered during the first
installed-Windows validation of 0.3.6.

### Fixed

- uses a dedicated public, POST-only ingestion path instead of the protected
  human dashboard path;
- records an install event as delivered only after the server returns
  `{"ok":true}`;
- retries an unacknowledged install event on later launches;
- migrates 0.3.6 state so installations whose initial event was rejected are
  retried automatically;
- writes delivery failures at warning level rather than hiding them at debug;
- shows the last confirmed delivery time or failure in Update Center.

### Server deployment package

The source archive now contains `deployment/telemetry/` with:

- a strict PHP ingestion endpoint;
- MariaDB/MySQL schema;
- external configuration example;
- Apache authentication-boundary example; and
- deployment and verification instructions.

The ingestion endpoint accepts only the documented six-field JSON payload. It
enforces POST-only access, JSON content type, a 4 KiB body limit, strict field
and UUID validation, parameterized SQL, idempotent install events, and a
per-installation burst cap. Dashboard authentication remains separate.

### Privacy

The transmitted field allowlist is unchanged. No PMS, property, guest, room,
call, credential, network-configuration, hardware-derived, account-derived, or
personally identifying field was added.
