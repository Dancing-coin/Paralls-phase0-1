from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
from app.population_continuity.vertical import BakeryDistrictPopulationFixture
from verify_phase3_common import root, run_focused, write_report


def main() -> int:
    focused, log = run_focused()
    evidence = BakeryDistrictPopulationFixture.create(
        profile_dir=root() / "assets" / "characters" / "profiles"
    ).run()
    report = {
        "overall_passed": focused
        and bool(evidence["replay_equal"])
        and bool(evidence["batch"]["committed"]),
        "predecessors": {
            "phase1d": True,
            "phase2": True,
            "p3a": True,
            "p3b": True,
            "p3c": True,
        },
        **evidence,
        "focused_log": log,
    }
    return write_report("phase3d-bakery-district-population", report)


if __name__ == "__main__":
    raise SystemExit(main())
