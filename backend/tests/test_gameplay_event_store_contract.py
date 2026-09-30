from __future__ import annotations

from copy import deepcopy

import pytest

from app.gameplay.event_store import DurableGameplayEventStore, GameplayEventStore
from app.gameplay.models import AtomicEventBatch, OwnerAuthorizedFragment


def _event(event_id: str, *, stream_id: str, tx: str = "tx:gameplay:1", command_id: str = "cmd:gameplay:1") -> dict[str, object]:
    return {
        "event_id": event_id,
        "event_type": "gameplay.session_reserved",
        "schema_version": 1,
        "stream_id": stream_id,
        "stream_revision": 0,
        "global_sequence": 0,
        "transaction_id": tx,
        "command_id": command_id,
        "causation_id": command_id,
        "correlation_id": "corr:gameplay:1",
        "visibility_policy": "godot_public",
        "payload": {"session_id": "session:handoff:1", "slot": stream_id},
    }


def _outbox(event_id: str, *, tx: str = "tx:gameplay:1") -> dict[str, object]:
    return {
        "outbox_id": f"outbox:{event_id}",
        "transaction_id": tx,
        "event_id": event_id,
        "global_sequence": 0,
        "topic": "gameplay.committed",
        "audience": "godot_room",
        "payload_projection": {
            "room_id": "room_demo",
            "scene_id": "scene_demo",
            "zone_id": "zone_focus",
            "source": {"layer": "gameplay", "system": "event_store"},
            "routing": {"audience_mode": "room", "routing_mode": "event_type", "target_ids": ["godot_mirror"]},
            "priority": "p1",
            "durability": "replayable",
            "ttl": 5000,
            "payload": {"safe_session_id": "session:handoff:1"},
        },
        "delivery_state": "pending",
        "attempt_count": 0,
        "last_error": None,
    }


def _batch(
    *,
    tx: str = "tx:gameplay:1",
    command_id: str = "cmd:gameplay:1",
    digest: str = "digest:v1",
    key: str = "idempotency:handoff:1",
    events: list[dict[str, object]] | None = None,
    outbox_entries: list[dict[str, object]] | None = None,
    expected: dict[str, int] | None = None,
) -> dict[str, object]:
    events = events or [
        _event("evt:session:reserved", stream_id="session:handoff:1", tx=tx, command_id=command_id),
        _event("evt:body:reserved", stream_id="body:char_a", tx=tx, command_id=command_id),
    ]
    outbox_entries = outbox_entries or [_outbox(str(event["event_id"]), tx=tx) for event in events]
    return {
        "transaction_id": tx,
        "command_id": command_id,
        "expected_stream_revisions": expected or {"session:handoff:1": 0, "body:char_a": 0},
        "pinned_revisions": {"policy": 7, "world": 3},
        "events": events,
        "idempotency_record": {
            "principal_ref": "player:local",
            "idempotency_key": key,
            "payload_digest": digest,
        },
        "outbox_entries": outbox_entries,
        "result_digest": "result:digest:v1",
        "projection_refresh_hints": [
            {"projection_id": "godot_mirror", "stream_id": "session:handoff:1", "reason": "session_slot_reserved"}
        ],
    }


def test_append_batch_commits_events_idempotency_and_outbox_atomically() -> None:
    store = GameplayEventStore()

    result = store.append_batch(_batch())

    assert result.committed is True
    assert result.committed_event_ids == ["evt:session:reserved", "evt:body:reserved"]
    assert result.global_sequence_range == (1, 2)
    assert result.resulting_stream_revisions == {"session:handoff:1": 1, "body:char_a": 1}
    assert [event.stream_revision for event in store.read_stream("session:handoff:1")] == [1]
    assert [entry.event_id for entry in store.list_outbox()] == ["evt:session:reserved", "evt:body:reserved"]
    assert store.get_by_idempotency("player:local", "idempotency:handoff:1") is not None


def test_duplicate_same_digest_returns_original_result_without_new_events_or_outbox() -> None:
    store = GameplayEventStore()
    first = store.append_batch(_batch())

    duplicate = store.append_batch(_batch(tx="tx:gameplay:duplicate"))

    assert duplicate.committed is True
    assert duplicate.idempotency_status == "duplicate_replayed"
    assert duplicate.transaction_id == first.transaction_id
    assert duplicate.committed_event_ids == first.committed_event_ids
    assert len(store.read_transactions()) == 1
    assert len(store.list_outbox()) == 2


def test_duplicate_different_digest_rejects_with_zero_mutation() -> None:
    store = GameplayEventStore()
    store.append_batch(_batch())
    before_events = len(store.read_events())
    before_outbox = len(store.list_outbox())

    rejected = store.append_batch(_batch(tx="tx:gameplay:2", digest="digest:changed"))

    assert rejected.committed is False
    assert rejected.failure is not None
    assert rejected.failure.error_code == "idempotency_key_reused"
    assert len(store.read_events()) == before_events
    assert len(store.list_outbox()) == before_outbox


def test_revision_conflict_rejects_whole_batch_without_partial_stream_or_outbox() -> None:
    store = GameplayEventStore()
    store.append_batch(_batch())

    stale = store.append_batch(
        _batch(
            tx="tx:gameplay:stale",
            command_id="cmd:gameplay:stale",
            key="idempotency:handoff:stale",
            events=[
                _event("evt:session:stale", stream_id="session:handoff:1", tx="tx:gameplay:stale", command_id="cmd:gameplay:stale"),
                _event("evt:object:stale", stream_id="object:shared:cup", tx="tx:gameplay:stale", command_id="cmd:gameplay:stale"),
            ],
            expected={"session:handoff:1": 0, "object:shared:cup": 0},
        )
    )

    assert stale.committed is False
    assert stale.failure is not None
    assert stale.failure.error_code == "revision_conflict"
    assert store.get_stream_head("session:handoff:1") == 1
    assert store.get_stream_head("object:shared:cup") == 0
    assert all(entry.transaction_id != "tx:gameplay:stale" for entry in store.list_outbox(include_delivered=True))


def test_invalid_event_schema_returns_typed_failure_without_mutation() -> None:
    store = GameplayEventStore()
    invalid = _event("evt:invalid", stream_id="session:invalid")
    invalid.pop("event_id")

    result = store.append_batch(
        _batch(
            tx="tx:gameplay:invalid",
            key="idempotency:invalid",
            events=[invalid],
            outbox_entries=[_outbox("evt:invalid", tx="tx:gameplay:invalid")],
            expected={"session:invalid": 0},
        )
    )

    assert result.committed is False
    assert result.failure is not None
    assert result.failure.error_code == "invalid_event_schema"
    assert store.read_events() == []
    assert store.list_outbox(include_delivered=True) == []


def test_outbox_projection_failure_rejects_before_commit() -> None:
    store = GameplayEventStore()
    outbox = _outbox("evt:session:projection-failed", tx="tx:gameplay:projection-failed")
    outbox["payload_projection"] = {"_projection_error": "private payload could not be filtered"}

    result = store.append_batch(
        _batch(
            tx="tx:gameplay:projection-failed",
            key="idempotency:projection-failed",
            events=[
                _event(
                    "evt:session:projection-failed",
                    stream_id="session:projection-failed",
                    tx="tx:gameplay:projection-failed",
                )
            ],
            outbox_entries=[outbox],
            expected={"session:projection-failed": 0},
        )
    )

    assert result.committed is False
    assert result.failure is not None
    assert result.failure.error_code == "outbox_projection_failed"
    assert store.get_stream_head("session:projection-failed") == 0
    assert store.list_outbox(include_delivered=True) == []


def test_gameplay_command_envelope_maps_to_atomic_event_batch_contract_fields() -> None:
    from app.gameplay.settlement_plan import SettlementPlan
    from app.gameplay.shared_contracts import GameplayCommandEnvelope

    command = GameplayCommandEnvelope(
        command_id="command:demo:1",
        command_type="gameplay.session.reserve",
        command_version=1,
        principal_ref="principal:player",
        actor_ref="actor:player",
        project_ref="project:demo",
        transaction_id="tx:gameplay:envelope",
        idempotency_key="idempotency:gameplay:envelope",
        expected_revisions={"stream:session": 0},
        causation_id="cause:gameplay:envelope",
        correlation_id="corr:gameplay:envelope",
        source_ref="source:godot",
        submitted_at="2026-08-07T00:00:00Z",
        pinned_revisions={"policy": 7, "world": 3},
        payload={"stream_ref": "stream:session", "event_type": "gameplay.session_reserved"},
    )

    batch = SettlementPlan.from_command_envelope(command).to_atomic_event_batch()

    assert batch.command_id == command.command_id
    assert batch.expected_stream_revisions == {"stream:session": 0}
    assert batch.pinned_revisions == {"policy": 7, "world": 3}


def test_reservation_terminal_state_rejection_is_fail_closed() -> None:
    from app.gameplay.settlement_plan import SettlementPlan
    from app.gameplay.shared_contracts import Reservation

    reservation = Reservation(
        reservation_ref="reservation:demo:1",
        owner_ref="owner:demo",
        target_ref="target:demo",
        quantity_or_amount=1,
        status="final",
        created_revision=1,
        expires_at_tick=None,
        source_obligation_ref="obligation:demo",
    )

    with pytest.raises(ValueError, match="reservation_unknown_or_final"):
        SettlementPlan.from_reservation(reservation).to_atomic_event_batch()


@pytest.mark.parametrize("durable", [False, True])
def test_append_copies_each_nested_payload_once_and_keeps_boundary_isolation(tmp_path, durable):
    copies = []

    class TrackedDict(dict):
        def __deepcopy__(self, memo):
            copies.append(self["kind"])
            cloned = type(self)()
            memo[id(self)] = cloned
            cloned.update((key, deepcopy(value, memo)) for key, value in self.items())
            return cloned

    batch = AtomicEventBatch.model_validate(_batch())
    batch.events[0].payload["nested"] = TrackedDict(kind="event", items=[{"ref": "original"}])
    batch.outbox_entries[0].payload_projection["nested"] = TrackedDict(kind="outbox", items=[{"ref": "original"}])
    store = DurableGameplayEventStore(tmp_path / "isolation.db") if durable else GameplayEventStore()
    try:
        result = store.append_batch(batch)
        assert result.committed
        assert copies == ["event", "outbox"]
        assert [event.global_sequence for event in batch.events] == [0, 0]
        assert [event.stream_revision for event in batch.events] == [0, 0]
        assert [entry.global_sequence for entry in batch.outbox_entries] == [0, 0]
        batch.events[0].payload["nested"]["items"][0]["ref"] = "changed-input"
        batch.outbox_entries[0].payload_projection["nested"]["items"][0]["ref"] = "changed-input"
        batch.pinned_revisions["policy"] = 99
        result.committed_event_ids.clear()
        result.resulting_stream_revisions.clear()
        event = store.get_event("evt:session:reserved")
        assert event.payload["nested"]["items"] == [{"ref": "original"}]
        event.payload["nested"]["items"][0]["ref"] = "changed-read"
        outbox = store.get_outbox("outbox:evt:session:reserved")
        assert outbox.payload_projection["nested"]["items"] == [{"ref": "original"}]
        outbox.payload_projection["nested"]["items"][0]["ref"] = "changed-read"
        transaction = store.get_transaction("tx:gameplay:1")
        assert transaction.pinned_revisions == {"policy": 7, "world": 3}
        assert transaction.events[0].payload["nested"]["items"] == [{"ref": "original"}]
        assert transaction.outbox_entries[0].payload_projection["nested"]["items"] == [{"ref": "original"}]
        transaction.events[0].payload["nested"]["items"][0]["ref"] = "changed-transaction"
        transaction.outbox_entries[0].payload_projection["nested"]["items"][0]["ref"] = "changed-transaction"
        transaction.pinned_revisions["policy"] = 100
        assert store.get_event("evt:session:reserved").payload["nested"]["items"] == [{"ref": "original"}]
        assert store.get_outbox("outbox:evt:session:reserved").payload_projection["nested"]["items"] == [{"ref": "original"}]
        assert store.get_transaction("tx:gameplay:1").pinned_revisions == {"policy": 7, "world": 3}
        assert store.get_by_idempotency("player:local", "idempotency:handoff:1").committed_event_ids == [
            "evt:session:reserved", "evt:body:reserved",
        ]
    finally:
        if durable:
            store.close()


@pytest.mark.parametrize("durable", [False, True])
def test_append_keeps_shared_input_payloads_separate_across_stored_fields(tmp_path, durable):
    shared = {"items": [{"ref": "original"}]}
    batch = AtomicEventBatch.model_validate(_batch())
    for event in batch.events:
        event.payload["nested"] = shared
    for entry in batch.outbox_entries:
        entry.payload_projection["nested"] = shared
    batch.owner_fragments.append(OwnerAuthorizedFragment(
        fragment_id="fragment:fixture", owner_principal_ref="owner:fixture", source_rule_ref="rule:fixture",
        expected_revisions={"stream:fixture": 0},
        event_specs={"stream:fixture": (("gameplay.fixture", {"nested": shared}),)},
    ))
    store = DurableGameplayEventStore(tmp_path / "shared.db") if durable else GameplayEventStore()
    try:
        assert store.append_batch(batch).committed
        transaction = store.get_transaction("tx:gameplay:1")
        transaction.events[0].payload["nested"]["items"][0]["ref"] = "changed-event"
        assert transaction.events[1].payload["nested"]["items"] == [{"ref": "original"}]
        assert [entry.payload_projection["nested"]["items"] for entry in transaction.outbox_entries] == [
            [{"ref": "original"}], [{"ref": "original"}],
        ]
        assert transaction.owner_fragments[0].event_specs["stream:fixture"][0][1]["nested"]["items"] == [{"ref": "original"}]
        transaction.outbox_entries[0].payload_projection["nested"]["items"][0]["ref"] = "changed-outbox"
        assert transaction.outbox_entries[1].payload_projection["nested"]["items"] == [{"ref": "original"}]
        assert transaction.owner_fragments[0].event_specs["stream:fixture"][0][1]["nested"]["items"] == [{"ref": "original"}]
        shared["items"][0]["ref"] = "changed-input"
        assert store.get_event("evt:session:reserved").payload["nested"]["items"] == [{"ref": "original"}]
    finally:
        if durable:
            store.close()


def test_group_rollback_retry_does_not_modify_input_payload_or_numbering(tmp_path):
    batch = AtomicEventBatch.model_validate(_batch())
    batch.events[0].payload["nested"] = {"items": [{"ref": "original"}]}
    store = DurableGameplayEventStore(tmp_path / "group-copy.db")
    try:
        with pytest.raises(RuntimeError, match="interrupt copy group"):
            with store.group_commit():
                assert store.append_batch(batch).committed
                raise RuntimeError("interrupt copy group")
        assert store.read_events() == []
        assert [event.global_sequence for event in batch.events] == [0, 0]
        assert [event.stream_revision for event in batch.events] == [0, 0]
        assert batch.events[0].payload["nested"]["items"] == [{"ref": "original"}]
        with store.group_commit():
            assert store.append_batch(batch).global_sequence_range == (1, 2)
        batch.events[0].payload["nested"]["items"][0]["ref"] = "changed-input"
        assert store.get_event("evt:session:reserved").payload["nested"]["items"] == [{"ref": "original"}]
    finally:
        store.close()
