from __future__ import annotations

from app.models.environment_field import EnvironmentFieldState
from app.services.candidate_percept_service import compile_candidate_percepts
from app.services.per_character_percept_filter import filter_candidate_for_actor
from app.world_runtime.l1_fact_projection import FactProjectionLayer
from app.world_runtime.l1_occupancy import SpatialOccupancyService


def test_projection_emits_los_reachability_affordance_and_negative_raw_fact_events() -> None:
    occupancy = SpatialOccupancyService()
    occupancy.apply_actor_zone_update(
        actor_id="char_b",
        previous_zone_id="",
        next_zone_id="zone_focus",
        producer_ts=100,
        source_ref="raw_fact_event:actor_entered_zone:100",
    )
    occupancy.apply_actor_proximity_update(
        actor_id="char_b",
        target_object_id="obj_letter",
        distance_m=2.0,
        producer_ts=101,
        source_ref="raw_fact_event:actor_approached_object:101",
    )
    occupancy.apply_environment_field(
        EnvironmentFieldState(
            field_id="field:room_demo:scene_demo:zone_focus",
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            smoke_density="dense",
            visibility_level="reduced",
            producer_ts=102,
            updated_at=102,
            source_environment_id="env_lamp",
        )
    )
    occupancy.apply_object_state_update(
        object_id="obj_letter",
        zone_id="zone_focus",
        state="visible",
        affordances=["inspect"],
        occludes=True,
        producer_ts=103,
        source_ref="object_state_result:obj_letter:103",
    )
    projection = FactProjectionLayer()

    facts = projection.project_actor_target_facts(
        occupancy.snapshot(),
        actor_id="char_b",
        target_object_id="obj_letter",
        producer_ts=110,
    )
    missing_facts = projection.project_actor_target_facts(
        occupancy.snapshot(),
        actor_id="char_b",
        target_object_id="obj_missing",
        producer_ts=111,
    )

    fact_types = {fact.fact_type for fact in [*facts, *missing_facts]}
    assert "line_of_sight_blocked" in fact_types
    assert "target_unreachable" in fact_types
    assert "interaction_affordance_changed" in fact_types
    assert "expected_target_missing" in fact_types
    assert all(fact.event_type == "raw_fact_event" for fact in facts)
    assert all(fact.fact_family == "spatial_access_fact" for fact in facts)
    object_target_fact_types = {
        "line_of_sight_blocked",
        "target_unreachable",
        "interaction_affordance_changed",
        "expected_target_missing",
    }
    for fact in [*facts, *missing_facts]:
        if fact.fact_type in object_target_fact_types:
            assert fact.source.actor_id == "char_b"
            assert fact.targets.actor_id == ""
            assert fact.targets.object_id.startswith("obj_")


def test_projected_fact_enters_candidate_and_private_percept_path() -> None:
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
            producer_ts=102,
            updated_at=102,
            source_environment_id="env_lamp",
        )
    )
    projection = FactProjectionLayer()
    [blocked_fact] = [
        fact
        for fact in projection.project_actor_target_facts(
            occupancy.snapshot(),
            actor_id="char_b",
            target_actor_id="char_c",
            producer_ts=110,
        )
        if fact.fact_type == "line_of_sight_blocked"
    ]

    candidates = compile_candidate_percepts(blocked_fact)
    perceived = filter_candidate_for_actor(candidates[0], actor_id="char_b")

    assert candidates[0].percept_channel == "spatial"
    assert candidates[0].source_fact_type == "line_of_sight_blocked"
    assert candidates[0].source_actor_id == "char_b"
    assert candidates[0].target_actor_id == "char_c"
    assert filter_candidate_for_actor(candidates[0], actor_id="char_b") is None
    perceived = filter_candidate_for_actor(candidates[0], actor_id="char_c")
    assert perceived is not None
    assert perceived.perceived_summary == "spatial_access_fact/line_of_sight_blocked"


def test_projection_emits_los_restored_after_environment_clears() -> None:
    occupancy = SpatialOccupancyService()
    projection = FactProjectionLayer()
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
    projection.project_actor_target_facts(
        occupancy.snapshot(),
        actor_id="char_b",
        target_object_id="obj_letter",
        producer_ts=102,
    )
    occupancy.apply_environment_field(
        EnvironmentFieldState(
            field_id="field:room_demo:scene_demo:zone_focus",
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            visibility_level="clear",
            smoke_density="clear",
            producer_ts=103,
            updated_at=103,
            source_environment_id="env_lamp",
        )
    )

    facts = projection.project_actor_target_facts(
        occupancy.snapshot(),
        actor_id="char_b",
        target_object_id="obj_letter",
        producer_ts=104,
    )

    assert "line_of_sight_restored" in {fact.fact_type for fact in facts}
