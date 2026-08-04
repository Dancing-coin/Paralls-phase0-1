from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen

import uvicorn

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
scripts_root = Path(__file__).resolve().parents[1]
if str(scripts_root) not in sys.path:
    sys.path.insert(0, str(scripts_root))

import app.main as backend_main
from launch_trusted_local_obj_archive_door import (
    build_godot_child_environment,
    request_enrollment,
)
from app.services.trusted_local_embodied_controller_launcher import (
    TrustedLocalEmbodiedControllerEnrollmentIssuer,
    TrustedLocalEmbodiedControllerLaunchProfile,
)
from common import (
    repo_root,
    resolve_godot_exe,
    resolve_python_exe,
    run_command,
    verification_dir,
    write_json,
    write_markdown,
)


PROFILE_NAME = "obj-archive-door-physical-embodiment"
PROFILE_ORDER = 85
MAIN_DEMO_SCENE = "res://scenes/phase0/MainDemo.tscn"
PROBE_SCENE = "res://scenes/phase0/ObjArchiveDoorPhysicalEmbodimentProbe.tscn"
LAUNCH_SCRIPT = "scripts/launch_trusted_local_obj_archive_door.py"
REPORT_FILENAME = "obj-archive-door-physical-embodiment-report.json"
RUNTIME_FILENAME = "obj-archive-door-physical-embodiment-runtime.json"
BACKEND_TRACE_FILENAME = "obj-archive-door-physical-embodiment-backend-settlement-trace.json"
REPLAY_TRACE_FILENAME = "obj-archive-door-physical-embodiment-replay-trace.json"
PROHIBITED_PROBE_MARKERS = (
    "DefaultSceneLetterAffordanceProbe",
    "EmbodiedKickChairVerticalSliceProbe",
    "runtime_state_raster_fallback",
)
SCENARIOS = (
    "success",
    "distance_failure",
    "revision_failure",
    "stance_failure",
)
SCREENSHOT_FILENAMES = {
    "success": "obj-archive-door-physical-embodiment-success.png",
    "distance_failure": "obj-archive-door-physical-embodiment-distance-failure.png",
    "revision_failure": "obj-archive-door-physical-embodiment-revision-failure.png",
    "stance_failure": "obj-archive-door-physical-embodiment-stance-failure.png",
}
FULL_PROFILE_SCOPE = (
    "real MainDemo wrapper probe plus live localhost backend proving obj_archive_door success, "
    "distance reject, revision stale reject, and stance conflict with correlated runtime, backend, replay, and screenshot evidence"
)
TEST_FILES = [
    "backend/tests/test_obj_archive_door_embodied_authority.py",
    "backend/tests/test_obj_archive_door_embodied_websocket.py",
    "backend/tests/test_obj_archive_door_embodied_godot_static.py",
    "backend/tests/test_obj_archive_door_embodied_local_static.py",
    "backend/tests/test_trusted_local_embodied_controller_launcher.py",
]
GODOT_TIMEOUT_SECONDS = 120.0
SERVER_HOST = "127.0.0.1"
SERVER_PORT = 8010
SERVER_HTTP_URL = f"http://{SERVER_HOST}:{SERVER_PORT}"
SERVER_WS_URL = f"ws://{SERVER_HOST}:{SERVER_PORT}/ws"
LAUNCH_PROFILE_REF = "obj-archive-door-demo"
LAUNCHER_SECRET = "obj-archive-door-launcher-secret"


def _result(check_id: str, title: str, proved: bool, evidence: list[str], notes: str = "") -> dict[str, object]:
    return {
        "id": check_id,
        "title": title,
        "status": "proved" if proved else "missing",
        "evidence": evidence if proved else [],
        "notes": notes,
    }


def profile_scope(selected_scenarios: tuple[str, ...]) -> str:
    """Describe whether evidence covers the complete acceptance matrix."""

    if selected_scenarios == SCENARIOS:
        return FULL_PROFILE_SCOPE
    return (
        f"diagnostic coverage for {', '.join(selected_scenarios)} only; it does not prove "
        "the full obj_archive_door physical embodiment profile"
    )


def _normalize_name(path_or_name: str) -> str:
    return Path(path_or_name).name


def scenario_result_ok(
    scenario: str,
    payload: dict[str, Any],
    *,
    existing_artifacts: set[str],
) -> tuple[bool, list[str]]:
    notes: list[str] = []
    if payload.get("scene") != MAIN_DEMO_SCENE:
        notes.append("wrong_scene")
    if payload.get("launch_scene") != PROBE_SCENE:
        notes.append("wrong_launch_scene")
    if str(payload.get("status", "")) != "scenario-verified":
        notes.append("scenario_not_verified")
    screenshot_name = _normalize_name(str(payload.get("screenshot", "")))
    expected_screenshot = SCREENSHOT_FILENAMES[scenario]
    if screenshot_name != expected_screenshot:
        notes.append("wrong_screenshot_name")
    if expected_screenshot not in existing_artifacts:
        notes.append("missing_screenshot")
    if str(payload.get("screenshot_source", "")) != "viewport_texture":
        notes.append("synthetic_screenshot_source")
    live_backend = payload.get("live_backend", {})
    if not isinstance(live_backend, dict) or str(live_backend.get("transport", "")) != "websocket":
        notes.append("missing_live_backend_transport")
    replay_join = payload.get("replay_join", {})
    if not isinstance(replay_join, dict) or str(replay_join.get("settlement_id", "")) == "":
        if scenario != "distance_failure":
            notes.append("missing_replay_join")

    settlement = payload.get("received_settlement", {})
    if not isinstance(settlement, dict):
        settlement = {}
    world_result = payload.get("received_world_result", {})
    if not isinstance(world_result, dict):
        world_result = {}
    final_snapshot = payload.get("final_snapshot", {})
    if not isinstance(final_snapshot, dict):
        final_snapshot = {}

    if scenario == "success":
        if str(settlement.get("settlement_status", "")) != "applied":
            notes.append("success_missing_applied_settlement")
        if str(world_result.get("target_object_id", "")) != "obj_archive_door" or str(world_result.get("current_state", "")) != "open":
            notes.append("success_missing_open_world_result")
        if str(final_snapshot.get("current_state", "")) != "open":
            notes.append("success_snapshot_not_open")
    elif scenario == "distance_failure":
        constraint = payload.get("received_constraint", {})
        if not isinstance(constraint, dict) or str(constraint.get("constraint_code", "")) != "out_of_range":
            notes.append("distance_missing_out_of_range_constraint")
        if payload.get("grant_id") is not None or payload.get("settlement_id") is not None:
            notes.append("distance_should_not_have_grant_or_settlement")
        if str(final_snapshot.get("current_state", "")) != "closed":
            notes.append("distance_snapshot_not_closed")
    elif scenario == "revision_failure":
        if str(settlement.get("error_code", "")) not in {"binding_revision_mismatch", "revision_conflict", "door_state_stale"}:
            notes.append("revision_missing_stale_error")
        if str(final_snapshot.get("current_state", "")) != "closed":
            notes.append("revision_snapshot_not_closed")
        if world_result:
            notes.append("revision_should_not_publish_world_result")
    elif scenario == "stance_failure":
        if str(settlement.get("error_code", "")) != "stance_occupied":
            notes.append("stance_missing_constraint")
        if str(final_snapshot.get("current_state", "")) != "closed":
            notes.append("stance_snapshot_not_closed")
    else:
        notes.append("unknown_scenario")
    return len(notes) == 0, notes


class LiveBackendServer:
    def __init__(self, *, host: str, port: int) -> None:
        self._host = host
        self._port = port
        config = uvicorn.Config(
            backend_main.app,
            host=host,
            port=port,
            log_level="warning",
            access_log=False,
        )
        self._server = uvicorn.Server(config)
        self._thread = threading.Thread(target=self._server.run, daemon=True)

    def start(self) -> None:
        backend_main.reset_runtime_state()
        backend_main.embodied_controller_launcher_bootstrap_secret = LAUNCHER_SECRET
        backend_main.embodied_controller_trusted_local_enrollment_issuer = TrustedLocalEmbodiedControllerEnrollmentIssuer(
            auth_service=backend_main.embodied_controller_auth_service,
            launch_profiles=(
                TrustedLocalEmbodiedControllerLaunchProfile(
                    profile_ref=LAUNCH_PROFILE_REF,
                    actor_id="char_c",
                    controller_instance_id="controller:char_c:obj_archive_door:1",
                    credential_ttl_seconds=45,
                ),
            ),
        )
        self._thread.start()
        deadline = time.time() + 15.0
        while time.time() < deadline:
            try:
                with urlopen(f"{SERVER_HTTP_URL}/health", timeout=1.0) as response:
                    payload = json.loads(response.read().decode("utf-8"))
            except (OSError, URLError, json.JSONDecodeError):
                payload = {}
            if payload.get("status") == "ok":
                return
            time.sleep(0.1)
        raise RuntimeError("live_backend_start_timeout")

    def stop(self) -> None:
        self._server.should_exit = True
        self._thread.join(timeout=10.0)


def _remove_if_exists(path: Path) -> None:
    if path.exists():
        path.unlink()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _wait_for_stage(stage_path: Path, expected_stage: str, timeout_seconds: float) -> dict[str, Any]:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        payload = _read_json(stage_path)
        if payload.get("stage") == expected_stage:
            return payload
        time.sleep(0.05)
    return {}


def _authoritative_preflight_snapshot(service: Any) -> dict[str, str]:
    attempts = getattr(service, "_attempts_by_grant", {})
    if not isinstance(attempts, dict):
        return {}
    for attempt in tuple(attempts.values()):
        request = getattr(attempt, "request", None)
        grant = getattr(attempt, "grant", None)
        attempt_id = str(getattr(request, "interaction_attempt_id", ""))
        grant_id = str(getattr(grant, "grant_id", ""))
        if attempt_id and grant_id:
            return {"attempt_id": attempt_id, "grant_id": grant_id}
    return {}


def _wait_for_authoritative_preflight(timeout_seconds: float) -> dict[str, str]:
    deadline = time.time() + timeout_seconds
    service = backend_main.default_scene_archive_door_embodied_service
    while time.time() < deadline:
        snapshot = _authoritative_preflight_snapshot(service)
        if snapshot:
            return snapshot
        time.sleep(0.025)
    return {}


def _run_probe_scenario(
    *,
    scenario: str,
    root: Path,
    log_dir: Path,
    godot_exe: Path,
) -> tuple[dict[str, Any], Path, dict[str, Any]]:
    runtime_path = log_dir / f"obj-archive-door-{scenario}-runtime.json"
    screenshot_path = log_dir / SCREENSHOT_FILENAMES[scenario]
    stage_path = log_dir / f"obj-archive-door-{scenario}-stage.json"
    log_path = log_dir / f"obj-archive-door-{scenario}-godot.log"
    for path in (runtime_path, screenshot_path, stage_path):
        _remove_if_exists(path)

    mutation_info: dict[str, Any] = {}
    environment = os.environ.copy()
    environment.update(
        {
            "EMBODIED_CONTROLLER_LAUNCHER_BOOTSTRAP_SECRET": LAUNCHER_SECRET,
            "PHASE0_DEBUG_LOGGING": "0",
            "PARALLS_OBJ_ARCHIVE_DOOR_SCENARIO": scenario,
            "PARALLS_OBJ_ARCHIVE_DOOR_RUNTIME_PATH": str(runtime_path),
            "PARALLS_OBJ_ARCHIVE_DOOR_SCREENSHOT_PATH": str(screenshot_path),
            "PARALLS_OBJ_ARCHIVE_DOOR_STAGE_PATH": str(stage_path),
        }
    )
    enrollment = request_enrollment(
        backend_http_url=SERVER_HTTP_URL,
        launch_profile_ref=LAUNCH_PROFILE_REF,
        launcher_secret=LAUNCHER_SECRET,
    )
    godot_environment = build_godot_child_environment(
        parent_environment=environment,
        enrollment=enrollment,
    )
    godot_environment["PARALLS_BACKEND_WS_URL"] = SERVER_WS_URL
    command = [
        str(godot_exe),
        "--path",
        str(root),
        "--scene",
        PROBE_SCENE,
        "--rendering-method",
        "gl_compatibility",
        "--quit-after",
        "900",
        "--render-thread",
        "safe",
    ]
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8") as log_handle:
        process = subprocess.Popen(
            command,
            cwd=str(root),
            env=godot_environment,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            text=True,
            )
        try:
            if scenario == "revision_failure":
                preflight = _wait_for_authoritative_preflight(GODOT_TIMEOUT_SECONDS)
                if not preflight:
                    stage_payload = _wait_for_stage(stage_path, "preflight_accepted", 0.5)
                    preflight = {
                        "grant_id": str(stage_payload.get("grant_id", "")),
                        "attempt_id": str(stage_payload.get("attempt_id", "")),
                    }
                if preflight.get("grant_id"):
                    before = backend_main.default_scene_archive_door_embodied_service.binding_revision
                    backend_main.default_scene_archive_door_embodied_service.binding_revision += 1
                    mutation_info = {
                        "kind": "binding_revision_increment",
                        "before": before,
                        "after": backend_main.default_scene_archive_door_embodied_service.binding_revision,
                        "grant_id": preflight["grant_id"],
                        "attempt_id": preflight.get("attempt_id", ""),
                        "source": "authoritative_preflight",
                    }
            deadline = time.time() + GODOT_TIMEOUT_SECONDS
            while time.time() < deadline:
                if runtime_path.exists() and process.poll() is not None:
                    break
                if process.poll() is not None and runtime_path.exists():
                    break
                if process.poll() is not None and not runtime_path.exists():
                    break
                time.sleep(0.1)
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=10.0)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5.0)
    payload = _read_json(runtime_path)
    payload["godot_exit_code"] = int(process.returncode or 0)
    return payload, log_path, mutation_info


def _backend_trace_for_scenario(
    *,
    scenario: str,
    runtime_payload: dict[str, Any],
    mutation_info: dict[str, Any],
) -> dict[str, Any]:
    attempt_id = str(runtime_payload.get("attempt_id") or "")
    ledger_events = backend_main.embodied_evidence_ledger.events_for_attempt(attempt_id) if attempt_id else []
    replay = backend_main.embodied_evidence_ledger.validate_replay(attempt_id) if attempt_id else None
    settlement = runtime_payload.get("received_settlement", {})
    world_result = runtime_payload.get("received_world_result", {})
    return {
        "scenario": scenario,
        "request_id": runtime_payload.get("request_id"),
        "correlation_id": runtime_payload.get("correlation_id"),
        "attempt_id": runtime_payload.get("attempt_id"),
        "grant_id": runtime_payload.get("grant_id"),
        "settlement_id": runtime_payload.get("settlement_id"),
        "pinned_revisions": runtime_payload.get("pinned_revisions", {}),
        "live_revisions": {
            "binding_revision": backend_main.default_scene_archive_door_embodied_service.binding_revision,
            "scene_revision": backend_main.default_scene_archive_door_embodied_service.scene_revision,
            "policy_revision": backend_main.default_scene_archive_door_embodied_service.policy_revision,
        },
        "injected_mutation": mutation_info,
        "esm_state": backend_main.esm_service.interaction_state_for(
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            target_object_id="obj_archive_door",
        ),
        "commit_count": backend_main.default_scene_archive_door_embodied_service.commit_count,
        "mutation_count": 1 if isinstance(world_result, dict) and world_result else 0,
        "settlement_payload": settlement,
        "world_result": world_result,
        "server_ledger_sequences": [event.server_ledger_sequence for event in ledger_events],
        "ledger_events": [event.model_dump(mode="json") for event in ledger_events],
        "replay_validation": replay.model_dump(mode="json") if replay is not None else {
            "accepted": scenario == "distance_failure",
            "error_code": "" if scenario == "distance_failure" else "missing_attempt",
            "event_count": len(ledger_events),
            "server_ledger_sequences": [],
        },
    }


def _replay_trace_for_scenario(
    *,
    scenario: str,
    runtime_payload: dict[str, Any],
    backend_trace: dict[str, Any],
) -> dict[str, Any]:
    artifact_name = _normalize_name(str(runtime_payload.get("screenshot", "")))
    settlement = runtime_payload.get("received_settlement", {})
    if not isinstance(settlement, dict):
        settlement = {}
    return {
        "scenario": scenario,
        "request_id": runtime_payload.get("request_id"),
        "correlation_id": runtime_payload.get("correlation_id"),
        "attempt_id": runtime_payload.get("attempt_id"),
        "grant_id": runtime_payload.get("grant_id"),
        "settlement_id": runtime_payload.get("settlement_id"),
        "server_ledger_sequences": backend_trace.get("server_ledger_sequences", []),
        "replay_validation": backend_trace.get("replay_validation", {}),
        "world_result_id": runtime_payload.get("received_world_result", {}).get("result_id")
        if isinstance(runtime_payload.get("received_world_result"), dict)
        else None,
        "presentation_ack_route": runtime_payload.get("presentation_ack", {}).get("route")
        if isinstance(runtime_payload.get("presentation_ack"), dict)
        else None,
        "settlement_error_code": settlement.get("error_code"),
        "artifact_names": [artifact_name] if artifact_name else [],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--godot-exe", default=None)
    parser.add_argument("--python-exe", default=None)
    parser.add_argument("--scenario", choices=SCENARIOS)
    args = parser.parse_args()

    root = repo_root()
    log_dir = verification_dir(root)
    python_exe = resolve_python_exe(args.python_exe)
    godot_exe = resolve_godot_exe(args.godot_exe)

    pytest_log = log_dir / "obj-archive-door-physical-embodiment-pytest.log"
    pytest_result = run_command(
        [python_exe, "-m", "pytest", "-q", *TEST_FILES, "scripts/verification/tests/test_verify_obj_archive_door_physical_embodiment.py"],
        root,
        pytest_log,
    )

    scenario_payloads: dict[str, dict[str, Any]] = {}
    backend_traces: dict[str, dict[str, Any]] = {}
    replay_traces: dict[str, dict[str, Any]] = {}
    scenario_logs: dict[str, str] = {}
    scenario_results: list[dict[str, object]] = []
    selected_scenarios = (args.scenario,) if args.scenario else SCENARIOS

    for scenario in selected_scenarios:
        server = LiveBackendServer(host=SERVER_HOST, port=SERVER_PORT)
        try:
            server.start()
            payload, log_path, mutation_info = _run_probe_scenario(
                scenario=scenario,
                root=root,
                log_dir=log_dir,
                godot_exe=godot_exe,
            )
            backend_trace = _backend_trace_for_scenario(
                scenario=scenario,
                runtime_payload=payload,
                mutation_info=mutation_info,
            )
            replay_trace = _replay_trace_for_scenario(
                scenario=scenario,
                runtime_payload=payload,
                backend_trace=backend_trace,
            )
        finally:
            server.stop()

        scenario_payloads[scenario] = payload
        backend_traces[scenario] = backend_trace
        replay_traces[scenario] = replay_trace
        scenario_logs[scenario] = str(log_path)
        screenshot_name = _normalize_name(str(payload.get("screenshot", "")))
        passed, notes = scenario_result_ok(
            scenario,
            payload,
            existing_artifacts={name for name in [screenshot_name] if (log_dir / name).exists()},
        )
        scenario_results.append(
            _result(
                f"scenario-{scenario}",
                f"{scenario} runs through the real MainDemo trusted-local embodied door route with correlated evidence",
                passed,
                [str(log_path), str(log_dir / SCREENSHOT_FILENAMES[scenario])],
                ", ".join(notes) if notes else f"godot_exit_code={payload.get('godot_exit_code', 1)}",
            )
        )

    runtime_artifact = {
        "scene": MAIN_DEMO_SCENE,
        "launch_scene": PROBE_SCENE,
        "scenarios": scenario_payloads,
    }
    backend_trace_artifact = {
        "scene": MAIN_DEMO_SCENE,
        "scenarios": backend_traces,
    }
    replay_trace_artifact = {
        "scene": MAIN_DEMO_SCENE,
        "scenarios": replay_traces,
    }
    write_json(log_dir / RUNTIME_FILENAME, runtime_artifact)
    write_json(log_dir / BACKEND_TRACE_FILENAME, backend_trace_artifact)
    write_json(log_dir / REPLAY_TRACE_FILENAME, replay_trace_artifact)

    results = [
        _result(
            "focused-door-pytests",
            "Existing obj_archive_door authority, websocket, static Godot, local static, launcher, and focused verifier tests pass",
            pytest_result.returncode == 0,
            [str(pytest_log)],
            f"exit_code={pytest_result.returncode}",
        ),
        *scenario_results,
    ]
    selected_coverage_passed = all(result["status"] == "proved" for result in results)
    overall = selected_scenarios == SCENARIOS and selected_coverage_passed
    report = {
        "overall_obj_archive_door_physical_embodiment_passed": overall,
        "selected_scenarios_passed": selected_coverage_passed,
        "selected_scenarios": list(selected_scenarios),
        "scope": profile_scope(selected_scenarios),
        "results": results,
        "artifacts": {
            "pytest_log": str(pytest_log),
            "runtime": str(log_dir / RUNTIME_FILENAME),
            "backend_trace": str(log_dir / BACKEND_TRACE_FILENAME),
            "replay_trace": str(log_dir / REPLAY_TRACE_FILENAME),
            "screenshots": {
                scenario: str(log_dir / filename)
                for scenario, filename in SCREENSHOT_FILENAMES.items()
            },
            "scenario_logs": scenario_logs,
        },
    }
    json_path = log_dir / REPORT_FILENAME
    md_path = log_dir / "obj-archive-door-physical-embodiment-report.md"
    write_json(json_path, report)
    write_markdown(
        md_path,
        "Obj Archive Door Physical Embodiment Verification Report",
        report,
        "overall_obj_archive_door_physical_embodiment_passed",
    )
    print(f"overall_obj_archive_door_physical_embodiment_passed={overall}")
    print(f"obj_archive_door_physical_embodiment_report_json={json_path}")
    print(f"obj_archive_door_physical_embodiment_report_md={md_path}")
    return 0 if selected_coverage_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
