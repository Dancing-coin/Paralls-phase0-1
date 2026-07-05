from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.models.raw_fact import RawFactEvent, RawFactObservability, RawFactSource, RawFactTargets, RawFactWorld
from app.services.authority_event_bus import InMemoryAuthorityEventBus
from app.services.character_agent_runtime import CharacterAgentRuntime
from app.services.siming_audit_writer import SimingAuditWriter
from app.services.siming_event_consumer import SimingEventConsumer
from app.services.siming_event_pipeline import SimingEventPipeline
from app.services.siming_event_producer import SimingEventProducer
from app.services.siming_runtime import SimingRuntime
from app.world_runtime.l1_occupancy import SpatialOccupancyService
from app.world_runtime.l1_runtime_perception_bridge import L1RuntimePerceptionBridge
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
    capture_root_id = "capture_root:godot_main:room_demo:scene_demo:zone_focus:123"
    world_anchor_id = "world_anchor:object:obj_letter"

    occupancy = SpatialOccupancyService()
    occupancy.apply_actor_zone_update(
        actor_id="char_b",
        previous_zone_id="",
        next_zone_id="zone_focus",
        producer_ts=100,
        source_ref="raw_fact_event:actor_entered_zone:char_b:100",
    )
    occupancy.apply_object_state_update(
        object_id="obj_letter",
        zone_id="zone_focus",
        state="visible",
        affordances=["inspect"],
        occludes=False,
        producer_ts=101,
        source_ref="object_state_result:obj_letter:101",
    )
    raw_fact = RawFactEvent(
        fact_family="spatial_access_fact",
        fact_type="actor_approached_object",
        relation_type="proximity",
        producer_ts=930,
        capture_root_id=capture_root_id,
        clock_domain="godot_main",
        monotonic_tick=123,
        source_frame_index=17,
        wall_clock_ts=930,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        source=RawFactSource(layer="L1", system="verify.downstream_identity", actor_id="char_b"),
        targets=RawFactTargets(object_id="obj_letter"),
        world_anchor_id=world_anchor_id,
        world=RawFactWorld(distance_m=1.1, state_after="near"),
        observability=RawFactObservability(visual=True),
    )

    bus = InMemoryAuthorityEventBus()
    character_runtime = CharacterAgentRuntime()
    siming_pipeline = SimingEventPipeline(
        bus=bus,
        consumer=SimingEventConsumer(),
        runtime=SimingRuntime(),
        producer=SimingEventProducer(bus),
        audit_writer=SimingAuditWriter(),
    )
    bridge_result = L1RuntimePerceptionBridge().consume_projected_facts(
        occupancy=occupancy.snapshot(),
        projected_facts=[raw_fact],
        character_runtime=character_runtime,
        siming_runtime=siming_pipeline,
        actor_id="char_b",
    )
    if bridge_result is None:
        raise RuntimeError("bridge did not produce downstream identity trace")

    observatory_messages = siming_pipeline.drain_observatory_messages()
    read_models = siming_pipeline.list_read_models(room_id="room_demo")
    trace = {
        "bridge_result": bridge_result.model_dump(mode="json"),
        "siming_observatory_messages": observatory_messages,
        "siming_read_models": [model.model_dump(mode="json") for model in read_models],
        "authority_event_bus": [event.model_dump(mode="json") for event in bus.list_events(room_id="room_demo")],
    }
    trace_path = log_dir / "perception-downstream-identity-propagation.json"
    write_json(trace_path, trace)

    character_identity = bridge_result.character_private_snapshot.get("recent_perception_identity", {})
    working_memory_identity = (
        bridge_result.character_working_memory.get("private_snapshot", {}).get("recent_perception_identity", {})
    )
    siming_read_identity = bridge_result.siming_result["read_model"]["current_state"].get("perception_identity", {})
    siming_output_identity = bridge_result.siming_result["outputs"][0]["payload"].get("perception_identity", {})
    debug_identity = observatory_messages[-1]["payload"].get("perception_identity", {}) if observatory_messages else {}
    authority_events = bus.list_events(room_id="room_demo")

    results = [
        _result(
            "character-private-snapshot-identity",
            "Character private snapshot retains capture and object identity",
            character_identity.get("capture_root_id") == capture_root_id
            and character_identity.get("world_anchor_id") == world_anchor_id,
            [str(trace_path)],
        ),
        _result(
            "character-working-memory-identity",
            "Character working memory exposes the private snapshot perception identity",
            working_memory_identity.get("capture_root_id") == capture_root_id
            and working_memory_identity.get("world_anchor_id") == world_anchor_id,
            [str(trace_path)],
        ),
        _result(
            "siming-read-model-identity",
            "Siming read model retains capture and object identity",
            siming_read_identity.get("capture_root_id") == capture_root_id
            and siming_read_identity.get("world_anchor_id") == world_anchor_id
            and read_models
            and read_models[-1].current_state["perception_identity"]["capture_root_id"] == capture_root_id,
            [str(trace_path)],
        ),
        _result(
            "siming-output-and-debug-identity",
            "Siming outputs and debug payloads retain perception identity metadata",
            siming_output_identity.get("capture_root_id") == capture_root_id
            and debug_identity.get("capture_root_id") == capture_root_id,
            [str(trace_path)],
        ),
        _result(
            "authority-bus-not-public-capture-main-identity",
            "Canonical bundle ingestion does not publish capture_id as an authority event identity",
            authority_events == [],
            [str(trace_path)],
            "Bridge-to-Siming bundle ingestion records read models only; no authority events are published in this path.",
        ),
    ]
    overall = all(entry["status"] == "proved" for entry in results)
    report = {
        "overall_perception_downstream_identity_propagation_passed": overall,
        "results": results,
        "artifacts": {"trace": str(trace_path)},
    }
    report_json = log_dir / "perception-downstream-identity-propagation-report.json"
    report_md = log_dir / "perception-downstream-identity-propagation-report.md"
    write_json(report_json, report)
    write_markdown(
        report_md,
        "Perception Downstream Identity Propagation Verification Report",
        report,
        "overall_perception_downstream_identity_propagation_passed",
    )
    print(f"perception_downstream_identity_propagation_report_json={report_json}")
    print(f"perception_downstream_identity_propagation_report_md={report_md}")
    print(f"overall_perception_downstream_identity_propagation_passed={overall}")
    for entry in results:
        print(f"{entry['id']}={entry['status']}")
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())
