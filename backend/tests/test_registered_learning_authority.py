"""Registered source receipts, durable learned facts and existing capability consumer."""
import pytest

from app.character_agent.skills.learning_authority import (
    LearningCommitRequest, LearningObjectRule, LearningSourceRule, RegisteredLearningAuthority,
)
from app.character_agent.skills.catalog import create_core_skill_registry
from app.character_agent.skills.service import CharacterSkillService
from app.gameplay.event_store import DurableGameplayEventStore, GameplayEventStore
from app.gameplay.settlement_plan import build_atomic_event_batch


def rule(**changes):
    values = dict(object_id="lesson:survey@1", world_ref="world:test", revision=1,
        skill_id="observation", operation="upgrade", stage="practiced", method="practice",
        caller_principal="service:learning", rank="basic", proficiency=.55, confidence=.6,
        source=LearningSourceRule(event_type="lesson.practice_committed", schema_version=1,
            principal_ref="authority:practice", subject_field="actor_id", world_field="world_ref",
            success_field="accepted", success_value=True))
    return LearningObjectRule(**{**values, **changes})


def source(store, *, command="practice:1", actor="char_a", principal="authority:practice", accepted=True):
    receipt = store.append_batch(build_atomic_event_batch(command_id=command, principal_ref=principal,
        stream_id="practice:char_a", expected_revision=store.get_stream_head("practice:char_a"),
        event_specs=(("lesson.practice_committed", dict(actor_id=actor, world_ref="world:test", accepted=accepted)),),
        idempotency_key=command, causation_id="cause", correlation_id="corr"))
    assert receipt.committed
    return receipt.committed_event_ids[0]


def setup(store=None, **changes):
    store = store or GameplayEventStore()
    registration = rule(**changes)
    owner = RegisteredLearningAuthority(store=store, registry=create_core_skill_registry(), rules=[registration])
    evidence = source(store)
    request = LearningCommitRequest(command_id="learn:1", idempotency_key="learning:1", actor_id="char_a",
        world_ref="world:test", object_id=registration.object_id, rule_digest=registration.digest,
        operation=registration.operation, stage=registration.stage, method=registration.method,
        evidence_refs=(evidence,), expected_source_revisions={"practice:char_a": 1},
        expected_revision=0, causation_id="cause", correlation_id="corr")
    return store, owner, registration, request


def test_registered_learning_commits_real_receipt_and_compiles_learned_capability():
    store, owner, registration, request = setup()
    receipt = owner.settle(request, caller_principal="service:learning")
    assert receipt.committed
    tx = store.get_transaction(receipt.transaction_id)
    assert tx.read_stream_revisions == {"practice:char_a": 1}
    assert tx.idempotency_record.principal_ref == owner.PRINCIPAL
    states = owner.states(world_ref=request.world_ref, actor_id="char_a")
    assert len(states) == 1 and states[0].skill_id == "observation" and states[0].source == "learned"
    assert states[0].proficiency == .55 and states[0].evidence_refs
    stable = CharacterSkillService(registry=create_core_skill_registry()).compile_stable_snapshot(
        actor_id="char_a", skill_states=states)
    assert stable.skills[0].skill_id == "observation"
    assert stable.capability_revision


@pytest.mark.parametrize("fault", ["caller", "digest", "actor", "world", "missing", "stale", "method", "operation", "revision", "prerequisite"])
def test_learning_rejection_is_zero_write(fault):
    store, owner, registration, request = setup(prerequisite_skill_ids=("mediation",) if fault == "prerequisite" else ())
    change = {
        "digest": {"rule_digest": "sha256:stale"}, "actor": {"actor_id": "char_b"},
        "world": {"world_ref": "other"}, "missing": {"evidence_refs": ("missing",)},
        "stale": {"expected_source_revisions": {"practice:char_a": 0}},
        "method": {"method": "research"}, "operation": {"operation": "evolution"},
        "revision": {"expected_revision": 1},
    }.get(fault, {})
    before = store.export_snapshot()
    with pytest.raises(ValueError):
        owner.settle(request.model_copy(update=change), caller_principal="wrong" if fault == "caller" else "service:learning")
    assert store.export_snapshot() == before


@pytest.mark.parametrize("fault", ["principal", "subject", "outcome"])
def test_learning_rejects_unqualified_committed_source(fault):
    store, owner, registration, request = setup()
    evidence = source(store, command="practice:2", principal="wrong" if fault == "principal" else "authority:practice",
        actor="char_b" if fault == "subject" else "char_a", accepted=fault != "outcome")
    request = request.model_copy(update={"evidence_refs": (evidence,), "expected_source_revisions": {"practice:char_a": 2}})
    before = store.export_snapshot()
    with pytest.raises(ValueError, match="source"):
        owner.settle(request, caller_principal="service:learning")
    assert store.export_snapshot() == before


def test_original_receipt_survives_source_advance_rule_removal_and_sqlite_reopen(tmp_path):
    path = tmp_path / "world.sqlite3"
    store, owner, registration, request = setup(DurableGameplayEventStore(path))
    receipt = owner.settle(request, caller_principal="service:learning")
    source(store, command="practice:2")
    before = store.get_last_global_sequence()
    store.close()
    store = DurableGameplayEventStore(path)
    try:
        reopened = RegisteredLearningAuthority(store=store, registry=create_core_skill_registry(), rules=[])
        assert reopened.settle(request, caller_principal="service:learning") == receipt
        assert reopened.settle(request, caller_principal="service:learning") == receipt
        assert len(reopened.states(world_ref="world:test", actor_id="char_a")) == 1
        with pytest.raises(ValueError, match="idempotency"):
            reopened.settle(request.model_copy(update={"method": "research"}), caller_principal="service:learning")
        assert store.get_last_global_sequence() == before
    finally:
        store.close()


def test_same_evidence_cannot_be_reused_under_another_command():
    store, owner, registration, request = setup()
    assert owner.settle(request, caller_principal="service:learning").committed
    before = store.export_snapshot()
    with pytest.raises(ValueError, match="evidence_reused"):
        owner.settle(request.model_copy(update={"command_id": "learn:2", "idempotency_key": "learning:2", "expected_revision": 1}),
                     caller_principal="service:learning")
    assert store.export_snapshot() == before


@pytest.mark.parametrize("learnability", ["granted", "locked"])
def test_registration_cannot_grant_restricted_skills(learnability):
    registry = create_core_skill_registry()
    registry.skill("observation").learnability = learnability
    with pytest.raises(ValueError, match="learnability"):
        RegisteredLearningAuthority(store=GameplayEventStore(), registry=registry, rules=[rule()])


def test_mutated_request_source_revision_is_not_coerced():
    store, owner, _, request = setup()
    request.expected_source_revisions["practice:char_a"] = True
    before = store.export_snapshot()
    with pytest.raises(ValueError):
        owner.settle(request, caller_principal="service:learning")
    assert store.export_snapshot() == before


def test_source_read_cas_conflict_cannot_commit_learning(monkeypatch):
    store, owner, _, request = setup()
    append = store.append_batch

    def race(batch):
        monkeypatch.setattr(store, "append_batch", append)
        source(store, command="practice:race")
        return append(batch)

    monkeypatch.setattr(store, "append_batch", race)
    receipt = owner.settle(request, caller_principal="service:learning")
    assert not receipt.committed and receipt.failure.error_code == "revision_conflict"
    assert owner.states(world_ref="world:test", actor_id="char_a") == []
    assert store.get_by_idempotency(owner.PRINCIPAL, request.idempotency_key) is None


def test_lost_append_response_recovers_original_receipt(monkeypatch):
    store, owner, _, request = setup()
    append = store.append_batch

    def lose_response(batch):
        append(batch)
        raise ConnectionError("response lost after commit")

    monkeypatch.setattr(store, "append_batch", lose_response)
    with pytest.raises(ConnectionError):
        owner.settle(request, caller_principal="service:learning")
    before = store.export_snapshot()
    receipt = owner.settle(request, caller_principal="service:learning")
    assert receipt.committed and store.export_snapshot() == before


def test_failed_append_does_not_create_learned_projection(monkeypatch):
    store, owner, _, request = setup()
    before = store.export_snapshot()

    def fail(batch):
        raise OSError("storage unavailable before commit")

    monkeypatch.setattr(store, "append_batch", fail)
    with pytest.raises(OSError):
        owner.settle(request, caller_principal="service:learning")
    assert store.export_snapshot() == before
    assert owner.states(world_ref="world:test", actor_id="char_a") == []


def test_other_actor_private_source_is_rejected():
    from app.gameplay.settlement_plan import build_multi_stream_atomic_event_batch

    store, owner, _, request = setup()
    receipt = store.append_batch(build_multi_stream_atomic_event_batch(
        command_id="private", principal_ref="authority:practice", expected_revisions={"private": 0},
        event_specs={"private": (("lesson.practice_committed", dict(actor_id="char_a", world_ref="world:test", accepted=True)),)},
        event_visibility_policies={"private": ("actor_private:char_b",)},
        idempotency_key="private", causation_id="cause", correlation_id="corr"))
    request = request.model_copy(update={"evidence_refs": tuple(receipt.committed_event_ids),
                                         "expected_source_revisions": {"private": 1}})
    before = store.export_snapshot()
    with pytest.raises(ValueError, match="source_invalid"):
        owner.settle(request, caller_principal="service:learning")
    assert store.export_snapshot() == before


def test_strict_store_requires_explicit_learning_event_registration():
    from app.gameplay.event_schema_registry import EventSchemaRegistration, EventSchemaRegistry

    schemas = EventSchemaRegistry()
    schemas.register(EventSchemaRegistration("lesson.practice_committed", 1, "sha256:test-source"))
    store, owner, _, request = setup(GameplayEventStore(event_schema_registry=schemas))
    before = store.export_snapshot()
    receipt = owner.settle(request, caller_principal="service:learning")
    assert not receipt.committed and receipt.failure.error_code == "event_schema_unregistered"
    assert store.export_snapshot() == before
    schemas.register(owner.SCHEMA)
    assert owner.settle(request, caller_principal="service:learning").committed


def test_projection_rejects_corrupt_recorded_state(monkeypatch):
    store, owner, _, request = setup()
    owner.settle(request, caller_principal="service:learning")
    read = store.read_stream

    def corrupt(stream):
        events = read(stream)
        events[0].payload["state"]["proficiency"] = .99
        return events

    monkeypatch.setattr(store, "read_stream", corrupt)
    with pytest.raises(ValueError, match="replay_invalid"):
        owner.states(world_ref="world:test", actor_id="char_a")


def test_prerequisite_chain_uses_actor_owner_stream():
    store, owner, _, request = setup()
    owner.settle(request, caller_principal="service:learning")
    next_rule = rule(object_id="lesson:mediation@1", skill_id="mediation", prerequisite_skill_ids=("observation",))
    next_owner = RegisteredLearningAuthority(store=store, registry=create_core_skill_registry(), rules=[next_rule])
    evidence = source(store, command="practice:2")
    next_request = request.model_copy(update=dict(command_id="learn:2", idempotency_key="learning:2",
        object_id=next_rule.object_id, rule_digest=next_rule.digest, evidence_refs=(evidence,),
        expected_source_revisions={"practice:char_a": 2}, expected_revision=1))
    assert next_owner.settle(next_request, caller_principal="service:learning").committed
    assert {state.skill_id for state in next_owner.states(world_ref="world:test", actor_id="char_a")} == {"observation", "mediation"}


@pytest.mark.parametrize("changes", [{"operation": "evolution"}, {"stage": "evolved"}])
def test_evolution_stage_and_operation_require_registered_siming_source(changes):
    with pytest.raises(ValueError, match="siming_owner"):
        setup(**changes)


def test_retry_cannot_accept_receipt_from_an_unrelated_stream():
    store, owner, _, request = setup()
    fake = store.append_batch(build_atomic_event_batch(command_id=request.command_id,
        principal_ref=owner.PRINCIPAL, stream_id="unrelated", expected_revision=0,
        event_specs=((owner.EVENT, dict(request=request.model_dump(mode="json"),
            caller_principal="service:learning", state={})),),
        idempotency_key=request.idempotency_key, causation_id=request.causation_id,
        correlation_id=request.correlation_id))
    assert fake.committed
    before = store.export_snapshot()
    with pytest.raises(ValueError, match="prior_receipt_invalid"):
        owner.settle(request, caller_principal="service:learning")
    assert store.export_snapshot() == before
