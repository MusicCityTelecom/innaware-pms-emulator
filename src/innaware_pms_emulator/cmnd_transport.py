"""Opt-in CMND HTNG HTTP transport; no discovery, retries or redirects."""
from __future__ import annotations

import http.client
import os
import ssl
from urllib.parse import urlsplit

from .protocols.cmnd import CmndHtngAdapter


def validate_options(options: dict) -> None:
    endpoint = options.get("endpoint_url")
    if not isinstance(endpoint, str) or any(ord(c) <= 32 or ord(c) > 126 or c == "\\" for c in endpoint):
        raise ValueError("Set CMND endpoint_url to the confirmed StayNotification service URL")
    try:
        url = urlsplit(endpoint)
        port = url.port
    except ValueError as exc:
        raise ValueError("Invalid CMND endpoint URL") from exc
    if (url.scheme not in {"https", "http"} or not url.hostname or url.username or
            url.password or url.query or url.fragment or not url.path or
            url.hostname.lower() == "tempuri.org" or port == 0):
        raise ValueError("CMND requires an explicit HTTP(S) service URL without credentials, query or fragment")
    if (url.scheme == "http" and url.hostname not in {"127.0.0.1", "::1", "localhost"}
            and options.get("allow_insecure_http") is not True):
        raise ValueError("CMND requires HTTPS; isolated legacy labs must explicitly allow_insecure_http")
    timeout = options.get("timeout_seconds", 10)
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not 0.1 <= timeout <= 30:
        raise ValueError("CMND timeout_seconds must be between 0.1 and 30")
    if options.get("framing", "raw") != "raw" or options.get("transactional_enq_ack"):
        raise ValueError("CMND SOAP uses raw XML over HTTP, not serial framing or ENQ/ACK")


def post_guest_event(options: dict, event: dict) -> dict:
    validate_options(options)
    if options.get("execute") is not True:
        raise ValueError("CMND writes are disabled; explicitly set options.execute=true for an authorized lab")
    allowed = options.get("allowed_rooms")
    if not isinstance(allowed, list) or event.get("room") not in allowed:
        raise ValueError("CMND room is not in options.allowed_rooms")
    adapter = CmndHtngAdapter()
    payload = adapter.encode_event(event)
    action = str(event["action"]).lower()
    url = urlsplit(options["endpoint_url"])
    headers = {"Content-Type": "text/xml; charset=us-ascii", "SOAPAction": f'"{adapter.soap_action(action)}"'}
    # Authentication is site-defined, not inferred from generic HTNG schemas.
    # Only an environment variable name is persisted in interface settings.
    auth_env = options.get("authorization_env")
    if auth_env:
        if not isinstance(auth_env, str):
            raise ValueError("CMND authorization_env must name an environment variable")
        authorization = os.environ.get(auth_env)
        if not authorization or any(ord(c) < 32 or ord(c) > 126 for c in authorization):
            raise ValueError("CMND authorization environment variable is absent or invalid")
        if url.scheme != "https":
            raise ValueError("CMND authentication requires HTTPS")
        headers["Authorization"] = authorization
    kwargs = {"timeout": options.get("timeout_seconds", 10)}
    if url.scheme == "https":
        connection = http.client.HTTPSConnection(url.hostname, url.port, context=ssl.create_default_context(), **kwargs)
    else:
        connection = http.client.HTTPConnection(url.hostname, url.port, **kwargs)
    try:
        connection.request("POST", url.path, body=payload, headers=headers)
        response = connection.getresponse()
        data = response.read(65537)
        if response.status != 200:
            raise RuntimeError(f"CMND HTTP {response.status}; delivery not confirmed; no automatic retry")
        result = adapter.decode(data)
        if not result.fields.get("success") or result.fields.get("action") != action:
            raise RuntimeError("CMND returned a SOAP fault, rejection or mismatched response; delivery not confirmed")
        return {"sent_to": 1, "cmnd_accepted": True, "tv_verified": False, "hex": payload.hex(" ")}
    except (OSError, http.client.HTTPException) as exc:
        raise RuntimeError("CMND delivery outcome unknown after transport failure; inspect CMND before retrying") from exc
    finally:
        connection.close()


def configured_event(options: dict, event: dict) -> dict:
    """Merge site defaults while requiring real per-stay IDs from the caller."""
    defaults = options.get("htng_defaults") or {}
    rooms = options.get("room_settings") or {}
    actions = options.get("action_settings") or {}
    if not isinstance(defaults, dict) or not isinstance(rooms, dict) or not isinstance(actions, dict):
        raise ValueError("CMND htng_defaults, room_settings and action_settings must be objects")
    room_data = rooms.get(event.get("room"), {})
    action_data = actions.get(str(event.get("action", "")).lower(), {})
    if not isinstance(room_data, dict) or not isinstance(action_data, dict):
        raise ValueError("CMND room and action settings must be objects")
    extra = {**defaults, **room_data, **action_data, **(event.get("extra") or {})}
    return {**event, "extra": extra}
