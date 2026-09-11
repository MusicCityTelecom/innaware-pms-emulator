from __future__ import annotations

import asyncio
import io
import os
import platform
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, Response, StreamingResponse
from pydantic import BaseModel, Field
from serial.tools import list_ports

from . import __version__
from .capture_diagnostics import diagnose_capture_interface
from .capture_diagnostics_console import html as capture_diagnostics_html
from .models import CallRecord, GuestEvent, InterfaceConfig
from .operator_console import html as operator_html
from .profiles import build_interface_from_profile, profile_catalog
from .property_api import router as property_router
from .property_state import property_manager
from .protocol_packs import active_pack_stubs, current_protocol_pack_version
from .protocols.registry import REGISTRY, protocol_catalog
from .sessions import manager
from .storage import data_dir, store
from .support import build_support_bundle, capture_export, safe_name
from .telemetry import telemetry_service
from .update_console import html as update_html
from .updates import UpdateError, update_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    await manager.restore(store.load())
    settings = update_manager.load_settings()
    if os.environ.get("INNAWARE_PMS_TELEMETRY_SUPPRESS_STARTUP") != "1":
        telemetry_service.start_background(
            __version__,
            enabled=bool(settings.get("send_anonymous_usage_statistics", True)),
        )
    update_manager.start_background_check(__version__)
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


class ProfileInstantiateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    property_id: str | None = None
    enabled: bool = True
    overrides: dict = Field(default_factory=dict)


class UpdateSettingsRequest(BaseModel):
    check_app_updates_on_start: bool = True
    check_protocol_updates_on_start: bool = True
    include_prereleases: bool = True
    send_anonymous_usage_statistics: bool = True


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


def _serial_port_catalog() -> list[dict]:
    return [
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


@app.get("/api/v1/health")
def health():
    return {
        "status": "ok",
        "version": __version__,
        "interfaces": len(manager.list()),
        "properties": len(property_manager.list()),
    }


@app.get("/api/v1/app-info")
def app_info():
    return {
        "product": "InnAware PMS Emulator",
        "version": __version__,
        "protocol_pack_version": current_protocol_pack_version(),
        "platform": platform.system(),
        "platform_release": platform.release(),
        "machine": platform.machine(),
        "data_dir": str(data_dir()),
        "primary_field_target": "Windows",
        "linux_role": "headless development and interoperability lab",
    }


@app.get("/api/v1/protocols")
def protocols():
    return {"protocols": protocol_catalog()}


@app.get("/api/v1/profiles")
def profiles():
    return {"profiles": profile_catalog()}


@app.post("/api/v1/profiles/{profile_id}/instantiate", status_code=201)
async def instantiate_profile(profile_id: str, request: ProfileInstantiateRequest):
    try:
        config = build_interface_from_profile(
            profile_id,
            name=request.name,
            property_id=request.property_id,
            enabled=request.enabled,
            overrides=request.overrides,
        )
    except KeyError:
        raise HTTPException(404, f"Profile '{profile_id}' not found")
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return await create_interface(config)


@app.get("/api/v1/serial-ports")
def serial_ports():
    return {"ports": _serial_port_catalog()}


@app.get("/api/v1/protocol-packs/stubs")
def protocol_pack_stubs():
    return {"stubs": active_pack_stubs()}


@app.get("/api/v1/updates/status")
def update_status():
    return update_manager.load_status()


@app.get("/api/v1/updates/settings")
def update_settings():
    return update_manager.load_settings()


@app.put("/api/v1/updates/settings")
def save_update_settings(request: UpdateSettingsRequest):
    return update_manager.save_settings(request.model_dump())


@app.get("/api/v1/telemetry/status")
def telemetry_status():
    settings = update_manager.load_settings()
    return telemetry_service.public_status(
        __version__,
        enabled=bool(settings.get("send_anonymous_usage_statistics", True)),
    )


@app.post("/api/v1/updates/check")
async def check_updates():
    return await asyncio.to_thread(update_manager.check, __version__)


@app.post("/api/v1/updates/app/download")
async def download_app_update():
    try:
        return await asyncio.to_thread(update_manager.download_app_update, __version__)
    except UpdateError as exc:
        raise HTTPException(409, str(exc))


@app.post("/api/v1/updates/app/launch")
async def launch_app_update():
    try:
        return await asyncio.to_thread(update_manager.launch_downloaded_app_update)
    except UpdateError as exc:
        raise HTTPException(409, str(exc))


@app.post("/api/v1/updates/protocol-pack/install")
async def install_protocol_pack():
    try:
        return await asyncio.to_thread(update_manager.install_latest_protocol_pack)
    except UpdateError as exc:
        raise HTTPException(409, str(exc))


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


@app.get("/api/v1/interfaces/{name}/captures/export")
def interface_capture_export(name: str, format: str = "csv", limit: int = 2000):
    _interface_or_404(name)
    try:
        content, media_type, extension = capture_export(manager.captures(name, limit), format)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    filename = f"{safe_name(name)}-capture.{extension}"
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/v1/interfaces/{name}/transactions")
def interface_transactions(name: str, limit: int = 100):
    _interface_or_404(name)
    return {"transactions": manager.transactions(name, limit)}


@app.get("/api/v1/interfaces/{name}/diagnostics")
def interface_diagnostics(name: str, limit: int = 100):
    _interface_or_404(name)
    return {"diagnostics": manager.diagnostics(name, limit)}


@app.get("/api/v1/interfaces/{name}/capture-diagnostics")
def interface_capture_diagnostics(name: str, limit: int = 200):
    runtime = _interface_or_404(name)
    report = diagnose_capture_interface(runtime.config, manager.captures(name, limit))
    return report.as_dict()


@app.get("/api/v1/support-bundle")
def support_bundle(include_property_state: bool = False):
    statuses = manager.list()
    configs = [config.model_dump(mode="json") for config in manager.configs()]
    property_summaries = property_manager.list()
    captures = {item["name"]: manager.captures(item["name"], 2000) for item in statuses}
    transactions = {item["name"]: manager.transactions(item["name"], 200) for item in statuses}
    diagnostics = {item["name"]: manager.diagnostics(item["name"], 500) for item in statuses}
    full_state = None
    if include_property_state:
        full_state = [property_manager.get(item["id"]).model_dump(mode="json") for item in property_summaries]
    content = build_support_bundle(
        interface_statuses=statuses,
        interface_configs=configs,
        property_summaries=property_summaries,
        protocol_catalog=protocol_catalog(),
        serial_ports=_serial_port_catalog(),
        captures_by_interface=captures,
        transactions_by_interface=transactions,
        diagnostics_by_interface=diagnostics,
        full_property_state=full_state,
    )
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%SZ")
    filename = f"InnAware-PMS-Emulator-Support-{stamp}.zip"
    return StreamingResponse(
        io.BytesIO(content),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


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
        if runtime.config.options.get("transactional_enq_ack"):
            transaction = await manager.send_pms_transaction(name, payload)
            return {
                "sent_to": 1 if transaction.get("success") else 0,
                "protocol": runtime.config.protocol,
                "hex": payload.hex(" "),
                "transaction": transaction,
            }
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


@app.get("/capture-diagnostics", response_class=HTMLResponse)
def capture_diagnostics_page():
    return capture_diagnostics_html()


@app.get("/updates", response_class=HTMLResponse)
def updates_page():
    return update_html()


@app.get("/", response_class=HTMLResponse)
def index():
    page = operator_html()
    marker = '<span id="health"'
    if marker in page:
        page = page.replace(
            marker,
            '<button onclick="location.href=\'/updates\'">Updates</button> '
            '<button onclick="location.href=\'/capture-diagnostics\'">Analyze Capture</button> '
            '<span id="health"',
            1,
        )
    return page


def run():
    import uvicorn

    uvicorn.run("innaware_pms_emulator.main:app", host="127.0.0.1", port=8080)
