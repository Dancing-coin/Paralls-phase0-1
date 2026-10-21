from __future__ import annotations

import pytest

from app.gameplay.economy_runtime import EconomyAuthorityService
from app.gameplay.economy_temporal_consumer import EconomyTemporalConsumer
from app.gameplay.event_store import GameplayEventStore
from app.world_runtime.replay_participants import (
    _economy_temporal_participant,
    _validate_economy_temporal_participant,
)
from app.world_runtime.replay_checkpoint import _manifest


def _driver(tick: int):
    class World:
        @staticmethod
        def is_paused() -> bool:
            return False

    return type("Driver", (), {"current_tick": tick, "catch_up_limit": 2, "world_runtime": World()})()


def _seed() -> tuple[GameplayEventStore, EconomyAuthorityService]:
    store = GameplayEventStore()
    service = EconomyAuthorityService(store=store)
    assert service.open_account(
        command_id="replay:account:alice", account_id="account:alice", owner_ref="actor:alice",
        currency_ref="currency:coin", initial_balance=10, idempotency_key="replay:account:alice",
        causation_id="cause:replay:account:alice", correlation_id="corr:replay:account:alice",
        expected_revision=0,
    ).committed
    assert service.open_account(
        command_id="replay:account:bob", account_id="account:bob", owner_ref="actor:bob",
        currency_ref="currency:coin", initial_balance=0, idempotency_key="replay:account:bob",
        causation_id="cause:replay:account:bob", correlation_id="corr:replay:account:bob",
        expected_revision=1,
    ).committed
    return store, service


def test_old_manifest_without_economy_participant_remains_readable() -> None:
    value = {
        "schema_version": 1,
        "versions": {
            "participant_manifest": 1, "batch_input": 1, "batch_operation": 1,
            "population_recovery": 1, "status_events": 1, "migration_events": 1,
        },
        "batches": [],
        "population": {"schema_version": 1},
        "status": {"schema_version": 1},
        "migration": {"schema_version": 1},
        "external_dependencies": {},
        "random_context": {},
    }
    assert _manifest(value, ()) == value


def test_economy_temporal_participant_scope_and_durable_boundary() -> None:
    store, service = _seed()
    assert service.open_scheduled_account_transfer_obligation(
        command_id="replay:transfer:open", transfer_ref="scheduled-transfer:replay:1",
        debit_account_id="account:alice", credit_account_id="account:bob", amount=4, due_tick=8,
        idempotency_key="replay:transfer:open", causation_id="cause:replay:transfer:open",
        correlation_id="corr:replay:transfer:open", expected_revision=2,
    ).committed
    boundary = store.get_last_global_sequence()
    before = _economy_temporal_participant(store, boundary_sequence=boundary)
    assert before is not None
    assert before["scope"] == "project:economy-temporal"
    assert before["policy_refs"] == [
        "policy:economy_scheduled_account_transfer@1", "policy:economy_tax_due@1"
    ]
    assert {row["event_type"] for row in before["event_refs"]} == {
        "gameplay.economy.scheduled_transfer_obligation_opened"
    }
    _validate_economy_temporal_participant(store, before, boundary_sequence=boundary)

    EconomyTemporalConsumer(store=store, authority=service).advance(_driver(8))
    # A participant frozen at the opening boundary remains valid against that
    # boundary, while the newly committed settlement is future input.
    _validate_economy_temporal_participant(store, before, boundary_sequence=boundary)
    with pytest.raises(ValueError, match="event_ref_mismatch|projection_mismatch"):
        _validate_economy_temporal_participant(store, before)

    after = _economy_temporal_participant(store)
    assert after is not None
    assert {row["event_type"] for row in after["event_refs"]} >= {
        "gameplay.economy.scheduled_transfer_obligation_opened",
        "gameplay.economy.scheduled_transfer_obligation_settled",
        "gameplay.economy.account_debited",
        "gameplay.economy.account_credited",
    }
    _validate_economy_temporal_participant(store, after)


def test_economy_temporal_participant_rejects_changed_event_digest() -> None:
    store, service = _seed()
    assert service.open_scheduled_account_transfer_obligation(
        command_id="replay:transfer:changed", transfer_ref="scheduled-transfer:replay:changed",
        debit_account_id="account:alice", credit_account_id="account:bob", amount=2, due_tick=4,
        idempotency_key="replay:transfer:changed", causation_id="cause:replay:transfer:changed",
        correlation_id="corr:replay:transfer:changed", expected_revision=2,
    ).committed
    saved = _economy_temporal_participant(store)
    assert saved is not None
    changed = {**saved, "event_refs": [dict(saved["event_refs"][0], payload_digest="sha256:changed")]}
    with pytest.raises(ValueError, match="event_ref_mismatch"):
        _validate_economy_temporal_participant(store, changed)


def test_economy_temporal_participant_survives_durable_reopen(tmp_path) -> None:
    from app.gameplay.event_store import DurableGameplayEventStore

    path = tmp_path / "economy-temporal.db"
    store = DurableGameplayEventStore(path)
    service = EconomyAuthorityService(store=store)
    assert service.open_account(
        command_id="replay:durable:alice", account_id="account:alice", owner_ref="actor:alice",
        currency_ref="currency:coin", initial_balance=10, idempotency_key="replay:durable:alice",
        causation_id="cause:replay:durable:alice", correlation_id="corr:replay:durable:alice",
        expected_revision=0,
    ).committed
    assert service.open_account(
        command_id="replay:durable:bob", account_id="account:bob", owner_ref="actor:bob",
        currency_ref="currency:coin", initial_balance=0, idempotency_key="replay:durable:bob",
        causation_id="cause:replay:durable:bob", correlation_id="corr:replay:durable:bob",
        expected_revision=1,
    ).committed
    assert service.open_scheduled_account_transfer_obligation(
        command_id="replay:durable:open", transfer_ref="scheduled-transfer:durable:1",
        debit_account_id="account:alice", credit_account_id="account:bob", amount=1, due_tick=2,
        idempotency_key="replay:durable:open", causation_id="cause:replay:durable:open",
        correlation_id="corr:replay:durable:open", expected_revision=2,
    ).committed
    saved = _economy_temporal_participant(store)
    assert saved is not None
    store.close()
    reopened = DurableGameplayEventStore(path)
    try:
        restored = _economy_temporal_participant(reopened)
        assert restored == saved
        _validate_economy_temporal_participant(reopened, saved)
    finally:
        reopened.close()
