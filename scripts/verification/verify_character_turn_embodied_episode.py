from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

SCRIPTS_ROOT = Path(__file__).resolve().parent
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from common import repo_root, resolve_godot_exe, resolve_python_exe, verification_dir, write_json, write_markdown


PROFILE_NAME = "character-turn-embodied-episode"
PROFILE_ORDER = 86
REPORT_FILENAME = "character-turn-embodied-episode-report.json"
LEGACY_VERIFIER = "scripts/verification/verify_obj_archive_door_physical_embodiment.py"


def _runtime_report(root: Path) -> dict[str, object]:
    path = verification_dir(root) / "obj-archive-door-physical-embodiment-report.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def episode_result_ok(report: dict[str, object], *, legacy_exit_code: int = 0) -> tuple[bool, list[str]]:
    notes: list[str] = []
    if not report:
        return False, ["missing_legacy_verifier_report"]
    if legacy_exit_code != 0:
        notes.append("legacy_verifier_failed")
    if "overall_obj_archive_door_physical_embodiment_passed" in report and not bool(report.get("overall_obj_archive_door_physical_embodiment_passed", False)):
        notes.append("legacy_profile_not_passed")
    if not bool(report.get("selected_scenarios_passed", False)):
        notes.append("selected_scenarios_failed")
    scenarios = report.get("selected_scenarios", [])
    if set(scenarios if isinstance(scenarios, list) else []) != {"success", "distance_failure", "revision_failure", "stance_failure"}:
        notes.append("incomplete_scenario_matrix")
    artifacts = report.get("artifacts", {})
    if not isinstance(artifacts, dict) or not artifacts.get("backend_trace") or not artifacts.get("replay_trace"):
        notes.append("missing_backend_or_replay_trace")
    return not notes, notes


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--godot-exe", default=None)
    parser.add_argument("--python-exe", default=None)
    args = parser.parse_args()
    root = repo_root()
    python_exe = resolve_python_exe(args.python_exe)
    godot_exe = resolve_godot_exe(args.godot_exe)
    command = [python_exe, str(root / LEGACY_VERIFIER), "--python-exe", python_exe]
    if godot_exe is not None:
        command.extend(["--godot-exe", str(godot_exe)])
    completed = subprocess.run(command, cwd=str(root), check=False)
    legacy = _runtime_report(root)
    passed, notes = episode_result_ok(legacy, legacy_exit_code=completed.returncode)
    report = {
        "overall_passed": passed,
        "profile": PROFILE_NAME,
        "source_verifier": LEGACY_VERIFIER,
        "legacy_exit_code": completed.returncode,
        "backend_settlement_trace": legacy.get("artifacts", {}).get("backend_trace") if isinstance(legacy.get("artifacts"), dict) else "",
        "replay_trace": legacy.get("artifacts", {}).get("replay_trace") if isinstance(legacy.get("artifacts"), dict) else "",
        "godot_runtime": legacy.get("artifacts", {}).get("runtime") if isinstance(legacy.get("artifacts"), dict) else "",
        "screenshots": legacy.get("artifacts", {}).get("screenshots", {}) if isinstance(legacy.get("artifacts"), dict) else {},
        "scenarios": legacy.get("selected_scenarios", []),
        "notes": notes,
    }
    output = verification_dir(root) / REPORT_FILENAME
    write_json(output, report)
    write_markdown(verification_dir(root) / "character-turn-embodied-episode-report.md", "Character Turn Embodied Episode Verification Report", report, "overall_passed")
    print(f"overall_passed={passed}")
    print(f"character_turn_embodied_episode_report_json={output}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
