"""Shared owner mechanics; domain validation and commit semantics remain local."""

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import AppendBatchResult, GameplayFailure


def replay_duplicate(
    store: GameplayEventStore, *, principal: str, idempotency_key: str,
    payload_digest: str, error_factory: type[Exception], missing_result_code: str,
) -> AppendBatchResult | None:
    record = store.get_idempotency_record(principal, idempotency_key)
    if record is None:
        return None
    if record.payload_digest != payload_digest:
        raise error_factory("idempotency_key_reused")
    result = store.get_by_idempotency(principal, idempotency_key)
    if result is None:
        raise error_factory(missing_result_code)
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
