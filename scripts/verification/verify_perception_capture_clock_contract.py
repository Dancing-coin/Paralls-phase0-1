from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.models.capture_clock import same_capture_tick
from app.models.raw_fact import RawFactEvent, RawFactSource, RawFactTargets, RawFactWorld
from app.services.character_agent_runtime import CharacterAgentRuntime
from app.services.siming_runtime import SimingRuntime
from app.world_runtime.intelligence_upgrade import PerceptionQueryFrame
from app.world_runtime.l1_occupancy import SpatialOccupancyService
from app.world_runtime.l1_runtime_perception_bridge import L1RuntimePerceptionBridge, MixedPerceptionCaptureError
from app.world_runtime.vla_provider import VLAProviderRequest
from app.world_runtime.vla_slow_path_scheduler import VLASlowPathScheduler
from common import repo_root, verification_dir, write_json, write_markdown


def _result(result_id: str, title: str, proved: bool, evidence: list[str], notes: str = "") -> dict[str, object]:
    return {
        "id": result_id,
        "title": title,
        "status": "proved" if proved else "missing",
        "evidence": evidence if proved else [],
        "notes": notes,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.parse_args()

    project_root = repo_root()
    log_dir = verification_dir(project_root)

    occupancy = SpatialOccupancyService()
    occupancy.apply_actor_zone_update(
        actor_id="char_b",
        previous_zone_id="",
        next_zone_id="zone_focus",
        producer_ts=100,
        source_ref="raw_fact_event:actor_entered_zone:100",
    )
    fact = RawFactEvent(
        fact_family="spatial_access_fact",
        fact_type="actor_approached_object",
        relation_type="proximity",
        producer_ts=900,
        capture_root_id="capture_root:godot_main:room_demo:scene_demo:zone_focus:77",
        clock_domain="godot_main",
        monotonic_tick=77,
        source_frame_index=12,
        wall_clock_ts=900,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        source=RawFactSource(layer="L1", system="verify.capture_clock", actor_id="char_b"),
        targets=RawFactTargets(object_id="obj_letter"),
        world=RawFactWorld(distance_m=1.2, state_after="near"),
    )
    bridge_result = L1RuntimePerceptionBridge().consume_projected_facts(
        occupancy=occupancy.snapshot(),
        projected_facts=[fact],
        character_runtime=CharacterAgentRuntime(),
        siming_runtime=SimingRuntime(),
        actor_id="char_b",
        provider_refs={
            "visual_inputs": [
                {
                    "provider_kind": "visual_patch",
                    "ref_id": "runtime://camera/MainCamera/frame/12",
                    "retention": "debug_artifact",
                }
            ]
        },
    )
    if bridge_result is None:
        raise RuntimeError("bridge did not consume the capture-clock fact")
    character_frame = bridge_result.character_frame
    siming_frame = bridge_result.siming_frame
    character_bundle = bridge_result.character_bundle
    request = VLAProviderRequest.from_pqf(
        PerceptionQueryFrame(**character_frame),
        owner_kind="character",
        owner_id="char_b",
        model_id="qwen3-vl-plus",
    )
    late_result = VLASlowPathScheduler(timeout_seconds=0.01).timeout_result(request)

    mixed_fact = RawFactEvent(
        fact_family="spatial_access_fact",
        fact_type="actor_approached_object",
        relation_type="proximity",
        producer_ts=901,
        capture_root_id="capture_root:godot_main:room_demo:scene_demo:zone_focus:78",
        clock_domain="godot_main",
        monotonic_tick=78,
        source_frame_index=13,
        wall_clock_ts=901,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        source=RawFactSource(layer="L1", system="verify.capture_clock", actor_id="char_b"),
        targets=RawFactTargets(object_id="obj_letter"),
        world=RawFactWorld(distance_m=1.2, state_after="near"),
    )
    mixed_rejected = False
    mixed_error = ""
    try:
        L1RuntimePerceptionBridge().consume_projected_facts(
            occupancy=occupancy.snapshot(),
            projected_facts=[fact, mixed_fact],
            character_runtime=CharacterAgentRuntime(),
            siming_runtime=SimingRuntime(),
            actor_id="char_b",
        )
    except MixedPerceptionCaptureError as exc:
        mixed_rejected = True
        mixed_error = str(exc)

    lineage = {
        "fact": fact.model_dump(),
        "character_frame": character_frame,
        "character_bundle": character_bundle,
        "siming_frame": siming_frame,
        "vla_request": request.model_dump(),
        "vla_late_advisory_result": late_result.model_dump(),
        "mixed_capture_fact": mixed_fact.model_dump(),
        "mixed_capture_rejection": mixed_error,
    }
    lineage_path = log_dir / "perception-capture-clock-lineage.json"
    write_json(lineage_path, lineage)

    results = [
        _result(
            "fact_and_bundle_same_capture_tick",
            "Fact chain and canonical bundle share capture_root_id and monotonic tick",
            same_capture_tick(fact, character_bundle),
            [str(lineage_path)],
        ),
        _result(
            "character_and_siming_capture_ids_are_private_projections",
            "Character and Siming share root capture while retaining different capture_id values",
            character_frame.get("capture_root_id") == siming_frame.get("capture_root_id")
            and character_frame.get("capture_id") != siming_frame.get("capture_id"),
            [str(lineage_path)],
        ),
        _result(
            "vla_timeout_is_late_advisory",
            "VLA slow path timeout keeps original capture identity and marks the result as late advisory",
            late_result.capture_root_id == fact.capture_root_id
            and late_result.monotonic_tick == fact.monotonic_tick
            and late_result.capture_relation == "late_advisory"
            and late_result.advisory is True,
            [str(lineage_path)],
        ),
        _result(
            "mixed_capture_batch_rejected",
            "Mixed capture batches are rejected instead of being silently synthesized into a new capture",
            mixed_rejected,
            [str(lineage_path)],
            mixed_error,
        ),
    ]
    overall_passed = all(entry["status"] == "proved" for entry in results)
    report = {
        "results": results,
        "overall_perception_capture_clock_contract_passed": overall_passed,
        "artifacts": {"lineage": str(lineage_path)},
    }
    report_json = log_dir / "perception-capture-clock-contract-report.json"
    report_md = log_dir / "perception-capture-clock-contract-report.md"
    write_json(report_json, report)
    write_markdown(
        report_md,
        "Perception Capture Clock Contract Verification Report",
        report,
        "overall_perception_capture_clock_contract_passed",
    )
    print(f"perception_capture_clock_contract_report_json={report_json}")
    print(f"perception_capture_clock_contract_report_md={report_md}")
    print(f"overall_perception_capture_clock_contract_passed={overall_passed}")
    for entry in results:
        print(f"{entry['id']}={entry['status']}")
    return 0 if overall_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
