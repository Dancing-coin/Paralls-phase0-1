import pytest

from app.models.authority_event import AuthorityEvent
from app.services.siming_observe import SimingObservePipeline
from app.services.siming_state_tree import InMemorySimingStateTree


def make_event(
    event_type: str = "visual_fact_event",
    *,
    payload_overrides: dict[str, object] | None = None,
    **event_overrides: object,
) -> AuthorityEvent:
    payload = {
        "event_id": f"{event_type}:300",
        "event_type": event_type,
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
            "target_actor_id": "char_b",
        },
    }
    payload["payload"].update(payload_overrides or {})  # type: ignore[index, union-attr]
    payload.update(event_overrides)
    return AuthorityEvent.model_validate(payload)


def test_observe_pipeline_accepts_allowed_authority_events_only() -> None:
    pipeline = SimingObservePipeline()

    observed = pipeline.observe([make_event()])
    ignored = pipeline.observe([make_event("presentation_event")])

    assert len(observed) == 1
    assert observed[0].source_event_id == "visual_fact_event:300"
    assert ignored == []


def test_observe_pipeline_rejects_allowed_events_not_routed_to_siming() -> None:
    pipeline = SimingObservePipeline()

    ignored_direct_target = pipeline.observe(
        [
            make_event(
                routing={
                    "audience_mode": "targeted",
                    "routing_mode": "target_ids",
                    "target_ids": ["character_agent:char_b"],
                }
            )
        ]
    )
    observed_broadcast = pipeline.observe(
        [
            make_event(
                routing={
                    "audience_mode": "broadcast",
                    "routing_mode": "event_type",
                    "target_ids": [],
                }
            )
        ]
    )

    assert ignored_direct_target == []
    assert len(observed_broadcast) == 1


def test_state_tree_mirrors_environment_and_character_without_taking_authority() -> None:
    observed = SimingObservePipeline().observe([make_event()])
    tree = InMemorySimingStateTree()

    snapshot = tree.update_from_observed(observed, sim_tick_ts=301)

    assert snapshot.environment.node_id == "environment:env_lamp"
    assert snapshot.environment.owner_system == "L1/ESM"
    assert snapshot.environment.authority == "mirror"
    assert snapshot.environment.summary["established_fact_id"] == "visual_fact:300:char_c:light_level_drop"
    assert snapshot.character.node_id == "character:char_b"
    assert snapshot.character.authority == "mirror"
    assert snapshot.storyline.authority == "editable"
    assert snapshot.group_simulation.status == "unavailable"


def test_state_tree_keeps_missing_branches_explicitly_stale_or_unavailable() -> None:
    observed = SimingObservePipeline().observe(
        [
            make_event(
                payload_overrides={
                    "target_environment_id": None,
                    "target_actor_id": None,
                }
            )
        ]
    )
    snapshot = InMemorySimingStateTree().update_from_observed(observed, sim_tick_ts=301)

    assert snapshot.environment.status == "partial"
    assert snapshot.character.status == "partial"
    assert snapshot.group_simulation.status == "unavailable"


def test_state_tree_aggregates_branch_sources_across_observed_batch() -> None:
    observed = SimingObservePipeline().observe(
        [
            make_event(
                payload_overrides={
                    "target_environment_id": "env_archive",
                    "established_fact_id": "visual_fact:300:env_archive:temperature_drop",
                    "target_actor_id": None,
                }
            ),
            make_event(
                payload_overrides={
                    "target_environment_id": None,
                    "established_fact_id": None,
                    "target_actor_id": "char_d",
                },
                event_id="visual_fact_event:301",
                producer_ts=301,
                room_id="room_second",
                scene_id="scene_second",
                zone_id="zone_second",
                causation_id="visual_fact:301",
                correlation_id="corr:301",
            ),
        ]
    )

    snapshot = InMemorySimingStateTree().update_from_observed(observed, sim_tick_ts=302)

    assert snapshot.snapshot_id == "state_tree:room_second:302"
    assert snapshot.room_id == "room_second"
    assert snapshot.scene_id == "scene_second"
    assert snapshot.zone_id == "zone_second"
    assert snapshot.world_ts == 301
    assert snapshot.causation_id == "visual_fact:301"
    assert snapshot.correlation_id == "corr:301"
    assert snapshot.environment.node_id == "environment:env_archive"
    assert snapshot.environment.summary["target_environment_id"] == "env_archive"
    assert (
        snapshot.environment.summary["established_fact_id"]
        == "visual_fact:300:env_archive:temperature_drop"
    )
    assert snapshot.character.node_id == "character:char_d"
    assert snapshot.character.summary["target_actor_id"] == "char_d"


def test_state_tree_requires_at_least_one_observed_event() -> None:
    with pytest.raises(ValueError, match="at least one observed event"):
        InMemorySimingStateTree().update_from_observed([], sim_tick_ts=301)
