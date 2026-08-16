"""Read-only admission checks shared by closed Ecology consumer rows.

The check validates an already-issued source pin against an already-registered
target contract.  It never mints an admission, builds a fragment, or appends.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Mapping

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.governed_contract_catalog import (
    GovernedAuthorityContractCatalog,
    GovernedAuthorityContractError,
)


def _digest(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class EcologyConsumerAdmissionCheck:
    """A finite, read-only result for a target owner's existing contract row."""

    accepted: bool
    contract_ref: str
    receipt_reader_ref: str | None = None
    replay_reader_ref: str | None = None
    request_digest: str | None = None
    error_code: str | None = None

    @classmethod
    def verify(
        cls,
        *,
        store: GameplayEventStore,
        contract_ref: object,
        target_owner_ref: object,
        target_stream_ids: object,
        target_event_types: object,
        projection_scope: object,
        source_event_id: object,
        source_stream_id: object,
        source_revision: object,
        target_expected_revisions: object,
        idempotency_key: object,
    ) -> "EcologyConsumerAdmissionCheck":
        """Validate a closed weather-front consumer row before owner work.

        An accepted result conveys only catalog metadata and a stable request
        digest.  The caller still needs the opaque domain admission and must
        use its own owner fragment plus the one event-store append path.
        """
        if (
            not isinstance(contract_ref, str)
            or not isinstance(target_owner_ref, str)
            or not isinstance(target_stream_ids, tuple)
            or not target_stream_ids
            or any(not isinstance(value, str) or not value for value in target_stream_ids)
            or not isinstance(target_event_types, tuple)
            or not target_event_types
            or any(not isinstance(value, str) or not value for value in target_event_types)
            or not isinstance(projection_scope, str)
            or not isinstance(source_event_id, str)
            or not isinstance(source_stream_id, str)
            or isinstance(source_revision, bool)
            or not isinstance(source_revision, int)
            or source_revision < 0
            or not isinstance(target_expected_revisions, Mapping)
            or set(target_expected_revisions) != set(target_stream_ids)
            or any(
                isinstance(revision, bool) or not isinstance(revision, int) or revision < 0
                for revision in target_expected_revisions.values()
            )
            or not isinstance(idempotency_key, str)
            or not idempotency_key
        ):
            return cls(accepted=False, contract_ref=str(contract_ref), error_code="ecology_consumer_contract_invalid")

        try:
            contract = GovernedAuthorityContractCatalog.require_operation(
                contract_ref=contract_ref,
                contract_kind="ecology_consumer",
                owner_ref=target_owner_ref,
                stream_ids=target_stream_ids,
                event_types=target_event_types,
                projection_scope=projection_scope,
            )
        except GovernedAuthorityContractError as exc:
            return cls(accepted=False, contract_ref=contract_ref, error_code=str(exc))

        try:
            source_event = store.get_event(source_event_id)
        except KeyError:
            return cls(accepted=False, contract_ref=contract_ref, error_code="ecology_consumer_source_missing")
        if (
            source_event.event_type != "gameplay.ecology.weather_front.propagated"
            or source_event.visibility_policy != "project"
            or source_event.stream_id != source_stream_id
            or source_event.stream_revision != source_revision
            or store.get_stream_head(source_stream_id) != source_revision
        ):
            return cls(accepted=False, contract_ref=contract_ref, error_code="ecology_consumer_source_pin_invalid")
        if any(store.get_stream_head(stream_id) != target_expected_revisions[stream_id] for stream_id in target_stream_ids):
            return cls(
                accepted=False,
                contract_ref=contract_ref,
                error_code="ecology_consumer_target_revision_conflict",
            )

        request_digest = _digest(
            {
                "contract_ref": contract_ref,
                "target_owner_ref": target_owner_ref,
                "target_stream_ids": target_stream_ids,
                "target_event_types": target_event_types,
                "projection_scope": projection_scope,
                "source_event_id": source_event_id,
                "source_stream_id": source_stream_id,
                "source_revision": source_revision,
                "target_expected_revisions": dict(sorted(target_expected_revisions.items())),
                "idempotency_key": idempotency_key,
            }
        )
        return cls(
            accepted=True,
            contract_ref=contract.contract_ref,
            receipt_reader_ref=contract.receipt_reader_ref,
            replay_reader_ref=contract.replay_reader_ref,
            request_digest=request_digest,
        )


__all__ = ["EcologyConsumerAdmissionCheck"]
