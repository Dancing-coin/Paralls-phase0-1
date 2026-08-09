from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from common import repo_root, verification_dir, write_json, write_markdown


def run_profile(*, name: str, overall_key: str, predecessor: str, checks: dict[str, object]) -> int:
    root = repo_root()
    directory = verification_dir(root)
    predecessor_path = directory / predecessor
    try:
        predecessor_report = json.loads(predecessor_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        predecessor_report = {}
    predecessor_ok = any(value is True for key, value in predecessor_report.items() if key.startswith("overall_"))
    passed = predecessor_ok and all(value is True for value in checks.values())
    report = {overall_key: passed, "predecessor": {"path": str(predecessor_path), "passed": predecessor_ok}, "checks": checks}
    json_path = directory / f"{name}-report.json"
    md_path = directory / f"{name}-report.md"
    write_json(json_path, report)
    write_markdown(md_path, f"{name} Verification Report", report, overall_key)
    print(f"{name}_report_json={json_path}")
    print(f"{name}_report_md={md_path}")
    print(f"{overall_key}={passed}")
    return 0 if passed else 1
