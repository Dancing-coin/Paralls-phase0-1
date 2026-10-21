from __future__ import annotations

import pytest

from app.gameplay.event_schema_registry import create_stormnight_event_schema_registry
from app.gameplay.event_store import DurableGameplayEventStore, GameplayEventStore
from app.gameplay.life_state_runtime import CaseDeathLifeStateCaller
from app.gameplay.action_consequence_runtime import WorldDeathConfirmationIntent
from app.gameplay.p5.investigation_conflict import InvestigationConflictAuthority
from app.gameplay.shared_contracts import GameplayCommandEnvelope
from test_p5_investigation_conflict import _registry
from app.gameplay.settlement_plan import build_atomic_event_batch


def _seed(store=None, actor_ref="character:death:1") -> tuple[GameplayEventStore, str]:
    store = store or GameplayEventStore(event_schema_registry=create_stormnight_event_schema_registry())
    batch = build_atomic_event_batch(
        command_id="case-death:source",
        principal_ref="authority:p5:investigation-conflict",
        stream_id="gameplay:conflict:attempt-death",
        expected_revision=0,
        event_specs=(("gameplay.conflict.terminal_outcome_recorded", {
            "actor_ref": actor_ref, "terminal_kind": "case_death",
        }),),
        idempotency_key="case-death:source",
        causation_id="event:terminal:1",
        correlation_id="case-death:source",
    )
    result = store.append_batch(batch)
    assert result.committed
    terminal_id = result.committed_event_ids[0]
    terminal_stream = "gameplay:conflict:attempt-death"
    command = GameplayCommandEnvelope(
        command_id="case-death:confirm", command_type="gameplay.conflict.confirm_world_death",
        command_version=1, principal_ref="authority:p5:investigation-conflict",
        actor_ref=actor_ref, project_ref="project:case",
        transaction_id="transaction:case-death:confirm", idempotency_key="case-death:confirm",
        expected_revisions={terminal_stream: 1}, causation_id=terminal_id,
        correlation_id="case-death:source", source_ref=terminal_id, submitted_at="now",
    )
    confirmation = InvestigationConflictAuthority(registry=_registry(), store=store).confirm_world_death(
        command=command,
        intent=WorldDeathConfirmationIntent(
            source_event_id=terminal_id, target_actor_ref=actor_ref,
            expected_source_revision=1, confirmation_ref="confirmation:1", confirmed=True,
            policy_revision="policy:case-death@1",
        ),
    )
    assert confirmation.committed
    assert confirmation.receipt is not None
    return store, confirmation.receipt.committed_event_ids[0]


def _advance_source(store: GameplayEventStore, confirmation_id: str) -> None:
    confirmation = store.get_event(confirmation_id)
    batch = build_atomic_event_batch(
        command_id="case-death:unrelated-source-advance",
        principal_ref="authority:p5:investigation-conflict",
        stream_id=confirmation.stream_id,
        expected_revision=confirmation.stream_revision,
        read_stream_revisions={confirmation.stream_id: confirmation.stream_revision},
        event_specs=(("gameplay.conflict.world_death_commit_rejected", {
            "source_event_id": confirmation.payload["source_event_id"],
            "target_actor_ref": confirmation.payload["target_actor_ref"],
            "confirmation_ref": "confirmation:unrelated",
            "confirmed": False,
            "policy_revision": "policy:case-death@1",
            "source_revision": confirmation.stream_revision,
            "visibility_policy": "project",
        }),),
        idempotency_key="case-death:unrelated-source-advance",
        causation_id=confirmation_id,
        correlation_id="case-death:unrelated-source-advance",
        pinned_revisions={"source": confirmation.stream_revision},
    )
    assert store.append_batch(batch).committed


def test_case_death_caller_writes_canonical_life_state() -> None:
    store, confirmation_id = _seed()
    caller = CaseDeathLifeStateCaller(store=store)
    result = caller.record_confirmed_case_death(
        confirmation_event_id=confirmation_id,
        expected_source_revision=2,
        command_id="life-state:death:1",
        idempotency_key="life-state:death:1",
        causation_id=confirmation_id,
        correlation_id="life-state:death:1",
    )
    assert result.result.committed
    event = store.get_event(result.result.committed_event_ids[0])
    assert event.event_type == "gameplay.character.life_state_changed"
    assert event.payload["to_state"] == "dead"
    assert event.payload["actor_ref"] == "character:death:1"
    assert event.payload["from_state"] == "unknown"
    assert event.schema_version == 2


def test_case_death_caller_exact_retry_changed_duplicate_and_stale_are_zero_write() -> None:
    store, confirmation_id = _seed()
    caller = CaseDeathLifeStateCaller(store=store)
    request = dict(
        confirmation_event_id=confirmation_id,
        expected_source_revision=2,
        command_id="life-state:death:2",
        idempotency_key="life-state:death:2",
        causation_id=confirmation_id,
        correlation_id="life-state:death:2",
    )
    first = caller.record_confirmed_case_death(**request)
    duplicate = caller.record_confirmed_case_death(**request)
    changed = caller.record_confirmed_case_death(**{**request, "command_id": "life-state:changed"})
    stale = caller.record_confirmed_case_death(**{**request, "expected_source_revision": 3, "idempotency_key": "life-state:stale"})
    assert first.result.committed
    assert duplicate.result.committed and duplicate.result.idempotency_status == "duplicate_replayed"
    assert not changed.result.committed and changed.result.failure.error_code == "life_state_idempotency_key_reused"
    assert not stale.result.committed and stale.result.failure.error_code == "life_state_confirmation_stale"
    assert len(store.read_events(event_type="gameplay.character.life_state_changed")) == 1


def test_case_death_does_not_infer_from_unconfirmed_source() -> None:
    store, confirmation_id = _seed()
    event = store.get_event(confirmation_id)
    forged = event.model_copy(update={"payload": {**event.payload, "confirmed": False}}, deep=True)
    store._events_by_id[confirmation_id] = forged
    store._events = [forged if item.event_id == confirmation_id else item for item in store._events]
    result = CaseDeathLifeStateCaller(store=store).record_confirmed_case_death(
        confirmation_event_id=confirmation_id,
        expected_source_revision=2,
        command_id="life-state:rejected",
        idempotency_key="life-state:rejected",
        causation_id=confirmation_id,
        correlation_id="life-state:rejected",
    )
    assert not result.result.committed
    assert result.result.failure.error_code == "life_state_confirmation_invalid"
    assert not store.read_events(event_type="gameplay.character.life_state_changed")


def test_case_death_rejects_missing_terminal_and_wrong_actor_terminal() -> None:
    store, confirmation_id = _seed()
    confirmation = store.get_event(confirmation_id)
    missing = confirmation.model_copy(update={"payload": {**confirmation.payload, "source_event_id": "event:missing-terminal"}}, deep=True)
    store._events_by_id[confirmation_id] = missing
    store._events = [missing if item.event_id == confirmation_id else item for item in store._events]
    result = CaseDeathLifeStateCaller(store=store).record_confirmed_case_death(
        confirmation_event_id=confirmation_id, expected_source_revision=2,
        command_id="life-state:missing-terminal", idempotency_key="life-state:missing-terminal",
        causation_id=confirmation_id, correlation_id="life-state:missing-terminal",
    )
    assert not result.result.committed
    assert result.result.failure.error_code == "life_state_terminal_source_missing"

    store, confirmation_id = _seed()
    terminal_id = store.get_event(confirmation_id).payload["source_event_id"]
    terminal = store.get_event(terminal_id)
    forged_terminal = terminal.model_copy(update={"payload": {**terminal.payload, "actor_ref": "character:other"}}, deep=True)
    store._events_by_id[terminal_id] = forged_terminal
    store._events = [forged_terminal if item.event_id == terminal_id else item for item in store._events]
    result = CaseDeathLifeStateCaller(store=store).record_confirmed_case_death(
        confirmation_event_id=confirmation_id, expected_source_revision=2,
        command_id="life-state:wrong-actor", idempotency_key="life-state:wrong-actor",
        causation_id=confirmation_id, correlation_id="life-state:wrong-actor",
    )
    assert not result.result.committed
    assert result.result.failure.error_code == "life_state_terminal_source_invalid"


def test_case_death_rejects_forged_source_transaction_and_second_dead_transition() -> None:
    store, confirmation_id = _seed()
    confirmation = store.get_event(confirmation_id)
    forged = confirmation.model_copy(update={"transaction_id": "transaction:forged"}, deep=True)
    store._events_by_id[confirmation_id] = forged
    store._events = [forged if item.event_id == confirmation_id else item for item in store._events]
    result = CaseDeathLifeStateCaller(store=store).record_confirmed_case_death(
        confirmation_event_id=confirmation_id, expected_source_revision=2,
        command_id="life-state:forged-owner", idempotency_key="life-state:forged-owner",
        causation_id=confirmation_id, correlation_id="life-state:forged-owner",
    )
    assert not result.result.committed
    assert result.result.failure.error_code == "life_state_confirmation_invalid"

    store, confirmation_id = _seed()
    caller = CaseDeathLifeStateCaller(store=store)
    first = caller.record_confirmed_case_death(
        confirmation_event_id=confirmation_id, expected_source_revision=2,
        command_id="life-state:first-dead", idempotency_key="life-state:first-dead",
        causation_id=confirmation_id, correlation_id="life-state:first-dead",
    )
    second = caller.record_confirmed_case_death(
        confirmation_event_id=confirmation_id, expected_source_revision=2,
        command_id="life-state:second-dead", idempotency_key="life-state:second-dead",
        causation_id=confirmation_id, correlation_id="life-state:second-dead",
    )
    assert first.result.committed
    assert not second.result.committed
    assert second.result.failure.error_code == "life_state_already_dead"


@pytest.mark.parametrize("corruption", ["transaction", "event_identity", "principal", "sequence", "revision"])
def test_case_death_duplicate_rejects_corrupted_receipt_or_transaction(corruption: str) -> None:
    store, confirmation_id = _seed()
    caller = CaseDeathLifeStateCaller(store=store)
    request = dict(
        confirmation_event_id=confirmation_id, expected_source_revision=2,
        command_id="life-state:receipt-check", idempotency_key="life-state:receipt-check",
        causation_id=confirmation_id, correlation_id="life-state:receipt-check",
    )
    first = caller.record_confirmed_case_death(**request)
    assert first.result.committed
    key = ("authority:character:life-state", request["idempotency_key"])
    receipt = store._idempotency_results[key]
    if corruption == "transaction":
        store._idempotency_results[key] = receipt.model_copy(update={"transaction_id": "transaction:unrelated"}, deep=True)
    elif corruption == "sequence":
        store._idempotency_results[key] = receipt.model_copy(update={"global_sequence_range": (1, 1)}, deep=True)
    elif corruption == "revision":
        store._idempotency_results[key] = receipt.model_copy(update={"resulting_stream_revisions": {}}, deep=True)
    elif corruption == "event_identity":
        event_id = receipt.committed_event_ids[0]
        event = store.get_event(event_id)
        store._events_by_id[event_id] = event.model_copy(update={"transaction_id": "transaction:unrelated"}, deep=True)
    else:
        index = next(i for i, batch in enumerate(store._transactions) if batch.transaction_id == receipt.transaction_id)
        batch = store._transactions[index]
        record = batch.idempotency_record.model_copy(update={"principal_ref": "authority:unrelated"}, deep=True)
        store._transactions[index] = batch.model_copy(update={"idempotency_record": record}, deep=True)
    before = store.get_last_global_sequence()
    retry = caller.record_confirmed_case_death(**request)
    assert not retry.result.committed
    assert retry.result.failure.error_code == "life_state_idempotency_key_reused"
    assert store.get_last_global_sequence() == before


def test_case_death_exact_and_changed_retry_after_unrelated_source_advance() -> None:
    store, confirmation_id = _seed()
    caller = CaseDeathLifeStateCaller(store=store)
    request = dict(
        confirmation_event_id=confirmation_id, expected_source_revision=2,
        command_id="life-state:advanced", idempotency_key="life-state:advanced",
        causation_id=confirmation_id, correlation_id="life-state:advanced",
    )
    first = caller.record_confirmed_case_death(**request)
    assert first.result.committed
    _advance_source(store, confirmation_id)
    before = store.get_last_global_sequence()
    duplicate = caller.record_confirmed_case_death(**request)
    changed = caller.record_confirmed_case_death(**{**request, "correlation_id": "correlation:changed"})
    assert duplicate.result.committed
    assert duplicate.result.idempotency_status == "duplicate_replayed"
    assert duplicate.result.committed_event_ids == first.result.committed_event_ids
    assert not changed.result.committed
    assert changed.result.failure.error_code == "life_state_idempotency_key_reused"
    assert store.get_last_global_sequence() == before


def test_case_death_life_state_durable_reopen_receipt_recovery_after_source_advance(tmp_path) -> None:
    source, confirmation_id = _seed()
    path = tmp_path / "life-state.db"
    durable = DurableGameplayEventStore(path, event_schema_registry=create_stormnight_event_schema_registry())
    for batch in source.read_transactions():
        assert durable.append_batch(batch).committed
    caller = CaseDeathLifeStateCaller(store=durable)
    first = caller.record_confirmed_case_death(
        confirmation_event_id=confirmation_id, expected_source_revision=2,
        command_id="life-state:durable", idempotency_key="life-state:durable",
        causation_id=confirmation_id, correlation_id="life-state:durable",
    )
    assert first.result.committed
    _advance_source(durable, confirmation_id)
    checkpoint = durable.get_last_global_sequence()
    durable.close()
    reopened = DurableGameplayEventStore(path, event_schema_registry=create_stormnight_event_schema_registry())
    restored = CaseDeathLifeStateCaller(store=reopened)
    duplicate = restored.record_confirmed_case_death(
        confirmation_event_id=confirmation_id, expected_source_revision=2,
        command_id="life-state:durable", idempotency_key="life-state:durable",
        causation_id=confirmation_id, correlation_id="life-state:durable",
    )
    assert duplicate.result.committed and duplicate.result.idempotency_status == "duplicate_replayed"
    assert reopened.get_last_global_sequence() == checkpoint
    reopened.close()


@pytest.mark.parametrize("invalid_revision", [True, 2.0, "2", -1])
def test_case_death_caller_rejects_non_strict_source_revision(invalid_revision: object) -> None:
    store, confirmation_id = _seed()
    caller = CaseDeathLifeStateCaller(store=store)

    result = caller.record_confirmed_case_death(
        confirmation_event_id=confirmation_id,
        expected_source_revision=invalid_revision,  # type: ignore[arg-type]
        command_id="life-state:invalid-revision",
        idempotency_key=f"life-state:invalid-revision:{invalid_revision!s}",
        causation_id=confirmation_id,
        correlation_id="life-state:invalid-revision",
    )

    assert not result.result.committed
    assert result.result.failure is not None
    assert result.result.failure.error_code == "life_state_confirmation_revision_invalid"
    assert not store.read_events(event_type="gameplay.character.life_state_changed")


def test_case_death_caller_recovers_after_lost_append_response() -> None:
    store, confirmation_id = _seed()
    caller = CaseDeathLifeStateCaller(store=store)
    original_append = store.append_batch
    lost = {"raised": False}

    def append_then_lose_response(batch):
        result = original_append(batch)
        if not lost["raised"]:
            lost["raised"] = True
            raise TimeoutError("simulated caller response loss")
        return result

    store.append_batch = append_then_lose_response  # type: ignore[method-assign]
    request = dict(
        confirmation_event_id=confirmation_id,
        expected_source_revision=2,
        command_id="life-state:lost-response",
        idempotency_key="life-state:lost-response",
        causation_id=confirmation_id,
        correlation_id="life-state:lost-response",
    )
    with pytest.raises(TimeoutError):
        caller.record_confirmed_case_death(**request)
    recovered = caller.record_confirmed_case_death(**request)
    assert recovered.result.committed
    assert recovered.result.idempotency_status == "duplicate_replayed"
    assert len(store.read_events(event_type="gameplay.character.life_state_changed")) == 1



def test_alive_death_reopen_uses_original_cut_and_rejects_tampered_receipt(tmp_path):
    from test_population_activation_presence_service import _proposal, _service_with_store

    path = tmp_path / "alive-death.sqlite"
    store = DurableGameplayEventStore(path)
    _, service = _service_with_store(store)
    spawned = service.commit_and_spawn(
        _proposal(), presence_idempotency_key="presence:before-death", presence_expected_revision=0,
    )
    assert spawned.life_state is not None and spawned.life_state.committed
    _, confirmation_id = _seed(store, "character:char_a")
    request = dict(
        confirmation_event_id=confirmation_id, expected_source_revision=2,
        command_id="death:after-alive", idempotency_key="death:after-alive",
        causation_id=confirmation_id, correlation_id="death:after-alive",
    )
    first = CaseDeathLifeStateCaller(store=store).record_confirmed_case_death(**request)
    death = store.get_event(first.result.committed_event_ids[0])
    assert death.schema_version == 2
    assert death.payload["from_state"] == "alive"
    assert death.payload["policy_revision"] == "policy:character-life-state-case-death@2"
    _advance_source(store, confirmation_id)
    before = store.get_last_global_sequence()
    store.close()

    reopened = DurableGameplayEventStore(path)
    caller = CaseDeathLifeStateCaller(store=reopened)
    duplicate = caller.record_confirmed_case_death(**request)
    assert duplicate.result.committed
    assert duplicate.result.idempotency_status == "duplicate_replayed"
    assert duplicate.result.committed_event_ids == first.result.committed_event_ids
    event_id = first.result.committed_event_ids[0]
    stored = reopened.get_event(event_id)
    forged = stored.model_copy(update={"transaction_id": "transaction:forged"}, deep=True)
    original_get_event = reopened.get_event
    reopened.get_event = lambda requested: forged if requested == event_id else original_get_event(requested)
    rejected = caller.record_confirmed_case_death(**request)
    assert not rejected.result.committed
    assert rejected.result.failure.error_code == "life_state_idempotency_key_reused"
    assert reopened.get_last_global_sequence() == before
    reopened.close()


def test_historical_schema1_death_receipt_retains_unknown_semantics():
    store, confirmation_id = _seed()
    request = dict(
        confirmation_event_id=confirmation_id, expected_source_revision=2,
        command_id="death:historical", idempotency_key="death:historical",
        causation_id=confirmation_id, correlation_id="death:historical",
    )
    historical = store.append_batch(build_atomic_event_batch(
        command_id=request["command_id"], principal_ref="authority:character:life-state",
        stream_id="gameplay:character:life:character:death:1", expected_revision=0,
        schema_version=1,
        event_specs=(("gameplay.character.life_state_changed", {
            "actor_ref": "character:death:1", "from_state": "unknown", "to_state": "dead",
            "source_confirmation_event_id": confirmation_id,
            "source_confirmation_revision": 2,
            "policy_revision": "policy:character-life-state-case-death@1",
            "visibility_policy": "project",
        }),), idempotency_key=request["idempotency_key"],
        causation_id=confirmation_id, correlation_id=request["correlation_id"],
    ))
    assert historical.committed
    before = store.get_last_global_sequence()
    duplicate = CaseDeathLifeStateCaller(store=store).record_confirmed_case_death(**request)
    assert duplicate.result.committed
    assert duplicate.result.idempotency_status == "duplicate_replayed"
    assert duplicate.result.committed_event_ids == historical.committed_event_ids
    assert store.get_event(historical.committed_event_ids[0]).schema_version == 1
    assert store.get_last_global_sequence() == before
