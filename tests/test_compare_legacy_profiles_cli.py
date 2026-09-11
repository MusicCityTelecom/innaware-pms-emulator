import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPARE_SCRIPT = ROOT / "scripts" / "compare-legacy-profiles.py"
CHARACTERIZE_SCRIPT = ROOT / "scripts" / "characterize-legacy-profile.py"


def test_compare_cli_reports_only_sanitized_delta(tmp_path):
    baseline = tmp_path / "psip-pbx-protocol.EPIT-HIT"
    candidate = tmp_path / "psip-pbx-protocol.EPIT-HIT2"
    baseline.write_text(
        "[pbx-protocol]\n"
        "protocol=EPIT-HIT\n"
        "site_secret=never-emit-base\n"
        "[pbx-masks]\n"
        "namroom=8 3 MASK_NUMBER\n"
        "namname=11 20 MASK_LITERAL\n",
        encoding="utf-8",
    )
    candidate.write_text(
        "[pbx-protocol]\n"
        "protocol=EPIT-HIT2\n"
        "site_secret=never-emit-candidate\n"
        "[pbx-masks]\n"
        "namroom=4 3 MASK_NUMBER\n"
        "namname=7 20 MASK_LITERAL\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(COMPARE_SCRIPT),
            "--include-record-layouts",
            str(baseline),
            str(candidate),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["baseline"]["source_name"] == "psip-pbx-protocol.EPIT-HIT"
    assert len(payload["comparisons"]) == 1
    delta = payload["comparisons"][0]
    assert delta["candidate_source_name"] == "psip-pbx-protocol.EPIT-HIT2"
    assert delta["record_mask_layout_changes"] == {
        "NAMNAME": {
            "baseline": "11 20 MASK_LITERAL",
            "candidate": "7 20 MASK_LITERAL",
        },
        "NAMROOM": {
            "baseline": "8 3 MASK_NUMBER",
            "candidate": "4 3 MASK_NUMBER",
        },
    }
    assert "never-emit" not in result.stdout


def test_compare_cli_fails_closed_without_exposing_missing_path(tmp_path):
    missing = tmp_path / "private-site" / "missing-profile"
    candidate = tmp_path / "candidate"
    candidate.write_text("[pbx-protocol]\nprotocol=SYNTHETIC\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(COMPARE_SCRIPT), str(missing), str(candidate)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["baseline"] == "missing-profile"
    assert payload["comparisons"] == []
    assert payload["error"] == "profile could not be read"
    assert str(tmp_path) not in result.stdout
    assert "private-site" not in result.stdout


def test_characterize_cli_fails_closed_without_exposing_missing_path(tmp_path):
    missing = tmp_path / "private-site" / "psip-pbx-protocol.EPIT-HIT"

    result = subprocess.run(
        [sys.executable, str(CHARACTERIZE_SCRIPT), str(missing)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload == [
        {
            "source_name": "psip-pbx-protocol.EPIT-HIT",
            "error": "profile could not be read",
        }
    ]
    assert str(tmp_path) not in result.stdout
    assert "private-site" not in result.stdout
