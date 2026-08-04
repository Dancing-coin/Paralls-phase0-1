"""Prove server-selected Adventure Basic authority reaches a live Godot mirror."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
from urllib.request import Request, urlopen

from common import (
    ensure_backend,
    repo_root,
    resolve_godot_exe,
    resolve_python_exe,
    stop_backend,
    verification_dir,
    write_json,
    write_markdown,
)


SCENARIOS: dict[str, dict[str, str]] = {
    "scenario-1": {"initial": "sword_offer_available", "final": "sword_equipped"},
    "scenario-2": {"initial": "sword_action_unavailable", "final": "resource_action_resolved"},
    "scenario-3": {"initial": "storage_ring_available", "final": "storage_ring_loaded"},
    "scenario-4": {"initial": "land_right_available", "final": "land_right_transferred"},
    "scenario-5": {"initial": "gift_debt_contract_available", "final": "gift_debt_contract_settled"},
}
ACTOR_REF = "character:char_player"
LAUNCH_PROFILE_REF = "adventure-basic-live-probe"
SECRET = "live-adventure-basic-mirror-verifier-secret"


def _post_canonical_commit(secret: str) -> dict[str, object]:
    request = Request(
        "http://127.0.0.1:8000/internal/trusted-local-adventure-basic-live-probe-commit",
        data=b"{}",
        headers={"Content-Type": "application/json", "X-Gameplay-Mirror-Launcher-Secret": secret},
        method="POST",
    )
    with urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def _runtime_environment(*, scenario_id: str) -> dict[str, str]:
    return {
        "ADVENTURE_BASIC_MIRROR_LIVE_SCENARIO": scenario_id,
        "GAMEPLAY_MIRROR_LAUNCHER_BOOTSTRAP_SECRET": SECRET,
        "GAMEPLAY_MIRROR_TRUSTED_LOCAL_LAUNCH_PROFILES_JSON": json.dumps(
            [
                {
                    "profile_ref": LAUNCH_PROFILE_REF,
                    "principal_ref": "principal:adventure-basic-live-probe",
                    "allowed_actor_refs": [ACTOR_REF],
                    "credential_ttl_seconds": 30,
                }
            ]
        ),
    }


def _read_json(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _wait_for(path: Path, process: subprocess.Popen[str], timeout_seconds: float) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline and not path.exists() and process.poll() is None:
        time.sleep(0.1)
    return path.exists()


def _run_scenario(*, root: Path, log_dir: Path, scenario_id: str, godot_exe: Path, python_exe: str) -> dict[str, object]:
    expected = SCENARIOS[scenario_id]
    ready_path = log_dir / "live-adventure-basic-mirror-ready.json"
    runtime_path = log_dir / "live-adventure-basic-mirror-runtime.json"
    scenario_ready_path = log_dir / f"live-adventure-basic-mirror-{scenario_id}-ready.json"
    scenario_runtime_path = log_dir / f"live-adventure-basic-mirror-{scenario_id}-runtime.json"
    backend_trace_path = log_dir / f"live-adventure-basic-mirror-{scenario_id}-backend.json"
    launcher_log_path = log_dir / f"live-adventure-basic-mirror-{scenario_id}-launcher.log"
    for path in (ready_path, runtime_path, scenario_ready_path, scenario_runtime_path, backend_trace_path, launcher_log_path):
        if path.exists():
            path.unlink()

    environment = _runtime_environment(scenario_id=scenario_id)
    backend: subprocess.Popen[str] | None = None
    godot_process: subprocess.Popen[str] | None = None
    commit_response: dict[str, object] = {}
    launch_exit_code: int | None = None
    try:
        _, backend = ensure_backend(root, python_exe, prefer_fresh_backend=True, env=environment)
        child_environment = os.environ.copy()
        child_environment.update(environment)
        child_environment.update(
            {
                "PARALLS_ADVENTURE_BASIC_MIRROR_SCENARIO": scenario_id,
                "PARALLS_ADVENTURE_BASIC_MIRROR_INITIAL_STATE": expected["initial"],
                "PARALLS_ADVENTURE_BASIC_MIRROR_FINAL_STATE": expected["final"],
            }
        )
        with launcher_log_path.open("w", encoding="utf-8") as launcher_log:
            godot_process = subprocess.Popen(
                [
                    python_exe,
                    "scripts/launch_trusted_local_gameplay_mirror.py",
                    "--launch-profile-ref",
                    LAUNCH_PROFILE_REF,
                    "--godot-exe",
                    str(godot_exe),
                    "--scene",
                    "res://scenes/phase0/LiveAdventureBasicMirrorDeliveryProbe.tscn",
                    "--headless",
                    "--quit-after",
                    "900",
                    "--render-thread",
                    "safe",
                ],
                cwd=root,
                env=child_environment,
                stdout=launcher_log,
                stderr=subprocess.STDOUT,
                text=True,
            )
            ready = _wait_for(ready_path, godot_process, 20)
            if ready:
                commit_response = _post_canonical_commit(SECRET)
            _wait_for(runtime_path, godot_process, 25)
            try:
                launch_exit_code = godot_process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                launch_exit_code = None
    except Exception as exc:  # The aggregate report must remain inspectable on an unavailable runtime.
        commit_response = {"error": type(exc).__name__, "detail": str(exc)}
    finally:
        if godot_process is not None and godot_process.poll() is None:
            godot_process.terminate()
            try:
                godot_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                godot_process.kill()
        stop_backend(backend)

    runtime = _read_json(runtime_path)
    if ready_path.exists():
        shutil.copyfile(ready_path, scenario_ready_path)
    if runtime_path.exists():
        shutil.copyfile(runtime_path, scenario_runtime_path)
    backend_trace = {
        "scenario_id": scenario_id,
        "expected_actor_ref": ACTOR_REF,
        "commit_response": commit_response,
        "launcher_exit_code": launch_exit_code,
    }
    write_json(backend_trace_path, backend_trace)
    committed_actor_ref = str(commit_response.get("actor_ref", ""))
    transaction_ids = commit_response.get("transaction_ids", [])
    proved = (
        launch_exit_code == 0
        and runtime.get("status") == "live_adventure_basic_mirror_verified"
        and runtime.get("scenario_id") == scenario_id
        and runtime.get("actor_ref") == ACTOR_REF
        and runtime.get("expected_initial_state") == expected["initial"]
        and runtime.get("expected_final_state") == expected["final"]
        and runtime.get("presentation_state") == expected["final"]
        and int(runtime.get("rejected_projection_count", -1)) == 0
        and runtime.get("resync_required") is False
        and committed_actor_ref == ACTOR_REF
        and isinstance(transaction_ids, list)
        and len(transaction_ids) > 0
    )
    return {
        "id": scenario_id,
        "title": f"{scenario_id} canonical authority reaches the live Godot mirror after commit",
        "status": "proved" if proved else "missing",
        "evidence": [str(path) for path in (launcher_log_path, backend_trace_path, scenario_runtime_path, scenario_ready_path) if path.exists()] if proved else [],
        "notes": "" if proved else json.dumps({"runtime": runtime, "backend": backend_trace}, ensure_ascii=True),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--godot-exe", default=None)
    parser.add_argument("--python-exe", default=None)
    args = parser.parse_args()

    root = repo_root()
    log_dir = verification_dir(root)
    godot_exe = resolve_godot_exe(args.godot_exe)
    python_exe = resolve_python_exe(args.python_exe)
    results = [
        _run_scenario(
            root=root,
            log_dir=log_dir,
            scenario_id=scenario_id,
            godot_exe=godot_exe,
            python_exe=python_exe,
        )
        for scenario_id in SCENARIOS
    ]
    overall = all(entry["status"] == "proved" for entry in results)
    report = {
        "overall_live_adventure_basic_mirror_passed": overall,
        "scenarios": results,
        "scope": "Five server-selected canonical Adventure Basic commands delivered through a fresh trusted-local Godot mirror. This verifier does not prove client authority, prediction, or generic transport durability.",
    }
    json_path = log_dir / "live-adventure-basic-mirror-report.json"
    markdown_path = log_dir / "live-adventure-basic-mirror-report.md"
    write_json(json_path, report)
    write_markdown(markdown_path, "Live Adventure Basic Mirror Report", report, "overall_live_adventure_basic_mirror_passed")
    print(f"live_adventure_basic_mirror_report_json={json_path}")
    print(f"live_adventure_basic_mirror_report_md={markdown_path}")
    print(f"overall_live_adventure_basic_mirror_passed={overall}")
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())
