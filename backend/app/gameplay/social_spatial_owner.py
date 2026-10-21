"""Durable owner for canonical actor-to-actor spatial actions.

The owner records the accepted spatial transition in the gameplay ledger. It
does not move a Godot actor or infer a physical position; those remain runtime
effects consumed from the committed receipt.
"""
from __future__ import annotations

from typing import Any

from app.gameplay.event_store import GameplayEventStore, GameplayEventStoreSnapshotError
from app.gameplay.models import AppendBatchResult, GameplayFailure
from app.gameplay.settlement_plan import build_atomic_event_batch


SOCIAL_SPATIAL_PRINCIPAL = "authority:character:social-spatial"
SOCIAL_SPATIAL_EVENT = "gameplay.character.social_spatial_action_committed"
SOCIAL_SPATIAL_ACTIONS = frozenset({
    "approach", "follow_target", "seek_private_distance", "withdraw", "break_contact",
})


class SocialSpatialOwner:
    """Persist one canonical spatial action and provide exact receipt replay."""

    def __init__(self, *, store: GameplayEventStore, authorized_callers: tuple[str, ...] = ("character_agent",)) -> None:
        self.store = store
        self.authorized_callers = frozenset(authorized_callers)

    def submit(
        self,
        *,
        actor_ref: str,
        target_ref: str,
        action_profile: str,
        request_ref: str,
        turn_id: str,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
        producer_ts: int,
        expected_revision_vector: dict[str, int],
        expected_memory_revision_vector: dict[str, int],
        expected_snapshot_revision: int,
        authorized_caller: str = "character_agent",
    ) -> AppendBatchResult:
        values = (actor_ref, target_ref, action_profile, request_ref, turn_id,
                  idempotency_key, causation_id, correlation_id)
        if authorized_caller not in self.authorized_callers:
            return self._reject(request_ref, "social_spatial_caller_not_authorized")
        if not all(isinstance(value, str) and value.strip() for value in values):
            return self._reject(request_ref, "social_spatial_request_invalid")
        if actor_ref == target_ref or action_profile not in SOCIAL_SPATIAL_ACTIONS:
            return self._reject(request_ref, "social_spatial_request_invalid")
        if type(producer_ts) is not int or producer_ts < 0 or type(expected_snapshot_revision) is not int or expected_snapshot_revision < 0:
            return self._reject(request_ref, "social_spatial_revision_invalid")
        if any(type(value) is not int or value < 0 for value in (*expected_revision_vector.values(), *expected_memory_revision_vector.values())):
            return self._reject(request_ref, "social_spatial_revision_invalid")
        stream_id = f"gameplay:character:social-spatial:{actor_ref}"
        payload = {
            "actor_ref": actor_ref, "target_ref": target_ref, "action_profile": action_profile,
            "request_ref": request_ref, "turn_id": turn_id, "producer_ts": producer_ts,
            "expected_revision_vector": dict(expected_revision_vector),
            "expected_memory_revision_vector": dict(expected_memory_revision_vector),
            "expected_snapshot_revision": expected_snapshot_revision,
            "authorized_caller": authorized_caller, "policy_revision": "social-spatial@1",
        }
        prior = self.store.get_by_idempotency(SOCIAL_SPATIAL_PRINCIPAL, idempotency_key)
        if prior is not None:
            return self._replay_or_reject(prior, payload, stream_id, request_ref, idempotency_key, causation_id, correlation_id)
        return self.store.append_batch(build_atomic_event_batch(
            command_id=request_ref, principal_ref=SOCIAL_SPATIAL_PRINCIPAL, stream_id=stream_id,
            expected_revision=self.store.get_stream_head(stream_id), event_specs=((SOCIAL_SPATIAL_EVENT, payload),),
            idempotency_key=idempotency_key, causation_id=causation_id, correlation_id=correlation_id,
        ))

    def replay(self, actor_ref: str) -> list[dict[str, Any]]:
        if not isinstance(actor_ref, str) or not actor_ref.strip():
            return []
        return [dict(event.payload, event_id=event.event_id, stream_revision=event.stream_revision)
                for event in self.store.read_stream(f"gameplay:character:social-spatial:{actor_ref}", event_type=SOCIAL_SPATIAL_EVENT)]

    def _replay_or_reject(self, prior: AppendBatchResult, payload: dict[str, Any], stream_id: str,
                          command_id: str, idempotency_key: str, causation_id: str, correlation_id: str) -> AppendBatchResult:
        try:
            if not prior.committed or len(prior.committed_event_ids) != 1:
                raise ValueError
            event = self.store.get_event(prior.committed_event_ids[0])
            tx = self.store.get_transaction(prior.transaction_id)
            valid = (tx is not None and event.event_type == SOCIAL_SPATIAL_EVENT and event.stream_id == stream_id
                     and event.command_id == command_id and event.causation_id == causation_id
                     and event.correlation_id == correlation_id and event.payload == payload
                     and self.store.transaction_owns_event(transaction_id=prior.transaction_id, event_id=event.event_id, principal_ref=SOCIAL_SPATIAL_PRINCIPAL))
        except (KeyError, ValueError, GameplayEventStoreSnapshotError):
            valid = False
        if not valid:
            return self._reject(command_id, "social_spatial_idempotency_key_reused")
        return prior.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True)

    @staticmethod
    def _reject(command_id: str, code: str) -> AppendBatchResult:
        return AppendBatchResult(committed=False, transaction_id=f"rejected:{command_id}", command_id=command_id,
                                 idempotency_status="rejected", failure=GameplayFailure(error_code=code, message=code, failed_stage="social_spatial"))


__all__ = ["SOCIAL_SPATIAL_EVENT", "SOCIAL_SPATIAL_PRINCIPAL", "SocialSpatialOwner"]
