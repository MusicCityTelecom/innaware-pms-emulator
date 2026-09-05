from __future__ import annotations

import configparser
import hashlib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

MAX_PROFILE_BYTES = 256 * 1024

_CONTROL_BYTE_KEYS = ("enq", "stx", "etx", "ack", "ack2", "nak")
_SERIAL_FIELD_ALIASES = {
    "baud": "baud_rate",
    "baudrate": "baud_rate",
    "baud_rate": "baud_rate",
    "databits": "data_bits",
    "data_bits": "data_bits",
    "parity": "parity",
    "stopbits": "stop_bits",
    "stop_bits": "stop_bits",
    "flowcontrol": "flow_control",
    "flow_control": "flow_control",
}
_RECORD_KEYS = {
    "chk",
    "nam",
    "rst",
    "wkp",
    "mw",
    "sts",
    "dnd",
    "lng",
    "lmt",
    "dpt",
    "loc",
    "vip",
    "sdd",
    "ste",
    "mov",
    "edt",
    "msg",
    "grs",
    "end",
    "rqinz",
    "areyouthere",
}
_SAFE_SCALAR_KEYS = ("description", "protocol", "family", "checksum", "nameorder")
_SAFE_MASK_KEYS = {
    "swapnames",
    "nameindex0",
    "chkdelim",
    "namdelim",
}
_SAFE_MASK_SUFFIXES = {
    "",
    "delim",
    "room",
    "name",
    "status",
    "index",
    "index0",
    "prefix",
    "suffix",
    "offset",
    "length",
    "mask",
    "literal",
    "first",
    "last",
}


@dataclass(frozen=True, slots=True)
class LegacyProfileEvidence:
    """Sanitized interoperability facts derived from a textual legacy profile.

    The object deliberately excludes unrecognized key values. This lets field
    technicians characterize an authorized legacy profile without copying the
    whole vendor file, credentials, or site-specific data into evidence notes.
    """

    source_name: str
    sha256: str
    evidence_class: str
    sections: tuple[str, ...]
    profile_section: str | None
    mask_section: str | None
    profile_identity: dict[str, str]
    transport: str
    transport_source: str
    control_bytes: dict[str, int]
    serial_parameters: dict[str, str | int | float]
    record_keys: tuple[str, ...]
    record_layouts: dict[str, str]
    record_mask_keys: tuple[str, ...]
    record_mask_layouts: dict[str, str]
    unknown_key_count: int
    unknown_mask_key_count: int
    warnings: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["sections"] = list(self.sections)
        value["record_keys"] = list(self.record_keys)
        value["record_mask_keys"] = list(self.record_mask_keys)
        value["warnings"] = list(self.warnings)
        return value


def _parse_int(value: str) -> int:
    token = value.strip().lower()
    base = 16 if token.startswith("0x") else 10
    number = int(token, base)
    if not 0 <= number <= 255:
        raise ValueError("control byte must be between 0 and 255")
    return number


def _parse_serial_value(key: str, value: str) -> str | int | float:
    token = value.strip()
    if key in {"baud_rate", "data_bits", "stop_bits"}:
        try:
            number = float(token)
        except ValueError:
            return token
        return int(number) if number.is_integer() else number
    return token


def _normalize_transport(value: str) -> str | None:
    token = value.strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "serial": "serial",
        "rs232": "serial",
        "rs_232": "serial",
        "tcp": "tcp",
        "tcpip": "tcp",
        "tcp_ip": "tcp",
        "tcp_server": "tcp_server",
        "tcp_client": "tcp_client",
    }
    return aliases.get(token)


def _is_safe_record_mask_key(key: str) -> bool:
    normalized = key.strip().lower()
    if normalized in _SAFE_MASK_KEYS:
        return True
    for prefix in _RECORD_KEYS:
        if normalized == prefix:
            return True
        if normalized.startswith(prefix) and normalized[len(prefix) :] in _SAFE_MASK_SUFFIXES:
            return True
    return False


def characterize_legacy_profile_bytes(
    data: bytes,
    *,
    source_name: str = "legacy-profile",
    include_record_layouts: bool = False,
) -> LegacyProfileEvidence:
    """Parse an authorized INI-like profile without inferring missing facts.

    Exact record-mask values are omitted by default. Callers must explicitly
    opt in to them for local characterization; even then only known protocol
    command keys and bounded PBX-mask layout keys are emitted, never arbitrary
    profile values.
    """

    if len(data) > MAX_PROFILE_BYTES:
        raise ValueError(f"profile exceeds {MAX_PROFILE_BYTES} byte safety limit")
    if b"\x00" in data:
        raise ValueError("profile contains NUL bytes; expected a textual legacy profile")

    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("profile is not valid UTF-8 text") from exc

    parser = configparser.RawConfigParser(
        interpolation=None,
        strict=False,
        delimiters=("=",),
        comment_prefixes=("#", ";"),
        inline_comment_prefixes=None,
        empty_lines_in_values=False,
    )
    parser.optionxform = str.lower
    try:
        parser.read_string(text)
    except configparser.Error as exc:
        raise ValueError(f"invalid INI-style legacy profile: {exc}") from exc

    sections = tuple(parser.sections())
    profile_section = next(
        (name for name in sections if name.strip().lower() == "pbx-protocol"),
        sections[0] if sections else None,
    )
    if profile_section is None:
        raise ValueError("legacy profile contains no INI section")
    mask_section = next(
        (name for name in sections if name.strip().lower() == "pbx-masks"),
        None,
    )

    items = dict(parser.items(profile_section, raw=True))
    mask_items = dict(parser.items(mask_section, raw=True)) if mask_section is not None else {}
    identity = {
        key: items[key].strip()
        for key in _SAFE_SCALAR_KEYS
        if key in items and items[key].strip()
    }

    warnings: list[str] = []
    control_bytes: dict[str, int] = {}
    for key in _CONTROL_BYTE_KEYS:
        raw = items.get(key)
        if raw is None or not raw.strip():
            continue
        try:
            control_bytes[key] = _parse_int(raw)
        except ValueError:
            warnings.append(f"{key} is present but is not a valid byte value")

    serial_parameters: dict[str, str | int | float] = {}
    for raw_key, normalized_key in _SERIAL_FIELD_ALIASES.items():
        raw = items.get(raw_key)
        if raw is None or not raw.strip() or normalized_key in serial_parameters:
            continue
        serial_parameters[normalized_key] = _parse_serial_value(normalized_key, raw)

    raw_transport = items.get("transport", "")
    normalized_transport = _normalize_transport(raw_transport) if raw_transport.strip() else None
    if normalized_transport is not None:
        transport = normalized_transport
        transport_source = "explicit_profile_key"
    else:
        transport = "unknown"
        transport_source = "none"
        if raw_transport.strip():
            warnings.append(
                "transport key is present but its value is not recognized; no transport was inferred"
            )

    record_keys = tuple(sorted(key.upper() for key in items if key in _RECORD_KEYS))
    record_layouts = (
        {key.upper(): items[key] for key in sorted(items) if key in _RECORD_KEYS}
        if include_record_layouts
        else {}
    )
    safe_mask_keys = tuple(sorted(key for key in mask_items if _is_safe_record_mask_key(key)))
    record_mask_keys = tuple(key.upper() for key in safe_mask_keys)
    record_mask_layouts = (
        {key.upper(): mask_items[key] for key in safe_mask_keys}
        if include_record_layouts
        else {}
    )

    recognized_keys = set(_SAFE_SCALAR_KEYS)
    recognized_keys.update(_CONTROL_BYTE_KEYS)
    recognized_keys.update(_SERIAL_FIELD_ALIASES)
    recognized_keys.update(_RECORD_KEYS)
    recognized_keys.add("transport")
    unknown_key_count = sum(1 for key in items if key not in recognized_keys)
    unknown_mask_key_count = sum(1 for key in mask_items if not _is_safe_record_mask_key(key))

    if transport == "unknown":
        warnings.append(
            "transport remains unqualified because no recognized explicit transport key is present"
        )
    if not serial_parameters:
        warnings.append(
            "no profile-bound serial parameters were found; do not inherit generic serial defaults"
        )
    if mask_section is not None and unknown_mask_key_count:
        warnings.append(
            "PBX mask section contains unrecognized keys whose values were intentionally omitted"
        )

    return LegacyProfileEvidence(
        source_name=Path(source_name).name,
        sha256=hashlib.sha256(data).hexdigest(),
        evidence_class="legacy_source_profile",
        sections=sections,
        profile_section=profile_section,
        mask_section=mask_section,
        profile_identity=identity,
        transport=transport,
        transport_source=transport_source,
        control_bytes=control_bytes,
        serial_parameters=serial_parameters,
        record_keys=record_keys,
        record_layouts=record_layouts,
        record_mask_keys=record_mask_keys,
        record_mask_layouts=record_mask_layouts,
        unknown_key_count=unknown_key_count,
        unknown_mask_key_count=unknown_mask_key_count,
        warnings=tuple(warnings),
    )


def characterize_legacy_profile_file(
    path: str | Path,
    *,
    include_record_layouts: bool = False,
) -> LegacyProfileEvidence:
    profile_path = Path(path)
    return characterize_legacy_profile_bytes(
        profile_path.read_bytes(),
        source_name=profile_path.name,
        include_record_layouts=include_record_layouts,
    )
