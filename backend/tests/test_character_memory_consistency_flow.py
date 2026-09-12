from __future__ import annotations

import pytest

from app.character_agent.models.memory_consistency import MemoryFactClaim
from app.character_agent.reasoning.active_perception import ActivePerceptionResult
from app.character_agent.runtime.runtime_loop import CharacterAgentRuntime
from app.models.character_perceived import CharacterPerceivedEvent
from app.models.player_input import InteractIntent
from app.services.esm_service import ESMService


def observation(value="visible", source="percept:letter:1", at=1, *, channel="visual", speaker=""):
    return CharacterPerceivedEvent(actor_id="char_a", percept_channel=channel, producer_ts=at,
        room_id="room_demo", scene_id="scene_demo", zone_id="zone_focus", target_object_id="obj_letter",
        source_actor_id=speaker, perceived_summary=f"letter {value}", source_candidate_event_id=source,
        source_ref_lineage=[source], fact_claim=MemoryFactClaim(scope_ref="world:main", subject_ref="obj_letter",
            predicate="state", value=value, valid_at=at, source_ref=source))


def test_world_change_does_not_teach_actor_until_successful_recheck(tmp_path, record_property):
    runtime = CharacterAgentRuntime(storage_root=tmp_path)
    esm = ESMService()
    runtime.record_character_perceived_event_without_cognition(observation())
    for action in ("inspect", "destroy"):
        intent = InteractIntent(player_id="player", actor_id="char_b", room_id="room_demo",
            target_object_id="obj_letter", interaction_type=action, producer_ts=2)
        assert esm.resolve_interaction(intent, actor_position=esm.OBJECT_POSITIONS["obj_letter"]).resolution_status == "accepted"
        policy = esm.interaction_policy_for("obj_letter", action, room_id="room_demo", scene_id="scene_demo", zone_id="zone_focus", actor_id="char_b")
        esm.commit_interaction_state(room_id="room_demo", scene_id="scene_demo", zone_id="zone_focus",
            target_object_id="obj_letter", interaction_type=action, actor_id="char_b", current_state=policy["current_state"])
    # 非视角故事已推进，但 A 未获得事件，仍只记得旧的可见状态。
    assert runtime.get_memory_record_bundle("char_a").knowledge_memories[0].claim.value == "visible"
    state = esm.interaction_state_for(room_id="room_demo", scene_id="scene_demo", zone_id="zone_focus", target_object_id="obj_letter")
    assert state == "removed_from_surface"
    failure = esm.reject_interaction_state(InteractIntent(player_id="player", actor_id="char_a", room_id="room_demo",
        target_object_id="obj_letter", interaction_type="read", producer_ts=3), actual_state=state, expected_state="partially_visible")
    runtime.record_settlement_result(actor_id="char_a", producer_ts=4, payload=failure.model_dump())
    request = runtime.get_memory_verification_requests("char_a", producer_ts=5)[0]
    result = ActivePerceptionResult(result_id="recheck:letter:1", request_id=request.request_id,
        actor_id="char_a", session_id=request.session_id, scene_id=request.scene_id, subject_ref="obj_letter",
        pqf_query_id=request.pqf_query_id, provider_result_refs=["provider:letter:6"],
        confidence=1.0, summary="letter removed", fact_claim=MemoryFactClaim(scope_ref="world:main",
            subject_ref="obj_letter", predicate="state", value="removed_from_surface", valid_at=6, source_ref="provider:letter:6"))
    runtime.apply_memory_verification_result(result, producer_ts=6)
    knowledge = next(k for k in runtime.get_memory_record_bundle("char_a").knowledge_memories if k.claim)
    assert knowledge.claim.value == "removed_from_surface"
    assert any(m.summary == "letter visible" for m in runtime.get_memory_record_bundle("char_a").event_memories)
    assert esm.interaction_state_for(room_id="room_demo", scene_id="scene_demo", zone_id="zone_focus", target_object_id="obj_letter") == state
    assert CharacterAgentRuntime(storage_root=tmp_path).get_memory_record_bundle("char_a").knowledge_memories == runtime.get_memory_record_bundle("char_a").knowledge_memories
    record_property("world_state_after", state)
    record_property("known_state_after", knowledge.claim.value)
    record_property("received_source_ref", knowledge.claim.source_ref)
    record_property("verification_request", request.request_id)


def test_unsolicited_or_failed_provider_result_cannot_update_memory():
    runtime = CharacterAgentRuntime()
    runtime.record_character_perceived_event_without_cognition(observation())
    before = runtime.get_memory_bundle("char_a")
    result = ActivePerceptionResult(result_id="unrequested", request_id="fake", actor_id="char_a",
        session_id="room_demo", scene_id="scene_demo", subject_ref="obj_letter", pqf_query_id="pqf:fake",
        provider_result_refs=["provider:fake"], confidence=1, summary="secret", failure_reason="unreachable")
    with pytest.raises(ValueError):
        runtime.apply_memory_verification_result(result, producer_ts=3)
    assert runtime.get_memory_bundle("char_a") == before


def test_record_content_only_enters_reader_memory_after_actual_authorized_read():
    esm = ESMService(readable_records={"obj_plaque": {"content": "The archive closes at dusk.",
        "source_ref": "record:archive-hours:1", "allowed_actor_ids": {"char_a"}}})
    runtime = CharacterAgentRuntime()
    for actor in ("char_a", "char_b"):
        event = InteractIntent(player_id="player", actor_id=actor, room_id="room_demo",
            target_object_id="obj_plaque", interaction_type="read", producer_ts=5)
        result = esm.resolve_interaction(event, actor_position=esm.OBJECT_POSITIONS["obj_plaque"])
        runtime.record_settlement_result(actor_id=actor, producer_ts=6, payload=result.model_dump())
    reader = [k for k in runtime.get_memory_record_bundle("char_a").knowledge_memories if k.claim]
    assert len(reader) == 1
    assert reader[0].claim.predicate == "record_content"
    assert reader[0].claim.value == "The archive closes at dusk."
    assert reader[0].claim.source_ref == "record:archive-hours:1"
    assert "The archive closes at dusk." not in str(runtime.get_memory_bundle("char_b"))


def test_disclosed_fact_updates_belief_but_keeps_who_said_it():
    runtime = CharacterAgentRuntime()
    runtime.record_character_perceived_event_without_cognition(observation())
    runtime.record_character_perceived_event_without_cognition(observation("destroyed", "dialogue:received:2", 2,
        channel="dialogue", speaker="char_b"))
    knowledge = runtime.get_memory_record_bundle("char_a").knowledge_memories[0]
    assert knowledge.claim.value == "destroyed"
    assert knowledge.state == "tentatively_believed"
    assert any(event["payload"].get("source_actor_id") == "char_b" for event in runtime.get_session_timeline("char_a"))


def test_focused_recall_recovers_own_known_fact_without_unrelated_memories():
    runtime = CharacterAgentRuntime()
    runtime.record_character_perceived_event_without_cognition(observation("destroyed", at=2))
    for index in range(20):
        runtime.record_character_perceived_event_without_cognition(CharacterPerceivedEvent(
            actor_id="char_a", percept_channel="auditory", producer_ts=index + 10,
            room_id="room_demo", scene_id="scene_demo", zone_id="zone_focus",
            perceived_summary="weather " * 100, source_candidate_event_id=f"noise:{index}"))
    focused = runtime.get_target_memory_record_bundle("char_a", {"obj_letter"})
    assert focused.knowledge_memories[0].claim.value == "destroyed"
    assert {m.summary for m in focused.event_memories} == {"letter destroyed"}
    assert runtime.get_target_memory_record_bundle("char_b", {"obj_letter"}).knowledge_memories == []


def test_strong_actor_defers_when_even_focused_evidence_exceeds_budget():
    from app.character_agent.gateway.memory_recall import CharacterMemoryRecallPolicy
    from app.models.character_agent_runtime import CharacterInterpretation, CharacterPrivateWorldSnapshot
    runtime = CharacterAgentRuntime()
    runtime.record_character_perceived_event_without_cognition(observation("destroyed", at=2))
    runtime._l3._memory_recall_policy = CharacterMemoryRecallPolicy(token_budget=1)
    snapshot = CharacterPrivateWorldSnapshot(actor_id="char_a", room_id="room_demo", scene_id="scene_demo",
        zone_id="zone_focus", producer_ts=3, updated_at=3, attention_targets=["obj_letter"])
    interpretation = CharacterInterpretation(actor_id="char_a", interpreted_summary="inspect letter",
        interpretation_type="curiosity", salience_score=1, ambiguity_level="low", risk_level="low",
        opportunity_level="low", attention_target="obj_letter")
    def run_model(memory_override=None):
        return runtime._l3.select_intent(interpretation, snapshot=snapshot.model_dump(),
            effective_profile={"capability_constraint_layer": {"memory_retention": "strong"}},
            memory_bundle=memory_override or runtime.get_memory_record_bundle("char_a"))
    decision = runtime._select_intent_with_continuity_floor(actor_id="char_a", producer_ts=3, snapshot=snapshot,
        interpretation=interpretation, control_mode="agent_full_auto", source_stage="test", run_model=run_model)
    assert decision.selected_intent == "stay_silent"
    assert decision.fallback_mode == "memory_evidence_pending"
    assert any(event["event_type"] == "character_memory_recall_deferred" for event in runtime.get_session_timeline("char_a"))


def test_model_belief_delta_cannot_erase_received_structured_fact():
    from app.models.character_agent_runtime import CharacterInterpretation
    runtime = CharacterAgentRuntime()
    runtime.record_character_perceived_event_without_cognition(observation("destroyed", at=2))
    original = runtime.get_memory_record_bundle("char_a").knowledge_memories[0]
    interpretation = CharacterInterpretation(actor_id="char_a", interpreted_summary="wrong summary",
        interpretation_type="curiosity", salience_score=1, ambiguity_level="low", risk_level="low",
        opportunity_level="low", belief_deltas=[{"proposition_key": original.proposition_key,
            "proposition": "letter intact", "state": "believed", "confidence": 1.0}])
    runtime._apply_cognition_update(actor_id="char_a", producer_ts=3, interpretation=interpretation)
    assert runtime.get_memory_record_bundle("char_a").knowledge_memories[0] == original


def test_public_authority_event_does_not_disclose_private_record_content():
    from app.services.phase0_authority_event_adapter import Phase0AuthorityEventAdapter
    esm = ESMService(readable_records={"obj_plaque": {"content": "private note", "source_ref": "record:private:1", "allowed_actor_ids": {"char_a"}}})
    intent = InteractIntent(player_id="player", actor_id="char_a", room_id="room_demo", target_object_id="obj_plaque", interaction_type="read", producer_ts=1)
    result = esm.resolve_interaction(intent, actor_position=esm.OBJECT_POSITIONS["obj_plaque"])
    assert result.read_content == "private note"
    public = Phase0AuthorityEventAdapter().world_result_event(result, source_event=intent)
    assert "private note" not in str(public.model_dump())
    assert "record:private:1" not in str(public.model_dump())


def test_main_world_result_handoff_deposits_reader_evidence(monkeypatch):
    from app import main
    from app.services.authority_event_bus import InMemoryAuthorityEventBus
    runtime = CharacterAgentRuntime()
    monkeypatch.setattr(main, "character_agent_runtime", runtime)
    monkeypatch.setattr(main, "authority_event_bus", InMemoryAuthorityEventBus())
    esm = ESMService(readable_records={"obj_plaque": {"content": "reader-only note", "source_ref": "record:reader:1", "allowed_actor_ids": {"char_a"}}})
    intent = InteractIntent(player_id="player", actor_id="char_a", room_id="room_demo", target_object_id="obj_plaque", interaction_type="read", producer_ts=1)
    result = esm.resolve_interaction(intent, actor_position=esm.OBJECT_POSITIONS["obj_plaque"])
    main._publish_world_result_authority_event(result, source_event=intent)
    assert any(record.claim and record.claim.value == "reader-only note" for record in runtime.get_memory_record_bundle("char_a").knowledge_memories)


def test_strong_recall_recovers_fact_missing_from_current_store_view(monkeypatch):
    from app.character_agent.storage.memory_store import CharacterAgentMemoryStore
    runtime = CharacterAgentRuntime()
    runtime.record_character_perceived_event_without_cognition(observation("destroyed", at=2))
    runtime._l1.apply_character_perceived_event(observation("destroyed", at=2))
    # 模拟可重建投影丢失；已获知经历仍保存在 Character Core 时间线。
    runtime._memory_store = CharacterAgentMemoryStore()
    monkeypatch.setattr(runtime, "_effective_profile_payload", lambda actor: {"capability_constraint_layer": {"memory_retention": "strong"}})
    restored = runtime.get_memory_record_bundle("char_a")
    assert restored.knowledge_memories[0].claim.value == "destroyed"
    assert restored.event_memories[0].summary == "letter destroyed"


def pending_recheck(runtime):
    runtime.record_character_perceived_event_without_cognition(observation())
    runtime.record_settlement_result(actor_id="char_a", producer_ts=2, payload={
        "result_type": "constraint_state_result", "result_id": "failure:letter", "actor_id": "char_a",
        "target_object_id": "obj_letter", "constraint_summary": "letter unavailable"})
    request = runtime.get_memory_verification_requests("char_a", producer_ts=3)[0]
    result = ActivePerceptionResult(result_id="recheck:letter", request_id=request.request_id,
        actor_id="char_a", session_id=request.session_id, scene_id=request.scene_id, subject_ref="obj_letter",
        pqf_query_id=request.pqf_query_id, provider_result_refs=["provider:letter:4"], confidence=1,
        summary="letter removed", fact_claim=MemoryFactClaim(scope_ref="world:main", subject_ref="obj_letter",
            predicate="state", value="removed", valid_at=4, source_ref="provider:letter:4"))
    return request, result


def test_recheck_request_is_reused_until_evidence_arrives(tmp_path):
    runtime = CharacterAgentRuntime(storage_root=tmp_path)
    request, result = pending_recheck(runtime)
    revision = runtime.get_memory_revision("char_a")
    assert runtime.get_memory_verification_requests("char_a", producer_ts=4) == [request]
    assert runtime.get_memory_revision("char_a") == revision
    runtime.apply_memory_verification_result(result, producer_ts=4)
    assert runtime.get_memory_verification_requests("char_a", producer_ts=5) == []
    restarted = CharacterAgentRuntime(storage_root=tmp_path)
    assert restarted.get_memory_verification_requests("char_a", producer_ts=6) == []


def test_recheck_persistence_failure_does_not_change_knowledge_and_can_retry(tmp_path, monkeypatch):
    runtime = CharacterAgentRuntime(storage_root=tmp_path)
    _, result = pending_recheck(runtime)
    before = [entry.model_dump() for entry in runtime._l1.get_actor_scene_knowledge_store().entries_for_actor("char_a")]
    def fail(*args, **kwargs):
        raise OSError("disk unavailable")
    with monkeypatch.context() as patch:
        patch.setattr(runtime._session_store, "_persist", fail)
        with pytest.raises(OSError):
            runtime.apply_memory_verification_result(result, producer_ts=4)
    assert [entry.model_dump() for entry in runtime._l1.get_actor_scene_knowledge_store().entries_for_actor("char_a")] == before
    runtime.apply_memory_verification_result(result, producer_ts=4)
    assert runtime.get_memory_record_bundle("char_a").knowledge_memories[0].claim.value == "removed"


def test_committed_recheck_projection_can_be_retried_without_duplicate_event(tmp_path, monkeypatch):
    runtime = CharacterAgentRuntime(storage_root=tmp_path)
    _, result = pending_recheck(runtime)
    def fail(*args, **kwargs):
        raise OSError("projection interrupted")
    with monkeypatch.context() as patch:
        patch.setattr(runtime._memory_store, "write_event", fail)
        with pytest.raises(OSError):
            runtime.apply_memory_verification_result(result, producer_ts=4)
    revision = runtime.get_memory_revision("char_a")
    runtime.apply_memory_verification_result(result, producer_ts=4)
    assert runtime.get_memory_revision("char_a") == revision
    assert runtime.get_memory_record_bundle("char_a").knowledge_memories[0].claim.value == "removed"
    restarted = CharacterAgentRuntime(storage_root=tmp_path)
    restarted.apply_memory_verification_result(result, producer_ts=4)
    assert restarted.get_memory_revision("char_a") == revision
    assert restarted.get_memory_verification_requests("char_a", producer_ts=5) == []


def test_recheck_cannot_replace_fact_using_another_world_branch():
    runtime = CharacterAgentRuntime()
    _, result = pending_recheck(runtime)
    result.fact_claim.scope_ref = "world:other"
    with pytest.raises(ValueError, match="scope"):
        runtime.apply_memory_verification_result(result, producer_ts=4)


def test_actual_interaction_failure_reaches_l3_and_new_evidence_clears_recheck_reason():
    from app.models.character_agent_runtime import CharacterInterpretation
    runtime = CharacterAgentRuntime()
    runtime._l1.apply_character_perceived_event(observation())
    _, result = pending_recheck(runtime)
    interpretation = CharacterInterpretation(actor_id="char_a", interpreted_summary="letter unavailable",
        interpretation_type="world_signal", salience_score=.8, ambiguity_level="high", risk_level="low",
        opportunity_level="medium", attention_target="obj_letter")
    def plan():
        return runtime._l3.build_intent_plan(interpretation=interpretation, control_mode="agent_full_auto",
            snapshot=runtime.get_private_snapshot("char_a").model_dump(), memory_bundle=runtime.get_memory_record_bundle("char_a"),
            unresolved_tensions=runtime.get_unresolved_tensions("char_a"))
    assert plan()["verification"]["reason"] == "failed_interaction"
    runtime.apply_memory_verification_result(result, producer_ts=4)
    assert plan()["verification"] == {}
