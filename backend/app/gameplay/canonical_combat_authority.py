"""Canonical explicit faction relation owner; combat hit/Threat deferred."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.gameplay.event_store import GameplayEventStore, GameplayEventStoreSnapshotError
from app.gameplay.models import AppendBatchResult
from app.gameplay.settlement_plan import build_atomic_event_batch


FACTION_PRINCIPAL = "authority:combat:faction-relation"
FACTION_EVENT = "gameplay.combat.faction_relation_recorded"


@dataclass(frozen=True)
class FactionRelationRequest:
    world_ref: str
    timeline_ref: str
    actor_ref: str
    target_ref: str
    hostile: bool
    command_id: str
    idempotency_key: str
    causation_id: str
    correlation_id: str
    authorized_caller: str
    authenticated_principal_ref: str | None = None
    credential_ref: str | None = None


class CombatFactionRelationAuthority:
    """Owner for explicit, project-visible combat faction relations."""

    def __init__(self, *, store: GameplayEventStore, authorized_callers: tuple[str, ...]) -> None:
        self.store = store
        self.authorized_callers = frozenset(authorized_callers)

    def record(self, request: FactionRelationRequest) -> AppendBatchResult:
        if request.authorized_caller not in self.authorized_callers:
            return self._reject(request.command_id, "faction_caller_not_authorized")
        if type(request.hostile) is not bool:
            return self._reject(request.command_id, "faction_request_invalid")
        if not all(isinstance(value, str) and value.strip() for value in (
            request.world_ref, request.timeline_ref, request.actor_ref, request.target_ref,
            request.command_id, request.idempotency_key, request.causation_id, request.correlation_id,
        )) or request.actor_ref == request.target_ref:
            return self._reject(request.command_id, "faction_request_invalid")
        identity = (request.authenticated_principal_ref, request.credential_ref)
        if any(value is not None for value in identity) and not all(
            isinstance(value, str) and value.strip() for value in identity
        ):
            return self._reject(request.command_id, "faction_identity_invalid")
        stream_id = f"faction:{request.world_ref}:{request.timeline_ref}"
        prior = self.store.get_by_idempotency(FACTION_PRINCIPAL, request.idempotency_key)
        payload = {
            "world_ref": request.world_ref, "timeline_ref": request.timeline_ref,
            "actor_ref": request.actor_ref, "target_ref": request.target_ref,
            "hostile": request.hostile, "policy_revision": "combat-faction@1",
        }
        if request.authenticated_principal_ref is not None:
            payload.update(authenticated_principal_ref=request.authenticated_principal_ref,
                           credential_ref=request.credential_ref)
        if prior is not None:
            return self._replay_or_reject(prior, payload, stream_id, request)
        return self.store.append_batch(build_atomic_event_batch(
            command_id=request.command_id, principal_ref=FACTION_PRINCIPAL,
            stream_id=stream_id, expected_revision=self.store.get_stream_head(stream_id),
            event_specs=((FACTION_EVENT, payload),), idempotency_key=request.idempotency_key,
            causation_id=request.causation_id, correlation_id=request.correlation_id,
        ))

    def _replay_or_reject(self, prior: AppendBatchResult, payload: dict[str, Any], stream_id: str, request: FactionRelationRequest) -> AppendBatchResult:
        if not prior.committed or len(prior.committed_event_ids) != 1:
            return self._reject(request.command_id, "faction_receipt_invalid")
        try:
            event = self.store.get_event(prior.committed_event_ids[0])
            tx = self.store.get_transaction(prior.transaction_id)
        except (KeyError, GameplayEventStoreSnapshotError):
            return self._reject(request.command_id, "faction_receipt_invalid")
        if (tx is None or tx.idempotency_record.principal_ref != FACTION_PRINCIPAL
                or tx.idempotency_record.idempotency_key != request.idempotency_key
                or event.event_type != FACTION_EVENT or event.stream_id != stream_id
                or prior.failure is not None
                or prior.command_id != request.command_id or tx.command_id != request.command_id
                or event.transaction_id != prior.transaction_id
                or tuple(tx.events) != (event,) or event.schema_version != 1
                or event.visibility_policy != "project"
                or prior.resulting_stream_revisions != {stream_id: event.stream_revision}
                or prior.global_sequence_range != (event.global_sequence, event.global_sequence)
                or event.causation_id != request.causation_id or event.correlation_id != request.correlation_id
                or event.command_id != request.command_id or event.payload != payload
                or not self.store.transaction_owns_event(transaction_id=tx.transaction_id, event_id=event.event_id, principal_ref=FACTION_PRINCIPAL)):
            return self._reject(request.command_id, "faction_idempotency_key_reused")
        return prior.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True)

    @staticmethod
    def _reject(command_id: str, code: str) -> AppendBatchResult:
        from app.gameplay.models import GameplayFailure
        return AppendBatchResult(committed=False, transaction_id=f"rejected:{command_id}", command_id=command_id,
                                 idempotency_status="rejected", failure=GameplayFailure(error_code=code, message=code, failed_stage="combat_faction"))
