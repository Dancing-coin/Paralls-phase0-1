from __future__ import annotations

from app.character_agent.reasoning.active_perception import ActivePerceptionPlanner, ActivePerceptionResult
from app.character_agent.reasoning.actor_scene_knowledge import ActorSceneKnowledgeEntry, ActorSceneKnowledgeStore


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
