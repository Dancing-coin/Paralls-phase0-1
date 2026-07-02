from __future__ import annotations

from app.models.environment_field import EnvironmentFieldState
from app.services.esm_service import ESMService
from app.world_runtime.l1_occupancy import RuntimeSpatialOccupancyService, SpatialOccupancyService
from app.world_runtime.l1_space_model import SceneSpaceModelExtractor


def test_scene_space_model_extractor_uses_runtime_scene_refs_and_writes_artifact(tmp_path) -> None:
    extractor = SceneSpaceModelExtractor(artifact_dir=tmp_path)

    model = extractor.extract_from_runtime_scene(
        room_id="room_demo",
        scene_id="scene_demo",
        runtime_nodes=[
            {
                "node_path": "/root/MainDemo/ZoneFocus",
                "groups": ["l1_zone"],
                "metadata": {"l1_space_type": "zone", "zone_id": "zone_focus"},
            },
            {
                "node_path": "/root/MainDemo/StaticCover",
                "groups": ["l1_occluder"],
                "metadata": {"l1_space_type": "occluder", "element_id": "cover_1"},
                "collision_shape_ref": "collision_shape:/root/MainDemo/StaticCover/CollisionShape3D",
            },
            {
                "node_path": "/root/MainDemo/NavLaneA",
                "groups": ["l1_navigation_lane"],
                "metadata": {"l1_space_type": "navigation_lane", "element_id": "lane_focus"},
                "navigation_region_ref": "navigation_region:/root/MainDemo/NavigationRegion3D",
            },
            {
                "node_path": "/root/MainDemo/EnvLamp",
                "groups": ["l1_environment_anchor"],
                "metadata": {"l1_space_type": "environment_anchor", "element_id": "env_lamp"},
            },
            {
                "node_path": "/root/MainDemo/Letter",
                "groups": ["l1_interaction_object"],
                "metadata": {"l1_space_type": "interaction_object", "element_id": "obj_letter"},
                "collision_shape_ref": "collision_shape:/root/MainDemo/Letter/CollisionShape3D",
            },
            {
                "node_path": "/root/MainDemo/Wall",
                "groups": ["l1_static_obstacle"],
                "metadata": {"l1_space_type": "static_obstacle", "element_id": "wall_1"},
                "collision_shape_ref": "collision_shape:/root/MainDemo/Wall/CollisionShape3D",
            },
        ],
        artifact_name="l1-space-model-test.json",
    )

    element_types = {element.element_type for element in model.elements}
    assert {
        "zone",
        "static_obstacle",
        "occluder",
        "environment_anchor",
        "interaction_object",
        "navigation_lane",
    }.issubset(element_types)
    assert any(ref.startswith("node_path:") for element in model.elements for ref in element.source_refs)
    assert any("collision_shape:" in ref for element in model.elements for ref in element.source_refs)
    assert any("navigation_region:" in ref for element in model.elements for ref in element.source_refs)
    assert (tmp_path / "l1-space-model-test.json").exists()


def test_spatial_occupancy_service_tracks_dirty_zone_incremental_updates() -> None:
    model = SceneSpaceModelExtractor().extract_from_runtime_scene(
        room_id="room_demo",
        scene_id="scene_demo",
        runtime_nodes=[
            {
                "node_path": "/root/MainDemo/ZoneFocus",
                "groups": ["l1_zone"],
                "metadata": {"l1_space_type": "zone", "zone_id": "zone_focus"},
            },
            {
                "node_path": "/root/MainDemo/Letter",
                "groups": ["l1_interaction_object"],
                "metadata": {"l1_space_type": "interaction_object", "element_id": "obj_letter"},
                "collision_shape_ref": "collision_shape:/root/MainDemo/Letter/CollisionShape3D",
            },
        ],
    )
    service = SpatialOccupancyService.from_space_model(model)

    service.apply_actor_zone_update(
        actor_id="char_b",
        previous_zone_id="",
        next_zone_id="zone_focus",
        producer_ts=100,
        source_ref="raw_fact_event:actor_entered_zone:100",
    )
    service.apply_actor_proximity_update(
        actor_id="char_b",
        target_object_id="obj_letter",
        distance_m=1.8,
        producer_ts=110,
        source_ref="raw_fact_event:actor_approached_object:110",
    )
    service.apply_actor_proximity_update(
        actor_id="char_b",
        target_object_id="obj_letter",
        producer_ts=111,
        source_ref="raw_fact_event:actor_left_object_range:111",
        is_near=False,
    )
    service.apply_environment_field(
        EnvironmentFieldState(
            field_id="field:room_demo:scene_demo:zone_focus",
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            smoke_density="dense",
            visibility_level="reduced",
            producer_ts=120,
            updated_at=120,
            source_environment_id="env_lamp",
        )
    )
    service.apply_object_state_update(
        object_id="obj_letter",
        zone_id="zone_focus",
        state="visible",
        affordances=["inspect", "read"],
        occludes=False,
        producer_ts=130,
        source_ref="object_state_result:obj_letter:130",
    )
    service.apply_object_state_update(
        object_id="obj_letter",
        zone_id="zone_focus",
        state="rolled_back",
        affordances=["inspect"],
        occludes=False,
        producer_ts=131,
        source_ref="object_state_rollback:obj_letter:131",
    )
    service.apply_temporary_blocker_update(
        zone_id="zone_focus",
        blocker_id="spill_1",
        active=True,
        producer_ts=132,
        source_ref="temporary_blocker:spill_1:132",
    )
    service.apply_temporary_blocker_update(
        zone_id="zone_focus",
        blocker_id="spill_1",
        active=False,
        producer_ts=133,
        source_ref="temporary_blocker:spill_1:133",
    )
    service.apply_actor_zone_update(
        actor_id="char_b",
        previous_zone_id="zone_focus",
        next_zone_id="",
        producer_ts=134,
        source_ref="raw_fact_event:actor_left_zone:134",
    )

    snapshot = service.snapshot()

    assert snapshot.full_scene_rescan_count == 0
    assert snapshot.dirty_zone_ids == ["zone_focus"]
    assert snapshot.zone_states["zone_focus"].actor_ids == []
    assert snapshot.zone_states["zone_focus"].visibility == "reduced"
    assert snapshot.zone_states["zone_focus"].passability == "requires_detour"
    assert snapshot.object_states["obj_letter"].affordances == ["inspect"]
    assert any(event.update_kind == "environment_field_changed" for event in snapshot.dirty_events)
    assert any(event.update_kind == "actor_left_zone" for event in snapshot.dirty_events)
    assert any(event.update_kind == "actor_proximity_cleared" for event in snapshot.dirty_events)
    assert any(event.update_kind == "temporary_blocker_added" for event in snapshot.dirty_events)
    assert any(event.update_kind == "temporary_blocker_removed" for event in snapshot.dirty_events)


def test_esm_environment_result_can_update_l1_occupancy_field() -> None:
    esm = ESMService()
    result = esm.emit_environment_shift(
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        actor_id="char_c",
        target_environment_id="env_lamp",
        previous_state="stable",
        current_state="alerted",
        producer_ts=200,
    )
    service = SpatialOccupancyService()

    service.apply_environment_result(result)
    snapshot = service.snapshot()

    assert snapshot.zone_states["zone_focus"].environment_field_ref == result.field_id
    assert snapshot.zone_states["zone_focus"].visibility == "reduced"
    assert snapshot.zone_states["zone_focus"].passability == "requires_detour"
    assert snapshot.dirty_events[-1].source_refs == [result.result_id]


def test_legacy_runtime_spatial_occupancy_import_remains_compatible() -> None:
    assert RuntimeSpatialOccupancyService is SpatialOccupancyService
