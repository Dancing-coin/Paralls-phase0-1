import pytest
from pydantic import ValidationError

from app.models.authority_event import AuthorityEvent
from app.models.siming_event import FairnessStateSnapshot, SimingTickResult
from app.models.siming_runtime_state import (
    FairnessDimensionSnapshot,
    GroupSimulationBranchSnapshot,
    NarrativeObligation,
    NarrativeObligationLedgerSnapshot,
    NarrativeReadModel,
    ObservedSimingEvent,
    SimingCheckpoint,
    StateTreeNode,
    StateTreeSnapshot,
    StorylineMarker,
    StorylineStateSnapshot,
)


def make_event() -> AuthorityEvent:
    return AuthorityEvent.model_validate(
        {
            "event_id": "visual_fact:300:char_c:light_level_drop",
            "event_type": "visual_fact_event",
            "producer_ts": 300,
            "room_id": "room_demo",
            "scene_id": "scene_demo",
            "zone_id": "zone_focus",
            "source": {"layer": "L1", "system": "visual_fact", "actor_id": "char_c"},
            "routing": {"audience_mode": "room", "routing_mode": "event_type", "target_ids": ["siming"]},
            "priority": "p2",
            "ttl": 5000,
            "durability": "replayable",
            "causation_id": "visual_fact:300",
            "correlation_id": "visual_fact:300",
            "payload": {
                "fact_type": "light_level_drop",
                "established_fact_id": "visual_fact:300:char_c:light_level_drop",
                "target_environment_id": "env_lamp",
            },
        }
    )


def test_observed_event_keeps_bus_event_separate_from_siming_domain_state() -> None:
    event = make_event()
    observed = ObservedSimingEvent.from_authority_event(event)

    assert observed.source_event_id == event.event_id
    assert observed.event_type == "visual_fact_event"
    assert observed.payload["established_fact_id"] == "visual_fact:300:char_c:light_level_drop"
    assert observed.authority_event is event


def test_state_tree_snapshot_has_authority_separated_branches() -> None:
    snapshot = StateTreeSnapshot(
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
            summary={"light_level": "low"},
        ),
        character=StateTreeNode(
            node_id="character:char_b",
            owner_system="character_agent",
            authority="mirror",
            status="partial",
            summary={"available": True},
        ),
        storyline=StateTreeNode(
            node_id="storyline:main",
            owner_system="siming",
            authority="editable",
            status="fresh",
            summary={"phase": "rising"},
        ),
        group_simulation=GroupSimulationBranchSnapshot(status="unavailable", summary={}),
    )

    assert snapshot.environment.authority == "mirror"
    assert snapshot.character.authority == "mirror"
    assert snapshot.storyline.authority == "editable"
    assert snapshot.group_simulation.status == "unavailable"


def test_state_tree_snapshot_rejects_non_mirror_environment_or_character_authority() -> None:
    with pytest.raises(
        ValidationError,
        match="environment and character branches must be mirror authority",
    ):
        StateTreeSnapshot(
            snapshot_id="state_tree:room_demo:invalid",
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
                authority="editable",
                status="fresh",
                summary={"light_level": "low"},
            ),
            character=StateTreeNode(
                node_id="character:char_b",
                owner_system="character_agent",
                authority="mirror",
                status="partial",
                summary={"available": True},
            ),
            storyline=StateTreeNode(
                node_id="storyline:main",
                owner_system="siming",
                authority="editable",
                status="fresh",
                summary={"phase": "rising"},
            ),
            group_simulation=GroupSimulationBranchSnapshot(status="unavailable", summary={}),
        )

    with pytest.raises(
        ValidationError,
        match="environment and character branches must be mirror authority",
    ):
        StateTreeSnapshot(
            snapshot_id="state_tree:room_demo:invalid-2",
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
                summary={"light_level": "low"},
            ),
            character=StateTreeNode(
                node_id="character:char_b",
                owner_system="character_agent",
                authority="editable",
                status="partial",
                summary={"available": True},
            ),
            storyline=StateTreeNode(
                node_id="storyline:main",
                owner_system="siming",
                authority="editable",
                status="fresh",
                summary={"phase": "rising"},
            ),
            group_simulation=GroupSimulationBranchSnapshot(status="unavailable", summary={}),
        )


def test_runtime_state_models_forbid_extra_fields() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        StateTreeNode.model_validate(
            {
                "node_id": "environment:env_lamp",
                "owner_system": "L1/ESM",
                "authority": "mirror",
                "status": "fresh",
                "summary": {"light_level": "low"},
                "unexpected": True,
            }
        )


def test_storyline_and_obligation_models_are_siming_owned() -> None:
    storyline = StorylineStateSnapshot(
        snapshot_id="storyline:room_demo:1",
        schema_version=1,
        producer_system="siming.storyline",
        room_id="room_demo",
        world_ts=300,
        sim_tick_ts=301,
        causation_id="visual_fact:300",
        correlation_id="visual_fact:300",
        active_phase="rising",
        markers=[
            StorylineMarker(
                marker_id="marker:light_drop",
                marker_type="tension",
                status="active",
                entity_refs=["env_lamp"],
                reason="Established light drop should affect participation.",
            )
        ],
    )
    ledger = NarrativeObligationLedgerSnapshot(
        ledger_id="obligation:room_demo:1",
        schema_version=1,
        producer_system="siming.obligation",
        room_id="room_demo",
        world_ts=300,
        sim_tick_ts=301,
        causation_id="visual_fact:300",
        correlation_id="visual_fact:300",
        obligations=[
            NarrativeObligation(
                obligation_id="obl:reveal_light_drop",
                source_ref="marker:light_drop",
                obligation_type="unresolved_reveal",
                status="open",
                reason="char_b is eligible but has not received the established fact.",
            )
        ],
    )

    assert storyline.markers[0].status == "active"
    assert ledger.obligations[0].status == "open"


def test_fairness_snapshot_can_record_unmapped_top_level_dimension() -> None:
    snapshot = FairnessStateSnapshot(
        snapshot_id="fairness:visual_fact:300",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        causation_id="visual_fact:300",
        correlation_id="visual_fact:300",
        known_fact_ids=["visual_fact:300:char_c:light_level_drop"],
        eligible_actor_ids=["char_b"],
        blocked_actor_ids=[],
        recent_intervention_ids=[],
        dimensions={
            "resource_pressure": FairnessDimensionSnapshot(
                dimension_id="resource_pressure",
                status="fresh",
                score=0.65,
                reason="Resource imbalance is observed but no policy mapping is active.",
                mapped_to_policy=False,
            )
        },
    )

    assert snapshot.dimensions["resource_pressure"].mapped_to_policy is False


def test_tick_result_can_return_runtime_state_without_publishing_truth() -> None:
    read_model = NarrativeReadModel(
        read_model_id="read:room_demo:1",
        schema_version=1,
        producer_system="siming.read_model",
        room_id="room_demo",
        scene_scope="scene_demo/zone_focus",
        world_ts=300,
        sim_tick_ts=301,
        current_state={"imbalance_type": "information_visibility"},
        focus_entities=["env_lamp", "char_b"],
        derived_from_snapshot_ref="fairness:visual_fact:300",
    )
    checkpoint = SimingCheckpoint(
        checkpoint_id="checkpoint:room_demo:1",
        schema_version=1,
        room_id="room_demo",
        world_ts=300,
        sim_tick_ts=301,
        checkpoint_type="fairness_after",
        fairness_snapshot_ref="fairness:visual_fact:300",
        state_tree_snapshot_ref="state_tree:room_demo:1",
        storyline_snapshot_ref="storyline:room_demo:1",
        causation_id="visual_fact:300",
        correlation_id="visual_fact:300",
    )
    result = SimingTickResult(read_model=read_model, checkpoints=[checkpoint])

    assert result.read_model.current_state["imbalance_type"] == "information_visibility"
    assert result.checkpoints[0].checkpoint_type == "fairness_after"
