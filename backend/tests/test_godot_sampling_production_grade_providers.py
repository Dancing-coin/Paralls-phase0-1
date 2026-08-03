from __future__ import annotations

from pathlib import Path

from app.models.environment_field import EnvironmentFieldState
from app.models.raw_fact import RawFactEvent, RawFactObservability, RawFactSource, RawFactTargets, RawFactWorld
from app.services.character_agent_runtime import CharacterAgentRuntime
from app.services.siming_runtime import SimingRuntime
from app.world_runtime.intelligence_upgrade import PerceptionQueryFrame, SampleInputRef, SpatialReference, TimeWindow
from app.world_runtime.l1_occupancy import SpatialOccupancyService
from app.world_runtime.l1_runtime_perception_bridge import L1RuntimePerceptionBridge
from app.world_runtime.l1_space_model import SceneSpaceModelExtractor


ROOT = Path(__file__).resolve().parents[2]


def _provider_entry(kind: str, ref_id: str, retention: str = "ref_only") -> dict[str, object]:
    return {
        "provider_kind": kind,
        "ref_id": ref_id,
        "summary": f"{kind} production provider sample",
        "retention": retention,
        "sample_status": "ok",
        "freshness": "fresh",
        "throttle_state": "allowed",
        "stable_source_ref": ref_id.rsplit("/", 1)[0],
        "runtime_source_refs": [ref_id],
        "failure_status": "none",
        "expires_at": 1000,
    }


def test_six_provider_refs_have_status_freshness_throttle_and_retention() -> None:
    entries = [
        _provider_entry("visual_patch", "runtime://camera/MainCamera/frame/1", "debug_artifact"),
        _provider_entry("spatial_patch", "runtime://space/zone_focus/occupancy/1"),
        _provider_entry("auditory_context", "runtime://auditory/char_b/window/1"),
        _provider_entry("embodied_state", "runtime://embodied/char_b/state/1"),
        _provider_entry("skeletal_state", "runtime://embodied_skeletal/char_b/high_mid/1"),
        _provider_entry("environment_field", "runtime://environment/zone_focus/field/1"),
    ]

    refs = [SampleInputRef(**entry) for entry in entries]

    assert {ref.provider_kind for ref in refs} == {
        "visual_patch",
        "spatial_patch",
        "auditory_context",
        "embodied_state",
        "skeletal_state",
        "environment_field",
    }
    assert all(ref.freshness == "fresh" for ref in refs)
    assert all(ref.throttle_state == "allowed" for ref in refs)
    assert all(ref.failure_status == "none" for ref in refs)


def test_pqf_accepts_skeletal_and_environment_refs_without_sharing_context() -> None:
    frame = PerceptionQueryFrame(
        query_id="pqf:char_b:1",
        consumer_kind="character",
        subject_id="char_b",
        time_window=TimeWindow(started_at=0, ended_at=1),
        spatial_reference=SpatialReference(room_id="room_demo", scene_id="scene_demo", zone_id="zone_focus"),
        visual_inputs=[SampleInputRef(**_provider_entry("visual_patch", "runtime://camera/MainCamera/frame/1"))],
        spatial_inputs=[SampleInputRef(**_provider_entry("spatial_patch", "runtime://space/zone_focus/occupancy/1"))],
        auditory_inputs=[SampleInputRef(**_provider_entry("auditory_context", "runtime://auditory/char_b/window/1"))],
        embodied_inputs=[SampleInputRef(**_provider_entry("embodied_state", "runtime://embodied/char_b/state/1"))],
        skeletal_inputs=[SampleInputRef(**_provider_entry("skeletal_state", "runtime://embodied_skeletal/char_b/high_mid/1"))],
        environment_inputs=[SampleInputRef(**_provider_entry("environment_field", "runtime://environment/zone_focus/field/1"))],
        multimodal_context_id="character_mm:char_b",
        cache_namespace="character_mm:char_b:godot_sampling_cache",
    )

    assert len(frame.skeletal_inputs) == 1
    assert len(frame.environment_inputs) == 1
    assert "shared" not in frame.cache_namespace


def test_pqf_preserves_known_godot_grounding_catalog() -> None:
    frame = PerceptionQueryFrame(
        query_id="pqf:char_b:grounding",
        consumer_kind="character",
        subject_id="char_b",
        target_ref="obj_letter",
        world_anchor_id="world_anchor:object:obj_letter",
        time_window=TimeWindow(started_at=0, ended_at=1),
        spatial_reference=SpatialReference(room_id="room_demo", scene_id="scene_demo", zone_id="zone_focus"),
        grounding_collider_refs=["collision_shape:/root/MainDemo/ThroneRoomCollisionRoot"],
        grounding_affordance_refs=["inspect", "read"],
        multimodal_context_id="character_mm:char_b",
        cache_namespace="character_mm:char_b:godot_sampling_cache",
    )

    assert {"char_b", "obj_letter"}.issubset(frame.grounding_entity_refs)
    assert frame.grounding_collider_refs == ["collision_shape:/root/MainDemo/ThroneRoomCollisionRoot"]
    assert frame.grounding_anchor_refs == ["world_anchor:object:obj_letter"]
    assert frame.grounding_affordance_refs == ["inspect", "read"]


def test_provider_refs_are_consumed_by_l1_bridge_and_kept_refs_only(tmp_path: Path) -> None:
    extractor = SceneSpaceModelExtractor(artifact_dir=tmp_path)
    space_model = extractor.extract_from_runtime_scene(
        room_id="room_demo",
        scene_id="scene_demo",
        runtime_nodes=[
            {"node_path": "/root/MainDemo/ZoneFocus", "groups": ["l1_zone"], "metadata": {"l1_space_type": "zone", "zone_id": "zone_focus"}},
        ],
        artifact_name="godot-sampling-test-space.json",
    )
    occupancy = SpatialOccupancyService.from_space_model(space_model)
    occupancy.apply_actor_zone_update(
        actor_id="char_b",
        previous_zone_id="",
        next_zone_id="zone_focus",
        producer_ts=1,
        source_ref="raw_fact_event:actor_entered_zone:1",
    )
    occupancy.apply_environment_field(
        EnvironmentFieldState(
            field_id="field:room_demo:scene_demo:zone_focus",
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            light_level="low",
            visibility_level="reduced",
            producer_ts=1,
            updated_at=1,
        )
    )
    raw_fact = RawFactEvent(
        fact_family="spatial_access_fact",
        fact_type="actor_approached_object",
        relation_type="proximity",
        producer_ts=2,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        source=RawFactSource(layer="L1", system="godot_sampling_probe", actor_id="char_b"),
        targets=RawFactTargets(object_id="obj_letter"),
        world=RawFactWorld(distance_m=1.0, state_after="near"),
        observability=RawFactObservability(visual=True),
        subject_key="actor_approached_object",
    )
    provider_refs = {
        "visual_inputs": [_provider_entry("visual_patch", "runtime://camera/MainCamera/frame/2", "debug_artifact")],
        "spatial_inputs": [_provider_entry("spatial_patch", "runtime://space/zone_focus/occupancy/2")],
        "auditory_inputs": [_provider_entry("auditory_context", "runtime://auditory/char_b/window/2")],
        "embodied_inputs": [_provider_entry("embodied_state", "runtime://embodied/char_b/state/2")],
        "skeletal_inputs": [_provider_entry("skeletal_state", "runtime://embodied_skeletal/char_b/high_mid/2")],
        "environment_inputs": [_provider_entry("environment_field", "runtime://environment/zone_focus/field/2")],
    }

    result = L1RuntimePerceptionBridge().consume_projected_facts(
        occupancy=occupancy.snapshot(),
        projected_facts=[raw_fact],
        character_runtime=CharacterAgentRuntime(),
        siming_runtime=SimingRuntime(),
        actor_id="char_b",
        provider_refs=provider_refs,
    )

    assert result is not None
    assert result.character_frame["skeletal_inputs"][0]["provider_kind"] == "skeletal_state"
    assert result.character_frame["environment_inputs"][0]["provider_kind"] == "environment_field"
    assert result.character_bundle["raw_input_retention_policy"] == "refs_only"
    assert result.context_isolation["isolated"] is True


def test_godot_provider_scripts_forbid_heavy_work_and_authority_writes() -> None:
    for relative_path in [
        "scripts/character/VisualPatchProvider.gd",
        "scripts/character/SpatialPatchProvider.gd",
        "scripts/character/AuditoryContextProvider.gd",
        "scripts/character/EmbodiedStateProvider.gd",
        "scripts/character/SkeletalStateProviderRefEmitter.gd",
        "scripts/character/EnvironmentFieldProvider.gd",
    ]:
        text = (ROOT / relative_path).read_text(encoding="utf-8")
        assert "feeds_query_frame" in text
        assert "runtime_source_refs" in text
        assert "ProviderSampleBase" in text or relative_path.endswith("ProviderSampleBase.gd")
        assert "world_truth" not in text
        assert "esm" not in text.lower()
    assert "heavy_voxelization_allowed := false" in (ROOT / "scripts/character/EnvironmentFieldProvider.gd").read_text(encoding="utf-8")
