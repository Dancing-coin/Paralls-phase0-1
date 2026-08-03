from __future__ import annotations

import pytest

from app.models.embodied_interaction import SceneAffordanceRecord
from app.services.scene_affordance_registry import SceneAffordanceRegistry
from app.world_runtime.l1_occupancy import SpatialOccupancyService
from app.world_runtime.l1_space_model import SceneSpaceModelExtractor


def _space_model(*, collider_ref: str = "collider:chair_01:body"):
    return SceneSpaceModelExtractor().extract_from_runtime_scene(
        room_id="room_demo",
        scene_id="scene_demo",
        runtime_nodes=[
            {
                "node_path": "/root/MainDemo/Chair01",
                "groups": ["l1_interaction_object"],
                "metadata": {
                    "l1_space_type": "interaction_object",
                    "element_id": "entity:scene_demo:chair_01",
                    "semantic_tags": ["chair"],
                },
                "collision_shape_ref": collider_ref,
                "source_refs": [
                    "anchor:chair_01:stance",
                    "anchor:chair_01:contact",
                    "affordance:chair_01:kick",
                ],
            },
            {
                "node_path": "/root/MainDemo/L1NavigationRegion",
                "groups": ["l1_navigation_lane"],
                "metadata": {"l1_space_type": "navigation_lane", "element_id": "nav:chair_01:footprint"},
                "navigation_region_ref": "navigation_region:/root/MainDemo/L1NavigationRegion",
            },
        ],
    )


def _occupancy(*, updated_at: int = 110) -> SpatialOccupancyService:
    service = SpatialOccupancyService(field_id="occupancy:room_demo:scene_demo", static_model_ref="scene_space:room_demo:scene_demo")
    service.apply_object_state_update(
        object_id="entity:scene_demo:chair_01",
        zone_id="zone_focus",
        state="upright",
        affordances=["kick"],
        occludes=False,
        producer_ts=updated_at,
        source_ref=f"object_state:chair_01:{updated_at}",
    )
    return service


def _record(**overrides: object) -> SceneAffordanceRecord:
    payload: dict[str, object] = {
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
    payload.update(overrides)
    return SceneAffordanceRecord.model_validate(payload)


def _registry(
    *,
    record: SceneAffordanceRecord | None = None,
    collider_ref: str = "collider:chair_01:body",
    catalog_collider_ref: str = "collider:chair_01:body",
    occupancy_updated_at: int = 110,
) -> SceneAffordanceRegistry:
    return SceneAffordanceRegistry.from_reviewed_records(
        records=[record or _record()],
        space_model=_space_model(collider_ref=collider_ref),
        occupancy_snapshot=_occupancy(updated_at=occupancy_updated_at).snapshot(),
        grounding_catalog={
            "entity_refs": ["entity:scene_demo:chair_01"],
            "collider_refs": [catalog_collider_ref],
            "anchor_refs": ["anchor:chair_01:stance", "anchor:chair_01:contact"],
            "affordance_refs": ["affordance:chair_01:kick"],
        },
        current_tick=120,
        occupancy_freshness_ticks=30,
    )


def test_registry_resolves_chair_with_catalog_ids_and_controller_binding() -> None:
    registry = _registry()

    result = registry.resolve(
        scene_id="scene_demo",
        scene_instance_id="scene_instance:main_demo:1",
        entity_ref="entity:scene_demo:chair_01",
        affordance_id="affordance:chair_01:kick",
        expected_binding_revision=7,
        required_anchor_roles=["approach_stance", "contact"],
        view="controller",
    )

    assert result.status == "available"
    assert result.record is not None
    assert result.record.entity_ref == "entity:scene_demo:chair_01"
    assert result.record.local_binding.collider_refs == ["collider:chair_01:body"]
    assert result.record.grounding_catalog_refs.anchor_refs == ["anchor:chair_01:stance", "anchor:chair_01:contact"]
    assert result.projection["local_binding"]["node_ref"] == "node:chair_01"


def test_public_registry_projection_hides_local_node_ref() -> None:
    result = _registry().resolve(
        scene_id="scene_demo",
        scene_instance_id="scene_instance:main_demo:1",
        entity_ref="entity:scene_demo:chair_01",
        affordance_id="affordance:chair_01:kick",
        expected_binding_revision=7,
        required_anchor_roles=["approach_stance", "contact"],
        view="public",
    )

    assert result.status == "available"
    assert "local_binding" not in result.projection
    assert result.projection["entity_ref"] == "entity:scene_demo:chair_01"


@pytest.mark.parametrize(
    ("kwargs", "expected_status"),
    [
        ({"scene_instance_id": "scene_instance:other"}, "registry_cross_scene_binding_rejected"),
        ({"expected_binding_revision": 6}, "registry_binding_stale"),
        ({"affordance_id": "affordance:chair_01:grab"}, "registry_target_unknown"),
        ({"required_anchor_roles": ["approach_stance", "grip"]}, "registry_target_unknown"),
    ],
)
def test_registry_rejects_unusable_binding_inputs(kwargs: dict[str, object], expected_status: str) -> None:
    payload = {
        "scene_id": "scene_demo",
        "scene_instance_id": "scene_instance:main_demo:1",
        "entity_ref": "entity:scene_demo:chair_01",
        "affordance_id": "affordance:chair_01:kick",
        "expected_binding_revision": 7,
        "required_anchor_roles": ["approach_stance", "contact"],
        "view": "controller",
    }
    payload.update(kwargs)

    result = _registry().resolve(**payload)

    assert result.status == expected_status
    assert result.record is None


def test_registry_rejects_missing_collider_from_scene_space_model() -> None:
    result = _registry(collider_ref="collider:chair_01:replacement").resolve(
        scene_id="scene_demo",
        scene_instance_id="scene_instance:main_demo:1",
        entity_ref="entity:scene_demo:chair_01",
        affordance_id="affordance:chair_01:kick",
        expected_binding_revision=7,
        required_anchor_roles=["approach_stance", "contact"],
        view="controller",
    )

    assert result.status == "registry_binding_unhealthy"
    assert result.record is None


def test_registry_rejects_stale_occupancy_snapshot() -> None:
    result = _registry(occupancy_updated_at=10).resolve(
        scene_id="scene_demo",
        scene_instance_id="scene_instance:main_demo:1",
        entity_ref="entity:scene_demo:chair_01",
        affordance_id="affordance:chair_01:kick",
        expected_binding_revision=7,
        required_anchor_roles=["approach_stance", "contact"],
        view="controller",
    )

    assert result.status == "registry_occupancy_stale"
    assert result.record is None


def test_registry_records_vla_conflict_without_overwriting_known_truth() -> None:
    registry = _registry()

    conflict = registry.review_vla_candidate(
        entity_ref="entity:scene_demo:chair_01",
        candidate_refs={
            "entity_refs": ["entity:vla:invented_chair"],
            "collider_refs": ["collider:vla:fake"],
            "anchor_refs": [],
            "affordance_refs": [],
        },
    )
    result = registry.resolve(
        scene_id="scene_demo",
        scene_instance_id="scene_instance:main_demo:1",
        entity_ref="entity:scene_demo:chair_01",
        affordance_id="affordance:chair_01:kick",
        expected_binding_revision=7,
        required_anchor_roles=["approach_stance", "contact"],
        view="controller",
    )

    assert conflict["status"] == "vla_conflict_recorded"
    assert result.status == "available"
    assert result.record is not None
    assert result.record.entity_ref == "entity:scene_demo:chair_01"
