from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import verify_obj_archive_door_physical_embodiment as verifier


ROOT = Path(__file__).resolve().parents[3]


def test_verifier_requires_real_main_demo_live_backend_and_four_scenarios() -> None:
    assert verifier.MAIN_DEMO_SCENE == "res://scenes/phase0/MainDemo.tscn"
    assert verifier.PROBE_SCENE == "res://scenes/phase0/ObjArchiveDoorPhysicalEmbodimentProbe.tscn"
    assert verifier.LAUNCH_SCRIPT == "scripts/launch_trusted_local_obj_archive_door.py"
    assert verifier.PROFILE_NAME == "obj-archive-door-physical-embodiment"
    assert verifier.REPORT_FILENAME == "obj-archive-door-physical-embodiment-report.json"
    assert verifier.RUNTIME_FILENAME == "obj-archive-door-physical-embodiment-runtime.json"
    assert verifier.BACKEND_TRACE_FILENAME == "obj-archive-door-physical-embodiment-backend-settlement-trace.json"
    assert verifier.REPLAY_TRACE_FILENAME == "obj-archive-door-physical-embodiment-replay-trace.json"
    assert verifier.TEST_FILES == [
        "backend/tests/test_obj_archive_door_embodied_authority.py",
        "backend/tests/test_obj_archive_door_embodied_websocket.py",
        "backend/tests/test_obj_archive_door_embodied_godot_static.py",
        "backend/tests/test_obj_archive_door_embodied_local_static.py",
        "backend/tests/test_trusted_local_embodied_controller_launcher.py",
    ]
    assert tuple(verifier.SCENARIOS) == (
        "success",
        "distance_failure",
        "revision_failure",
        "stance_failure",
    )
    assert verifier.SCREENSHOT_FILENAMES == {
        "success": "obj-archive-door-physical-embodiment-success.png",
        "distance_failure": "obj-archive-door-physical-embodiment-distance-failure.png",
        "revision_failure": "obj-archive-door-physical-embodiment-revision-failure.png",
        "stance_failure": "obj-archive-door-physical-embodiment-stance-failure.png",
    }


def test_probe_scene_wraps_main_demo_and_rejects_synthetic_probe_shortcuts() -> None:
    scene_text = (
        ROOT / "scenes" / "phase0" / "ObjArchiveDoorPhysicalEmbodimentProbe.tscn"
    ).read_text(encoding="utf-8")
    script_text = (
        ROOT / "scripts" / "verification" / "ObjArchiveDoorPhysicalEmbodimentProbe.gd"
    ).read_text(encoding="utf-8")

    assert 'path="res://scenes/phase0/MainDemo.tscn"' in scene_text
    assert '[node name="MainDemo" parent="." instance=ExtResource("2_main_demo")]' in scene_text
    assert 'PHASE0_AUTOTEST' not in script_text
    assert 'DefaultSceneLetterAffordanceProbe' not in script_text
    assert 'EmbodiedKickChairVerticalSliceProbe' not in script_text
    assert "runtime_state_raster_fallback" not in script_text
    assert "get_viewport().get_texture().get_image()" in script_text


def test_probe_uses_a_launch_time_player_shell_fixture_with_a_nonzero_real_approach() -> None:
    scene_text = (
        ROOT / "scenes" / "phase0" / "ObjArchiveDoorPhysicalEmbodimentProbe.tscn"
    ).read_text(encoding="utf-8")

    assert '[editable path="MainDemo/PlayerCharacter"]' in scene_text
    assert '[node name="PlayerCharacter" parent="MainDemo"' in scene_text
    assert "transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0.5, -1.9625)" in scene_text


def test_probe_treats_the_server_controller_bound_state_as_a_completed_bind() -> None:
    script_text = (
        ROOT / "scripts" / "verification" / "ObjArchiveDoorPhysicalEmbodimentProbe.gd"
    ).read_text(encoding="utf-8")

    assert 'str(_bound_payload.get("state", "")) == "bound"' in script_text


def test_probe_completes_async_finish_and_does_not_teleport_the_physical_path() -> None:
    script_text = (
        ROOT / "scripts" / "verification" / "ObjArchiveDoorPhysicalEmbodimentProbe.gd"
    ).read_text(encoding="utf-8")
    run_probe = script_text.split("func _run_probe() -> void:", maxsplit=1)[1].split(
        "func _connect_bus() -> void:", maxsplit=1
    )[0]

    assert "await _finish(false)" in run_probe
    assert "await _finish(ok)" in run_probe
    assert '"controller_bound": str(_bound_payload.get("state", "")) == "bound"' in script_text
    assert "player.global_position =" not in script_text
    assert "await RenderingServer.frame_post_draw" not in script_text
    assert "_phase_names.append(parts[parts.size() - 1])" in script_text


def test_probe_starts_the_async_lifecycle_from_ready() -> None:
    script_text = (
        ROOT / "scripts" / "verification" / "ObjArchiveDoorPhysicalEmbodimentProbe.gd"
    ).read_text(encoding="utf-8")

    ready = script_text.split("func _ready() -> void:", maxsplit=1)[1].split(
        "func _process", maxsplit=1
    )[0]

    assert "await get_tree().process_frame" in ready
    assert "await _run_probe()" in ready
    assert "call_deferred(\"_start_probe\")" not in script_text
    assert "func _start_probe()" not in script_text
    assert "_probe_task" not in script_text


def test_profile_manifest_requires_real_main_demo_runtime_report() -> None:
    profile = json.loads(
        (ROOT / ".harness" / "profiles" / "obj-archive-door-physical-embodiment.json").read_text(
            encoding="utf-8"
        )
    )

    assert profile == {
        "schema_version": 1,
        "name": "obj-archive-door-physical-embodiment",
        "order": verifier.PROFILE_ORDER,
        "script": "scripts/verification/verify_obj_archive_door_physical_embodiment.py",
        "requires_godot": True,
        "max_attempts": 1,
        "result_artifact": ".harness/verification/obj-archive-door-physical-embodiment-report.json",
        "description": "Real MainDemo wrapper probe that launches a live backend plus trusted-local embodied controller enrollment and proves obj_archive_door open, distance reject, revision stale reject, and stance conflict with correlated runtime, backend, replay, and screenshot evidence",
    }


def test_live_probe_disables_unrelated_debug_event_flooding() -> None:
    verifier_text = (
        ROOT
        / "scripts"
        / "verification"
        / "verify_obj_archive_door_physical_embodiment.py"
    ).read_text(encoding="utf-8")

    assert '"PHASE0_DEBUG_LOGGING": "0"' in verifier_text


def test_revision_injector_reads_an_authoritative_live_preflight_before_mutating() -> None:
    service = SimpleNamespace(
        _attempts_by_grant={
            "grant:door:1": SimpleNamespace(
                request=SimpleNamespace(interaction_attempt_id="attempt:door:1"),
                grant=SimpleNamespace(grant_id="grant:door:1"),
            )
        }
    )

    assert verifier._authoritative_preflight_snapshot(service) == {
        "attempt_id": "attempt:door:1",
        "grant_id": "grant:door:1",
    }


def test_revision_injector_waits_for_the_godot_runtime_window_not_a_short_startup_guess() -> None:
    verifier_text = (
        ROOT
        / "scripts"
        / "verification"
        / "verify_obj_archive_door_physical_embodiment.py"
    ).read_text(encoding="utf-8")
    revision_branch = verifier_text.rsplit('if scenario == "revision_failure":', maxsplit=1)[1].split(
        "deadline = time.time() + GODOT_TIMEOUT_SECONDS", maxsplit=1
    )[0]

    assert "_wait_for_authoritative_preflight(GODOT_TIMEOUT_SECONDS)" in revision_branch


def test_live_probe_uses_a_renderer_capable_of_capturing_the_required_png_evidence() -> None:
    verifier_text = (
        ROOT
        / "scripts"
        / "verification"
        / "verify_obj_archive_door_physical_embodiment.py"
    ).read_text(encoding="utf-8")

    assert '"--headless",' not in verifier_text
    assert '"--rendering-method",\n        "gl_compatibility",' in verifier_text


def test_live_probe_directly_supervises_the_godot_child_after_launcher_handoff() -> None:
    verifier_text = (
        ROOT
        / "scripts"
        / "verification"
        / "verify_obj_archive_door_physical_embodiment.py"
    ).read_text(encoding="utf-8")
    run_probe = verifier_text.split("def _run_probe_scenario(", maxsplit=1)[1].split(
        "def _backend_trace_for_scenario", maxsplit=1
    )[0]

    assert "from launch_trusted_local_obj_archive_door import (" in verifier_text
    assert "request_enrollment(" in run_probe
    assert "build_godot_child_environment(" in run_probe
    assert "LAUNCH_SCRIPT," not in run_probe
    assert "str(godot_exe)," in run_probe


def test_main_demo_probe_timeout_covers_cold_start_and_terminal_evidence_write() -> None:
    assert verifier.GODOT_TIMEOUT_SECONDS >= 120.0


def test_each_door_scenario_keeps_a_result_delivery_buffer_after_the_bounded_grant_window() -> None:
    script_text = (
        ROOT / "scripts" / "verification" / "ObjArchiveDoorPhysicalEmbodimentProbe.gd"
    ).read_text(encoding="utf-8")

    assert "const SCENARIO_TIMEOUT_MS := 45000" in script_text


def test_verifier_supports_a_single_live_scenario_diagnostic_without_changing_default_coverage() -> None:
    verifier_text = (
        ROOT
        / "scripts"
        / "verification"
        / "verify_obj_archive_door_physical_embodiment.py"
    ).read_text(encoding="utf-8")

    assert 'parser.add_argument("--scenario", choices=SCENARIOS)' in verifier_text
    assert "selected_scenarios = (args.scenario,) if args.scenario else SCENARIOS" in verifier_text


def test_single_scenario_diagnostic_cannot_report_the_full_door_profile_as_passed() -> None:
    assert verifier.profile_scope(("distance_failure",)).startswith("diagnostic coverage for distance_failure")
    assert verifier.profile_scope(verifier.SCENARIOS).startswith("real MainDemo wrapper probe")


def test_probe_records_host_runtime_state_with_each_scenario_artifact() -> None:
    script_text = (
        ROOT / "scripts" / "verification" / "ObjArchiveDoorPhysicalEmbodimentProbe.gd"
    ).read_text(encoding="utf-8")

    assert '"host_runtime_state": _host_runtime_state(),' in script_text
    assert "func _host_runtime_state() -> Dictionary:" in script_text


def test_success_probe_finishes_on_a_terminal_local_or_authority_rejection() -> None:
    script_text = (
        ROOT / "scripts" / "verification" / "ObjArchiveDoorPhysicalEmbodimentProbe.gd"
    ).read_text(encoding="utf-8")
    wait_body = script_text.split("func _wait_for_settlement_applied() -> bool:", maxsplit=1)[1].split(
        "func _wait_for_distance_constraint", maxsplit=1
    )[0]

    assert 'str(_settlement_payload.get("settlement_status", "")) == "rejected"' in wait_body
    assert 'not _local_outcome_payload.is_empty()' in wait_body
    assert "success_terminal_local_failure" in wait_body
    assert "success_settlement_rejected" in wait_body


def test_stance_failure_blocker_enters_the_tree_before_its_global_position_is_set() -> None:
    script_text = (
        ROOT / "scripts" / "verification" / "ObjArchiveDoorPhysicalEmbodimentProbe.gd"
    ).read_text(encoding="utf-8")
    spawn_blocker = script_text.split("func _spawn_stance_blocker() -> void:", maxsplit=1)[1].split(
        "func _approach_start_position", maxsplit=1
    )[0]

    assert spawn_blocker.index("main_demo.add_child(blocker)") < spawn_blocker.index(
        "blocker.global_position = stance.global_position"
    )


def test_scenario_gate_rejects_missing_or_synthetic_artifacts() -> None:
    passed, notes = verifier.scenario_result_ok(
        "success",
        {
            "status": "scenario-verified",
            "scene": verifier.MAIN_DEMO_SCENE,
            "launch_scene": verifier.PROBE_SCENE,
            "screenshot": "missing.png",
            "screenshot_source": "runtime_state_raster_fallback",
            "live_backend": {"transport": "websocket"},
            "received_settlement": {"settlement_status": "applied"},
            "received_world_result": {"target_object_id": "obj_archive_door", "current_state": "open"},
            "replay_join": {"settlement_id": "settlement:1"},
        },
        existing_artifacts=set(),
    )

    assert not passed
    assert "missing_screenshot" in notes
    assert "synthetic_screenshot_source" in notes


def test_revision_failure_gate_accepts_binding_revision_mismatch_as_revision_state_stale_proof() -> None:
    passed, notes = verifier.scenario_result_ok(
        "revision_failure",
        {
            "status": "scenario-verified",
            "scene": verifier.MAIN_DEMO_SCENE,
            "launch_scene": verifier.PROBE_SCENE,
            "screenshot": verifier.SCREENSHOT_FILENAMES["revision_failure"],
            "screenshot_source": "viewport_texture",
            "live_backend": {"transport": "websocket"},
            "received_settlement": {
                "settlement_status": "rejected",
                "error_code": "binding_revision_mismatch",
            },
            "received_world_result": {},
            "final_snapshot": {"current_state": "closed", "passage_occlusion_state": "closed"},
            "replay_join": {"settlement_id": "settlement:revision:1"},
        },
        existing_artifacts={verifier.SCREENSHOT_FILENAMES["revision_failure"]},
    )

    assert passed
    assert notes == []
