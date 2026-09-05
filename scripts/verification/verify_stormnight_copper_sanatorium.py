from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from common import repo_root, resolve_python_exe, run_command, verification_dir, write_json


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--godot-exe", default=None)
    parser.add_argument("--python-exe", default=None)
    args = parser.parse_args()
    root = repo_root()
    log = verification_dir(root) / "stormnight-copper-sanatorium-pytest.log"
    result = run_command([resolve_python_exe(args.python_exe), "-m", "pytest", "-q", "backend/tests/test_stormnight_godot_contract_static.py", "backend/tests/test_scripted_mystery_content.py", "backend/tests/test_scripted_mystery_case_package.py", "backend/tests/test_scripted_mystery_case_runtime.py", "backend/tests/test_scripted_mystery_evidence.py", "backend/tests/test_scripted_mystery_agent_turns.py", "backend/tests/test_stormnight_action_loop.py", "backend/tests/test_stormnight_owner_handoff.py", "backend/tests/test_stormnight_scenario.py", "backend/tests/test_stormnight_cross_owner_replay.py", "backend/tests/test_stormnight_copper_sanatorium_full_replay.py", "backend/tests/test_stormnight_case_template_genericity.py"], root, log)
    godot_log = verification_dir(root) / "stormnight-copper-sanatorium-godot.log"
    godot_artifact = verification_dir(root) / "stormnight-copper-sanatorium-godot-runtime.json"
    godot_ok = False
    if args.godot_exe:
        godot_result = run_command([args.godot_exe, "--headless", "--path", str(root), "--scene", "res://scenes/phase0/StormnightCopperSanatorium.tscn", "--quit-after", "300", "--render-thread", "safe"], root, godot_log)
        godot_ok = godot_result.returncode == 0 and "stormnight_copper_sanatorium_probe:verified=true" in godot_log.read_text(encoding="utf-8", errors="replace") and godot_artifact.exists()
    report = {"overall_passed": result.returncode == 0 and godot_ok, "focused_pytest_passed": result.returncode == 0, "godot_runtime_verified": godot_ok, "pytest_log": str(log), "godot_log": str(godot_log), "godot_artifact": str(godot_artifact)}
    artifact = verification_dir(root) / "stormnight-copper-sanatorium-report.json"
    write_json(artifact, report)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
