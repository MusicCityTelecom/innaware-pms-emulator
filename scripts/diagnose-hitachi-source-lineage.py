#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from innaware_pms_emulator.hitachi_source_guidance import (
    build_hitachi_source_guidance,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Emit fail-closed Hitachi/Epitome source-lineage guidance without "
            "inferring transport, framing, record offsets, or compatibility."
        )
    )
    parser.add_argument(
        "--source-sha",
        required=True,
        help="Exact 40-character Emulator Git SHA producing this guidance",
    )
    parser.add_argument(
        "--pms-protocol",
        required=True,
        choices=("EPIT-HIT", "EPIT-HIT2"),
        help="Legacy Epitome/Hitachi profile lineage under review",
    )
    parser.add_argument(
        "--symptom",
        default="unknown",
        choices=("unknown", "baseline", "checkin_failure", "room_name_mismatch"),
        help="Source-bounded technician symptom; does not auto-select a runtime profile",
    )
    parser.add_argument(
        "--requested-transport",
        default="unknown",
        choices=("unknown", "serial", "tcp", "tcp_client", "tcp_server"),
        help="Transport being investigated; concrete values remain unqualified here",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Write deterministic JSON to this file instead of stdout",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        report = build_hitachi_source_guidance(
            source_sha=args.source_sha,
            pms_protocol=args.pms_protocol,
            symptom=args.symptom,
            requested_transport=args.requested_transport,
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
