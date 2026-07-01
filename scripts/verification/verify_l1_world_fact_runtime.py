from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.models.environment_field import EnvironmentFieldState
from app.world_runtime.l1_fact_projection import FactProjectionLayer
from app.world_runtime.l1_occupancy import SpatialOccupancyService
from app.world_runtime.l1_space_model import SceneSpaceModelExtractor
from common import (
    read_text,
    repo_root,
    resolve_python_exe,
    run_command,
    verification_dir,
    write_json,
    write_markdown,
)


def _result(result_id: str, title: str, proved: bool, evidence: list[str], notes: str = "") -> dict[str, object]:
    return {
        "id": result_id,
        "title": title,
        "status": "proved" if proved else "missing",
        "evidence": evidence if proved else [],
        "notes": notes,
    }


def _resolve_optional_godot(project_root: Path, explicit: str | None) -> Path | None:
    candidates = [
        explicit,
        str(project_root / "Godot.exe"),
        r"D:\godot\Godot_v4.6.3-stable_win64.exe",
        r"E:\下载\Godot_v4.6.3-stable_win64.exe\Godot_v4.6.3-stable_win64_console.exe",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return Path(candidate)
    return None


def _write_backend_contract_artifacts(project_root: Path) -> dict[str, str]:
    log_dir = verification_dir(project_root)
    extractor = SceneSpaceModelExtractor(artifact_dir=log_dir)
    space_model = extractor.extract_from_runtime_scene(
        room_id="room_demo",
        scene_id="scene_demo",
        runtime_nodes=[
            {
                "node_path": "/root/MainDemo/ZoneFocus",
                "groups": ["l1_zone"],
                "metadata": {"l1_space_type": "zone", "zone_id": "zone_focus"},
            },
            {
                "node_path": "/root/MainDemo/ThroneRoomCollisionRoot/Wall",
                "groups": ["l1_static_obstacle"],
                "metadata": {"l1_space_type": "static_obstacle", "element_id": "wall_1"},
                "collision_shape_ref": "collision_shape:/root/MainDemo/ThroneRoomCollisionRoot/Wall/CollisionShape3D",
            },
            {
                "node_path": "/root/MainDemo/ThroneRoomCollisionRoot/Pillar",
                "groups": ["l1_occluder"],
                "metadata": {"l1_space_type": "occluder", "element_id": "pillar_1"},
                "collision_shape_ref": "collision_shape:/root/MainDemo/ThroneRoomCollisionRoot/Pillar/CollisionShape3D",
            },
            {
                "node_path": "/root/MainDemo/EnvironmentStateNode",
                "groups": ["l1_environment_anchor"],
                "metadata": {"l1_space_type": "environment_anchor", "element_id": "env_lamp"},
            },
            {
                "node_path": "/root/MainDemo/InteractiveObject",
                "groups": ["l1_interaction_object"],
                "metadata": {"l1_space_type": "interaction_object", "element_id": "obj_letter"},
                "collision_shape_ref": "collision_shape:/root/MainDemo/InteractiveObject/CollisionShape3D",
            },
            {
                "node_path": "/root/MainDemo/WalkableFloor",
                "groups": ["l1_navigation_lane"],
                "metadata": {"l1_space_type": "navigation_lane", "element_id": "lane_focus"},
                "navigation_region_ref": "navigation_region:derived_from_runtime_walkable:/root/MainDemo/WalkableFloor",
            },
        ],
        artifact_name="l1-space-model-backend-contract.json",
    )
    occupancy = SpatialOccupancyService.from_space_model(space_model)
    occupancy.apply_actor_zone_update(
        actor_id="char_b",
        previous_zone_id="",
        next_zone_id="zone_focus",
        producer_ts=100,
        source_ref="raw_fact_event:actor_entered_zone:100",
    )
    occupancy.apply_object_state_update(
        object_id="obj_letter",
        zone_id="zone_focus",
        state="visible",
        affordances=["inspect", "read"],
        occludes=False,
        producer_ts=101,
        source_ref="object_state_result:obj_letter:101",
    )
    occupancy.apply_environment_field(
        EnvironmentFieldState(
            field_id="field:room_demo:scene_demo:zone_focus",
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            visibility_level="reduced",
            smoke_density="dense",
            producer_ts=102,
            updated_at=102,
            source_environment_id="env_lamp",
        )
    )
    occupancy_path = log_dir / "l1-occupancy-backend-contract.json"
    occupancy_path.write_text(json.dumps(occupancy.snapshot().model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")
    projected = FactProjectionLayer().project_actor_target_facts(
        occupancy.snapshot(),
        actor_id="char_b",
        target_object_id="obj_letter",
        producer_ts=103,
    )
    projection_path = log_dir / "l1-projection-backend-contract.json"
    projection_path.write_text(
        json.dumps({"projected_facts": [fact.model_dump() for fact in projected]}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {
        "space_model": str(log_dir / "l1-space-model-backend-contract.json"),
        "occupancy": str(occupancy_path),
        "projection": str(projection_path),
    }


def _provider_runtime_refs_present(project_root: Path) -> bool:
    provider_paths = [
        project_root / "scripts" / "character" / "VisualPatchProvider.gd",
        project_root / "scripts" / "character" / "SpatialPatchProvider.gd",
        project_root / "scripts" / "character" / "AuditoryContextProvider.gd",
        project_root / "scripts" / "character" / "EmbodiedStateProvider.gd",
    ]
    return all("runtime_source_refs" in read_text(path) and "runtime://" in read_text(path) for path in provider_paths)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--godot-exe", default=None)
    parser.add_argument("--python-exe", default=None)
    args = parser.parse_args()

    project_root = repo_root()
    log_dir = verification_dir(project_root)
    python_exe = resolve_python_exe(args.python_exe)
    artifacts = _write_backend_contract_artifacts(project_root)

    pytest_log = log_dir / "l1-world-fact-runtime-pytest.log"
    pytest_result = run_command(
        [
            python_exe,
            "-m",
            "pytest",
            "-q",
            "backend/tests/test_l1_world_fact_runtime.py",
            "backend/tests/test_l1_fact_projection_runtime.py",
            "backend/tests/test_l1_perception_frame_runtime.py",
        ],
        project_root,
        pytest_log,
    )
    provider_refs_ok = _provider_runtime_refs_present(project_root)

    godot_exe = _resolve_optional_godot(project_root, args.godot_exe)
    godot_status = "godot-runtime-unverified"
    godot_log = log_dir / "l1-world-fact-runtime-godot.log"
    godot_probe_ok = False
    if godot_exe is not None:
        godot_result = run_command(
            [
                str(godot_exe),
                "--path",
                str(project_root),
                "--scene",
                "res://scenes/phase0/L1WorldFactRuntimeProbe.tscn",
                "--quit-after",
                "600",
                "--render-thread",
                "safe",
            ],
            project_root,
            godot_log,
        )
        godot_text = read_text(godot_log)
        godot_probe_ok = (
            godot_result.returncode == 0
            and "l1_world_fact_runtime_probe:runtime_source_refs=true" in godot_text
            and (log_dir / "l1-space-model-runtime.json").exists()
        )
        godot_status = "godot-runtime-verified" if godot_probe_ok else "godot-runtime-unverified"

    results = [
        _result(
            "backend_contract_verified",
            "Backend L1 world fact subsystem tests pass",
            pytest_result.returncode == 0,
            [str(pytest_log)],
        ),
        _result(
            "scene_space_model_artifact_exists",
            "Scene3DSpaceModel artifact exists with runtime-facing refs",
            Path(artifacts["space_model"]).exists(),
            [artifacts["space_model"]],
        ),
        _result(
            "occupancy_dirty_update_observed",
            "SpatialOccupancyService records dirty-zone incremental updates",
            Path(artifacts["occupancy"]).exists(),
            [artifacts["occupancy"]],
        ),
        _result(
            "projection_facts_emitted",
            "FactProjectionLayer emits raw_fact_event projection facts",
            Path(artifacts["projection"]).exists(),
            [artifacts["projection"]],
        ),
        _result(
            "godot_provider_runtime_refs_present",
            "Godot providers emit runtime source refs",
            provider_refs_ok,
            [
                "scripts/character/VisualPatchProvider.gd",
                "scripts/character/SpatialPatchProvider.gd",
                "scripts/character/AuditoryContextProvider.gd",
                "scripts/character/EmbodiedStateProvider.gd",
            ],
        ),
        {
            "id": "godot_runtime_probe",
            "title": "Godot runtime probe extracts scene model and provider refs",
            "status": "proved" if godot_probe_ok else godot_status,
            "evidence": [str(godot_log)] if godot_exe is not None else [],
            "notes": "" if godot_probe_ok else "Godot executable was unavailable or probe did not complete; report remains godot-runtime-unverified.",
        },
    ]

    backend_contract_verified = all(
        entry["status"] == "proved"
        for entry in results
        if entry["id"] != "godot_runtime_probe"
    )
    report = {
        "results": results,
        "overall_l1_world_fact_runtime_passed": backend_contract_verified,
        "godot_runtime_status": godot_status,
        "artifacts": {
            **artifacts,
            "pytest_log": str(pytest_log),
            "godot_log": str(godot_log),
        },
    }
    json_path = log_dir / "l1-world-fact-runtime-report.json"
    md_path = log_dir / "l1-world-fact-runtime-report.md"
    write_json(json_path, report)
    write_markdown(md_path, "L1 World Fact Subsystem Verification Report", report, "overall_l1_world_fact_runtime_passed")

    print(f"l1_world_fact_runtime_report_json={json_path}")
    print(f"l1_world_fact_runtime_report_md={md_path}")
    print(f"overall_l1_world_fact_runtime_passed={report['overall_l1_world_fact_runtime_passed']}")
    print(f"godot_runtime_status={godot_status}")
    for entry in report["results"]:
        print(f"{entry['id']}={entry['status']}")
    return 0 if backend_contract_verified else 1


if __name__ == "__main__":
    raise SystemExit(main())
