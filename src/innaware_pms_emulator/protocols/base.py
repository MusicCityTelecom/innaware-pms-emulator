from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class DecodedRecord:
    kind: str
    room: str | None = None
    fields: dict[str, Any] = field(default_factory=dict)
    raw: bytes = b""


class ProtocolAdapter(Protocol):
    name: str
    purpose: str

    def encode_event(self, event: dict[str, Any]) -> bytes: ...
    def decode(self, payload: bytes) -> DecodedRecord: ...
