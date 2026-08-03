from __future__ import annotations

import argparse

from common import repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


TEST_FILES = ["backend/tests/test_equipment_runtime.py"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python-exe", default=None)
    args = parser.parse_args()
    root = repo_root()
    log = verification_dir(root) / "gameplay-possession-equipment-pytest.log"
    result = run_command([resolve_python_exe(args.python_exe), "-m", "pytest", "-q", *TEST_FILES], root, log)
    report = {
        "overall_gameplay_possession_equipment_passed": result.returncode == 0,
        "scope": "backend proof that inventory placement, multi-slot equipment activation, atomic swap, activation-scoped ability-path grants, and modifier sources commit together or not at all; it excludes container-access propagation and Godot presentation binding",
        "results": [
            {
                "id": "equipment-authority-core",
                "title": "Equip, unequip, and swap coordinate inventory, multi-slot activation, ability-grant, and modifier streams atomically",
                "status": "proved" if result.returncode == 0 else "missing",
                "evidence": [str(log)] if result.returncode == 0 else [],
                "notes": f"exit_code={result.returncode}",
            }
        ],
        "artifacts": {"pytest_log": str(log)},
    }
    write_json(verification_dir(root) / "gameplay-possession-equipment-report.json", report)
    write_markdown(
        verification_dir(root) / "gameplay-possession-equipment-report.md",
        "Gameplay Possession Equipment Verification Report",
        report,
        "overall_gameplay_possession_equipment_passed",
    )
    print(f"overall_gameplay_possession_equipment_passed={report['overall_gameplay_possession_equipment_passed']}")
    return 0 if result.returncode == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
