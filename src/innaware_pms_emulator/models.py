from enum import Enum
from pydantic import BaseModel, Field
from typing import Any


class InterfacePurpose(str, Enum):
    PMS = "pms"
    CALL_ACCOUNTING = "call_accounting"


class TransportMode(str, Enum):
    TCP_SERVER = "tcp_server"
    TCP_CLIENT = "tcp_client"
    SERIAL = "serial"
    HTTP_SERVER = "http_server"


class InterfaceConfig(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    purpose: InterfacePurpose
    protocol: str
    transport: TransportMode
    enabled: bool = True
    bind_host: str = "0.0.0.0"
    host: str | None = None
    port: int | None = Field(default=None, ge=1, le=65535)
    serial_device: str | None = None
    baud_rate: int = 9600
    data_bits: int = 8
    parity: str = "N"
    stop_bits: int = 1
    flow_control: str = "none"
    options: dict[str, Any] = Field(default_factory=dict)


class GuestEvent(BaseModel):
    action: str
    room: str
    last_name: str = ""
    first_name: str = ""
    new_room: str | None = None
    wakeup_time: str | None = None
    wakeup_date: str | None = None
    status_code: str | None = None
    restriction: str | None = None
    language: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class CallRecord(BaseModel):
    room: str
    number: str
    duration_seconds: int = Field(ge=0)
    cost: float = Field(default=0.0, ge=0)
    call_type: str = "D"
    timestamp: str | None = None
    description: str = ""
