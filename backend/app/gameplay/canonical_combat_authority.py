"""Canonical explicit faction relation owner; combat hit/Threat deferred."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.gameplay.event_store import GameplayEventStore, GameplayEventStoreSnapshotError
from app.gameplay.models import AppendBatchResult
from app.gameplay.settlement_plan import build_atomic_event_batch


PRESENCE_PRINCIPAL = "population.presence_authority"
LIFE_PRINCIPAL = "authority:character:life-state"
_TARGET_ELIGIBLE_LIFE_STATES = frozenset({"alive", "impaired", "downed", "dying", "unconscious", "reviving", "revived"})

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


@dataclass(frozen=True)
class CombatTargetIdentity:
    """Read-only identity; no physics or execution attempt is manufactured."""

    actor_ref: str
    target_refs: tuple[str, ...]


class CanonicalCombatTargetReader:
    """Source eligibility only. Callers must carry returned heads into owner CAS."""

    def __init__(self, *, store: GameplayEventStore) -> None:
        self.store = store

    def source_eligibility(self, *, actor_ref: str, target_ref: str, presence_event_ids: tuple[str, str],
                           life_event_ids: tuple[str, str], faction_event_id: str,
                           world_ref: str, timeline_ref: str, actor_incarnation_ref: str,
                           target_incarnation_ref: str) -> dict[str, Any]:
        """Read-only target decision, revalidating the canonical source facts."""
        attempt = CombatTargetIdentity(actor_ref=actor_ref, target_refs=(target_ref,))
        try:
            sources = [self.store.get_event(ref) for ref in (*presence_event_ids, *life_event_ids, faction_event_id)]
            revisions = {event.stream_id: self.store.get_stream_head(event.stream_id) for event in sources}
            revisions[f"population:{world_ref}"] = self.store.get_stream_head(f"population:{world_ref}")
            for actor in (attempt.actor_ref, *attempt.target_refs):
                for suffix in {actor, actor.removeprefix("character:")}:
                    stream = f"gameplay:character:life:{suffix}"
                    revisions[stream] = self.store.get_stream_head(stream)
            eligible = (self._valid_sources(sources, attempt, world_ref, timeline_ref,
                                            actor_incarnation_ref, target_incarnation_ref)
                        and sources[-1].event_type == FACTION_EVENT
                        and self.store.transaction_owns_event(transaction_id=sources[-1].transaction_id,
                                                               event_id=sources[-1].event_id, principal_ref=FACTION_PRINCIPAL)
                        and self._current_faction(sources[-1], actor_ref=attempt.actor_ref,
                                                 target_ref=attempt.target_refs[0], world_ref=world_ref,
                                                 timeline_ref=timeline_ref))
            # Re-read every pinned head immediately before returning. A caller
            # that later commits must carry these revisions into its CAS.
            stable = all(self.store.get_stream_head(stream) == revision for stream, revision in revisions.items())
            return {"eligible": bool(eligible and stable), "reason": "eligible" if eligible and stable else "source_unavailable",
                    "world_ref": world_ref, "timeline_ref": timeline_ref,
                    "actor_incarnation_ref": actor_incarnation_ref,
                    "target_incarnation_ref": target_incarnation_ref,
                    "source_event_ids": [event.event_id for event in sources],
                    "source_revisions": revisions}
        except (KeyError, IndexError, TypeError, ValueError, GameplayEventStoreSnapshotError):
            return {"eligible": False, "reason": "source_unavailable", "world_ref": world_ref,
                    "timeline_ref": timeline_ref, "source_event_ids": [], "source_revisions": {}}

    def _valid_sources(self, events: list[Any], attempt: CombatTargetIdentity, world_ref: str, timeline_ref: str, actor_incarnation_ref: str, target_incarnation_ref: str) -> bool:
        if len(events) != 5 or len(attempt.target_refs) != 1 or attempt.actor_ref == attempt.target_refs[0]:
            return False
        # Population Presence and its initial LifeState are world facts. They
        # have no timeline field; combat's faction source supplies that scope.
        faction = events[-1]
        if (faction.schema_version != 1 or faction.visibility_policy != "project"
                or faction.payload.get("world_ref") != world_ref
                or faction.payload.get("timeline_ref") != timeline_ref):
            return False
        for presence, life, actor_ref, incarnation_ref in zip(
            events[:2], events[2:4], (attempt.actor_ref, attempt.target_refs[0]),
            (actor_incarnation_ref, target_incarnation_ref),
        ):
            if (presence.schema_version != 1 or presence.visibility_policy != "project"
                    or presence.event_type != "population.presence.spawned"
                    or presence.stream_id != f"presence:{world_ref}"
                    or presence.payload.get("world_ref") != world_ref
                    or life.event_type != "gameplay.character.life_state_changed"
                    or life.visibility_policy != "project"
                    or life.payload.get("actor_ref") != actor_ref
                    or life.payload.get("to_state") not in _TARGET_ELIGIBLE_LIFE_STATES):
                return False
            incarnation = presence.payload.get("incarnation")
            if type(incarnation) is not int or incarnation < 1 or incarnation_ref != f"{actor_ref}@{incarnation}":
                return False
            if life.schema_version == 2:
                life_principal = "authority:character:life-state:presence-admission"
                if (presence.payload.get("character_ref") != actor_ref
                        or "timeline_ref" in presence.payload or "timeline_ref" in life.payload
                        or life.stream_id != f"gameplay:character:life:{actor_ref}"
                        or life.payload.get("world_ref") != world_ref
                        or life.payload.get("incarnation") != incarnation
                        or life.payload.get("from_state") != "unknown" or life.payload.get("to_state") != "alive"
                        or life.payload.get("policy_revision") != "policy:character-life-state-presence-admission@1"
                        or life.payload.get("source_presence_event_id") != presence.event_id
                        or life.payload.get("source_presence_revision") != presence.stream_revision
                        or life.payload.get("source_activation_event_id") != presence.payload.get("source_activation_event_id")):
                    return False
                activation = self.store.get_event(life.payload["source_activation_event_id"])
                activation_tx = self.store.get_transaction(activation.transaction_id)
                if (activation.event_type != "population.activation.committed"
                        or activation.schema_version != 1 or activation.visibility_policy != "project"
                        or activation.stream_id != f"population:{world_ref}"
                        or activation.payload.get("profile_ref") != actor_ref
                        or activation.payload.get("world_ref") != world_ref
                        or life.payload.get("source_activation_revision") != activation.stream_revision
                        or not activation.global_sequence < presence.global_sequence < life.global_sequence
                        or activation_tx is None
                        or not activation_tx.idempotency_record.principal_ref.startswith(("population:", "world_runtime."))
                        or activation not in activation_tx.events):
                    return False
            elif life.schema_version == 1:
                life_principal = LIFE_PRINCIPAL
                if (presence.payload.get("character_ref") != actor_ref.removeprefix("character:")
                        or presence.payload.get("timeline_ref") != timeline_ref
                        or life.payload.get("timeline_ref") != timeline_ref
                        or life.stream_id != f"gameplay:character:life:{actor_ref.removeprefix('character:')}"):
                    return False
            else:
                return False
            if (not self._current_presence(presence, world_ref, presence.payload["character_ref"])
                    or not self._current_life(life, actor_ref)
                    or not self.store.transaction_owns_event(transaction_id=presence.transaction_id, event_id=presence.event_id, principal_ref=PRESENCE_PRINCIPAL)
                    or not self.store.transaction_owns_event(transaction_id=life.transaction_id, event_id=life.event_id, principal_ref=life_principal)
                    or self.store.get_event(presence.event_id) != presence
                    or self.store.get_event(life.event_id) != life):
                return False
        return True

    def _current_presence(self, event: Any, world_ref: str, actor: str) -> bool:
        rows = [item for item in self.store.read_stream(f"presence:{world_ref}") if item.payload.get("character_ref") == actor]
        return bool(rows) and rows[-1].event_id == event.event_id

    def _current_life(self, event: Any, actor_ref: str) -> bool:
        # Both contracts exist in the store. A newer transition in either
        # registered stream must supersede the supplied eligibility fact.
        streams = {f"gameplay:character:life:{actor_ref}",
                   f"gameplay:character:life:{actor_ref.removeprefix('character:')}"}
        rows = [row for stream in streams for row in self.store.read_stream(stream)
                if row.payload.get("actor_ref") == actor_ref]
        return bool(rows) and max(rows, key=lambda row: row.global_sequence).event_id == event.event_id

    def _current_faction(self, event: Any, *, actor_ref: str, target_ref: str,
                         world_ref: str, timeline_ref: str) -> bool:
        stream_id = f"faction:{world_ref}:{timeline_ref}"
        if event.stream_id != stream_id:
            return False
        rows = [row for row in self.store.read_stream(stream_id)
                if row.payload.get("actor_ref") == actor_ref and row.payload.get("target_ref") == target_ref]
        return bool(rows) and rows[-1].event_id == event.event_id and rows[-1].payload == event.payload and all(
            event.payload.get(key) == expected for key, expected in {
                "actor_ref": actor_ref, "target_ref": target_ref, "world_ref": world_ref,
                "timeline_ref": timeline_ref, "hostile": True,
            }.items()
        )
