"""Shared owner mechanics; domain validation and commit semantics remain local."""

from collections.abc import Mapping, Sequence

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import AppendBatchResult, GameplayEvent, GameplayFailure


class OwnerCommitBuilder:
    @staticmethod
    def build(
        *,
        principal_ref: str,
        command_id: str,
        transaction_id: str,
        idempotency_key: str,
        payload_digest: str,
        events: Sequence[Mapping[str, object]],
        expected_stream_revisions: Mapping[str, int],
        pinned_revisions: Mapping[str, int],
        result_digest: str,
        read_stream_revisions: Mapping[str, int] | None = None,
    ) -> dict[str, object]:
        batch: dict[str, object] = {
            "transaction_id": transaction_id,
            "command_id": command_id,
            "expected_stream_revisions": dict(expected_stream_revisions),
            "pinned_revisions": dict(pinned_revisions),
            "events": list(events),
            "idempotency_record": {
                "principal_ref": principal_ref,
                "idempotency_key": idempotency_key,
                "payload_digest": payload_digest,
            },
            "outbox_entries": [],
            "result_digest": result_digest,
            "projection_refresh_hints": [],
        }
        if read_stream_revisions is not None:
            batch["read_stream_revisions"] = dict(read_stream_revisions)
        return batch


def replay_duplicate(
    store: GameplayEventStore, *, principal: str, idempotency_key: str,
    payload_digest: str, error_factory: type[Exception], missing_result_code: str,
    transaction_mismatch_code: str = "owner_replay_transaction_mismatch",
    event_count_mismatch_code: str = "owner_replay_event_count_mismatch",
    event_missing_code: str = "owner_replay_event_missing",
    expected_event_types: Sequence[str] | None = None,
    expected_command_id: str | None = None,
    expected_transaction_id: str | None = None,
) -> AppendBatchResult | None:
    record = store.get_idempotency_record(principal, idempotency_key)
    if record is None:
        return None
    if record.payload_digest != payload_digest:
        raise error_factory("idempotency_key_reused")
    result = store.get_by_idempotency(principal, idempotency_key)
    if result is None:
        raise error_factory(missing_result_code)

    transaction = store.get_transaction(result.transaction_id)
    if (
        not result.committed
        or transaction is None
        or transaction.transaction_id != result.transaction_id
        or transaction.command_id != result.command_id
        or (expected_command_id is not None and result.command_id != expected_command_id)
        or (expected_transaction_id is not None and result.transaction_id != expected_transaction_id)
        or transaction.idempotency_record.principal_ref != principal
        or transaction.idempotency_record.idempotency_key != idempotency_key
        or transaction.idempotency_record.payload_digest != payload_digest
    ):
        raise error_factory(transaction_mismatch_code)

    event_ids = result.committed_event_ids
    if (
        not event_ids
        or len(event_ids) != len(transaction.events)
        or len(set(event_ids)) != len(event_ids)
    ):
        raise error_factory(event_count_mismatch_code)

    resolved_events = []
    for event_id in event_ids:
        try:
            resolved_events.append(store.get_event(event_id))
        except KeyError as error:
            raise error_factory(event_missing_code) from error

    if (
        event_ids != [event.event_id for event in transaction.events]
        or any(
            actual != committed
            or actual.transaction_id != transaction.transaction_id
            or actual.command_id != transaction.command_id
            for actual, committed in zip(resolved_events, transaction.events)
        )
        or (
            expected_event_types is not None
            and tuple(event.event_type for event in resolved_events)
            != tuple(expected_event_types)
        )
        or result.global_sequence_range
        != (resolved_events[0].global_sequence, resolved_events[-1].global_sequence)
        or result.resulting_stream_revisions
        != {event.stream_id: event.stream_revision for event in resolved_events}
    ):
        raise error_factory(transaction_mismatch_code)

    return result.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True)


def rejected_result(*, command_id: str, error_code: str, stage: str,
                    transaction_prefix: str) -> AppendBatchResult:
    return AppendBatchResult(
        committed=False,
        transaction_id=f"{transaction_prefix}:{command_id}",
        command_id=command_id,
        idempotency_status="rejected",
        failure=GameplayFailure(error_code=error_code, message=error_code, failed_stage=stage),
    )


class StoreReadSnapshot:
    """Reuse a tuple of store events for read-only projection at the same head."""

    __slots__ = ("_store", "_events")

    def __init__(self, store: GameplayEventStore) -> None:
        self._store = store
        self._events: tuple[GameplayEvent, ...] | None = None

    def all_events(self) -> tuple[GameplayEvent, ...]:
        events = self._events
        if events is not None:
            head = events[-1].global_sequence if events else 0
            if head == self._store.get_last_global_sequence():
                return events

        events = tuple(self._store.read_events())
        self._events = events
        return events
