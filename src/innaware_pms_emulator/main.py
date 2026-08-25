from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from . import __version__
from .models import CallRecord, GuestEvent, InterfaceConfig
from .protocols.registry import REGISTRY, protocol_catalog
from .sessions import manager

app = FastAPI(title="InnAware PMS Emulator", version=__version__)


class RawSendRequest(BaseModel):
    text: str | None = None
    hex: str | None = None
    apply_framing: bool = True


class ControlRequest(BaseModel):
    control: str


def _interface_or_404(name: str):
    try:
        return manager.get(name)
    except KeyError:
        raise HTTPException(404, f"Interface '{name}' not found")


def _bytes_from_request(request: RawSendRequest) -> bytes:
    if request.hex is not None:
        try:
            return bytes.fromhex(request.hex)
        except ValueError as exc:
            raise HTTPException(400, f"Invalid hexadecimal payload: {exc}")
    if request.text is not None:
        return request.text.encode("latin-1", errors="replace")
    raise HTTPException(400, "Supply either text or hex")


@app.get("/api/v1/health")
def health():
    return {"status": "ok", "version": __version__, "interfaces": len(manager.list())}


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


@app.get("/api/v1/interfaces")
def list_interfaces():
    return {"interfaces": manager.list()}


@app.post("/api/v1/interfaces", status_code=201)
async def create_interface(config: InterfaceConfig):
    adapter = REGISTRY.get(config.protocol.upper())
    if not adapter:
        raise HTTPException(400, f"Protocol '{config.protocol}' is not implemented")
    if adapter.purpose != config.purpose.value:
        raise HTTPException(400, f"Protocol '{config.protocol}' is not a {config.purpose.value} protocol")
    config.protocol = config.protocol.upper()
    try:
        runtime = await manager.create(config)
    except (ValueError, OSError) as exc:
        raise HTTPException(400, str(exc))
    return runtime.status()


@app.get("/api/v1/interfaces/{name}")
def get_interface(name: str):
    return _interface_or_404(name).status()


@app.post("/api/v1/interfaces/{name}/start")
async def start_interface(name: str):
    _interface_or_404(name)
    try:
        await manager.start(name)
    except (ValueError, OSError) as exc:
        raise HTTPException(400, str(exc))
    return manager.get(name).status()


@app.post("/api/v1/interfaces/{name}/stop")
async def stop_interface(name: str):
    _interface_or_404(name)
    await manager.stop(name)
    return manager.get(name).status()


@app.delete("/api/v1/interfaces/{name}", status_code=204)
async def delete_interface(name: str):
    _interface_or_404(name)
    await manager.remove(name)


@app.get("/api/v1/interfaces/{name}/captures")
def interface_captures(name: str, limit: int = 200):
    _interface_or_404(name)
    return {"captures": manager.captures(name, limit)}


@app.post("/api/v1/interfaces/{name}/send/raw")
async def send_raw(name: str, request: RawSendRequest):
    _interface_or_404(name)
    payload = _bytes_from_request(request)
    try:
        recipients = await manager.send(name, payload, frame=request.apply_framing)
    except RuntimeError as exc:
        raise HTTPException(409, str(exc))
    return {"sent_to": recipients, "hex": payload.hex(" ")}


@app.post("/api/v1/interfaces/{name}/send/control")
async def send_control(name: str, request: ControlRequest):
    _interface_or_404(name)
    try:
        recipients = await manager.send_control(name, request.control)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except RuntimeError as exc:
        raise HTTPException(409, str(exc))
    return {"sent_to": recipients, "control": request.control.upper()}


@app.post("/api/v1/interfaces/{name}/send/guest-event")
async def send_guest_event(name: str, event: GuestEvent):
    runtime = _interface_or_404(name)
    if runtime.config.purpose.value != "pms":
        raise HTTPException(400, "Interface is not a PMS interface")
    adapter = REGISTRY[runtime.config.protocol]
    try:
        payload = adapter.encode_event(event.model_dump())
        recipients = await manager.send(name, payload)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except RuntimeError as exc:
        raise HTTPException(409, str(exc))
    return {"sent_to": recipients, "protocol": runtime.config.protocol, "hex": payload.hex(" ")}


@app.post("/api/v1/interfaces/{name}/send/call-record")
async def send_call_record(name: str, call: CallRecord):
    runtime = _interface_or_404(name)
    if runtime.config.purpose.value != "call_accounting":
        raise HTTPException(400, "Interface is not a call-accounting interface")
    adapter = REGISTRY[runtime.config.protocol]
    payload = adapter.encode_call(call.model_dump())
    try:
        recipients = await manager.send(name, payload)
    except RuntimeError as exc:
        raise HTTPException(409, str(exc))
    return {"sent_to": recipients, "protocol": runtime.config.protocol, "hex": payload.hex(" ")}


@app.get("/", response_class=HTMLResponse)
def index():
    return """<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>InnAware PMS Emulator</title>
<style>body{font-family:system-ui;max-width:1100px;margin:3rem auto;padding:0 1rem;background:#f6f7f9;color:#17202a}code{background:#e9edf2;padding:.2rem .4rem;border-radius:4px}.card{background:#fff;border:1px solid #dfe3e8;border-radius:12px;padding:1rem 1.2rem;margin:1rem 0;box-shadow:0 2px 6px #0000000d}.ok{color:#16803a}</style></head><body>
<h1>InnAware PMS Emulator</h1><p class="ok"><b>Wire-session foundation enabled.</b></p>
<div class="card"><b>Health</b><p><code>/api/v1/health</code></p></div>
<div class="card"><b>Protocols</b><p><code>/api/v1/protocols</code></p></div>
<div class="card"><b>Live interfaces</b><p><code>/api/v1/interfaces</code></p><p>TCP server, TCP client and serial sessions can now be created and controlled through the API.</p></div>
<div class="card"><b>Capture console</b><p>Each interface records RX/TX text, hexadecimal bytes, peer, timestamps and control-byte annotations. The interactive operator GUI is the next layer.</p></div>
</body></html>"""


def run():
    import uvicorn
    uvicorn.run("innaware_pms_emulator.main:app", host="0.0.0.0", port=8080)
