from __future__ import annotations

from app.character_agent.models.embodied_episode import CandidateActionObservation
from app.character_agent.models.turn_context import CharacterTurnContext
from app.character_agent.services.embodied_episode_service import EmbodiedEpisodeService
from app.character_agent.runtime.runtime_loop import CharacterAgentRuntime
from app.character_agent.reasoning.actor_scene_knowledge import (
    ActorSceneKnowledgeEntry,
    ActorSceneKnowledgeStore,
)


def _running_turn() -> CharacterTurnContext:
    turn = CharacterTurnContext.begin(
        actor_id="char_b",
        source_event_ref="visual:archive-door",
        producer_ts=10,
        causation_id="cause:archive-door",
        correlation_id="corr:archive-door",
        input_revision_vector={"l1": 1},
        memory_revision_vector={"memory": 1},
        policy_revision="policy:character:v1",
        snapshot_revision=1,
        branch_id="branch:main",
    )
    return turn.stage_event(
        "context",
        stage_ref="stage:context",
        idempotency_key="key:context",
        producer_ts=10,
        payload={"l1_snapshot": {}},
    )[0]


def _door_candidate() -> CandidateActionObservation:
    return CandidateActionObservation(
        candidate_id="candidate:archive-door:open",
        target_ref="obj_archive_door",
        semantic_action_id="open_close",
        reviewed_target_ref="obj_archive_door",
        reviewed_action_ref="affordance:archive-door:open-close",
        preconditions=["door_closed"],
        expected_observation={"observed_state": "open"},
        confidence=0.8,
        uncertainty={"source": "provider_advisory"},
        evidence_refs=["vla_result:door", "pqf:door:1"],
    )


def _accepted_door_result() -> dict[str, object]:
    return {
        "result_id": "authority_result:archive-door:open",
        "settlement_status": "accepted",
        "target_object_id": "obj_archive_door",
    }


def test_episode_requires_authority_and_post_capture_for_success() -> None:
    service = EmbodiedEpisodeService()
    episode = service.begin(_running_turn(), _door_candidate(), pre_capture_ref="capture:1")

    result = service.complete(
        episode,
        authority_result=_accepted_door_result(),
        post_capture_ref="capture:2",
        observed_state="open",
    )

    assert result.outcome == "confirmed_success"
    assert result.authority_result_ref == "authority_result:archive-door:open"

    mismatch = service.complete(
        episode,
        authority_result=_accepted_door_result(),
        post_capture_ref="capture:2",
        observed_state="closed",
    )
    assert mismatch.outcome == "recovery_required"
    assert mismatch.failure_class == "observation_mismatch"
    assert mismatch.reobserve_required is True


def test_candidate_rejects_unreviewed_or_control_fields() -> None:
    candidate = _door_candidate().model_dump()
    candidate.pop("reviewed_action_ref")

    from pydantic import ValidationError
    import pytest

    with pytest.raises(ValidationError, match="reviewed"):
        CandidateActionObservation.model_validate(candidate)
    with pytest.raises(ValidationError, match="forbidden candidate field"):
        CandidateActionObservation.model_validate({**_door_candidate().model_dump(), "velocity": [1, 0, 0]})


def test_episode_rejected_authority_is_typed_recoverable_failure() -> None:
    service = EmbodiedEpisodeService()
    episode = service.begin(_running_turn(), _door_candidate(), pre_capture_ref="capture:1")

    result = service.complete(
        episode,
        authority_result={"result_id": "authority_result:rejected", "settlement_status": "rejected"},
        post_capture_ref="capture:2",
        observed_state="closed",
    )

    assert result.failure_class == "authority_rejected"
    assert result.recovery_candidate["failure_class"] == "authority_rejected"


def test_runtime_persists_episode_and_routes_mismatch_to_private_recovery() -> None:
    runtime = CharacterAgentRuntime()
    episode = runtime.begin_embodied_episode(
        turn=_running_turn(),
        candidate=_door_candidate(),
        pre_capture_ref="capture:1",
        producer_ts=10,
    )

    completed = runtime.complete_embodied_episode(
        episode=episode,
        authority_result=_accepted_door_result(),
        post_capture_ref="capture:2",
        observed_state="closed",
        producer_ts=11,
    )

    timeline = runtime.get_session_timeline("char_b")
    assert completed.failure_class == "observation_mismatch"
    assert runtime.get_embodied_episode("char_b", episode.episode_ref) == completed
    assert any(event["event_type"] == "character_embodied_episode_recovery_candidate" for event in timeline)
    assert any(event["event_type"] == "character_embodied_episode_observation_requested" for event in timeline)
    assert not any(event["event_type"] == "character_agent_settlement_result" for event in timeline)


def test_percept_conflict_retains_structured_fact_and_requires_fresh_observation() -> None:
    store = ActorSceneKnowledgeStore()
    retained = store.upsert(
        ActorSceneKnowledgeEntry(
            entry_id="ask:door:structured",
            actor_id="char_b",
            session_id="room_demo",
            scene_id="scene_demo",
            subject_ref="obj_archive_door",
            knowledge_type="target",
            summary="door observed closed",
            source_kind="l1_projected_fact",
            source_refs=["fact:door:closed"],
            confidence=0.95,
            world_truth_marker="l1_projected_fact_ref",
        ),
        producer_ts=10,
    ).entry

    result = store.record_percept_conflict(
        retained_entry=retained,
        incoming_source="provider_advisory",
        incoming_ref="vla_result:door-open",
        producer_ts=11,
    )

    assert result.entry.source_kind == "l1_projected_fact"
    assert result.conflict is not None
    assert result.conflict.reason == "percept_conflict"
    assert "fact:door:closed" in result.conflict.source_refs
    assert "vla_result:door-open" in result.conflict.source_refs
    assert result.active_perception_reasons == ["percept_conflict", "fresh_observation_required"]
