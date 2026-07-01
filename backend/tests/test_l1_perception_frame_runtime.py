from __future__ import annotations

from app.services.character_agent_runtime import CharacterAgentRuntime
from app.services.siming_runtime import SimingRuntime
from app.world_runtime.intelligence_upgrade import SampleInputRef
from app.world_runtime.l1_perception_frame import L1PerceptionFrameService


def test_perception_frame_uses_runtime_refs_and_builds_character_bundle() -> None:
    service = L1PerceptionFrameService()

    frame = service.build_character_frame(
        subject_id="char_b",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        started_at=100,
        ended_at=120,
        visual_inputs=[
            SampleInputRef(
                provider_kind="visual_patch",
                ref_id="runtime://camera/MainCamera/frame/120",
                summary="camera pose and viewport capture",
                retention="debug_artifact",
            )
        ],
        spatial_inputs=[
            SampleInputRef(
                provider_kind="spatial_patch",
                ref_id="runtime://space/zone_focus/occupancy/120",
                summary="dirty-zone occupancy patch",
            )
        ],
        structured_fact_refs=["raw_fact_event:spatial_access_fact:line_of_sight_blocked:120"],
        attention_target_object_ids=["obj_letter"],
    )
    bundle = service.build_canonical_bundle(
        frame,
        local_spatial_state={"visibility": "reduced", "passability": "requires_detour"},
        target_state={"target_ref": "obj_letter", "los": "blocked"},
        environment_state={"visibility_level": "reduced", "smoke_density": "dense"},
    )

    assert frame.multimodal_context_id == "character_mm:char_b"
    assert frame.cache_namespace == "character_mm:char_b:l1_world_fact_cache"
    assert frame.visual_inputs[0].ref_id.startswith("runtime://camera/")
    assert bundle.consumer_kind == "character"
    assert bundle.local_spatial_state["passability"] == "requires_detour"


def test_character_runtime_consumes_canonical_percept_bundle_into_private_snapshot_and_memory() -> None:
    frame_service = L1PerceptionFrameService()
    runtime = CharacterAgentRuntime()
    frame = frame_service.build_character_frame(
        subject_id="char_b",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        started_at=100,
        ended_at=120,
        visual_inputs=[
            SampleInputRef(provider_kind="visual_patch", ref_id="runtime://camera/MainCamera/frame/120")
        ],
        structured_fact_refs=["raw_fact_event:spatial_access_fact:target_unreachable:120"],
        attention_target_object_ids=["obj_letter"],
    )
    bundle = frame_service.build_canonical_bundle(
        frame,
        local_spatial_state={"passability": "requires_detour"},
        target_state={"target_ref": "obj_letter", "reachable": False},
        environment_state={"visibility_level": "reduced"},
        uncertainty={"reason": "smoke occlusion"},
    )

    snapshot = runtime.ingest_canonical_percept_bundle(bundle)
    timeline = runtime.get_session_timeline("char_b")
    working_memory = runtime.get_working_memory_state("char_b", snapshot.model_dump())

    assert snapshot.current_attention_targets == ["obj_letter"]
    assert "raw_fact_event:spatial_access_fact:target_unreachable:120" in snapshot.recent_world_changes
    assert snapshot.local_spatial_confidence_map["obj_letter"] == 0.75
    assert any(entry["event_type"] == "canonical_percept_bundle" for entry in timeline)
    assert working_memory["private_snapshot"]["recent_world_changes"]


def test_siming_runtime_consumes_global_bundle_without_sharing_character_context() -> None:
    frame_service = L1PerceptionFrameService()
    runtime = SimingRuntime()
    frame = frame_service.build_siming_frame(
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        started_at=100,
        ended_at=150,
        environment_inputs=[
            SampleInputRef(provider_kind="spatial_patch", ref_id="runtime://space/zone_focus/global/150")
        ],
        structured_fact_refs=["raw_fact_event:spatial_access_fact:line_of_sight_blocked:150"],
    )
    bundle = frame_service.build_canonical_bundle(
        frame,
        local_spatial_state={"zone_id": "zone_focus"},
        target_state={"affected_actors": ["char_b"]},
        environment_state={"visibility_level": "reduced"},
    )

    result = runtime.ingest_canonical_percept_bundle(bundle)

    assert bundle.percept_context_id.startswith("siming_mm:")
    assert "character_mm" not in bundle.percept_context_id
    assert result.outputs[0].output_type == "fairness_snapshot"
    assert result.outputs[1].output_type == "intervention_candidate"
    assert result.read_model is not None
    assert result.read_model.current_state["source_bundle_id"] == bundle.bundle_id
