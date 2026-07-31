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


TEST_FILES = ["backend/tests/test_scene_affordance_registry.py"]


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
