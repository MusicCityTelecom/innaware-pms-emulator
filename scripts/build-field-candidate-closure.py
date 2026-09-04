#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from innaware_pms_emulator.field_candidate_closure import build_field_candidate_closure


def _load(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build fail-closed InnAware PMS Emulator field candidate closure manifest")
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--artifact-manifest", type=Path, required=True)
    parser.add_argument("--windows-acceptance", type=Path, required=True)
    parser.add_argument("--ucp-exchange", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    result = build_field_candidate_closure(
        expected_source_sha=args.source_sha,
        artifact_manifest=_load(args.artifact_manifest),
        windows_acceptance=_load(args.windows_acceptance),
        ucp_exchange=_load(args.ucp_exchange),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"closure_ready": result["closure_ready"], "blockers": result["blockers"]}, indent=2))
    return 0 if result["closure_ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
