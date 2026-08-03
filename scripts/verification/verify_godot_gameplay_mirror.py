from __future__ import annotations

import argparse
import json

from common import read_text, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


TEST_FILES = [
    "backend/tests/test_godot_gameplay_mirror_projection.py",
    "backend/tests/test_godot_gameplay_mirror_delivery.py",
    "backend/tests/test_gameplay_mirror_session_access_service.py",
    "backend/tests/test_websocket_session_auth_service.py",
    "backend/tests/test_websocket_connection_context.py",
    "backend/tests/test_phase3_mirror_source.py",
    "backend/tests/test_gameplay_runtime_state_mirror_static.py",
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--godot-exe", default=None)
    parser.add_argument("--python-exe", default=None)
    args = parser.parse_args()
    root = repo_root()
    log_dir = verification_dir(root)
    pytest_log = log_dir / "godot-gameplay-mirror-pytest.log"
    pytest_result = run_command([resolve_python_exe(args.python_exe), "-m", "pytest", "-q", *TEST_FILES], root, pytest_log)
    godot_log = log_dir / "gameplay-mirror-bridge-godot.log"
    godot_artifact = log_dir / "gameplay-mirror-bridge-godot-runtime.json"
    godot_ok = False
    if args.godot_exe:
        godot_result = run_command(
            [
                args.godot_exe,
                "--headless",
                "--path",
                str(root),
                "--scene",
                "res://scenes/phase0/GameplayMirrorBridgeProbe.tscn",
                "--quit-after",
                "300",
                "--render-thread",
                "safe",
            ],
            root,
            godot_log,
        )
        godot_ok = godot_result.returncode == 0 and "gameplay_mirror_bridge_probe:verified=true" in read_text(godot_log) and godot_artifact.exists()
    try:
        godot_payload = json.loads(godot_artifact.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        godot_payload = {}
    results = [
        {
            "id": "backend-and-static-contracts",
            "title": "Filtered envelope, configured Phase 3 source, session scope, WebSocket commands, and fanout plumbing pass",
            "status": "proved" if pytest_result.returncode == 0 else "missing",
            "evidence": [str(pytest_log)] if pytest_result.returncode == 0 else [],
            "notes": f"exit_code={pytest_result.returncode}",
        },
        {
            "id": "godot-local-bridge",
            "title": "Godot local bridge routes only session-granted actors and clears state on disconnect",
            "status": "proved" if godot_ok and godot_payload.get("status") == "godot-runtime-gameplay-mirror-bridge-verified" else "missing",
            "evidence": [str(godot_log), str(godot_artifact)] if godot_ok else [],
            "notes": "local presentation probe; not live WebSocket proof",
        },
    ]
    overall = all(result["status"] == "proved" for result in results)
    report = {
        "overall_godot_gameplay_mirror_passed": overall,
        "scope": "backend-safe Godot envelope, backend-configured Phase 3 committed-event source, backend-issued session/read scope, live /ws trusted-local bind/subscribe snapshot proof, bounded after-commit connection-fanout plumbing, plus a local Godot bridge probe; it excludes a production identity adapter, a live WebSocket-to-Godot deployment proof, reconnect/resync, prediction, persistence, and migration closure",
        "results": results,
        "artifacts": {"pytest_log": str(pytest_log), "godot_log": str(godot_log), "godot_runtime": str(godot_artifact)},
    }
    json_path = log_dir / "godot-gameplay-mirror-report.json"
    md_path = log_dir / "godot-gameplay-mirror-report.md"
    write_json(json_path, report)
    write_markdown(md_path, "Godot Gameplay Mirror Verification Report", report, "overall_godot_gameplay_mirror_passed")
    print(f"overall_godot_gameplay_mirror_passed={overall}")
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())
