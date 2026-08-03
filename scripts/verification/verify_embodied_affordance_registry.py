from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.models.embodied_interaction import SceneAffordanceRecord
from app.services.scene_affordance_registry import SceneAffordanceRegistry
from app.world_runtime.l1_occupancy import SpatialOccupancyService
from app.world_runtime.l1_space_model import SceneSpaceModelExtractor
from common import read_text, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


TEST_FILES = [
    "backend/tests/test_scene_affordance_registry.py",
    "backend/tests/test_default_scene_letter_affordance_static.py",
    "backend/tests/test_default_scene_pickup_authority.py",
    "backend/tests/test_ws_protocol.py::test_websocket_interact_intent_emits_ack_action_resolution_transition_object_state_body_state_environment_shift_and_siming_output",
    "backend/tests/test_ws_protocol.py::test_websocket_press_intent_uses_registered_switch_authority_policy",
    "backend/tests/test_ws_protocol.py::test_websocket_open_intent_uses_registered_archive_door_authority_policy",
    "backend/tests/test_ws_protocol.py::test_door_close_requires_the_authority_committed_open_state",
    "backend/tests/test_ws_protocol.py::test_worktable_finish_use_requires_the_authority_committed_engaged_state",
    "backend/tests/test_ws_protocol.py::test_observation_bench_stand_requires_the_authority_scoped_occupant_and_emits_posture",
    "backend/tests/test_ws_protocol.py::test_websocket_interact_intent_emits_constraint_when_player_is_far",
]


def _result(check_id: str, title: str, proved: bool, evidence: list[str], notes: str = "") -> dict[str, object]:
    return {
        "id": check_id,
        "title": title,
        "status": "proved" if proved else "missing",
        "evidence": evidence if proved else [],
        "notes": notes,
    }


def _record() -> SceneAffordanceRecord:
    return SceneAffordanceRecord.model_validate(
        {
            "entity_ref": "entity:scene_demo:chair_01",
            "scene_id": "scene_demo",
            "scene_instance_id": "scene_instance:main_demo:1",
            "binding_revision": 7,
            "semantic_type": "chair",
            "semantic_tags": ["chair", "kickable"],
            "authoritative_state_ref": "esm:object:chair_01",
            "local_binding": {
                "node_ref": "node:chair_01",
                "collider_refs": ["collider:chair_01:body"],
                "navigation_footprint_ref": "nav:chair_01:footprint",
            },
            "anchors": [
                {"anchor_id": "anchor:chair_01:stance", "role": "approach_stance"},
                {"anchor_id": "anchor:chair_01:contact", "role": "contact"},
            ],
            "affordances": [
                {
                    "affordance_id": "affordance:chair_01:kick",
                    "action_semantic": "kick",
                    "preconditions": ["upright"],
                    "execution_profile_ref": "execution_profile:kick:v1",
                    "observation_rule_ref": "observation_rule:chair_tipped:v1",
                    "policy_ref": "authority_policy:kick_chair:v1",
                }
            ],
            "grounding_catalog_refs": {
                "entity_ref": "entity:scene_demo:chair_01",
                "collider_refs": ["collider:chair_01:body"],
                "anchor_refs": ["anchor:chair_01:stance", "anchor:chair_01:contact"],
            },
            "physical_profile_ref": "physical_profile:chair_rigidbody:v1",
            "visibility_policy": "public_safe",
            "binding_health": "healthy",
        }
    )


def _backend_registry_trace(log_dir: Path) -> Path:
    space_model = SceneSpaceModelExtractor().extract_from_runtime_scene(
        room_id="room_demo",
        scene_id="scene_demo",
        runtime_nodes=[
            {
                "node_path": "/root/MainDemo/Chair01",
                "groups": ["l1_interaction_object"],
                "metadata": {"l1_space_type": "interaction_object", "element_id": "entity:scene_demo:chair_01"},
                "collision_shape_ref": "collider:chair_01:body",
                "source_refs": ["anchor:chair_01:stance", "anchor:chair_01:contact", "affordance:chair_01:kick"],
            },
            {
                "node_path": "/root/MainDemo/L1NavigationRegion",
                "groups": ["l1_navigation_lane"],
                "metadata": {"l1_space_type": "navigation_lane", "element_id": "nav:chair_01:footprint"},
                "navigation_region_ref": "navigation_region:/root/MainDemo/L1NavigationRegion",
            },
        ],
    )
    occupancy = SpatialOccupancyService(field_id="occupancy:room_demo:scene_demo", static_model_ref=space_model.model_id)
    occupancy.apply_object_state_update(
        object_id="entity:scene_demo:chair_01",
        zone_id="zone_focus",
        state="upright",
        affordances=["kick"],
        occludes=False,
        producer_ts=110,
        source_ref="object_state:chair_01:110",
    )
    registry = SceneAffordanceRegistry.from_reviewed_records(
        records=[_record()],
        space_model=space_model,
        occupancy_snapshot=occupancy.snapshot(),
        grounding_catalog={
            "entity_refs": ["entity:scene_demo:chair_01"],
            "collider_refs": ["collider:chair_01:body"],
            "anchor_refs": ["anchor:chair_01:stance", "anchor:chair_01:contact"],
            "affordance_refs": ["affordance:chair_01:kick"],
        },
        current_tick=120,
        occupancy_freshness_ticks=30,
    )
    available = registry.resolve(
        scene_id="scene_demo",
        scene_instance_id="scene_instance:main_demo:1",
        entity_ref="entity:scene_demo:chair_01",
        affordance_id="affordance:chair_01:kick",
        expected_binding_revision=7,
        required_anchor_roles=["approach_stance", "contact"],
        view="controller",
    )
    stale = registry.resolve(
        scene_id="scene_demo",
        scene_instance_id="scene_instance:main_demo:1",
        entity_ref="entity:scene_demo:chair_01",
        affordance_id="affordance:chair_01:kick",
        expected_binding_revision=6,
        required_anchor_roles=["approach_stance", "contact"],
        view="controller",
    )
    vla_conflict = registry.review_vla_candidate(
        entity_ref="entity:scene_demo:chair_01",
        candidate_refs={
            "entity_refs": ["entity:vla:invented"],
            "collider_refs": ["collider:vla:fake"],
            "anchor_refs": [],
            "affordance_refs": [],
        },
    )
    trace_path = log_dir / "embodied-affordance-registry-trace.json"
    write_json(
        trace_path,
        {
            "available": available.model_dump(mode="json"),
            "stale": stale.model_dump(mode="json"),
            "vla_conflict": vla_conflict,
        },
    )
    return trace_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--godot-exe", default=None)
    parser.add_argument("--python-exe", default=None)
    args = parser.parse_args()

    project_root = repo_root()
    log_dir = verification_dir(project_root)
    python_exe = resolve_python_exe(args.python_exe)
    pytest_log = log_dir / "embodied-affordance-registry-pytest.log"
    pytest_result = run_command([python_exe, "-m", "pytest", "-q", *TEST_FILES], project_root, pytest_log)
    trace_path = _backend_registry_trace(log_dir)

    godot_log = log_dir / "embodied-affordance-registry-godot.log"
    godot_artifact = log_dir / "embodied-affordance-registry-godot-runtime.json"
    godot_ok = False
    if args.godot_exe:
        godot_result = run_command(
            [
                args.godot_exe,
                "--headless",
                "--path",
                str(project_root),
                "--scene",
                "res://scenes/phase0/SceneAffordanceRegistryProbe.tscn",
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
            and "scene_affordance_registry_probe:resolved=true" in godot_text
            and godot_artifact.exists()
        )
    try:
        godot_payload = json.loads(godot_artifact.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        godot_payload = {}
    try:
        trace_payload = json.loads(trace_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        trace_payload = {}

    letter_godot_log = log_dir / "default-scene-letter-affordance-godot.log"
    letter_godot_artifact = log_dir / "default-scene-letter-affordance-godot-runtime.json"
    letter_godot_ok = False
    if args.godot_exe:
        letter_godot_result = run_command(
            [
                args.godot_exe,
                "--headless",
                "--path",
                str(project_root),
                "--scene",
                "res://scenes/phase0/DefaultSceneLetterAffordanceProbe.tscn",
                "--quit-after",
                "300",
                "--render-thread",
                "safe",
            ],
            project_root,
            letter_godot_log,
        )
        letter_godot_text = read_text(letter_godot_log)
        letter_godot_ok = (
            letter_godot_result.returncode == 0
            and "default_scene_letter_affordance_probe:verified=true" in letter_godot_text
            and letter_godot_artifact.exists()
        )
    try:
        letter_godot_payload = json.loads(letter_godot_artifact.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        letter_godot_payload = {}

    available = trace_payload.get("available", {}) if isinstance(trace_payload, dict) else {}
    stale = trace_payload.get("stale", {}) if isinstance(trace_payload, dict) else {}
    vla_conflict = trace_payload.get("vla_conflict", {}) if isinstance(trace_payload, dict) else {}
    identity_refs = godot_payload.get("identity_refs", {}) if isinstance(godot_payload, dict) else {}
    results = [
        _result("focused-pytest-pass", "SceneAffordanceRegistry focused pytest suite passes", pytest_result.returncode == 0, [str(pytest_log)]),
        _result(
            "backend-registry-resolves-chair",
            "Backend registry resolves chair_01 against reviewed scene/PQF IDs",
            isinstance(available, dict) and available.get("status") == "available",
            [str(trace_path)],
        ),
        _result(
            "backend-rejects-stale-binding",
            "Backend registry rejects stale binding revisions before controller start",
            isinstance(stale, dict) and stale.get("status") == "registry_binding_stale",
            [str(trace_path)],
        ),
        _result(
            "vla-conflict-recorded-no-overwrite",
            "VLA advisory conflict is recorded without overwriting registry truth",
            isinstance(vla_conflict, dict) and vla_conflict.get("status") == "vla_conflict_recorded",
            [str(trace_path)],
        ),
        _result(
            "godot-runtime-registry-binding",
            "Godot runtime probe resolves chair_01 through SceneSpaceModelExtractor and RuntimeOccupancySampler",
            godot_ok
            and isinstance(identity_refs, dict)
            and identity_refs.get("entity_ref") == "entity:scene_demo:chair_01"
            and identity_refs.get("collider_refs") == ["collider:chair_01:body"],
            [str(godot_log), str(godot_artifact)],
        ),
        _result(
            "default-main-scene-letter-binding",
            "Default MainDemo letter resolves through reviewed grounding refs and changes presentation only after an authority object result",
            letter_godot_ok
            and isinstance(letter_godot_payload, dict)
            and letter_godot_payload.get("initial_state") == "partially_visible"
            and isinstance(letter_godot_payload.get("stale_refresh_resolution"), dict)
            and letter_godot_payload["stale_refresh_resolution"].get("status") == "available"
            and letter_godot_payload.get("state_after_authority") == "visible"
            and letter_godot_payload.get("state_after_constraint") == "visible"
            and letter_godot_payload.get("authority_owned_presentation") is True,
            [str(letter_godot_log), str(letter_godot_artifact)],
        ),
        _result(
            "default-main-scene-plaque-binding",
            "Default MainDemo plaque resolves through reviewed grounding refs and changes presentation only after an authority object result",
            letter_godot_ok
            and isinstance(letter_godot_payload, dict)
            and isinstance(letter_godot_payload.get("plaque_initial_resolution"), dict)
            and letter_godot_payload["plaque_initial_resolution"].get("status") == "available"
            and letter_godot_payload.get("plaque_initial_state") == "partially_visible"
            and letter_godot_payload.get("plaque_state_after_authority") == "visible"
            and letter_godot_payload.get("plaque_state_after_constraint") == "visible"
            and letter_godot_payload.get("plaque_authority_owned_presentation") is True,
            [str(letter_godot_log), str(letter_godot_artifact)],
        ),
        _result(
            "default-main-scene-lamp-switch-binding",
            "Default MainDemo lamp switch resolves the explicit press affordance and changes presentation only after an authority switch result",
            letter_godot_ok
            and isinstance(letter_godot_payload, dict)
            and isinstance(letter_godot_payload.get("lamp_switch_initial_resolution"), dict)
            and letter_godot_payload["lamp_switch_initial_resolution"].get("status") == "available"
            and letter_godot_payload.get("lamp_switch_default_interaction") == "press"
            and letter_godot_payload.get("lamp_switch_initial_state") == "idle"
            and letter_godot_payload.get("lamp_switch_state_after_authority") == "activated"
            and letter_godot_payload.get("lamp_switch_state_after_constraint") == "activated"
            and letter_godot_payload.get("lamp_switch_authority_owned_presentation") is True,
            [str(letter_godot_log), str(letter_godot_artifact)],
        ),
        _result(
            "default-main-scene-archive-door-binding",
            "Default MainDemo archive door resolves open then close from authority-presented state and ignores a later state constraint",
            letter_godot_ok
            and isinstance(letter_godot_payload, dict)
            and isinstance(letter_godot_payload.get("archive_door_initial_resolution"), dict)
            and letter_godot_payload["archive_door_initial_resolution"].get("status") == "available"
            and letter_godot_payload.get("archive_door_default_interaction") == "open"
            and letter_godot_payload.get("archive_door_initial_state") == "closed"
            and letter_godot_payload.get("archive_door_state_after_authority") == "open"
            and isinstance(letter_godot_payload.get("archive_door_close_resolution"), dict)
            and letter_godot_payload["archive_door_close_resolution"].get("status") == "available"
            and letter_godot_payload.get("archive_door_close_interaction") == "close"
            and letter_godot_payload.get("archive_door_state_after_close") == "closed"
            and letter_godot_payload.get("archive_door_reopened_interaction") == "open"
            and letter_godot_payload.get("archive_door_state_after_constraint") == "closed"
            and letter_godot_payload.get("archive_door_authority_owned_presentation") is True,
            [str(letter_godot_log), str(letter_godot_artifact)],
        ),
        _result(
            "default-main-scene-worktable-binding",
            "Default MainDemo worktable resolves use then finish_use from authority-presented state and ignores a later state constraint",
            letter_godot_ok
            and isinstance(letter_godot_payload, dict)
            and isinstance(letter_godot_payload.get("worktable_initial_resolution"), dict)
            and letter_godot_payload["worktable_initial_resolution"].get("status") == "available"
            and letter_godot_payload.get("worktable_default_interaction") == "use"
            and letter_godot_payload.get("worktable_initial_state") == "ready"
            and letter_godot_payload.get("worktable_state_after_authority") == "engaged"
            and isinstance(letter_godot_payload.get("worktable_finish_resolution"), dict)
            and letter_godot_payload["worktable_finish_resolution"].get("status") == "available"
            and letter_godot_payload.get("worktable_finish_interaction") == "finish_use"
            and letter_godot_payload.get("worktable_state_after_finish") == "ready"
            and letter_godot_payload.get("worktable_reused_interaction") == "use"
            and letter_godot_payload.get("worktable_state_after_constraint") == "ready"
            and letter_godot_payload.get("worktable_authority_owned_presentation") is True,
            [str(letter_godot_log), str(letter_godot_artifact)],
        ),
        _result(
            "default-main-scene-observation-bench-binding",
            "Default MainDemo observation bench resolves sit then stand from authority-presented state and ignores a later owner constraint",
            letter_godot_ok
            and isinstance(letter_godot_payload, dict)
            and isinstance(letter_godot_payload.get("observation_bench_initial_resolution"), dict)
            and letter_godot_payload["observation_bench_initial_resolution"].get("status") == "available"
            and letter_godot_payload.get("observation_bench_default_interaction") == "sit"
            and letter_godot_payload.get("observation_bench_initial_state") == "available"
            and letter_godot_payload.get("observation_bench_state_after_authority") == "occupied"
            and isinstance(letter_godot_payload.get("observation_bench_stand_resolution"), dict)
            and letter_godot_payload["observation_bench_stand_resolution"].get("status") == "available"
            and letter_godot_payload.get("observation_bench_stand_interaction") == "stand"
            and letter_godot_payload.get("observation_bench_state_after_stand") == "available"
            and letter_godot_payload.get("observation_bench_resit_interaction") == "sit"
            and letter_godot_payload.get("observation_bench_state_after_constraint") == "available"
            and letter_godot_payload.get("observation_bench_authority_owned_presentation") is True,
            [str(letter_godot_log), str(letter_godot_artifact)],
        ),
        _result(
            "default-main-scene-archive-token-pickup-binding",
            "Default MainDemo archive token resolves a reviewed grab affordance and changes its local presentation only after an authority-only placement directive",
            letter_godot_ok
            and isinstance(letter_godot_payload, dict)
            and isinstance(letter_godot_payload.get("archive_token_initial_resolution"), dict)
            and letter_godot_payload["archive_token_initial_resolution"].get("status") == "available"
            and letter_godot_payload.get("archive_token_default_interaction") == "grab"
            and letter_godot_payload.get("archive_token_initial_visible") is True
            and letter_godot_payload.get("archive_token_visible_after_unsafe_directive") is True
            and letter_godot_payload.get("archive_token_visible_after_authority") is False
            and letter_godot_payload.get("archive_token_presentation_state") == "carried"
            and letter_godot_payload.get("archive_token_stow_allowed_after_pickup") is True
            and letter_godot_payload.get("archive_token_presentation_state_after_unsafe_stow") == "carried"
            and letter_godot_payload.get("archive_token_presentation_state_after_authority_stow") == "stowed"
            and letter_godot_payload.get("archive_token_stow_allowed_after_authority_stow") is False
            and letter_godot_payload.get("archive_token_authority_owned_presentation") is True,
            [str(letter_godot_log), str(letter_godot_artifact)],
        ),
        _result(
            "default-main-scene-archive-storage-chest-retrieve-binding",
            "Default MainDemo archive storage chest resolves only its reviewed retrieve affordance and restores the local carried marker only from an authority-only directive",
            letter_godot_ok
            and isinstance(letter_godot_payload, dict)
            and isinstance(letter_godot_payload.get("archive_storage_chest_initial_resolution"), dict)
            and letter_godot_payload["archive_storage_chest_initial_resolution"].get("status") == "available"
            and letter_godot_payload.get("archive_storage_chest_default_interaction") == "retrieve"
            and letter_godot_payload.get("archive_token_presentation_state_after_unsafe_retrieve") == "stowed"
            and letter_godot_payload.get("archive_token_presentation_state_after_authority_retrieve") == "carried",
            [str(letter_godot_log), str(letter_godot_artifact)],
        ),
    ]
    overall = all(entry["status"] == "proved" for entry in results)
    report = {
        "overall_embodied_affordance_registry_passed": overall,
        "results": results,
        "artifacts": {
            "pytest_log": str(pytest_log),
            "trace": str(trace_path),
            "godot_log": str(godot_log),
            "godot_runtime": str(godot_artifact),
            "default_scene_letter_godot_log": str(letter_godot_log),
            "default_scene_letter_godot_runtime": str(letter_godot_artifact),
        },
    }
    json_path = log_dir / "embodied-affordance-registry-report.json"
    md_path = log_dir / "embodied-affordance-registry-report.md"
    write_json(json_path, report)
    write_markdown(md_path, "Embodied Affordance Registry Verification Report", report, "overall_embodied_affordance_registry_passed")
    print(f"embodied_affordance_registry_report_json={json_path}")
    print(f"embodied_affordance_registry_report_md={md_path}")
    print(f"overall_embodied_affordance_registry_passed={overall}")
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())
