#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from innaware_pms_emulator.phonesuite_serial_diagnostics import (
    analyze_phonesuite_serial_transactions,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Characterize the evidence-bounded PhoneSuite MITEL 1-compatible serial "
            "PBX-to-PMS ENQ/ACK and STX/ETX application sequence without inferring "
            "serial defaults, checksum semantics, retry policy, or compatibility promotion."
        )
    )
    parser.add_argument(
        "capture",
        type=Path,
        help="JSON capture list or object containing a 'captures' list",
    )
    parser.add_argument(
        "--transport",
        required=True,
        choices=("tcp", "serial", "unknown"),
        help="Must be serial for the currently evidence-qualified PhoneSuite row",
    )
    parser.add_argument(
        "--evidence-class",
        required=True,
        choices=(
            "packet_capture",
            "operator_confirmed",
            "legacy_source_profile",
            "simulator_characterization",
            "inference",
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Write deterministic JSON to this file instead of stdout",
    )
    return parser


def _load_capture(path: Path) -> list[object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("capture could not be read as UTF-8 JSON") from exc

    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and isinstance(payload.get("captures"), list):
        return payload["captures"]
    raise ValueError("capture JSON must be a list or an object containing a 'captures' list")


def main() -> int:
    args = _parser().parse_args()
    try:
        captures = _load_capture(args.capture)
        report = analyze_phonesuite_serial_transactions(
            captures,
            transport=args.transport,
            evidence_class=args.evidence_class,
        )
    except ValueError as exc:
        print(json.dumps({"error": str(exc)}, sort_keys=True))
        return 2

    encoded = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        try:
            args.output.write_text(encoded, encoding="utf-8")
        except OSError:
            print(json.dumps({"error": "output could not be written"}, sort_keys=True))
            return 2
    else:
        print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
