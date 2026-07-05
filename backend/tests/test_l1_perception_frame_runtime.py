from __future__ import annotations

import pytest

from app.services.character_agent_runtime import CharacterAgentRuntime
from app.services.authority_event_bus import InMemoryAuthorityEventBus
from app.services.siming_audit_writer import SimingAuditWriter
from app.services.siming_event_consumer import SimingEventConsumer
from app.services.siming_event_pipeline import SimingEventPipeline
from app.services.siming_event_producer import SimingEventProducer
from app.services.siming_runtime import SimingRuntime
from app.ws_protocol import Envelope
from app.models.environment_field import EnvironmentFieldState
from app.models.capture_clock import same_capture_tick
from app.models.raw_fact import RawFactEvent, RawFactObservability, RawFactSource, RawFactTargets, RawFactWorld
from app.world_runtime.l1_fact_projection import FactProjectionLayer
from app.world_runtime.l1_occupancy import SpatialOccupancyService
from app.world_runtime.intelligence_upgrade import PerceptionInputFrame, SampleInputRef
from app.world_runtime.l1_perception_frame import L1PerceptionFrameService
from app.world_runtime.l1_runtime_perception_bridge import (
    L1ActorProjectionInput,
    L1RuntimePerceptionBridge,
    MixedPerceptionCaptureError,
)


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


def test_perception_input_frame_is_explicit_runtime_input_boundary() -> None:
    service = L1PerceptionFrameService()
    input_frame = service.build_character_input_frame(
        subject_id="char_b",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        started_at=1000,
        ended_at=1010,
        capture_root_id="capture_root:godot_main:room_demo:scene_demo:zone_focus:44",
        clock_domain="godot_main",
        monotonic_tick=44,
        source_frame_index=9,
        wall_clock_ts=1000,
        visual_inputs=[SampleInputRef(provider_kind="visual_patch", ref_id="runtime://camera/MainCamera/frame/9")],
        attention_target_object_ids=["obj_letter"],
    )

    frame = service.build_frame_from_input(input_frame)

    assert isinstance(input_frame, PerceptionInputFrame)
    assert input_frame.capture_root_id == "capture_root:godot_main:room_demo:scene_demo:zone_focus:44"
    assert input_frame.capture_id.endswith(":character:char_b")
    assert frame.capture_root_id == input_frame.capture_root_id
    assert frame.capture_id == input_frame.capture_id
    assert frame.world_anchor_id == "world_anchor:object:obj_letter"


def test_perception_input_frame_can_resolve_world_anchor_from_source_lineage() -> None:
    service = L1PerceptionFrameService()
    input_frame = service.build_character_input_frame(
        subject_id="char_b",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        started_at=1000,
        ended_at=1010,
        source_ref_lineage=["artifact://crop/obj_letter/view_001.png"],
        visual_inputs=[SampleInputRef(provider_kind="visual_patch", ref_id="runtime://camera/MainCamera/frame/9")],
    )

    assert input_frame.world_anchor_id == "world_anchor:object:obj_letter"


def test_perception_frame_propagates_capture_clock_to_samples_and_bundle() -> None:
    service = L1PerceptionFrameService()

    frame = service.build_character_frame(
        subject_id="char_b",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        started_at=1000,
        ended_at=1010,
        capture_root_id="capture_root:godot_main:room_demo:scene_demo:zone_focus:44",
        clock_domain="godot_main",
        monotonic_tick=44,
        source_frame_index=9,
        wall_clock_ts=1000,
        visual_inputs=[SampleInputRef(provider_kind="visual_patch", ref_id="runtime://camera/MainCamera/frame/9")],
    )
    bundle = service.build_canonical_bundle(
        frame,
        local_spatial_state={},
        target_state={},
        environment_state={},
    )
    wall_clock_shifted = bundle.model_copy(update={"wall_clock_ts": 999999})

    assert frame.capture_root_id == "capture_root:godot_main:room_demo:scene_demo:zone_focus:44"
    assert frame.capture_id.endswith(":character:char_b")
    assert frame.visual_inputs[0].capture_root_id == frame.capture_root_id
    assert frame.visual_inputs[0].capture_id == frame.capture_id
    assert frame.visual_inputs[0].monotonic_tick == 44
    assert frame.visual_inputs[0].sample_ref_id.startswith("sample_ref:visual_patch:")
    assert bundle.capture_root_id == frame.capture_root_id
    assert same_capture_tick(frame, wall_clock_shifted)


def test_perception_frame_enriches_bundle_with_world_anchor_identity() -> None:
    service = L1PerceptionFrameService()
    frame = service.build_character_frame(
        subject_id="char_b",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        started_at=100,
        ended_at=120,
        structured_fact_refs=["sample_ref:spatial_access_fact:abc"],
        attention_target_object_ids=["obj_letter"],
    )
    bundle = service.build_canonical_bundle(
        frame,
        local_spatial_state={},
        target_state={"summary": "letter visible"},
        environment_state={},
    )

    assert frame.target_ref == "obj_letter"
    assert frame.world_anchor_id == "world_anchor:object:obj_letter"
    assert bundle.target_state["target_ref"] == "obj_letter"
    assert bundle.target_state["world_anchor_id"] == "world_anchor:object:obj_letter"
    assert "sample_ref:spatial_access_fact:abc" in bundle.target_state["source_ref_lineage"]


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
    assert snapshot.recent_perception_identity["capture_root_id"] == bundle.capture_root_id
    assert snapshot.recent_perception_identity["capture_id"] == bundle.capture_id
    assert snapshot.recent_perception_identity["world_anchor_id"] == bundle.world_anchor_id
    assert snapshot.recent_perception_identity["target_ref"] == "obj_letter"
    assert any(entry["event_type"] == "canonical_percept_bundle" for entry in timeline)
    assert working_memory["private_snapshot"]["recent_world_changes"]
    assert working_memory["private_snapshot"]["recent_perception_identity"]["capture_root_id"] == bundle.capture_root_id


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
    assert result.outputs[0].payload["perception_identity"]["capture_root_id"] == bundle.capture_root_id
    assert result.outputs[1].payload["perception_identity"]["capture_id"] == bundle.capture_id
    assert result.read_model.current_state["perception_identity"]["capture_root_id"] == bundle.capture_root_id
    assert result.read_model.intervention_surface["perception_identity"]["capture_id"] == bundle.capture_id
    debug_payload = runtime.drain_observatory_messages()[-1]["payload"]
    assert debug_payload["perception_identity"]["world_anchor_id"] == bundle.world_anchor_id


def test_l1_runtime_bridge_builds_pqf_and_consumes_bundles_from_projected_facts() -> None:
    occupancy = SpatialOccupancyService()
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
        affordances=["inspect"],
        occludes=True,
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
    projected_facts = FactProjectionLayer().project_actor_target_facts(
        occupancy.snapshot(),
        actor_id="char_b",
        target_object_id="obj_letter",
        producer_ts=110,
    )

    bridge_result = L1RuntimePerceptionBridge().consume_projected_facts(
        occupancy=occupancy.snapshot(),
        projected_facts=projected_facts,
        character_runtime=CharacterAgentRuntime(),
        siming_runtime=SimingRuntime(),
        actor_id="char_b",
    )

    assert bridge_result is not None
    assert bridge_result.character_frame["multimodal_context_id"] == "character_mm:char_b"
    assert bridge_result.siming_frame["multimodal_context_id"].startswith("siming_mm:")
    assert bridge_result.context_isolation["isolated"] is True
    assert bridge_result.character_private_snapshot["current_attention_targets"] == ["obj_letter"]
    assert bridge_result.character_private_snapshot["recent_world_changes"]
    assert bridge_result.character_private_snapshot["recent_perception_identity"]["capture_root_id"] == bridge_result.character_bundle["capture_root_id"]
    assert bridge_result.character_private_snapshot["recent_perception_identity"]["world_anchor_id"] == bridge_result.character_bundle["world_anchor_id"]
    assert bridge_result.character_working_memory["private_snapshot"]["recent_world_changes"]
    assert bridge_result.character_working_memory["private_snapshot"]["recent_perception_identity"]["capture_id"] == bridge_result.character_bundle["capture_id"]
    assert bridge_result.siming_result["outputs"][0]["output_type"] == "fairness_snapshot"
    assert bridge_result.siming_result["read_model"]["current_state"]["source_bundle_id"].startswith("bundle:siming:")
    assert bridge_result.siming_result["read_model"]["current_state"]["perception_identity"]["capture_root_id"] == bridge_result.siming_bundle["capture_root_id"]
    assert bridge_result.siming_result["outputs"][0]["payload"]["perception_identity"]["world_anchor_id"] == bridge_result.siming_bundle["world_anchor_id"]


def test_l1_runtime_bridge_keeps_one_capture_root_with_actor_and_siming_capture_ids() -> None:
    occupancy = SpatialOccupancyService()
    occupancy.apply_actor_zone_update(
        actor_id="char_b",
        previous_zone_id="",
        next_zone_id="zone_focus",
        producer_ts=100,
        source_ref="raw_fact_event:actor_entered_zone:100",
    )
    raw_fact = RawFactEvent(
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
        source=RawFactSource(layer="L1", system="godot.runtime_probe", actor_id="char_b"),
        targets=RawFactTargets(object_id="obj_letter"),
        world=RawFactWorld(distance_m=1.2, state_after="near"),
        observability=RawFactObservability(visual=True),
    )

    bridge_result = L1RuntimePerceptionBridge().consume_projected_facts(
        occupancy=occupancy.snapshot(),
        projected_facts=[raw_fact],
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

    assert bridge_result is not None
    character_frame = bridge_result.character_frame
    siming_frame = bridge_result.siming_frame
    assert character_frame["capture_root_id"] == raw_fact.capture_root_id
    assert siming_frame["capture_root_id"] == raw_fact.capture_root_id
    assert character_frame["capture_id"].endswith(":character:char_b")
    assert siming_frame["capture_id"].endswith(":siming:siming")
    assert character_frame["capture_id"] != siming_frame["capture_id"]
    assert character_frame["monotonic_tick"] == 77
    assert character_frame["source_frame_index"] == 12
    assert character_frame["visual_inputs"][0]["capture_root_id"] == raw_fact.capture_root_id
    assert character_frame["world_anchor_id"] == raw_fact.world_anchor_id
    assert character_frame["target_ref"] == "obj_letter"
    assert bridge_result.character_bundle["capture_root_id"] == raw_fact.capture_root_id
    assert bridge_result.character_bundle["target_state"]["world_anchor_id"] == raw_fact.world_anchor_id
    assert raw_fact.sample_ref_id in bridge_result.character_bundle["target_state"]["source_ref_lineage"]
    assert bridge_result.siming_bundle["capture_root_id"] == raw_fact.capture_root_id
    assert bridge_result.character_private_snapshot["recent_perception_identity"]["capture_root_id"] == raw_fact.capture_root_id
    assert bridge_result.siming_result["read_model"]["current_state"]["perception_identity"]["capture_root_id"] == raw_fact.capture_root_id


def test_l1_runtime_bridge_builds_multi_actor_private_projections_under_shared_capture() -> None:
    occupancy = SpatialOccupancyService()
    for actor_id in ("char_a", "char_b"):
        occupancy.apply_actor_zone_update(
            actor_id=actor_id,
            previous_zone_id="",
            next_zone_id="zone_focus",
            producer_ts=100,
            source_ref=f"raw_fact_event:actor_entered_zone:{actor_id}:100",
        )
    shared_root = "capture_root:godot_main:room_demo:scene_demo:zone_focus:88"
    fact_a = RawFactEvent(
        fact_family="visual_fact",
        fact_type="object_visible",
        relation_type="actor_sees_object",
        producer_ts=910,
        capture_root_id=shared_root,
        clock_domain="godot_main",
        monotonic_tick=88,
        source_frame_index=14,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        source=RawFactSource(layer="L1", system="godot.runtime_probe", actor_id="char_a"),
        targets=RawFactTargets(object_id="obj_letter"),
        world_anchor_id="world_anchor:object:obj_letter",
        world=RawFactWorld(distance_m=1.0, state_after="visible"),
        observability=RawFactObservability(visual=True, occluded=False),
    )
    fact_b = RawFactEvent(
        fact_family="visual_fact",
        fact_type="object_partly_occluded",
        relation_type="actor_sees_object",
        producer_ts=911,
        capture_root_id=shared_root,
        clock_domain="godot_main",
        monotonic_tick=88,
        source_frame_index=14,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        source=RawFactSource(layer="L1", system="godot.runtime_probe", actor_id="char_b"),
        targets=RawFactTargets(object_id="obj_letter"),
        world_anchor_id="world_anchor:object:obj_letter",
        world=RawFactWorld(distance_m=2.4, state_after="partly_occluded"),
        observability=RawFactObservability(visual=True, occluded=True),
    )

    result = L1RuntimePerceptionBridge().consume_multi_actor_projected_facts(
        occupancy=occupancy.snapshot(),
        actor_projections=[
            L1ActorProjectionInput(
                actor_id="char_a",
                projected_facts=[fact_a],
                actor_frame_ref="actor_frame:char_a:88",
                camera_frame_ref="camera:char_a:88",
                listener_frame_ref="listener:char_a:88",
            ),
            L1ActorProjectionInput(
                actor_id="char_b",
                projected_facts=[fact_b],
                actor_frame_ref="actor_frame:char_b:88",
                camera_frame_ref="camera:char_b:88",
                listener_frame_ref="listener:char_b:88",
            ),
        ],
        character_runtime=CharacterAgentRuntime(),
        siming_runtime=SimingRuntime(),
    )

    assert result is not None
    char_a = result.actor_results["char_a"]
    char_b = result.actor_results["char_b"]
    assert result.capture_root_id == shared_root
    assert char_a["character_frame"]["capture_root_id"] == shared_root
    assert char_b["character_frame"]["capture_root_id"] == shared_root
    assert char_a["character_frame"]["capture_id"] != char_b["character_frame"]["capture_id"]
    assert char_a["character_frame"]["multimodal_context_id"] == "character_mm:char_a"
    assert char_b["character_frame"]["multimodal_context_id"] == "character_mm:char_b"
    assert char_a["character_frame"]["spatial_reference"]["camera_frame_ref"] == "camera:char_a:88"
    assert char_b["character_frame"]["spatial_reference"]["camera_frame_ref"] == "camera:char_b:88"
    assert char_a["character_bundle"]["target_state"]["world_anchor_id"] == "world_anchor:object:obj_letter"
    assert char_b["character_bundle"]["target_state"]["world_anchor_id"] == "world_anchor:object:obj_letter"
    assert char_a["character_private_snapshot"]["recent_perception_identity"]["capture_root_id"] == shared_root
    assert char_b["character_private_snapshot"]["recent_perception_identity"]["world_anchor_id"] == "world_anchor:object:obj_letter"
    assert char_a["character_bundle"]["uncertainty"]["occluded_fact_count"] == 0
    assert char_b["character_bundle"]["uncertainty"]["occluded_fact_count"] == 1
    assert result.multi_actor_patch["world_anchor_id"] == "world_anchor:object:obj_letter"
    assert result.siming_bundle["target_state"]["multi_actor_patch"]["world_anchor_id"] == "world_anchor:object:obj_letter"
    assert result.siming_result["read_model"]["current_state"]["perception_identity"]["world_anchor_id"] == "world_anchor:object:obj_letter"
    assert result.context_isolation["isolated"] is True
    assert result.context_isolation["siming_reads_character_private_context"] is False


def test_l1_runtime_bridge_siming_pipeline_consumption_persists_read_model() -> None:
    occupancy = SpatialOccupancyService()
    occupancy.apply_actor_zone_update(
        actor_id="char_b",
        previous_zone_id="",
        next_zone_id="zone_focus",
        producer_ts=100,
        source_ref="raw_fact_event:actor_entered_zone:100",
    )
    occupancy.apply_environment_field(
        EnvironmentFieldState(
            field_id="field:room_demo:scene_demo:zone_focus",
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            visibility_level="reduced",
            smoke_density="dense",
            producer_ts=101,
            updated_at=101,
            source_environment_id="env_lamp",
        )
    )
    projected_facts = FactProjectionLayer().project_actor_target_facts(
        occupancy.snapshot(),
        actor_id="char_b",
        target_actor_id="char_c",
        producer_ts=110,
    )
    bus = InMemoryAuthorityEventBus()
    pipeline = SimingEventPipeline(
        bus=bus,
        consumer=SimingEventConsumer(),
        runtime=SimingRuntime(),
        producer=SimingEventProducer(bus),
        audit_writer=SimingAuditWriter(),
    )

    bridge_result = L1RuntimePerceptionBridge().consume_projected_facts(
        occupancy=occupancy.snapshot(),
        projected_facts=projected_facts,
        character_runtime=CharacterAgentRuntime(),
        siming_runtime=pipeline,
        actor_id="char_b",
    )

    assert bridge_result is not None
    read_models = pipeline.list_read_models(room_id="room_demo")
    assert len(read_models) == 1
    assert read_models[0].derived_from_snapshot_ref == bridge_result.siming_bundle["bundle_id"]
    assert read_models[0].current_state["perception_identity"]["capture_root_id"] == bridge_result.siming_bundle["capture_root_id"]


def test_main_raw_fact_route_consumes_l1_projection_with_real_provider_refs() -> None:
    from app.debug_stream import debug_stream
    from app import main as backend_main

    backend_main.reset_runtime_state()
    provider_refs = {
        "visual_inputs": [
            {
                "provider_kind": "visual_patch",
                "ref_id": ".harness/verification/l1-visual-capture-runtime.png",
                "summary": "Godot runtime viewport capture artifact",
                "retention": "debug_artifact",
            }
        ],
        "spatial_inputs": [
            {
                "provider_kind": "spatial_patch",
                "ref_id": ".harness/verification/l1-occupancy-runtime.json",
                "summary": "Godot runtime dirty-zone occupancy artifact",
                "retention": "debug_artifact",
            }
        ],
        "auditory_inputs": [
            {
                "provider_kind": "auditory_context",
                "ref_id": "runtime://auditory/char_b/window/godot-probe",
                "summary": "Godot auditory source refs",
                "retention": "ref_only",
            }
        ],
        "embodied_inputs": [
            {
                "provider_kind": "embodied_state",
                "ref_id": "runtime://node/root/MainDemo/PlayerCharacter",
                "summary": "Godot actor node ref",
                "retention": "ref_only",
            }
        ],
    }

    backend_main.l1_occupancy_service.apply_object_state_update(
        object_id="obj_letter",
        zone_id="zone_focus",
        state="visible",
        affordances=["inspect", "read"],
        occludes=True,
        producer_ts=99,
        source_ref="object_state_result:obj_letter:99",
    )
    backend_main.l1_occupancy_service.apply_environment_field(
        EnvironmentFieldState(
            field_id="field:room_demo:scene_demo:zone_focus",
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            visibility_level="reduced",
            smoke_density="dense",
            producer_ts=100,
            updated_at=100,
            source_environment_id="env_lamp",
        )
    )
    raw_fact = RawFactEvent(
        fact_family="spatial_access_fact",
        fact_type="actor_approached_object",
        relation_type="proximity",
        producer_ts=101,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        source=RawFactSource(layer="L1", system="godot.runtime_probe", actor_id="char_b"),
        targets=RawFactTargets(object_id="obj_letter"),
        world=RawFactWorld(distance_m=1.2, state_after="near"),
        observability=RawFactObservability(visual=True),
        subject_key="actor_approached_object",
        causation_id="test:l1:provider_refs",
        correlation_id="test:l1:provider_refs",
    )
    payload = raw_fact.model_dump()
    payload["l1_provider_refs"] = provider_refs

    messages = backend_main._handle_envelope(Envelope(message_type="raw_fact_event", payload=payload))
    history = debug_stream.history()
    consumed_events = [
        event
        for event in history
        if event.get("stage") == "l1_canonical_percept_bundle_consumed"
    ]
    pqf_events = [
        event
        for event in history
        if event.get("stage") == "l1_perception_query_frame_assembled"
    ]

    assert any(message.get("message_type") == "ack" for message in messages)
    assert pqf_events
    assert consumed_events
    consumed_detail = consumed_events[-1]["detail"]
    assert consumed_detail["character_private_snapshot"]["current_attention_targets"] == ["obj_letter"]
    assert consumed_detail["character_private_snapshot"]["recent_perception_identity"]["world_anchor_id"] == consumed_detail["character_bundle"]["world_anchor_id"]
    assert "obj_letter" in consumed_detail["character_bundle"]["attention_state"]["target_object_ids"]
    assert consumed_detail["character_bundle"]["attention_state"]["target_actor_ids"] == []
    assert consumed_detail["character_frame"]["visual_inputs"][0]["ref_id"] == ".harness/verification/l1-visual-capture-runtime.png"
    assert consumed_detail["siming_result"]["read_model"]["derived_from_snapshot_ref"] == consumed_detail["siming_bundle"]["bundle_id"]
    assert consumed_detail["siming_result"]["read_model"]["current_state"]["perception_identity"]["capture_root_id"] == consumed_detail["siming_bundle"]["capture_root_id"]
    assert backend_main.character_agent_runtime.get_private_snapshot("char_b").current_attention_targets == ["obj_letter"]
    read_models = backend_main.siming_event_pipeline.list_read_models(room_id="room_demo")
    assert read_models
    assert read_models[-1].derived_from_snapshot_ref == consumed_detail["siming_bundle"]["bundle_id"]


def test_l1_runtime_bridge_rejects_mixed_capture_batches() -> None:
    bridge = L1RuntimePerceptionBridge()
    occupancy = SpatialOccupancyService()
    occupancy.apply_actor_zone_update(
        actor_id="char_b",
        previous_zone_id="",
        next_zone_id="zone_focus",
        producer_ts=100,
        source_ref="raw_fact_event:actor_entered_zone:100",
    )
    facts = [
        RawFactEvent(
            fact_family="visual_fact",
            fact_type="fixed_gaze_on_target",
            relation_type="actor_looks_at_object",
            producer_ts=1201,
            capture_root_id="capture_root:godot_main:room_demo:scene_demo:zone_focus:201",
            clock_domain="godot_main",
            monotonic_tick=201,
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            source=RawFactSource(layer="L1", system="test", actor_id="char_b"),
            targets=RawFactTargets(object_id="obj_letter"),
        ),
        RawFactEvent(
            fact_family="visual_fact",
            fact_type="object_partly_occluded",
            relation_type="actor_looks_at_object",
            producer_ts=1202,
            capture_root_id="capture_root:godot_main:room_demo:scene_demo:zone_focus:202",
            clock_domain="godot_main",
            monotonic_tick=202,
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            source=RawFactSource(layer="L1", system="test", actor_id="char_b"),
            targets=RawFactTargets(object_id="obj_letter"),
        ),
    ]

    with pytest.raises(MixedPerceptionCaptureError):
        bridge.consume_projected_facts(
            occupancy=occupancy.snapshot(),
            projected_facts=facts,
            character_runtime=CharacterAgentRuntime(),
            siming_runtime=SimingRuntime(),
            actor_id="char_b",
        )


def test_main_projected_fact_path_uses_multi_actor_bridge(monkeypatch) -> None:
    from app import main as backend_main

    backend_main.reset_runtime_state()
    called: dict[str, object] = {"multi": None, "single": False}

    class StubBridge:
        def consume_projected_facts(self, **_kwargs):
            called["single"] = True
            raise AssertionError("single-actor bridge path should not be used")

        def consume_multi_actor_projected_facts(self, **kwargs):
            called["multi"] = kwargs["actor_projections"]
            return None

    monkeypatch.setattr(backend_main, "l1_perception_bridge", StubBridge())
    facts = [
        RawFactEvent(
            fact_family="visual_fact",
            fact_type="fixed_gaze_on_target",
            relation_type="actor_looks_at_object",
            producer_ts=1300,
            capture_root_id="capture_root:godot_main:room_demo:scene_demo:zone_focus:300",
            clock_domain="godot_main",
            monotonic_tick=300,
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            source=RawFactSource(layer="L1", system="test", actor_id="char_a"),
            targets=RawFactTargets(object_id="obj_letter"),
        ),
        RawFactEvent(
            fact_family="visual_fact",
            fact_type="object_partly_occluded",
            relation_type="actor_looks_at_object",
            producer_ts=1301,
            capture_root_id="capture_root:godot_main:room_demo:scene_demo:zone_focus:300",
            clock_domain="godot_main",
            monotonic_tick=300,
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            source=RawFactSource(layer="L1", system="test", actor_id="char_b"),
            targets=RawFactTargets(object_id="obj_letter"),
        ),
    ]

    backend_main._messages_from_projected_l1_facts(facts, provider_refs=None)

    assert called["single"] is False
    projections = called["multi"]
    assert isinstance(projections, list)
    assert {projection.actor_id for projection in projections} == {"char_a", "char_b"}
