"""Inspect sanitized endpoint declarations without extracting or executing CMND."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from innaware_pms_emulator.cmnd_reference import inspect_reference


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("war", type=Path)
    parser.add_argument("--context-path", default="/SmartInstall")
    args = parser.parse_args()
    print(json.dumps(inspect_reference(args.war, context_path=args.context_path), indent=2))


if __name__ == "__main__":
    main()
