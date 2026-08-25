from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from . import __version__
from .models import GuestEvent, CallRecord
from .protocols.registry import REGISTRY, protocol_catalog

app = FastAPI(title="InnAware PMS Emulator", version=__version__)


@app.get("/api/v1/health")
def health():
    return {"status": "ok", "version": __version__}


@app.get("/api/v1/protocols")
def protocols():
    return {"protocols": protocol_catalog()}


@app.post("/api/v1/protocols/{protocol}/guest-event")
def encode_guest_event(protocol: str, event: GuestEvent):
    adapter = REGISTRY.get(protocol.upper())
    if not adapter or adapter.purpose != "pms":
        raise HTTPException(404, "PMS protocol not found")
    try:
        payload = adapter.encode_event(event.model_dump())
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return {"protocol": protocol.upper(), "hex": payload.hex(" "), "text": payload.decode("latin-1", errors="replace")}


@app.post("/api/v1/protocols/{protocol}/call-record")
def encode_call_record(protocol: str, call: CallRecord):
    adapter = REGISTRY.get(protocol.upper())
    if not adapter or adapter.purpose != "call_accounting":
        raise HTTPException(404, "Call-accounting protocol not found")
    payload = adapter.encode_call(call.model_dump())
    return {"protocol": protocol.upper(), "hex": payload.hex(" "), "text": payload.decode("latin-1", errors="replace")}


@app.get("/", response_class=HTMLResponse)
def index():
    return """<!doctype html><html><head><meta charset="utf-8"><title>InnAware PMS Emulator</title>
<style>body{font-family:system-ui;max-width:1000px;margin:3rem auto;padding:0 1rem}code{background:#eee;padding:.2rem .4rem}
.card{border:1px solid #ddd;border-radius:10px;padding:1rem;margin:1rem 0}</style></head><body>
<h1>InnAware PMS Emulator</h1><p>Protocol engine foundation is running.</p>
<div class="card"><b>API health:</b> <code>/api/v1/health</code></div>
<div class="card"><b>Protocol catalog:</b> <code>/api/v1/protocols</code></div>
<p>The full interface/session operator console is under active development.</p></body></html>"""


def run():
    import uvicorn
    uvicorn.run("innaware_pms_emulator.main:app", host="0.0.0.0", port=8080)
