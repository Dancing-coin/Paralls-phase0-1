from __future__ import annotations

import argparse

from common import repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python-exe", default=None)
    args = parser.parse_args()
    root = repo_root()
    log = verification_dir(root) / "gameplay-inventory-pytest.log"
    result = run_command([resolve_python_exe(args.python_exe), "-m", "pytest", "-q", "backend/tests/test_inventory_runtime.py"], root, log)
    report = {"overall_gameplay_inventory_passed": result.returncode == 0, "scope": "backend proof for event-derived item location, container capacity, sealed rejection, and atomic move; it excludes nesting, encumbrance, ownership, equipment, transport, and Godot mirror", "results": [{"id": "inventory-core", "title": "Minimal inventory authority preserves one item location", "status": "proved" if result.returncode == 0 else "missing", "evidence": [str(log)] if result.returncode == 0 else []}], "artifacts": {"pytest_log": str(log)}}
    write_json(verification_dir(root) / "gameplay-inventory-report.json", report)
    write_markdown(verification_dir(root) / "gameplay-inventory-report.md", "Gameplay Inventory Verification Report", report, "overall_gameplay_inventory_passed")
    print(f"overall_gameplay_inventory_passed={report['overall_gameplay_inventory_passed']}")
    return 0 if result.returncode == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
