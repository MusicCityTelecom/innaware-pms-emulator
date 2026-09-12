# Philips / TP Vision CMND guest-TV profile

Status: **experimental, schema-backed; not CMND-runtime or physical-TV qualified**.
This feature is on `codex/cmnd-guest-tv-profile`, based on Emulator main
`810c553a1cd4ca024460ccde38846614480fb418`. It is not in the published v0.4.1 binaries.

The profile is `philips-cmnd-htng-guest-tv`; its protocol is `CMND_HTNG_2011B`.
It sends HTNG 2011B StayNotification SOAP requests to an explicitly configured
CMND-side endpoint. It does not send WIXP directly to TVs, impersonate a PBX,
modify CMND's database, or assume that CMND accepts generic FIAS.

## Read-only reference evidence

The CMND for Linux project was used only as a local reference. No files in it
were changed; no services, TV connections or deployments were started there.
Reference project commit: `d33748d7f17b913f62a2eae36ac7de33a7f6d8ba`.
Its README identifies the vendor installer as 7.5.9 and extracted build as
7.5.10.3168; these labels do not qualify every API operation.

The supplied `SmartInstall.war` has SHA-256
`55bbdbefc9c87ce2156ac4a69403b8171845c405727d9355d717f85c2695659d`.
Only interface schemas/WSDL were read for the implementation; no vendor
implementation code, binaries, schemas, credentials or private data are copied
into this repository.

| Contract | Reference inside SmartInstall.war | Observation |
| --- | --- | --- |
| Service | `WEB-INF/classes/HTNG/services/HTNG_GuestAndRoomStatusService.wsdl` | StayNotification port; service address is only `http://tempuri.org`, not a usable CMND endpoint |
| Binding | `WEB-INF/classes/HTNG/wsdls/HTNG_CommonBindings.wsdl` | SOAP 1.1 document/literal over HTTP; CheckedIn / CheckedOut operations |
| Check-in | `WEB-INF/classes/HTNG/messages/HTNG_HotelCheckInNotifRQ.xsd` | PropertyInfo, AffectedGuests, Room and HotelReservations required |
| Check-out | `WEB-INF/classes/HTNG/messages/HTNG_HotelCheckOutNotifRQ.xsd` | Same required structural groups, departing guest identity |
| Room | `WEB-INF/classes/HTNG/schemas/HTNG_CommonTypes.xsd` | String RoomID (1–16), RoomType, TelephoneExtensions and HKStatus; exact child spelling `TelephoneExtention` |
| Result | HTNG check-in/out RS schemas and common response type | Explicit Success or Errors, separately from HTTP status |

Check-in XSD SHA-256:
`236f1c09d580f962086cd1695c71dd04cb0af53d4e021e695f8cf41be31c607c`.
Check-out XSD SHA-256:
`66370f32ef7de30a0bb338bade6e2596d7c50989f2265a976d7103090d8c6625`.

Public corroboration: [PPDS CMND PMS FAQ](https://pms.cmnd.pro/support-page/)
confirms an integration API exists and directs developers to PPDS for details.
It does not publish the deployment-specific endpoint or authentication contract.
[Philips professional-TV installation documentation](https://www.documents.philips.com/assets/20230412/7ca98a42ee5042d9980dafe200c07e64.pdf)
explains Room ID routing, PMSService / Default Dashboard PMS and guest-data
clearing on check-in/out. Check exact settings for the TV model and firmware.

## Operator console

Expand **Philips / TP Vision CMND guest TV — experimental**. Enter the confirmed
SOAP URL, hotel code, OTA guest-ID type, exact test Room ID, telephone extension
and site-qualified housekeeping values for each action. Nothing is guessed from
room numbering. Select the property to bind, then create the test interface.

Writes are **off by default**. Starting a configured interface merely marks it
ready; it does not establish connectivity. Enable the explicit authorization
checkbox only for an approved isolated endpoint and room. All TVs sharing that
Room ID may be affected. Checkout can clear guest personalization/data.

Select this interface in Front Desk and use Check In / Check Out. The property
workflow preserves the same guest ID through both operations. A local property
change and a remote transmission are separate outcomes: inspect `transmission`.
An unsuccessful transmission does not undo the local property operation.
For multiple rooms use the profile API with explicit `allowed_rooms` and
`room_settings` entries. Profiles do not automatically transmit every local event.

## API configuration and preview

Create through `POST /api/v1/profiles/philips-cmnd-htng-guest-tv/instantiate`.
The following is synthetic configuration, **not a working CMND address or a
vendor-default guest-ID code**. Keep `enabled` and `execute` false until the
deployment contract and authorized lab are confirmed.

```json
{
  "name": "cmnd-tv-lab",
  "enabled": false,
  "overrides": {
    "options": {
      "endpoint_url": "https://cmnd.invalid/confirmed-stay-service",
      "execute": false,
      "allowed_rooms": ["00101"],
      "htng_defaults": {"hotel_code": "LAB", "guest_id_type": "1"},
      "room_settings": {"00101": {"telephone_extension": "0101"}},
      "action_settings": {
        "checkin": {"housekeeping_status": "OCCUPIED_CLEAN"},
        "checkout": {"housekeeping_status": "VACANT_DIRTY"}
      }
    }
  }
}
```

For a network-free preview, POST to
`/api/v1/protocols/CMND_HTNG_2011B/guest-event`:

```json
{
  "action": "checkin",
  "room": "00101",
  "first_name": "Synthetic",
  "last_name": "Guest",
  "language": "en-US",
  "extra": {
    "hotel_code": "LAB",
    "guest_id": "synthetic-guest-1",
    "guest_id_type": "1",
    "telephone_extension": "0101",
    "housekeeping_status": "OCCUPIED_CLEAN"
  }
}
```

The response contains readable XML and exact hexadecimal bytes. Preview has no
interface defaults, so all schema-required site fields must be explicit. For
checkout use `action: checkout`, the same guest ID and the appropriate site
housekeeping value. Checkout omits guest names and language. Unicode names are
XML-escaped without truncation; leading zeros in Room IDs are retained.

For a started, authorized interface, use
`POST /api/v1/interfaces/cmnd-tv-lab/send/guest-event`. Site fields are merged
from interface options; an explicit `extra.guest_id` is still required outside
the property workflow. Raw sends and control-byte sends are disabled for CMND.

SOAPAction values are:

- `http://htng.org/2011B/HTNG_GuestAndRoomStatusService#CheckedIn`
- `http://htng.org/2011B/HTNG_GuestAndRoomStatusService#CheckedOut`

## Transport and privacy boundaries

- HTTPS certificate verification is on. No certificate bypass or proxy use.
- Plain HTTP is allowed automatically only on loopback; a legacy isolated lab
  requires explicit `allow_insecure_http: true`. Credentials require HTTPS.
- No automatic redirects, retries, discovery or port guesses. A timeout can mean
  CMND applied the operation but its response was lost: inspect before retrying.
- If the site's API uses an HTTP Authorization header, `authorization_env` names
  an environment variable containing that header's full value. Never enter
  credentials in URLs or interface options. Restart the application after
  setting the variable. No HTTP auth scheme, WS-Security header, shared default
  password or login endpoint is inferred from the bundled HTNG schemas.
- `cmnd_accepted: true` requires HTTP 200 and a matching HTNG Success response.
  `tv_verified` remains false. Acceptance is not physical-TV confirmation.
- Capture/support bundles may contain synthetic guest XML; use lab identities
  only and review captures before sharing. Authorization headers are not captured.
- Wakeups, move-room, billing, channel control and TV discovery are not included.

## Verification and remaining gate

`tests/test_cmnd.py` covers payload structure, names and IDs, XML safety,
response rejection, loopback HTTP/SOAPAction, no retries/redirects, opt-in guards,
profile/runtime routing and property guest-ID continuity.

Development verification on Windows: **571 tests passed, 4 skipped** (including
40 CMND tests). Browser checks verified required-field errors, creation with
writes disabled, restored interface state and retention of the existing FIAS
default. The CMND panel was visually inspected at a narrow viewport. These are
software/loopback checks, not vendor runtime or TV tests.

Optional reference validation (requires `lxml` in the developer environment):

```text
python scripts/validate-cmnd-reference.py PATH-TO-SmartInstall.war
```

This reads the reference archive only and validates both generated requests.
The validator assembles reachable XSD declarations by namespace in memory to
handle the archive's multiple same-namespace OTA imports with libxml2. It does
not rewrite or publish the reference schemas. Schema conformance is not proof
that the vendor's runtime consumes every represented field.

Before claiming CMND compatibility, obtain a confirmed StayNotification endpoint,
authentication/WS-Security requirements and site field mappings (or an authorized
sanitized working request/response capture). Then test an isolated CMND instance
and an explicitly authorized TV: check-in, displayed name/language, checkout,
guest-data clearing, shared Room IDs, disconnected TV and failed/late responses.
No live CMND or TV endpoint was contacted during this implementation.
