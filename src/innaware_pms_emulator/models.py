from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class InterfacePurpose(str, Enum):
    PMS = "pms"
    CALL_ACCOUNTING = "call_accounting"


class EmulationRole(str, Enum):
    PMS = "pms"
    PBX = "pbx"
    CALL_ACCOUNTING_SYSTEM = "call_accounting_system"
    PBX_CALL_ACCOUNTING_OUTPUT = "pbx_call_accounting_output"


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
    property_id: str | None = Field(default=None, max_length=80)
    # These fields are additive so 0.3.x saved interface files remain valid.
    # When emulation_role is omitted, legacy behavior is inferred from purpose.
    emulation_role: EmulationRole | None = None
    personality_id: str | None = Field(default=None, max_length=120)
    enabled: bool = True
    bind_host: str = "0.0.0.0"
    host: str | None = None
    port: int | None = Field(default=None, ge=1, le=65535)
    serial_device: str | None = None
    baud_rate: int = Field(default=9600, ge=50, le=4_000_000)
    data_bits: int = 8
    parity: str = "N"
    stop_bits: float = 1
    flow_control: str = "none"
    options: dict[str, Any] = Field(default_factory=dict)

    def effective_emulation_role(self) -> EmulationRole:
        if self.emulation_role is not None:
            return self.emulation_role
        if self.purpose is InterfacePurpose.CALL_ACCOUNTING:
            return EmulationRole.CALL_ACCOUNTING_SYSTEM
        return EmulationRole.PMS

    @field_validator("personality_id")
    @classmethod
    def normalize_personality_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        return normalized or None

    @field_validator("data_bits")
    @classmethod
    def validate_data_bits(cls, value: int) -> int:
        if value not in {5, 6, 7, 8}:
            raise ValueError("data_bits must be 5, 6, 7, or 8")
        return value

    @field_validator("parity")
    @classmethod
    def validate_parity(cls, value: str) -> str:
        normalized = value.strip().upper()
        if normalized not in {"N", "E", "O", "M", "S"}:
            raise ValueError("parity must be N, E, O, M, or S")
        return normalized

    @field_validator("stop_bits")
    @classmethod
    def validate_stop_bits(cls, value: float) -> float:
        if value not in {1, 1.5, 2}:
            raise ValueError("stop_bits must be 1, 1.5, or 2")
        return value

    @field_validator("flow_control")
    @classmethod
    def validate_flow_control(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"none", "rtscts", "xonxoff"}:
            raise ValueError("flow_control must be none, rtscts, or xonxoff")
        return normalized


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
