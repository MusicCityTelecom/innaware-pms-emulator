from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Iterable

from .models import InterfaceConfig


def data_dir() -> Path:
    override = os.environ.get("INNAWARE_PMS_DATA_DIR")
    if override:
        path = Path(override).expanduser()
    elif os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home()))
        path = base / "InnAware" / "PMS Emulator"
    else:
        path = Path.home() / ".local" / "share" / "innaware-pms-emulator"
    path.mkdir(parents=True, exist_ok=True)
    return path


class ConfigStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (data_dir() / "interfaces.json")

    def load(self) -> list[InterfaceConfig]:
        if not self.path.exists():
            return []
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        if not isinstance(raw, list):
            return []
        configs: list[InterfaceConfig] = []
        for item in raw:
            try:
                configs.append(InterfaceConfig.model_validate(item))
            except Exception:
                continue
        return configs

    def save(self, configs: Iterable[InterfaceConfig]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = [config.model_dump(mode="json") for config in configs]
        temp = self.path.with_suffix(self.path.suffix + ".tmp")
        temp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temp.replace(self.path)


store = ConfigStore()
