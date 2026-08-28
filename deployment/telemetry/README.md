# Telemetry server deployment

The application sends anonymous events to the public, POST-only endpoint
`pms-telemetry-ingest.php`. The human dashboard remains a separate protected
resource at `pms-telemetry.php`. Never embed dashboard or database credentials
in the desktop application.

## Deploy

1. Create a dedicated MariaDB/MySQL database and apply `schema.sql`.
2. Create a database user limited to `SELECT`, `INSERT`, and `UPDATE` on the two
   telemetry tables.
3. Copy `config.example.php` outside the public web root, replace its values,
   restrict it to the web-service account, and set `INNAWARE_TELEMETRY_CONFIG`.
4. Place `pms-telemetry-ingest.php` beside the existing dashboard.
5. Adapt `apache-vhost.example.conf` in the active TLS virtual host. Confirm no
   parent `<Directory>` or `.htaccess` rule re-applies Basic Authentication to
   the ingestion file.
6. Reload Apache and verify the checks below before releasing a client.

## Verification

An unauthenticated `GET` must return `405`, not `401`. An unauthenticated POST
with an invalid body must return `400` or `422`, proving that the request reached
the ingestion code. A valid POST must return exactly `{"ok":true}` and create
one installation/event row. The protected dashboard must continue to return
`401` without credentials.

The endpoint stores only the six documented fields and server timestamps. It
does not store source IP addresses, request headers, user-agent strings, PMS
data, property data, or any device-derived identifier. Normal web-server access
logs may still contain source IP addresses and should follow the site's stated
retention policy.

The endpoint enforces HTTPS at the virtual-host layer, POST-only access, JSON
content type, a 4 KiB request limit, exact fields, strict values, UUID-v4 format,
parameterized SQL, idempotent install events, and a per-installation burst cap.
