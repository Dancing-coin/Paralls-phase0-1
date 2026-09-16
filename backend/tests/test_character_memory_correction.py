from __future__ import annotations

import pytest

from app.character_agent.models.memory_consistency import MemoryCorrectionRequest, MemoryFactClaim, MemorySourceRecord
from app.character_agent.runtime.runtime_loop import CharacterAgentRuntime
from app.models.character_perceived import CharacterPerceivedEvent


def perceived_claim(*, value="destroyed", source="receipt:letter:2", valid_at=2):
    return CharacterPerceivedEvent(
        actor_id="char_a", percept_channel="visual", producer_ts=3,
        room_id="room_demo", scene_id="scene_demo", zone_id="zone_focus",
        perceived_summary=f"letter {value}", source_candidate_event_id=source,
        target_object_id="obj_letter", source_ref_lineage=[source],
        fact_claim=MemoryFactClaim(scope_ref="world:main", subject_ref="obj_letter",
            predicate="state", value=value, valid_at=valid_at, source_ref=source),
    )


def make_runtime(tmp_path, **overrides):
    options = dict(
        storage_root=tmp_path,
        memory_correction_authorizer=lambda principal, request: principal == "siming" and request.actor_id == "char_a",
        memory_source_resolver=lambda source: MemorySourceRecord(claim=perceived_claim().fact_claim, revision=2) if source == "receipt:letter:2" else None,
        memory_now_ts_provider=lambda: 10,
    )
    options.update(overrides)
    return CharacterAgentRuntime(**options)


def request_for(runtime, **updates):
    knowledge = runtime.get_memory_record_bundle("char_a").knowledge_memories[0]
    values = dict(request_id="correction:1", idempotency_key="correction:1", actor_id="char_a",
        target_memory_refs=(knowledge.memory_id,), source_refs=("receipt:letter:2",),
        reason="restore_known_evidence", expected_character_revision=runtime.get_memory_revision("char_a"),
        source_revision_vector={"receipt:letter:2": 2}, requested_at=9, expires_at=20)
    values.update(updates)
    return MemoryCorrectionRequest(**values)


def test_evidence_survives_restart_and_correction_is_idempotent(tmp_path, record_property):
    runtime = make_runtime(tmp_path)
    runtime.record_character_perceived_event_without_cognition(perceived_claim())
    before = runtime.get_memory_record_bundle("char_a")
    assert before.knowledge_memories[0].claim.value == "destroyed"
    request = request_for(runtime)
    receipt = runtime.apply_memory_correction(request, principal_ref="siming")
    assert receipt.status == "applied"
    assert receipt.after_revision == receipt.before_revision + 1
    after = runtime.get_memory_record_bundle("char_a")
    assert after.event_memories[:len(before.event_memories)] == before.event_memories
    assert after.knowledge_memories[0].source_event_id != before.knowledge_memories[0].source_event_id
    restarted = make_runtime(tmp_path)
    assert restarted.get_memory_record_bundle("char_a").knowledge_memories == after.knowledge_memories
    assert restarted.apply_memory_correction(request, principal_ref="siming") == receipt
    changed = request.model_copy(update={"reason": "different_request"})
    assert restarted.apply_memory_correction(changed, principal_ref="siming").reason == "idempotency_conflict"
    record_property("correction_receipt", receipt.model_dump_json())
    record_property("correction_source_event_id", after.knowledge_memories[0].source_event_id)
    record_property("correction_restart_idempotent", "true")


@pytest.mark.parametrize("change,reason", [
    ({"expected_character_revision": 0}, "character_revision_conflict"),
    ({"expires_at": 10}, "request_expired"),
    ({"source_revision_vector": {"receipt:letter:2": 1}}, "source_revision_conflict"),
    ({"source_refs": ("receipt:hidden",), "source_revision_vector": {"receipt:hidden": 2}}, "source_not_known"),
    ({"target_memory_refs": ("knowledge:char_b:secret",)}, "target_memory_not_found"),
])
def test_rejected_correction_never_changes_actor_memory(tmp_path, change, reason):
    runtime = make_runtime(tmp_path)
    runtime.record_character_perceived_event_without_cognition(perceived_claim())
    request = request_for(runtime, **change)
    before = runtime.get_memory_bundle("char_a")
    receipt = runtime.apply_memory_correction(request, principal_ref="siming")
    assert receipt.status == "rejected"
    assert receipt.reason == reason
    assert runtime.get_memory_bundle("char_a") == before


def test_default_edit_is_closed_and_does_not_read_authority(tmp_path):
    runtime = make_runtime(tmp_path, memory_correction_authorizer=None,
        memory_source_resolver=lambda _: pytest.fail("unauthorized authority lookup"))
    runtime.record_character_perceived_event_without_cognition(perceived_claim())
    assert runtime.apply_memory_correction(request_for(runtime), principal_ref="siming").reason == "permission_denied"


def test_committed_correction_recovers_after_projection_failure(tmp_path, monkeypatch):
    runtime = make_runtime(tmp_path)
    runtime.record_character_perceived_event_without_cognition(perceived_claim())
    request = request_for(runtime)
    original = runtime._memory_store.write_event
    def fail_projection(event):
        if event["event_type"] == "character_memory_correction":
            raise OSError("projection interrupted")
        original(event)
    monkeypatch.setattr(runtime._memory_store, "write_event", fail_projection)
    with pytest.raises(OSError, match="projection interrupted"):
        runtime.apply_memory_correction(request, principal_ref="siming")
    restarted = make_runtime(tmp_path)
    receipt = restarted.apply_memory_correction(request, principal_ref="siming")
    assert receipt.status == "applied"
    assert restarted.get_memory_record_bundle("char_a").knowledge_memories[0].claim.value == "destroyed"
    assert len([event for event in restarted.get_session_timeline("char_a") if event["event_type"] == "character_memory_correction"]) == 1


def test_repair_changes_erroneous_projection_and_keeps_experience(tmp_path):
    runtime = make_runtime(tmp_path)
    runtime.record_character_perceived_event_without_cognition(perceived_claim())
    original = runtime.get_memory_record_bundle("char_a").knowledge_memories[0]
    # 模拟旧版本压缩/写回错误：持久经历仍在，但有效认知被错误摘要覆盖。
    runtime._session_append_event(actor_id="char_a", event_type="knowledge_belief_event", producer_ts=4,
        payload={"proposition_key": original.proposition_key, "proposition": "letter intact", "state": "believed", "confidence": 0.8})
    assert runtime.get_memory_record_bundle("char_a").knowledge_memories[0].proposition == "letter intact"
    receipt = runtime.apply_memory_correction(request_for(runtime), principal_ref="siming")
    assert receipt.status == "applied"
    assert runtime.get_memory_record_bundle("char_a").knowledge_memories[0].proposition == "obj_letter:state=destroyed"
    assert runtime.get_memory_record_bundle("char_a").event_memories[0].summary == "letter destroyed"


def test_graph_memory_correction_replays_from_continuity_snapshot(tmp_path):
    from app.character_agent.storage.graph_continuity_store import CharacterGraphContinuityStore
    from app.character_agent.storage.graph_memory_store import CharacterGraphMemoryStore
    from app.models.siming_heavenly_graph import HeavenlyGraphScope
    from app.services.sqlite_heavenly_graph import SQLiteHeavenlyGraphAdapter
    def scope(actor):
        return HeavenlyGraphScope(world_id="world:main", session_id="session:main", story_branch_id="main", graph_namespace="actor_private", owner_actor_id=actor)
    def runtime_for(graph):
        return make_runtime(None, memory_store=CharacterGraphMemoryStore(graph, scope_resolver=scope),
            continuity_store=CharacterGraphContinuityStore(graph, scope_resolver=scope))
    graph = SQLiteHeavenlyGraphAdapter(tmp_path / "memory.sqlite3")
    first = runtime_for(graph)
    first.record_character_perceived_event_without_cognition(perceived_claim())
    request = request_for(first)
    receipt = first.apply_memory_correction(request, principal_ref="siming")
    before = first.get_memory_record_bundle("char_a")
    graph.close()
    graph = SQLiteHeavenlyGraphAdapter(tmp_path / "memory.sqlite3")
    restored = runtime_for(graph)
    assert restored.apply_memory_correction(request, principal_ref="siming") == receipt
    assert restored.get_memory_record_bundle("char_a").knowledge_memories == before.knowledge_memories
    graph.close()


def test_session_commit_failure_leaves_no_phantom_receipt(tmp_path, monkeypatch):
    runtime = make_runtime(tmp_path)
    runtime.record_character_perceived_event_without_cognition(perceived_claim())
    request = request_for(runtime)
    before = runtime.get_session_timeline("char_a")
    monkeypatch.setattr(
        runtime._session_store,
        "_persist",
        lambda *_: (_ for _ in ()).throw(OSError("disk full")),
    )
    with pytest.raises(OSError, match="disk full"):
        runtime.apply_memory_correction(request, principal_ref="siming")
    assert runtime.get_session_timeline("char_a") == before


def test_siming_adapter_uses_server_principal_not_request_payload(tmp_path):
    from app.services.siming_character_dispatch_adapter import SimingCharacterDispatchAdapter
    runtime = make_runtime(tmp_path)
    runtime.record_character_perceived_event_without_cognition(perceived_claim())
    request = request_for(runtime)
    assert SimingCharacterDispatchAdapter(runtime=runtime).dispatch_memory_correction(request).reason == "permission_denied"
    adapter = SimingCharacterDispatchAdapter(runtime=runtime, memory_edit_principal_ref="siming")
    assert adapter.dispatch_memory_correction(request).status == "applied"


def test_real_source_revision_cannot_authorize_fabricated_content(tmp_path):
    runtime = make_runtime(tmp_path)
    runtime.record_character_perceived_event_without_cognition(perceived_claim(value="intact"))
    assert runtime.apply_memory_correction(request_for(runtime), principal_ref="siming").reason == "source_content_mismatch"


def test_reused_source_ref_with_different_claim_is_rejected(tmp_path):
    runtime = make_runtime(tmp_path)
    runtime.record_character_perceived_event_without_cognition(perceived_claim(value="intact"))
    runtime.record_character_perceived_event_without_cognition(perceived_claim())
    assert runtime.apply_memory_correction(request_for(runtime), principal_ref="siming").reason == "source_conflict"
