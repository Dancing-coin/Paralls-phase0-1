from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from common import read_text, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


TEST_FILES = ["backend/tests/test_embodied_action_controller_static.py"]


def _result(check_id: str, title: str, proved: bool, evidence: list[str], notes: str = "") -> dict[str, object]:
    return {
        "id": check_id,
        "title": title,
        "status": "proved" if proved else "missing",
        "evidence": evidence if proved else [],
        "notes": notes,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--godot-exe", default=None)
    parser.add_argument("--python-exe", default=None)
    args = parser.parse_args()

    project_root = repo_root()
    log_dir = verification_dir(project_root)
    python_exe = resolve_python_exe(args.python_exe)
    pytest_log = log_dir / "embodied-action-controller-pytest.log"
    pytest_result = run_command([python_exe, "-m", "pytest", "-q", *TEST_FILES], project_root, pytest_log)

    godot_log = log_dir / "embodied-action-controller-godot.log"
    godot_artifact = log_dir / "embodied-action-controller-godot-runtime.json"
    godot_ok = False
    if args.godot_exe:
        godot_result = run_command(
            [
                args.godot_exe,
                "--headless",
                "--path",
                str(project_root),
                "--scene",
                "res://scenes/phase0/EmbodiedActionControllerProbe.tscn",
                "--quit-after",
                "300",
                "--render-thread",
                "safe",
            ],
            project_root,
            godot_log,
        )
        godot_text = read_text(godot_log)
        godot_ok = (
            godot_result.returncode == 0
            and "embodied_action_controller_probe:verified=true" in godot_text
            and "leaked" not in godot_text.lower()
            and godot_artifact.exists()
        )
    try:
        runtime_payload = json.loads(godot_artifact.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        runtime_payload = {}
    outcomes = runtime_payload.get("outcomes", {}) if isinstance(runtime_payload, dict) else {}
    success = outcomes.get("success", {}) if isinstance(outcomes, dict) else {}
    miss = outcomes.get("miss", {}) if isinstance(outcomes, dict) else {}
    no_path = outcomes.get("no_path", {}) if isinstance(outcomes, dict) else {}
    results = [
        _result("focused-pytest-pass", "EmbodiedActionController static contract pytest passes", pytest_result.returncode == 0, [str(pytest_log)]),
        _result(
            "godot-runtime-terminal-paths",
            "Godot runtime controller probe covers success, miss, no-path, fixed target, target move, cancellation, alignment, and stance failures",
            godot_ok and isinstance(outcomes, dict) and len(outcomes) >= 8,
            [str(godot_log), str(godot_artifact)],
        ),
        _result(
            "contact-observation-bounded",
            "Success emits bounded contact/object observation while miss does not fabricate contact",
            isinstance(success, dict)
            and success.get("terminal_status") == "contact_observed"
            and "contact_observation" in success
            and isinstance(miss, dict)
            and miss.get("terminal_status") == "missed_contact"
            and "contact_observation" not in miss,
            [str(godot_artifact)],
        ),
        _result(
            "failure-recovers-local-ownership",
            "Failure terminal paths restore local ownership and keep attestation fields",
            isinstance(no_path, dict)
            and no_path.get("terminal_status") == "failed_navigation"
            and no_path.get("local_ownership_restored") is True
            and bool(no_path.get("controller_grant_id"))
            and bool(no_path.get("outcome_nonce")),
            [str(godot_artifact)],
        ),
    ]
    overall = all(entry["status"] == "proved" for entry in results)
    report = {
        "overall_embodied_action_controller_passed": overall,
        "results": results,
        "artifacts": {
            "pytest_log": str(pytest_log),
            "godot_log": str(godot_log),
            "godot_runtime": str(godot_artifact),
        },
    }
    json_path = log_dir / "embodied-action-controller-report.json"
    md_path = log_dir / "embodied-action-controller-report.md"
    write_json(json_path, report)
    write_markdown(md_path, "Embodied Action Controller Verification Report", report, "overall_embodied_action_controller_passed")
    print(f"embodied_action_controller_report_json={json_path}")
    print(f"embodied_action_controller_report_md={md_path}")
    print(f"overall_embodied_action_controller_passed={overall}")
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())
