from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.models.raw_fact import RawFactEvent, RawFactObservability, RawFactSource, RawFactTargets, RawFactWorld
from app.services.character_agent_runtime import CharacterAgentRuntime
from app.services.siming_global_situation import SimingGlobalSituationLayer
from app.services.siming_runtime import SimingRuntime
from app.world_runtime.l1_occupancy import SpatialOccupancyService
from app.world_runtime.l1_runtime_perception_bridge import L1ActorProjectionInput, L1RuntimePerceptionBridge
from common import repo_root, verification_dir, write_json, write_markdown


def _result(result_id: str, title: str, proved: bool, evidence: list[str], notes: str = "") -> dict[str, object]:
    return {
        "id": result_id,
        "title": title,
        "status": "proved" if proved else "missing",
        "evidence": evidence if proved else [],
        "notes": notes,
    }


def _fact(actor_id: str, *, fact_type: str, occluded: bool) -> RawFactEvent:
    return RawFactEvent(
        fact_family="visual_fact",
        fact_type=fact_type,
        relation_type="actor_sees_object",
        producer_ts=920,
        capture_root_id="capture_root:godot_main:room_demo:scene_demo:zone_focus:99",
        clock_domain="godot_main",
        monotonic_tick=99,
        source_frame_index=15,
        wall_clock_ts=920,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        source=RawFactSource(layer="L1", system="verify.multi_actor", actor_id=actor_id),
        targets=RawFactTargets(object_id="obj_letter"),
        world_anchor_id="world_anchor:object:obj_letter",
        world=RawFactWorld(distance_m=1.0 if actor_id == "char_a" else 2.6, state_after=fact_type),
        observability=RawFactObservability(visual=True, occluded=occluded),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.parse_args()

    project_root = repo_root()
    log_dir = verification_dir(project_root)
    occupancy = SpatialOccupancyService()
    for actor_id in ("char_a", "char_b"):
        occupancy.apply_actor_zone_update(
            actor_id=actor_id,
            previous_zone_id="",
            next_zone_id="zone_focus",
            producer_ts=100,
            source_ref=f"raw_fact_event:actor_entered_zone:{actor_id}:100",
        )

    result = L1RuntimePerceptionBridge().consume_multi_actor_projected_facts(
        occupancy=occupancy.snapshot(),
        actor_projections=[
            L1ActorProjectionInput(
                actor_id="char_a",
                projected_facts=[_fact("char_a", fact_type="object_visible", occluded=False)],
                actor_frame_ref="actor_frame:char_a:99",
                camera_frame_ref="camera:char_a:99",
                listener_frame_ref="listener:char_a:99",
            ),
            L1ActorProjectionInput(
                actor_id="char_b",
                projected_facts=[_fact("char_b", fact_type="object_partly_occluded", occluded=True)],
                actor_frame_ref="actor_frame:char_b:99",
                camera_frame_ref="camera:char_b:99",
                listener_frame_ref="listener:char_b:99",
            ),
        ],
        character_runtime=CharacterAgentRuntime(),
        siming_runtime=SimingRuntime(),
    )
    if result is None:
        raise RuntimeError("multi-actor bridge did not produce a result")

    siming_snapshot = SimingGlobalSituationLayer().assemble_snapshot(
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        context_id="siming_mm:room_demo:scene_demo",
        multi_actor_patch=result.multi_actor_patch,
        producer_ts=99,
    )

    trace = {
        "bridge_result": result.model_dump(mode="json"),
        "siming_snapshot": siming_snapshot.model_dump(mode="json"),
    }
    trace_path = log_dir / "perception-multi-actor-private-perspective.json"
    write_json(trace_path, trace)

    char_a = result.actor_results["char_a"]
    char_b = result.actor_results["char_b"]
    same_root_ok = (
        char_a["character_frame"]["capture_root_id"] == result.capture_root_id
        and char_b["character_frame"]["capture_root_id"] == result.capture_root_id
    )
    private_context_ok = (
        char_a["character_frame"]["capture_id"] != char_b["character_frame"]["capture_id"]
        and char_a["character_frame"]["multimodal_context_id"] == "character_mm:char_a"
        and char_b["character_frame"]["multimodal_context_id"] == "character_mm:char_b"
        and result.context_isolation["isolated"] is True
    )
    view_refs_ok = (
        char_a["character_frame"]["spatial_reference"]["camera_frame_ref"] == "camera:char_a:99"
        and char_b["character_frame"]["spatial_reference"]["camera_frame_ref"] == "camera:char_b:99"
    )
    same_anchor_different_private_attributes_ok = (
        char_a["character_bundle"]["target_state"]["world_anchor_id"] == "world_anchor:object:obj_letter"
        and char_b["character_bundle"]["target_state"]["world_anchor_id"] == "world_anchor:object:obj_letter"
        and char_a["character_bundle"]["uncertainty"]["occluded_fact_count"] == 0
        and char_b["character_bundle"]["uncertainty"]["occluded_fact_count"] == 1
    )
    siming_ok = (
        "character_mm:" not in str(result.multi_actor_patch)
        and any(evidence.source_kind == "multi_actor_patch" for evidence in siming_snapshot.evidence_chain)
        and any(evidence.world_anchor_id == "world_anchor:object:obj_letter" for evidence in siming_snapshot.evidence_chain)
    )

    results = [
        _result("same-root-capture", "Actor A/B projections share one capture_root_id", same_root_ok, [str(trace_path)]),
        _result("private-capture-and-context", "Actor A/B retain distinct capture_id and character_mm context", private_context_ok, [str(trace_path)]),
        _result("different-viewpoint-refs", "Actor A/B retain different actor/camera/listener viewpoint refs", view_refs_ok, [str(trace_path)]),
        _result("same-object-different-private-attributes", "Actor A/B can differ privately without splitting world_anchor_id", same_anchor_different_private_attributes_ok, [str(trace_path)]),
        _result("siming-public-patch-only", "Siming consumes public multi_actor_patch without character private context", siming_ok, [str(trace_path)]),
    ]
    overall = all(entry["status"] == "proved" for entry in results)
    report = {
        "overall_perception_multi_actor_private_perspective_passed": overall,
        "results": results,
        "artifacts": {"trace": str(trace_path)},
    }
    report_json = log_dir / "perception-multi-actor-private-perspective-report.json"
    report_md = log_dir / "perception-multi-actor-private-perspective-report.md"
    write_json(report_json, report)
    write_markdown(
        report_md,
        "Perception Multi-Actor Private Perspective Verification Report",
        report,
        "overall_perception_multi_actor_private_perspective_passed",
    )
    print(f"perception_multi_actor_private_perspective_report_json={report_json}")
    print(f"perception_multi_actor_private_perspective_report_md={report_md}")
    print(f"overall_perception_multi_actor_private_perspective_passed={overall}")
    for entry in results:
        print(f"{entry['id']}={entry['status']}")
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())
