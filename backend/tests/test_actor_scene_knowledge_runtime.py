from __future__ import annotations

import pytest

from app.character_agent.reasoning.actor_scene_knowledge import ActorSceneKnowledgeEntry, ActorSceneKnowledgeStore
from app.character_agent.reasoning.l1_perception import CharacterAgentL1Service
from app.world_runtime.intelligence_upgrade import CanonicalPerceptBundle


def _bundle(actor_id: str, *, subject_ref: str = "obj_box") -> CanonicalPerceptBundle:
    return CanonicalPerceptBundle(
        bundle_id=f"bundle:{actor_id}:10",
        consumer_kind="character",
        subject_id=actor_id,
        query_id=f"pqf:{actor_id}:10",
        percept_context_id=f"character_mm:{actor_id}",
        local_spatial_state={"room_id": "room_demo", "scene_id": "scene_demo", "session_id": "session_a"},
        target_state={"target_ref": subject_ref, "summary": "box visible", "confidence": 0.8},
        structured_fact_refs=["l1_fact:obj_box:reachable"],
    )


def test_bundle_ingestion_updates_private_ask_store_and_keeps_actor_isolation() -> None:
    service = CharacterAgentL1Service()

    service.apply_canonical_percept_bundle(_bundle("char_a"))
    service.apply_canonical_percept_bundle(_bundle("char_b", subject_ref="obj_lamp"))

    store = service.get_actor_scene_knowledge_store()
    char_a_entries = store.entries_for_actor("char_a")
    char_b_entries = store.entries_for_actor("char_b")

    assert {entry.actor_id for entry in char_a_entries} == {"char_a"}
    assert {entry.actor_id for entry in char_b_entries} == {"char_b"}
    assert any(entry.subject_ref == "obj_box" for entry in char_a_entries)
    assert not any(entry.subject_ref == "obj_lamp" for entry in char_a_entries)


def test_l1_and_vla_conflict_records_conflict_without_overwriting_world_truth() -> None:
    store = ActorSceneKnowledgeStore()
    l1 = ActorSceneKnowledgeEntry(
        entry_id="ask:char_a:obj_box:l1",
        actor_id="char_a",
        session_id="session_a",
        scene_id="scene_demo",
        subject_ref="obj_box",
        knowledge_type="space",
        summary="L1 says obj_box is reachable",
        source_kind="l1_projected_fact",
        source_refs=["l1_fact:obj_box:reachable"],
        confidence=0.95,
        world_truth_marker="l1_projected_fact_ref",
    )
    advisory = ActorSceneKnowledgeEntry(
        entry_id="ask:char_a:obj_box:vla",
        actor_id="char_a",
        session_id="session_a",
        scene_id="scene_demo",
        subject_ref="obj_box",
        knowledge_type="space",
        summary="VLA advisory says obj_box is blocked",
        source_kind="vla_advisory",
        source_refs=["vla_result:1"],
        confidence=0.65,
        advisory=True,
    )

    store.upsert(l1, producer_ts=10)
    update = store.upsert(advisory, producer_ts=11)

    assert update.operation == "conflict"
    assert update.entry.world_anchor_id == "world_anchor:object:obj_box"
    assert update.entry.summary == "L1 says obj_box is reachable"
    assert update.entry.world_truth_marker == "l1_projected_fact_ref"
    assert update.entry.freshness.state == "contested"
    assert update.entry.conflict_state == "conflicted"
    with pytest.raises(ValueError, match="advisory"):
        ActorSceneKnowledgeEntry(
            entry_id="bad",
            actor_id="char_a",
            session_id="session_a",
            scene_id="scene_demo",
            subject_ref="obj_box",
            knowledge_type="space",
            summary="bad",
            source_kind="vla_advisory",
            source_refs=["vla_result:bad"],
            confidence=0.7,
            advisory=True,
            world_truth_marker="l1_projected_fact_ref",
        )


def test_ask_uses_world_anchor_to_conflict_same_object_even_with_different_subject_refs() -> None:
    store = ActorSceneKnowledgeStore()

    store.upsert(
        ActorSceneKnowledgeEntry(
            entry_id="ask:char_a:obj_box:l1",
            actor_id="char_a",
            session_id="session_a",
            scene_id="scene_demo",
            world_anchor_id="world_anchor:object:obj_box",
            subject_ref="obj_box",
            target_ref="obj_box",
            knowledge_type="space",
            summary="L1 says object is reachable",
            source_kind="l1_projected_fact",
            source_refs=["sample_ref:l1:obj_box"],
            confidence=0.95,
            world_truth_marker="l1_projected_fact_ref",
        ),
        producer_ts=10,
    )
    update = store.upsert(
        ActorSceneKnowledgeEntry(
            entry_id="ask:char_a:vla_artifact:vla",
            actor_id="char_a",
            session_id="session_a",
            scene_id="scene_demo",
            world_anchor_id="world_anchor:object:obj_box",
            subject_ref="runtime://artifact/patch-a.png",
            target_ref="obj_box",
            knowledge_type="space",
            summary="VLA says object is blocked",
            source_kind="vla_advisory",
            source_refs=["vla_result:obj_box"],
            confidence=0.65,
            advisory=True,
        ),
        producer_ts=11,
    )

    assert update.operation == "conflict"
    assert len(store.entries_for_actor("char_a")) == 1
    assert update.conflict is not None
    assert update.conflict.world_anchor_id == "world_anchor:object:obj_box"


def test_ask_does_not_merge_nearby_or_named_targets_without_same_world_anchor() -> None:
    store = ActorSceneKnowledgeStore()
    first = ActorSceneKnowledgeEntry(
        entry_id="ask:char_a:box_a:l1",
        actor_id="char_a",
        session_id="session_a",
        scene_id="scene_demo",
        world_anchor_id="world_anchor:object:obj_box_a",
        subject_ref="box",
        target_ref="obj_box_a",
        knowledge_type="space",
        summary="left box reachable",
        source_kind="l1_projected_fact",
        source_refs=["sample_ref:l1:box_a"],
        confidence=0.9,
        world_truth_marker="l1_projected_fact_ref",
    )
    second = first.model_copy(
        update={
            "entry_id": "ask:char_a:box_b:l1",
            "world_anchor_id": "world_anchor:object:obj_box_b",
            "target_ref": "obj_box_b",
            "summary": "right box reachable",
            "source_refs": ["sample_ref:l1:box_b"],
        }
    )

    store.upsert(first, producer_ts=10)
    store.upsert(second, producer_ts=11)

    anchors = {entry.world_anchor_id for entry in store.entries_for_actor("char_a")}
    assert anchors == {"world_anchor:object:obj_box_a", "world_anchor:object:obj_box_b"}


def test_store_marks_stale_expires_and_resolves_conflict() -> None:
    store = ActorSceneKnowledgeStore()
    entry = ActorSceneKnowledgeEntry(
        entry_id="ask:char_a:door:path",
        actor_id="char_a",
        session_id="session_a",
        scene_id="scene_demo",
        subject_ref="door",
        knowledge_type="path",
        summary="door path is open",
        source_kind="l1_projected_fact",
        source_refs=["l1_fact:door:path_open"],
        confidence=0.9,
        freshness={"state": "fresh", "observed_at": 1, "last_confirmed_at": 1, "expires_at": 5},
        world_truth_marker="l1_projected_fact_ref",
    )
    store.upsert(entry, producer_ts=1)

    stale = store.mark_stale(entry.entry_id, producer_ts=2)
    expired = store.expire(now=6)

    assert stale.operation == "stale"
    assert expired[0].operation == "expire"
    failure = store.record_failure(
        actor_id="char_a",
        session_id="session_a",
        scene_id="scene_demo",
        subject_ref="door",
        failure_kind="interaction_failure",
        reason="expected reachable but failed",
        source_refs=["world_result:constraint"],
        producer_ts=7,
    )
    assert failure.operation in {"add", "conflict"}


def test_siming_cannot_read_character_private_ask_store_by_contract() -> None:
    store = ActorSceneKnowledgeStore()
    store.apply_canonical_percept_bundle(_bundle("char_a"), session_id="session_a", producer_ts=10)

    assert store.entries_for_actor("siming") == []
    with pytest.raises(ValueError, match="character"):
        store.apply_canonical_percept_bundle(
            CanonicalPerceptBundle(
                bundle_id="bundle:siming:1",
                consumer_kind="siming",
                subject_id="siming",
                query_id="pqf:siming:1",
                percept_context_id="siming_mm:room_demo",
            )
        )
