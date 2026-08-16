from __future__ import annotations

from dataclasses import dataclass

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.governed_contract_catalog import (
    GovernedAuthorityContract,
    GovernedAuthorityContractCatalog,
    GovernedAuthorityContractError,
)
from app.gameplay.models import AppendBatchResult, GameplayEvent


class EcologyConsumerContractAdapterError(ValueError):
    def __init__(self, error_code: str) -> None:
        super().__init__(error_code)
        self.error_code = error_code


@dataclass(frozen=True)
class EcologyConsumerContractAdmission:
    contract: GovernedAuthorityContract
    source_event: GameplayEvent
    existing_result: AppendBatchResult | None
    source_authority_ref: str
    source_stream_id: str
    source_stream_revision: int
    source_event_id: str
    source_event_revision: int
    target_stream_ids: tuple[str, ...]
    target_expected_revisions: dict[str, int]
    idempotency_key: str

    @property
    def receipt_reader_ref(self) -> str:
        return self.contract.receipt_reader_ref

    @property
    def replay_reader_ref(self) -> str:
        return self.contract.replay_reader_ref


def admit_ecology_consumer_contract(
    *,
    store: GameplayEventStore,
    contract_ref: str,
    owner_ref: str,
    target_stream_ids: tuple[str, ...],
    target_event_types: tuple[str, ...],
    target_expected_revisions: dict[str, int],
    source_authority_ref: str,
    source_stream_id: str,
    source_stream_revision: int,
    source_event_id: str,
    source_event_revision: int,
    allowed_source_event_types: tuple[str, ...],
    idempotency_key: str,
) -> EcologyConsumerContractAdmission:
    if not idempotency_key:
        raise EcologyConsumerContractAdapterError("ecology_consumer_idempotency_key_required")
    if not target_stream_ids or set(target_stream_ids) != set(target_expected_revisions):
        raise EcologyConsumerContractAdapterError("ecology_consumer_target_revision_conflict")
    try:
        contract = GovernedAuthorityContractCatalog.require_operation(
            contract_ref=contract_ref,
            contract_kind="ecology_consumer",
            owner_ref=owner_ref,
            stream_ids=target_stream_ids,
            event_types=target_event_types,
            projection_scope="project",
        )
    except GovernedAuthorityContractError as error:
        raise EcologyConsumerContractAdapterError(str(error)) from error
    if source_authority_ref != "authority:ecology":
        raise EcologyConsumerContractAdapterError("ecology_consumer_source_owner_mismatch")
    try:
        source_event = store.get_event(source_event_id)
    except KeyError as error:
        raise EcologyConsumerContractAdapterError("ecology_consumer_source_missing") from error
    if source_event.event_type not in allowed_source_event_types:
        raise EcologyConsumerContractAdapterError("ecology_consumer_source_event_mismatch")
    if source_event.stream_id != source_stream_id:
        raise EcologyConsumerContractAdapterError("ecology_consumer_source_stream_mismatch")
    if source_event.visibility_policy != "project":
        raise EcologyConsumerContractAdapterError("ecology_consumer_source_privacy_denied")
    if (
        source_event.stream_revision != source_event_revision
        or source_stream_revision != source_event_revision
        or store.get_stream_head(source_stream_id) != source_stream_revision
    ):
        raise EcologyConsumerContractAdapterError("ecology_consumer_source_revision_conflict")
    for stream_id, expected_revision in target_expected_revisions.items():
        actual_revision = store.get_stream_head(stream_id)
        if actual_revision != expected_revision or actual_revision <= 0:
            raise EcologyConsumerContractAdapterError("ecology_consumer_target_revision_conflict")
    return EcologyConsumerContractAdmission(
        contract=contract,
        source_event=source_event,
        existing_result=store.get_by_idempotency(owner_ref, idempotency_key),
        source_authority_ref=source_authority_ref,
        source_stream_id=source_stream_id,
        source_stream_revision=source_stream_revision,
        source_event_id=source_event_id,
        source_event_revision=source_event_revision,
        target_stream_ids=target_stream_ids,
        target_expected_revisions=dict(target_expected_revisions),
        idempotency_key=idempotency_key,
    )


__all__ = [
    "EcologyConsumerContractAdmission",
    "EcologyConsumerContractAdapterError",
    "admit_ecology_consumer_contract",
]
