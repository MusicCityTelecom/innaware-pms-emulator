from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from serial.tools import list_ports

from . import __version__
from .models import CallRecord, GuestEvent, InterfaceConfig
from .operator_console import html as operator_html
from .property_api import router as property_router
from .property_state import property_manager
from .protocols.registry import REGISTRY, protocol_catalog
from .sessions import manager
from .storage import store


@asynccontextmanager
async def lifespan(app: FastAPI):
    await manager.restore(store.load())
    try:
        yield
    finally:
        await manager.shutdown()


app = FastAPI(title="InnAware PMS Emulator", version=__version__, lifespan=lifespan)
app.include_router(property_router)


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


def _persist() -> None:
    try:
        store.save(manager.configs())
    except OSError as exc:
        raise HTTPException(500, f"Unable to persist interface configuration: {exc}")


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
    return {
        "status": "ok",
        "version": __version__,
        "interfaces": len(manager.list()),
        "properties": len(property_manager.list()),
    }


@app.get("/api/v1/protocols")
def protocols():
    return {"protocols": protocol_catalog()}


@app.get("/api/v1/serial-ports")
def serial_ports():
    return {
        "ports": [
            {
                "device": item.device,
                "description": item.description,
                "hwid": item.hwid,
                "manufacturer": item.manufacturer,
                "product": item.product,
                "serial_number": item.serial_number,
            }
            for item in list_ports.comports()
        ]
    }


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
    if config.property_id:
        try:
            property_manager.get(config.property_id)
        except KeyError:
            raise HTTPException(400, f"Property '{config.property_id}' does not exist")
    config.protocol = config.protocol.upper()
    try:
        runtime = await manager.create(config)
    except (ValueError, OSError) as exc:
        raise HTTPException(400, str(exc))
    _persist()
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
    runtime = manager.get(name)
    runtime.config.enabled = True
    _persist()
    return runtime.status()


@app.post("/api/v1/interfaces/{name}/stop")
async def stop_interface(name: str):
    runtime = _interface_or_404(name)
    await manager.stop(name)
    runtime.config.enabled = False
    _persist()
    return runtime.status()


@app.delete("/api/v1/interfaces/{name}", status_code=204)
async def delete_interface(name: str):
    _interface_or_404(name)
    await manager.remove(name)
    _persist()


@app.get("/api/v1/interfaces/{name}/captures")
def interface_captures(name: str, limit: int = 200):
    _interface_or_404(name)
    return {"captures": manager.captures(name, limit)}


@app.get("/api/v1/interfaces/{name}/transactions")
def interface_transactions(name: str, limit: int = 100):
    _interface_or_404(name)
    return {"transactions": manager.transactions(name, limit)}


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


@app.post("/api/v1/interfaces/{name}/send/call-record-transaction")
async def send_call_record_transaction(name: str, call: CallRecord):
    runtime = _interface_or_404(name)
    if runtime.config.purpose.value != "call_accounting":
        raise HTTPException(400, "Interface is not a call-accounting interface")
    adapter = REGISTRY[runtime.config.protocol]
    payload = adapter.encode_call(call.model_dump())
    try:
        result = await manager.send_call_transaction(name, payload)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except RuntimeError as exc:
        raise HTTPException(409, str(exc))
    return {"protocol": runtime.config.protocol, "hex": payload.hex(" "), "transaction": result}


@app.get("/", response_class=HTMLResponse)
def index():
    return operator_html()


def run():
    import uvicorn

    uvicorn.run("innaware_pms_emulator.main:app", host="127.0.0.1", port=8080)
