import pytest

from app.models.siming_event import InterventionCandidate
from app.models.siming_runtime_state import (
    GroupSimulationBranchSnapshot,
    StateTreeNode,
    StateTreeSnapshot,
)
from app.services.siming_fairness_audit import SimingFairnessAuditEngine
from app.services.siming_feature_registry import SimingFeatureRegistry
from app.services.siming_policy import SimingInterventionPolicy


def make_state_tree() -> StateTreeSnapshot:
    return StateTreeSnapshot(
        snapshot_id="state_tree:room_demo:1",
        schema_version=1,
        producer_system="siming.state_tree",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        world_ts=300,
        sim_tick_ts=301,
        causation_id="visual_fact:300",
        correlation_id="visual_fact:300",
        environment=StateTreeNode(
            node_id="environment:env_lamp",
            owner_system="L1/ESM",
            authority="mirror",
            status="fresh",
            summary={"established_fact_id": "visual_fact:300:char_c:light_level_drop"},
        ),
        character=StateTreeNode(
            node_id="character:char_b",
            owner_system="character_agent",
            authority="mirror",
            status="fresh",
            summary={"target_actor_id": "char_b"},
        ),
        storyline=StateTreeNode(
            node_id="storyline:room_demo:main",
            owner_system="siming",
            authority="editable",
            status="fresh",
            summary={"active_phase": "rising"},
        ),
        group_simulation=GroupSimulationBranchSnapshot(status="unavailable", summary={}),
    )


def make_candidate() -> InterventionCandidate:
    return InterventionCandidate(
        candidate_id="cand:1",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        causation_id="visual_fact:300",
        correlation_id="visual_fact:300",
        proposed_band="fact_reveal",
        target_actor_id="char_b",
        established_fact_ids=["visual_fact:300:char_c:light_level_drop"],
        reason_tags=["resource_pressure_sensitive"],
        source="rule",
    )


def test_default_dimensions_are_present_and_mapped_to_policy() -> None:
    snapshot = SimingFairnessAuditEngine().build_snapshot(make_state_tree())

    assert set(snapshot.dimensions) >= set(SimingFairnessAuditEngine.DEFAULT_DIMENSIONS)
    for dimension_id in SimingFairnessAuditEngine.DEFAULT_DIMENSIONS:
        assert snapshot.dimensions[dimension_id].mapped_to_policy is True


def test_default_dimensions_have_builtin_policy_mappings() -> None:
    registry = SimingFeatureRegistry()

    for dimension_id in SimingFairnessAuditEngine.DEFAULT_DIMENSIONS:
        mapping = registry.policy_mapping_for(dimension_id)
        assert mapping is not None
        assert mapping.reject_reason_tag == f"{dimension_id}_sensitive"
        assert mapping.rejection_reason == f"{dimension_id}_policy_rejected"


@pytest.mark.parametrize("fact_value", [None, ""])
def test_build_snapshot_ignores_empty_established_fact_id(fact_value: str | None) -> None:
    state_tree = make_state_tree().model_copy(
        update={
            "environment": make_state_tree().environment.model_copy(
                update={"summary": {"established_fact_id": fact_value}}
            )
        }
    )

    snapshot = SimingFairnessAuditEngine().build_snapshot(state_tree)

    assert snapshot.known_fact_ids == []


def test_build_snapshot_ignores_missing_established_fact_id() -> None:
    state_tree = make_state_tree().model_copy(
        update={
            "environment": make_state_tree().environment.model_copy(update={"summary": {}})
        }
    )

    snapshot = SimingFairnessAuditEngine().build_snapshot(state_tree)

    assert snapshot.known_fact_ids == []


@pytest.mark.parametrize("actor_value", [None, ""])
def test_build_snapshot_ignores_empty_target_actor_id(actor_value: str | None) -> None:
    state_tree = make_state_tree().model_copy(
        update={
            "character": make_state_tree().character.model_copy(
                update={"summary": {"target_actor_id": actor_value}}
            )
        }
    )

    snapshot = SimingFairnessAuditEngine().build_snapshot(state_tree)

    assert snapshot.eligible_actor_ids == []


def test_build_snapshot_ignores_missing_target_actor_id() -> None:
    state_tree = make_state_tree().model_copy(
        update={"character": make_state_tree().character.model_copy(update={"summary": {}})}
    )

    snapshot = SimingFairnessAuditEngine().build_snapshot(state_tree)

    assert snapshot.eligible_actor_ids == []


def test_registered_dimension_enters_snapshot_without_policy_mapping() -> None:
    registry = SimingFeatureRegistry()
    registry.register_fairness_dimension("resource_pressure", required=False)

    snapshot = SimingFairnessAuditEngine(registry).build_snapshot(make_state_tree())

    assert "resource_pressure" in snapshot.dimensions
    assert snapshot.dimensions["resource_pressure"].mapped_to_policy is False
    assert snapshot.dimensions["resource_pressure"].status == "fresh"


def test_unmapped_dimension_does_not_change_policy_decision() -> None:
    registry = SimingFeatureRegistry()
    registry.register_fairness_dimension("resource_pressure", required=False)
    snapshot = SimingFairnessAuditEngine(registry).build_snapshot(make_state_tree())

    result = SimingInterventionPolicy(feature_registry=registry).evaluate(
        make_candidate(), snapshot=snapshot
    )

    assert result.accepted is True
    assert "resource_pressure_policy_rejected" not in result.reasons


def test_builtin_default_dimension_affects_policy_when_reject_tag_is_present() -> None:
    registry = SimingFeatureRegistry()
    snapshot = SimingFairnessAuditEngine(registry).build_snapshot(make_state_tree())

    result = SimingInterventionPolicy(feature_registry=registry).evaluate(
        make_candidate().model_copy(
            update={"reason_tags": ["information_distribution_sensitive"]}
        ),
        snapshot=snapshot,
    )

    assert result.accepted is False
    assert "information_distribution_policy_rejected" in result.reasons


def test_dimension_affects_policy_only_after_mapping_is_registered() -> None:
    registry = SimingFeatureRegistry()
    registry.register_fairness_dimension("resource_pressure", required=False)
    registry.register_policy_mapping(
        dimension_id="resource_pressure",
        reject_reason_tag="resource_pressure_sensitive",
        rejection_reason="resource_pressure_policy_rejected",
    )
    snapshot = SimingFairnessAuditEngine(registry).build_snapshot(make_state_tree())

    result = SimingInterventionPolicy(feature_registry=registry).evaluate(
        make_candidate(), snapshot=snapshot
    )

    assert result.accepted is False
    assert "resource_pressure_policy_rejected" in result.reasons
    assert snapshot.dimensions["resource_pressure"].mapped_to_policy is True


def test_registering_mapping_requires_known_dimension() -> None:
    registry = SimingFeatureRegistry()

    with pytest.raises(
        ValueError,
        match="fairness dimension must be registered before policy mapping",
    ):
        registry.register_policy_mapping(
            dimension_id="resource_pressure",
            reject_reason_tag="resource_pressure_sensitive",
            rejection_reason="resource_pressure_policy_rejected",
        )

    assert all(
        dimension.dimension_id != "resource_pressure"
        for dimension in registry.fairness_dimensions()
    )
