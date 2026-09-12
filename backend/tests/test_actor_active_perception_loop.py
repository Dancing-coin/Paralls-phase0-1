from __future__ import annotations

from app.character_agent.reasoning.active_perception import ActivePerceptionPlanner, ActivePerceptionResult
from app.character_agent.reasoning.actor_scene_knowledge import ActorSceneKnowledgeEntry, ActorSceneKnowledgeStore
from app.character_agent.models.memory_consistency import MemoryFactClaim
import pytest


def test_conflict_generates_active_perception_request_that_returns_to_pqf_provider_chain() -> None:
    store = ActorSceneKnowledgeStore()
    store.upsert(
        ActorSceneKnowledgeEntry(
            entry_id="ask:char_a:box:l1",
            actor_id="char_a",
            session_id="session_a",
            scene_id="scene_demo",
            subject_ref="box",
            knowledge_type="space",
            summary="L1 says clear",
            source_kind="l1_projected_fact",
            source_refs=["l1_fact:box:clear"],
            confidence=0.95,
            world_truth_marker="l1_projected_fact_ref",
        ),
        producer_ts=1,
    )
    store.upsert(
        ActorSceneKnowledgeEntry(
            entry_id="ask:char_a:box:vla",
            actor_id="char_a",
            session_id="session_a",
            scene_id="scene_demo",
            subject_ref="box",
            knowledge_type="space",
            summary="VLA says blocked",
            source_kind="vla_advisory",
            source_refs=["vla_result:box"],
            confidence=0.7,
            advisory=True,
        ),
        producer_ts=2,
    )

    request = ActivePerceptionPlanner().requests_for_actor(
        store,
        actor_id="char_a",
        session_id="session_a",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
    )[0]
    frame = request.to_pqf(started_at=2, ended_at=3)

    assert request.reason == "conflict"
    assert request.must_use_provider_chain is True
    assert request.pqf_query_id == frame.query_id
    assert frame.consumer_kind == "character"
    assert frame.multimodal_context_id == "character_mm:char_a"
    assert frame.spatial_inputs[0].ref_id.startswith("provider_ref:")


def test_active_perception_result_requires_provider_refs_and_writes_revision() -> None:
    store = ActorSceneKnowledgeStore()
    planner = ActivePerceptionPlanner()
    result = ActivePerceptionResult(
        result_id="active_result:1",
        request_id="active_perception:char_a:box:conflict:1",
        actor_id="char_a",
        session_id="session_a",
        scene_id="scene_demo",
        subject_ref="box",
        pqf_query_id="pqf:char_a:3",
        provider_result_refs=["provider_result:spatial_patch:1"],
        source_refs=["l1_fact:box:clear"],
        confidence=0.9,
        summary="provider chain confirms box is clear",
    )

    update = planner.apply_result(store, result, producer_ts=3)

    assert update.operation == "add"
    assert update.entry.source_kind == "active_perception"
    assert "pqf:char_a:3" in update.entry.source_refs
    assert "provider_result:spatial_patch:1" in update.entry.source_refs


def test_stale_or_failed_result_cannot_write_successful_knowledge() -> None:
    store = ActorSceneKnowledgeStore()
    result = ActivePerceptionResult(result_id="r", request_id="req", actor_id="a", session_id="s", scene_id="scene",
                                    subject_ref="box", pqf_query_id="pqf:a", provider_result_refs=["provider:1"],
                                    summary="observed", freshness="stale")
    with pytest.raises(ValueError, match="fresh"):
        ActivePerceptionPlanner().apply_result(store, result, producer_ts=3)
    with pytest.raises(ValueError, match="failure"):
        ActivePerceptionPlanner().apply_result(store, result.model_copy(update={"freshness": "fresh", "failure_reason": "inaccessible"}), producer_ts=3)
    assert store.entries_for_actor("a") == []


def test_claim_requires_matching_subject_time_and_provider_lineage() -> None:
    base = dict(scope_ref="world:main", subject_ref="box", predicate="location", value="desk", valid_at=3,
                source_ref="provider:1")
    result = ActivePerceptionResult(result_id="r", request_id="req", actor_id="a", session_id="s", scene_id="scene",
                                    subject_ref="box", pqf_query_id="pqf:a", provider_result_refs=["provider:1"],
                                    summary="on desk", fact_claim=MemoryFactClaim(**base))
    store = ActorSceneKnowledgeStore()
    assert ActivePerceptionPlanner().apply_result(store, result, producer_ts=3).entry.claim.value == "desk"
    for changes in ({"subject_ref": "other"}, {"source_ref": "private:secret"}, {"valid_at": 4}):
        with pytest.raises(ValueError):
            ActivePerceptionPlanner().apply_result(store, result.model_copy(update={"fact_claim": MemoryFactClaim(**(base | changes))}), producer_ts=3)


def test_result_resolves_only_named_conflict_on_matching_subject() -> None:
    store = ActorSceneKnowledgeStore()
    first = ActorSceneKnowledgeEntry(entry_id="box", actor_id="a", session_id="s", scene_id="scene", subject_ref="box",
                                     knowledge_type="space", summary="clear", source_kind="l1_projected_fact",
                                     world_truth_marker="l1_projected_fact_ref", source_refs=["l1:box"], confidence=.9)
    store.upsert(first, producer_ts=1)
    for timestamp in (2, 3):
        store.upsert(first.model_copy(update={"summary": f"blocked {timestamp}", "source_kind": "vla_advisory",
                                            "world_truth_marker": "subjective_not_world_truth", "advisory": True}), producer_ts=timestamp)
    conflicts = store.entries_for_actor("a")[0].conflicts
    result = ActivePerceptionResult(result_id="r", request_id="req", actor_id="a", session_id="s", scene_id="scene",
                                    subject_ref="box", pqf_query_id="pqf:a", provider_result_refs=["provider:1"],
                                    summary="clear", conflict_refs=[conflicts[0].conflict_id])
    ActivePerceptionPlanner().apply_result(store, result, producer_ts=4)
    resolved = store.entries_for_actor("a")[0].conflicts
    assert [item.resolved for item in resolved] == [True, False]
    with pytest.raises(ValueError, match="conflict"):
        ActivePerceptionPlanner().apply_result(store, result.model_copy(update={"conflict_refs": ["other:conflict"]}), producer_ts=5)
