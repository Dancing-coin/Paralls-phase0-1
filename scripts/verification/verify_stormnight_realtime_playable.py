from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from common import ensure_backend, repo_root, resolve_godot_exe, resolve_python_exe, run_command, stop_backend, verification_dir, write_json


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--godot-exe", default=None)
    parser.add_argument("--python-exe", default=None)
    args = parser.parse_args()
    root = repo_root()
    python_exe = resolve_python_exe(args.python_exe)
    godot_exe = resolve_godot_exe(args.godot_exe)
    focused_log = verification_dir(root) / "stormnight-realtime-playable-pytest.log"
    focused = run_command(
        [python_exe, "-m", "pytest", "-q", "backend/tests/test_stormnight_realtime_session.py", "backend/tests/test_stormnight_realtime_websocket.py", "backend/tests/test_stormnight_realtime_godot_contract.py"],
        root,
        focused_log,
    )
    process = None
    backend_ok = False
    try:
        _health, process = ensure_backend(root, python_exe, prefer_fresh_backend=True)
        backend_ok = True
        godot_log = verification_dir(root) / "stormnight-realtime-playable-godot.log"
        godot = run_command(
            [str(godot_exe), "--headless", "--path", str(root), "--scene", "res://scenes/phase0/StormnightRealtimePlayable.tscn", "--quit-after", "120", "--render-thread", "safe"],
            root,
            godot_log,
        )
    finally:
        stop_backend(process)
    report = {
        "overall_passed": focused.returncode == 0 and backend_ok and godot.returncode == 0,
        "focused_pytest_passed": focused.returncode == 0,
        "backend_started": backend_ok,
        "godot_scene_loaded": godot.returncode == 0,
        "focused_log": str(focused_log),
        "godot_log": str(godot_log),
    }
    write_json(verification_dir(root) / "stormnight-realtime-playable-report.json", report)
    print(report)
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
