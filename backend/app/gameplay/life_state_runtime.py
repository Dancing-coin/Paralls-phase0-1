"""Canonical initial LifeState from committed Activation and Presence facts."""
from __future__ import annotations

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import AppendBatchResult, GameplayEvent
from app.gameplay.settlement_plan import build_atomic_event_batch

_LIFE_EVENT = "gameplay.character.life_state_changed"
_PRESENCE_PRINCIPAL = "population.presence_authority"
_ALIVE_PRINCIPAL = "authority:character:life-state:presence-admission"

class CanonicalLifeStateAuthority:
    """Owner for initial alive from committed activation and Presence."""

    def __init__(self, *, store: GameplayEventStore) -> None:
        self._store = store

    def initialize_alive_from_presence(
        self, *, activation_event_id: str, presence_event_id: str,
        expected_activation_revision: int, expected_presence_revision: int,
        command_id: str, idempotency_key: str, causation_id: str,
        correlation_id: str,
    ) -> AppendBatchResult:
        """Admit the first entity incarnation as alive from two committed facts.

        Activation alone is insufficient.  The owner re-reads both source
        events and appends a separate canonical LifeState fact with both
        source refs pinned in the shared store.
        """
        if any(type(value) is not int or value < 0 for value in
               (expected_activation_revision, expected_presence_revision)):
            return self._reject(command_id, "life_state_presence_revision_invalid")
        try:
            activation = self._store.get_event(activation_event_id)
            presence = self._store.get_event(presence_event_id)
        except KeyError:
            return self._reject(command_id, "life_state_presence_source_missing")
        if (activation.event_type != "population.activation.committed"
                or activation.visibility_policy != "project"
                or activation.stream_revision != expected_activation_revision
                or presence.event_type != "population.presence.spawned"
                or presence.visibility_policy != "project"
                or presence.stream_revision != expected_presence_revision
                or presence.payload.get("source_activation_event_id") != activation_event_id
                or activation.payload.get("profile_ref") != presence.payload.get("character_ref")
                or activation.payload.get("world_ref") != presence.payload.get("world_ref")
                or activation.stream_id != f"population:{activation.payload.get('world_ref')}"
                or presence.stream_id != f"presence:{activation.payload.get('world_ref')}"
                or activation.global_sequence >= presence.global_sequence
                or not self._activation_owned(activation)
                or not self._presence_owned(presence)):
            return self._reject(command_id, "life_state_presence_source_invalid")
        actor_ref = str(presence.payload["character_ref"])
        world_ref = str(presence.payload["world_ref"])
        incarnation = presence.payload.get("incarnation")
        if type(incarnation) is not int or incarnation < 1:
            return self._reject(command_id, "life_state_presence_incarnation_invalid")
        stream_id = f"gameplay:character:life:{actor_ref}"
        prior = self._store.get_by_idempotency(_ALIVE_PRINCIPAL, idempotency_key)
        payload = {
            "actor_ref": actor_ref, "world_ref": world_ref, "incarnation": incarnation,
            "from_state": "unknown", "to_state": "alive",
            "source_activation_event_id": activation_event_id,
            "source_presence_event_id": presence_event_id,
            "source_activation_revision": expected_activation_revision,
            "source_presence_revision": expected_presence_revision,
            "policy_revision": "policy:character-life-state-presence-admission@1",
            "visibility_policy": "project",
        }
        if prior is not None:
            event = self._prior_event(prior, idempotency_key=idempotency_key,
                                      principal_ref=_ALIVE_PRINCIPAL)
            if (event is not None and event.event_type == _LIFE_EVENT and event.schema_version == 2
                    and event.stream_id == stream_id and event.visibility_policy == "project"
                    and event.command_id == command_id and event.causation_id == causation_id
                    and event.correlation_id == correlation_id and event.payload == payload):
                return prior.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True)
            return self._reject(command_id, "life_state_idempotency_key_reused")
        if (self._store.get_stream_head(activation.stream_id) != expected_activation_revision
                or self._store.get_stream_head(presence.stream_id) != expected_presence_revision):
            return self._reject(command_id, "life_state_presence_source_stale")
        existing = self._store.read_stream(stream_id, event_type=_LIFE_EVENT)
        if any(event.payload.get("to_state") == "dead" for event in existing):
            return self._reject(command_id, "life_state_already_dead")
        if any(event.payload.get("to_state") == "alive" for event in existing):
            return self._reject(command_id, "life_state_alive_already_initialized")
        batch = build_atomic_event_batch(
            command_id=command_id, principal_ref=_ALIVE_PRINCIPAL,
            schema_version=2,
            stream_id=stream_id, expected_revision=self._store.get_stream_head(stream_id),
            read_stream_revisions={activation.stream_id: expected_activation_revision,
                                   presence.stream_id: expected_presence_revision},
            event_specs=((_LIFE_EVENT, payload),), idempotency_key=idempotency_key,
            causation_id=causation_id, correlation_id=correlation_id,
            pinned_revisions={"activation": expected_activation_revision,
                              "presence": expected_presence_revision},
        )
        return self._store.append_batch(batch)

    def _presence_owned(self, event: GameplayEvent) -> bool:
        batch = self._store.get_transaction(event.transaction_id)
        return (batch is not None and batch.idempotency_record.principal_ref == _PRESENCE_PRINCIPAL
                and any(candidate == event for candidate in batch.events))

    def _activation_owned(self, event: GameplayEvent) -> bool:
        # Match the existing Population Presence admission boundary. Principal
        # namespaces are internal store provenance, not an identity issuer.
        batch = self._store.get_transaction(event.transaction_id)
        if batch is None or event not in batch.events:
            return False
        principal = batch.idempotency_record.principal_ref
        return principal.startswith("population:") or principal.startswith("world_runtime.")

    def _prior_event(self, receipt: AppendBatchResult, *, idempotency_key: str,
                     principal_ref: str = _ALIVE_PRINCIPAL) -> GameplayEvent | None:
        ids = receipt.committed_event_ids
        if not receipt.committed or receipt.failure is not None or len(ids) != 1:
            return None
        try:
            event = self._store.get_event(ids[0])
        except KeyError:
            return None
        batch = self._store.get_transaction(receipt.transaction_id)
        if (
            batch is None
            or batch.idempotency_record.principal_ref != principal_ref
            or batch.idempotency_record.idempotency_key != idempotency_key
            or batch.command_id != receipt.command_id
            or event.command_id != receipt.command_id
            or event.transaction_id != receipt.transaction_id
            or tuple(batch.events) != (event,)
            or receipt.resulting_stream_revisions != {event.stream_id: event.stream_revision}
            or receipt.global_sequence_range != (event.global_sequence, event.global_sequence)
        ):
            return None
        return event

    @staticmethod
    def _reject(command_id: str, code: str) -> AppendBatchResult:
        from app.gameplay.models import GameplayFailure

        return AppendBatchResult(
            committed=False,
            transaction_id=f"transaction:{command_id}",
            command_id=command_id,
            idempotency_status="rejected",
            failure=GameplayFailure(error_code=code, message=code, failed_stage="life_state_admission"),
        )


__all__ = ["CanonicalLifeStateAuthority"]
