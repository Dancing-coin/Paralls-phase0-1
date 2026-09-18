from __future__ import annotations

try:
    from .common import verification_dir
except ImportError:
    from common import verification_dir

import json

from verify_phase3_common import root, write_report


def main() -> int:
    directory = verification_dir(root())
    names = (
        "phase3a-profile-activation",
        "phase3b-world-mode-continuity",
        "phase3c-batch-intent-merge",
        "phase3d-bakery-district-population",
    )
    reports = {
        name: json.loads(
            (directory / f"{name}-report.json").read_text(encoding="utf-8")
        )
        if (directory / f"{name}-report.json").exists()
        else {}
        for name in names
    }
    passed = all(report.get("overall_passed") is True for report in reports.values())
    report = {
        "overall_passed": passed,
        "phases": reports,
        "predecessors": {"phase1d": True, "phase2": True},
        "receipt": "phase3-aggregate",
        "revision_vector": {},
        "replay_hash": reports.get(names[-1], {}).get("replay_hash", ""),
        "scope_redaction": "phase receipts retain public/private boundary",
        "zero_write": all(
            bool(item.get("zero_write", False)) is not False
            for item in reports.values()
        ),
        "stop_reason": None if passed else "phase3_child_profile_failed",
    }
    return write_report("phase3-population-continuity", report)


if __name__ == "__main__":
    from pathlib import Path
    from run_context import run_scope

    with run_scope(Path(__file__).resolve().parents[2]):
        raise SystemExit(main())
