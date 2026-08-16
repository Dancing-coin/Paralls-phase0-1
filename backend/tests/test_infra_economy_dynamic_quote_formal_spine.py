from __future__ import annotations

from app.gameplay.economy_runtime import EconomyAuthorityService
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.replay import GameplayProjectionReplay
import pytest


def _quote(*, version: int = 1) -> dict[str, object]:
    return {"quote_ref": "quote:weather:flour", "version": version, "status": "active", "item_ref": "item:flour", "unit_price_minor": 8}


def test_dynamic_quote_uses_the_formal_economy_owner_spine_and_redacted_project_outbox() -> None:
    store = GameplayEventStore()

    result = EconomyAuthorityService(store=store).publish_dynamic_quote(
        command_id="command:economy:weather-quote", quote_payload=_quote(), idempotency_key="economy:weather-quote",
        causation_id="cause:weather", correlation_id="corr:weather",
    )

    assert result.committed
    transaction = store.read_transactions()[-1]
    assert {fragment.owner_principal_ref for fragment in transaction.owner_fragments} == {"actor_gameplay.economy_domain"}
    outbox = [entry for entry in store.list_outbox() if entry.transaction_id == transaction.transaction_id]
    assert len(outbox) == 1 and outbox[0].audience == "project"
    assert outbox[0].payload_projection == {"quote_ref": "quote:weather:flour", "version": 1, "status": "active"}


def test_dynamic_quote_idempotency_revision_and_invalid_payload_are_zero_write() -> None:
    store = GameplayEventStore()
    authority = EconomyAuthorityService(store=store)
    first = authority.publish_dynamic_quote(command_id="command:quote", quote_payload=_quote(), idempotency_key="quote", causation_id="cause", correlation_id="corr")
    before = store.export_snapshot()
    duplicate = authority.publish_dynamic_quote(command_id="command:quote", quote_payload=_quote(), idempotency_key="quote", causation_id="cause", correlation_id="corr")
    with pytest.raises(Exception):
        authority.publish_dynamic_quote(command_id="command:quote:bad", quote_payload={"quote_ref": "quote:weather:flour", "version": 1, "status": "active"}, idempotency_key="quote:bad", causation_id="cause", correlation_id="corr")
    changed = authority.publish_dynamic_quote(command_id="command:quote", quote_payload=_quote(version=2), idempotency_key="quote", causation_id="cause", correlation_id="corr")
    assert first.committed and duplicate.idempotency_status == "duplicate_replayed"
    assert store.export_snapshot() == before
    assert not changed.committed


def test_dynamic_quote_replays_full_and_checkpoint_tail() -> None:
    store = GameplayEventStore()
    EconomyAuthorityService(store=store).publish_dynamic_quote(command_id="command:quote:replay", quote_payload=_quote(), idempotency_key="quote:replay", causation_id="cause", correlation_id="corr")
    replay = GameplayProjectionReplay(projector_id="inf2o-quote", projector_version="1")
    full = replay.full_replay(store.read_events())
    tail = replay.checkpoint_plus_tail_replay(replay.create_checkpoint(()), store.read_events())
    assert full.succeeded and tail.succeeded and full.projection_hash == tail.projection_hash


def test_dynamic_quote_stale_revision_is_zero_write() -> None:
    store = GameplayEventStore()
    authority = EconomyAuthorityService(store=store)
    assert authority.publish_dynamic_quote(command_id="command:quote:first", quote_payload=_quote(), idempotency_key="quote:first", causation_id="cause", correlation_id="corr").committed
    before = store.export_snapshot()

    stale = authority.publish_dynamic_quote(
        command_id="command:quote:stale", quote_payload=_quote(version=2), idempotency_key="quote:stale",
        causation_id="cause", correlation_id="corr", expected_revision=0,
    )

    assert not stale.committed
    assert stale.failure is not None and stale.failure.error_code == "revision_conflict"
    assert store.export_snapshot() == before


def test_dynamic_quote_rejects_account_truth_in_project_quote_payload() -> None:
    store = GameplayEventStore()
    authority = EconomyAuthorityService(store=store)
    before = store.export_snapshot()

    with pytest.raises(Exception, match="economy_dynamic_quote_privacy_denied"):
        authority.publish_dynamic_quote(
            command_id="command:quote:private", quote_payload={**_quote(), "account_id": "account:private"},
            idempotency_key="quote:private", causation_id="cause", correlation_id="corr",
        )

    assert store.export_snapshot() == before
