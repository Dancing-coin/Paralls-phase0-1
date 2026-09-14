import pytest

from app.character_agent.models.memory_consistency import MemoryFactClaim, MemorySourceRecord
from app.character_agent.runtime.runtime_loop import CharacterAgentRuntime
from app.models.character_perceived import CharacterPerceivedEvent


def expose_conflict(runtime, actor_id="char_a", *, scene_id="scene_demo"):
    for index, value in enumerate(("intact", "destroyed")):
        runtime.record_character_perceived_event_without_cognition(CharacterPerceivedEvent(
            actor_id=actor_id, percept_channel="visual", producer_ts=index + 1,
            room_id="room_demo", scene_id=scene_id, zone_id="zone_focus",
            perceived_summary=f"letter {value}", source_candidate_event_id=f"source:{index}",
            target_object_id="obj_letter", fact_claim=MemoryFactClaim(scope_ref="world:main",
                subject_ref="obj_letter", predicate="state", value=value, valid_at=1,
                source_ref=f"source:{index}")))


def test_known_conflict_defers_to_owner_truth_without_rewriting_memory():
    truth = MemorySourceRecord(revision=2, claim=MemoryFactClaim(scope_ref="world:main",
        subject_ref="obj_letter", predicate="state", value="removed", valid_at=1, source_ref="source:0"))
    runtime = CharacterAgentRuntime(memory_source_resolver=lambda source: truth if source == "source:0" else None)
    expose_conflict(runtime)
    before = runtime.get_memory_record_bundle("char_a")
    result = runtime.run_memory_consistency_pass("char_a", producer_ts=10)
    assert result.status == "truth_wins"
    assert result.verification_request_refs
    assert runtime.get_memory_record_bundle("char_a") == before
    assert "removed" not in str(runtime.get_session_timeline("char_a"))
    assert not any(event["event_type"] == "character_memory_correction"
        for event in runtime.get_session_timeline("char_a"))


def test_known_failure_requires_exposure_and_does_not_materialize_memory():
    runtime = CharacterAgentRuntime()
    expose_conflict(runtime)
    before = runtime.get_memory_record_bundle("char_a")
    result = runtime.run_memory_consistency_pass("char_a", producer_ts=10)
    assert result.status == "verification_required"
    assert runtime.get_memory_record_bundle("char_a") == before
    requested = [event for event in runtime.get_session_timeline("char_a")
        if event["event_type"] == "character_memory_verification_requested"]
    assert [event["payload"]["request_id"] for event in requested] == list(result.verification_request_refs)


@pytest.mark.parametrize("retention,interval", [("normal", 60_000), ("strong", 300_000)])
def test_consistency_rate_limit_survives_restart_and_reuses_pending_request(tmp_path, monkeypatch, retention, interval):
    runtime = CharacterAgentRuntime(storage_root=tmp_path)
    profile = runtime._profile_registry.get("char_a")
    monkeypatch.setattr(profile.capability_constraint_layer, "memory_retention", retention)
    expose_conflict(runtime)
    first = runtime.run_memory_consistency_pass("char_a", producer_ts=10)
    restarted = CharacterAgentRuntime(storage_root=tmp_path)
    monkeypatch.setattr(restarted._profile_registry.get("char_a").capability_constraint_layer, "memory_retention", retention)
    before = restarted.get_memory_revision("char_a")
    limited = restarted.run_memory_consistency_pass("char_a", producer_ts=10 + interval - 1)
    assert limited.status == "rate_limited"
    assert limited.next_check_at == 10 + interval
    assert restarted.get_memory_revision("char_a") == before
    retry = restarted.run_memory_consistency_pass("char_a", producer_ts=10 + interval)
    assert retry.status == "verification_required"
    assert retry.verification_request_refs == first.verification_request_refs


def test_pass_skips_non_rigorous_actor_and_unexposed_actor_without_writes():
    runtime = CharacterAgentRuntime()
    expose_conflict(runtime, actor_id="char_c")
    before = runtime.get_memory_revision("char_c")
    assert runtime.run_memory_consistency_pass("char_c", producer_ts=10).status == "policy_skipped"
    assert runtime.get_memory_revision("char_c") == before
    assert runtime.run_memory_consistency_pass("char_b", producer_ts=10).status == "no_conflicts"
    assert runtime.get_session_timeline("char_b") == []


def test_pass_uses_known_conflict_scene_and_leaves_other_anomalies_alone():
    runtime = CharacterAgentRuntime()
    expose_conflict(runtime, scene_id="scene_archive")
    runtime.record_settlement_result(actor_id="char_a", producer_ts=3, payload={
        "result_type": "constraint_state_result", "target_object_id": "obj_unrelated",
        "room_id": "room_demo", "scene_id": "scene_archive", "constraint_summary": "unreachable"})
    result = runtime.run_memory_consistency_pass("char_a", producer_ts=10)
    requested = [event["payload"] for event in runtime.get_session_timeline("char_a")
        if event["event_type"] == "character_memory_verification_requested"]
    assert result.status == "verification_required"
    assert len(requested) == 1
    assert requested[0]["scene_id"] == "scene_archive"
    assert requested[0]["subject_ref"] == "obj_letter"


@pytest.mark.parametrize("producer_ts", [-1, 0, 1.5, True])
def test_pass_rejects_invalid_timestamp_before_writing(producer_ts):
    runtime = CharacterAgentRuntime()
    expose_conflict(runtime)
    before = runtime.get_memory_revision("char_a")
    with pytest.raises(ValueError):
        runtime.run_memory_consistency_pass("char_a", producer_ts=producer_ts)
    assert runtime.get_memory_revision("char_a") == before
