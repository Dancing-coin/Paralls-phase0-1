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


def episode_result_ok(
    report: dict[str, object],
    *,
    legacy_exit_code: int = 0,
    artifact_root: Path | None = None,
) -> tuple[bool, list[str]]:
    notes: list[str] = []
    if not report:
        return False, ["missing_legacy_verifier_report"]
    if legacy_exit_code != 0:
        notes.append("legacy_verifier_failed")
    if not bool(report.get("overall_obj_archive_door_physical_embodiment_passed", False)):
        notes.append("legacy_profile_not_passed")
    if not bool(report.get("selected_scenarios_passed", False)):
        notes.append("selected_scenarios_failed")
    scenarios = report.get("selected_scenarios", [])
    if set(scenarios if isinstance(scenarios, list) else []) != {"success", "distance_failure", "revision_failure", "stance_failure"}:
        notes.append("incomplete_scenario_matrix")
    artifacts = report.get("artifacts", {})
    if not isinstance(artifacts, dict):
        notes.append("missing_backend_or_replay_trace")
    else:
        required = ("backend_trace", "replay_trace", "runtime")
        if any(not artifacts.get(name) for name in required):
            notes.append("missing_backend_or_replay_trace")
        screenshots = artifacts.get("screenshots")
        required_screenshots = {"success", "distance_failure", "revision_failure", "stance_failure"}
        if not isinstance(screenshots, dict) or set(screenshots) < required_screenshots or any(not value for value in screenshots.values()):
            notes.append("missing_runtime_screenshots")
        if artifact_root is not None:
            paths = [artifacts.get(name) for name in required]
            if isinstance(screenshots, dict):
                paths.extend(screenshots.values())
            if any(not isinstance(value, str) or not (artifact_root / value).exists() for value in paths):
                notes.append("artifact_path_missing")
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
    passed, notes = episode_result_ok(legacy, legacy_exit_code=completed.returncode, artifact_root=root)
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
