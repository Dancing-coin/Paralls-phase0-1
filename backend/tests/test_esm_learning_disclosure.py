import pytest

from app.gameplay.event_schema_registry import EventSchemaRegistry
from app.gameplay.event_store import GameplayEventStore
from app.models.player_input import InteractIntent
from app.services.esm_service import ESMService, ESM_OBJECT_SETTLEMENT_SCHEMA


def event():
    return InteractIntent(player_id="p1", room_id="room_demo", scene_id="scene_demo",
        zone_id="zone_focus", actor_id="char_a", intent_type="interact_intent",
        producer_ts=10, target_object_id="obj_plaque", interaction_type="inspect",
        turn_id="turn:1", execution_contract_ref="contract:1")


def disclose(service, command, *, world_ref, receipt, action_request=None):
    return service.publish_learning_disclosure(command, world_ref=world_ref, receipt=receipt,
        action_request=action_request or service.build_action_request(command))


def committed_service():
    schemas = EventSchemaRegistry()
    schemas.register(ESM_OBJECT_SETTLEMENT_SCHEMA)
    schemas.register(ESMService.LEARNING_DISCLOSURE_SCHEMA)
    store = GameplayEventStore(event_schema_registry=schemas)
    service = ESMService(store=store, learning_disclosure_scopes={
        ("room_demo", "scene_demo", "zone_focus"): "world:test"})
    result, receipt = service.settle_object_interaction(event(), action_request=service.build_action_request(event()),
        actor_position=(-2.2, 1.2, -2))
    assert receipt is not None and receipt.committed
    return service, store, result, receipt


def test_esm_owner_disclosure_is_actor_private_and_binds_original_receipt():
    service, store, result, receipt = committed_service()
    disclosure = disclose(service, event(), world_ref="world:test",
        receipt=receipt)
    assert disclosure.committed
    event_record = store.get_event(disclosure.committed_event_ids[0])
    assert event_record.visibility_policy == "actor_private:char_a"
    assert event_record.payload["source_event_id"]
    assert event_record.payload["source_transaction_id"] == receipt.transaction_id
    assert event_record.payload["world_ref"] == "world:test"
    assert event_record.payload["scene_id"] == "scene_demo"
    assert event_record.payload["target_object_id"] == "obj_plaque"
    assert event_record.payload["accepted"] is True
    assert "current_state" not in event_record.payload and "request" not in event_record.payload


def test_esm_disclosure_rejects_wrong_receipt_scope_without_write():
    service, store, _, receipt = committed_service()
    before = store.export_snapshot()
    wrong = event().model_copy(update={"actor_id": "char_b", "execution_contract_ref": "contract:wrong"})
    with pytest.raises(ValueError, match="learning_disclosure"):
        disclose(service, wrong, world_ref="world:test", receipt=receipt)
    assert store.export_snapshot() == before


def test_esm_disclosure_exact_retry_and_changed_world_conflict():
    service, store, _, receipt = committed_service()
    first = disclose(service, event(), world_ref="world:test", receipt=receipt)
    retry = disclose(service, event(), world_ref="world:test", receipt=receipt)
    assert retry == first
    with pytest.raises(ValueError, match="idempotency"):
        disclose(service, event(), world_ref="world:other", receipt=receipt)
    assert store.get_last_global_sequence() == first.global_sequence_range[1]


def test_failed_object_receipt_cannot_be_disclosed():
    schemas = EventSchemaRegistry()
    schemas.register(ESM_OBJECT_SETTLEMENT_SCHEMA)
    schemas.register(ESMService.LEARNING_DISCLOSURE_SCHEMA)
    store = GameplayEventStore(event_schema_registry=schemas)
    service = ESMService(store=store)
    with pytest.raises(ValueError, match="learning_disclosure"):
        disclose(service, event(), world_ref="world:test", receipt=None)


def test_scope_registration_is_required_for_first_disclosure():
    service, store, _, receipt = committed_service()
    unregistered = ESMService(store=store)
    before = store.export_snapshot()
    with pytest.raises(ValueError, match="scope_invalid"):
        disclose(unregistered, event(), world_ref="world:test", receipt=receipt)
    assert store.export_snapshot() == before


def test_disclosure_is_a_real_registered_learning_source():
    from app.character_agent.skills.catalog import create_core_skill_registry
    from app.character_agent.skills.learning_authority import (
        LearningCommitRequest, LearningObjectRule, LearningSourceRule, RegisteredLearningAuthority,
    )

    service, store, _, receipt = committed_service()
    store._event_schema_registry.register(RegisteredLearningAuthority.SCHEMA)
    disclosed = disclose(service, event(), world_ref="world:test", receipt=receipt)
    source = store.get_event(disclosed.committed_event_ids[0])
    rule = LearningObjectRule(object_id="lesson:personal-inspect@1", world_ref="world:test", revision=1,
        skill_id="observation", operation="upgrade", stage="practiced", method="practice",
        caller_principal="service:learning", rank="basic", proficiency=.5, confidence=.6,
        source=LearningSourceRule(event_type=source.event_type, schema_version=1,
            principal_ref="authority:esm:object", subject_field="actor_id", world_field="world_ref",
            success_field="accepted", success_value=True))
    owner = RegisteredLearningAuthority(store=store, registry=create_core_skill_registry(), rules=[rule])
    learned = owner.settle(LearningCommitRequest(command_id="learn:disclosed", idempotency_key="learn:disclosed",
        actor_id="char_a", world_ref="world:test", object_id=rule.object_id, rule_digest=rule.digest,
        operation="upgrade", stage="practiced", method="practice", evidence_refs=(source.event_id,),
        expected_source_revisions={source.stream_id: source.stream_revision}, expected_revision=0,
        causation_id=source.event_id, correlation_id=source.correlation_id), caller_principal="service:learning")
    assert learned.committed
    assert owner.states(world_ref="world:test", actor_id="char_a")[0].evidence_refs == [source.event_id]
    assert store.get_event(receipt.committed_event_ids[0]).visibility_policy == "authority_only"


def test_disclosure_sqlite_reopen_retry_does_not_require_scope_registration(tmp_path):
    from app.gameplay.event_store import DurableGameplayEventStore

    path = tmp_path / "world.sqlite3"
    store = DurableGameplayEventStore(path)
    try:
        service = ESMService(store=store, learning_disclosure_scopes={
            ("room_demo", "scene_demo", "zone_focus"): "world:test"})
        _, original = service.settle_object_interaction(event(), action_request=service.build_action_request(event()),
            actor_position=(-2.2, 1.2, -2))
        first = disclose(service, event(), world_ref="world:test", receipt=original)
        # Source stream advances, but retry recovers the originally disclosed fact.
        second = event().model_copy(update={"turn_id": "turn:2", "execution_contract_ref": "contract:2", "producer_ts": 20})
        service.settle_object_interaction(second, action_request=service.build_action_request(second),
            actor_position=(-2.2, 1.2, -2))
        sequence = store.get_last_global_sequence()
    finally:
        store.close()
    store = DurableGameplayEventStore(path)
    try:
        recovered = ESMService(store=store)
        assert disclose(recovered, event(), world_ref="world:test", receipt=original) == first
        assert store.get_last_global_sequence() == sequence
    finally:
        store.close()


def test_disclosure_source_cas_conflict_does_not_publish(monkeypatch):
    service, store, _, receipt = committed_service()
    append = store.append_batch

    def race(batch):
        monkeypatch.setattr(store, "append_batch", append)
        second = event().model_copy(update={"turn_id": "turn:2", "execution_contract_ref": "contract:2", "producer_ts": 20})
        service.settle_object_interaction(second, action_request=service.build_action_request(second),
            actor_position=(-2.2, 1.2, -2))
        return append(batch)

    monkeypatch.setattr(store, "append_batch", race)
    rejected = disclose(service, event(), world_ref="world:test", receipt=receipt)
    assert not rejected.committed and rejected.failure.error_code == "revision_conflict"
    assert all(not stream.startswith("gameplay:esm:learning:") for stream in store.get_stream_heads())


def test_disclosure_uses_original_request_time_and_rejects_changed_receipt():
    service, store, _, receipt = committed_service()
    before = store.export_snapshot()
    with pytest.raises(ValueError, match="source_invalid"):
        disclose(service, event(), world_ref="world:test", receipt=receipt.model_copy(update={"transaction_id": "fake"}))
    assert store.export_snapshot() == before
    disclosed = disclose(service, event().model_copy(update={"producer_ts": 999}),
        action_request=service.build_action_request(event()), world_ref="world:test", receipt=receipt)
    assert store.get_event(disclosed.committed_event_ids[0]).payload["producer_ts"] == 10


def test_canonical_l4_execution_emits_disclosure_before_session_outcome_and_recovers(tmp_path, monkeypatch):
    from app.character_agent.execution.object_execution import CharacterObjectExecution
    from test_character_object_execution import vertical

    with vertical(tmp_path) as (_, runtime, _, source, world, sessions, clock, contract):
        owner = ESMService(store=world, learning_disclosure_scopes={("r", "s", "z"): "world:test"})
        execution = CharacterObjectExecution(runtime=runtime, owner=owner, source=source,
            scopes=tuple(source._scopes.values()), clock_ms=lambda: clock[0], learning_world_ref="world:test")
        original_record = runtime.record_settlement_result
        monkeypatch.setattr(runtime, "record_settlement_result", lambda **_: (_ for _ in ()).throw(OSError("session write failed")))
        execution.offer(contract)
        with pytest.raises(OSError, match="session write failed"):
            execution.execute(contract)
        sequence = world.get_last_global_sequence()
        assert sequence == 3  # spatial sample, object receipt, personal disclosure
        monkeypatch.setattr(runtime, "record_settlement_result", original_record)
        result = execution.execute(contract)
        assert result[3].committed and world.get_last_global_sequence() == sequence
        disclosures = [stream for stream in world.get_stream_heads() if stream.startswith("gameplay:esm:learning:")]
        assert len(disclosures) == 1
        record = world.read_stream(disclosures[0])[0]
        assert record.payload["source_transaction_id"] == result[3].transaction_id
        assert record.visibility_policy == "actor_private:char_a"
