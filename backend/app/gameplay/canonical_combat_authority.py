"""Canonical combat source owners designed in this phase.

This module owns an explicit faction relation source and a Threat owner API.
The Threat API is intentionally conservative: it consumes an embodied owner's
committed receipt plus canonical Presence, LifeState, and faction events.  It
does not promote contact, HP, or profile fields into world facts.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.gameplay.event_store import GameplayEventStore, GameplayEventStoreSnapshotError
from app.gameplay.models import AppendBatchResult
from app.gameplay.settlement_plan import build_atomic_event_batch
from app.models.embodied_interaction import ActionAttempt, AuthorityResult


FACTION_PRINCIPAL = "authority:combat:faction-relation"
FACTION_EVENT = "gameplay.combat.faction_relation_recorded"
THREAT_PRINCIPAL = "authority:combat:threat-relation"
THREAT_EVENT = "gameplay.combat.threat_relation_recorded"
ENCOUNTER_PRINCIPAL = "authority:combat:encounter"
ENCOUNTER_BEGUN = "gameplay.combat.encounter_begun"
ENCOUNTER_ENDED = "gameplay.combat.encounter_ended"
PRESENCE_PRINCIPAL = "population.presence_authority"
LIFE_PRINCIPAL = "authority:character:life-state"
EMBODIED_PRINCIPAL = "authority:embodied:street-owner"
EMBODIED_EVENT = "gameplay.embodied.street_settled@1"
_TARGET_ELIGIBLE_LIFE_STATES = frozenset({"alive", "impaired", "downed", "dying", "unconscious", "reviving", "revived"})


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
                or not prior.committed or prior.failure is not None
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


class CanonicalCombatThreatAuthority(CanonicalCombatTargetReader):
    """Threat owner for confirmed hits; target eligibility is fail-closed."""

    def __init__(self, *, store: GameplayEventStore, authorized_callers: tuple[str, ...] = ()) -> None:
        self.store = store
        self.authorized_callers = frozenset(authorized_callers)

    def begin_encounter(self, *, attempt: ActionAttempt, authority_result: AuthorityResult,
                        presence_event_ids: tuple[str, str], life_event_ids: tuple[str, str],
                        faction_event_id: str, world_ref: str, timeline_ref: str, encounter_ref: str,
                        actor_incarnation_ref: str, target_incarnation_ref: str,
                        command_id: str, idempotency_key: str, authorized_caller: str) -> AppendBatchResult:
        """Admit a bounded encounter from an already committed real hit.

        The caller allowlist is backend composition, never a client assertion
        of identity. No public ingress or identity issuer is created here.
        """
        if authorized_caller not in self.authorized_callers:
            return self._reject(command_id, "encounter_caller_not_authorized")
        if not all(isinstance(value, str) and value.strip() for value in
                   (world_ref, timeline_ref, encounter_ref, command_id, idempotency_key)):
            return self._reject(command_id, "encounter_request_invalid")
        try:
            sources = [self.store.get_event(ref) for ref in (*presence_event_ids, *life_event_ids, faction_event_id)]
            revisions = {row.stream_id: self.store.get_stream_head(row.stream_id) for row in sources}
            for actor in (attempt.actor_ref, *attempt.target_refs):
                for suffix in {actor, actor.removeprefix("character:")}:
                    stream = f"gameplay:character:life:{suffix}"
                    revisions[stream] = self.store.get_stream_head(stream)
            if (not self._valid_sources(sources, attempt, world_ref, timeline_ref,
                                        actor_incarnation_ref, target_incarnation_ref)
                    or not self.store.transaction_owns_event(transaction_id=sources[-1].transaction_id,
                                                            event_id=sources[-1].event_id, principal_ref=FACTION_PRINCIPAL)
                    or sources[-1].event_type != FACTION_EVENT
                    or not self._current_faction(sources[-1], actor_ref=attempt.actor_ref,
                                                target_ref=attempt.target_refs[0], world_ref=world_ref,
                                                timeline_ref=timeline_ref)
                    or not self._embodied_receipt_matches(attempt, authority_result)):
                return self._reject(command_id, "encounter_source_unavailable")
            payload = dict(world_ref=world_ref, timeline_ref=timeline_ref, encounter_ref=encounter_ref,
                           actor_ref=attempt.actor_ref, target_ref=attempt.target_refs[0],
                           actor_incarnation_ref=actor_incarnation_ref, target_incarnation_ref=target_incarnation_ref,
                           source_event_ids=[row.event_id for row in sources],
                           embodied_event_id=authority_result.committed_event_ids[0],
                           policy_revision="combat-encounter@1", authorized_caller=authorized_caller)
            prior = self.store.get_by_idempotency(ENCOUNTER_PRINCIPAL, idempotency_key)
            if prior is not None:
                return self._lifecycle_replay(prior, payload, ENCOUNTER_BEGUN, command_id, idempotency_key)
            stream = f"gameplay:combat:encounter:{encounter_ref}"
            if self.store.get_stream_head(stream):
                return self._reject(command_id, "encounter_already_exists")
            return self.store.append_batch(build_atomic_event_batch(
                command_id=command_id, principal_ref=ENCOUNTER_PRINCIPAL, stream_id=stream,
                expected_revision=0, event_specs=((ENCOUNTER_BEGUN, payload),),
                idempotency_key=idempotency_key, causation_id=attempt.causation_id,
                correlation_id=attempt.correlation_id, read_stream_revisions=revisions))
        except (KeyError, ValueError, TypeError, IndexError, GameplayEventStoreSnapshotError):
            return self._reject(command_id, "encounter_source_unavailable")

    def end_encounter(self, *, world_ref: str, timeline_ref: str, encounter_ref: str,
                      command_id: str, idempotency_key: str, authorized_caller: str,
                      expected_revision: int, reason: str) -> AppendBatchResult:
        if authorized_caller not in self.authorized_callers:
            return self._reject(command_id, "encounter_caller_not_authorized")
        if not all(isinstance(value, str) and value.strip() for value in
                   (world_ref, timeline_ref, encounter_ref, command_id, idempotency_key, reason)):
            return self._reject(command_id, "encounter_request_invalid")
        if type(expected_revision) is not int or expected_revision < 1:
            return self._reject(command_id, "encounter_revision_invalid")
        payload = dict(world_ref=world_ref, timeline_ref=timeline_ref, encounter_ref=encounter_ref,
                       reason=reason, expected_revision=expected_revision,
                       policy_revision="combat-encounter@1", authorized_caller=authorized_caller)
        prior = self.store.get_by_idempotency(ENCOUNTER_PRINCIPAL, idempotency_key)
        if prior is not None:
            return self._lifecycle_replay(prior, payload, ENCOUNTER_ENDED, command_id, idempotency_key)
        try:
            view = self.encounter_projection(world_ref=world_ref, timeline_ref=timeline_ref, encounter_ref=encounter_ref)
            if view["state"] != "active":
                return self._reject(command_id, "encounter_not_active")
            return self.store.append_batch(build_atomic_event_batch(
                command_id=command_id, principal_ref=ENCOUNTER_PRINCIPAL,
                stream_id=f"gameplay:combat:encounter:{encounter_ref}", expected_revision=expected_revision,
                event_specs=((ENCOUNTER_ENDED, payload),), idempotency_key=idempotency_key,
                causation_id=command_id, correlation_id=command_id))
        except (KeyError, ValueError, GameplayEventStoreSnapshotError):
            return self._reject(command_id, "encounter_source_unavailable")

    def _lifecycle_replay(self, prior: AppendBatchResult, payload: dict[str, Any], event_type: str,
                          command_id: str, idempotency_key: str) -> AppendBatchResult:
        try:
            if not prior.committed or len(prior.committed_event_ids) != 1:
                raise ValueError("invalid receipt")
            event = self.store.get_event(prior.committed_event_ids[0])
            tx = self.store.get_transaction(prior.transaction_id)
            if (tx is None or tx.idempotency_record.idempotency_key != idempotency_key
                    or event.command_id != command_id or event.event_type != event_type or event.payload != payload
                    or event.stream_id != f"gameplay:combat:encounter:{payload['encounter_ref']}"
                    or not self.store.transaction_owns_event(transaction_id=prior.transaction_id,
                                                            event_id=event.event_id, principal_ref=ENCOUNTER_PRINCIPAL)):
                raise ValueError("changed receipt")
            return prior.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True)
        except (KeyError, ValueError, GameplayEventStoreSnapshotError):
            return self._reject(command_id, "encounter_idempotency_key_reused")

    def encounter_projection(self, *, world_ref: str, timeline_ref: str, encounter_ref: str,
                             checkpoint_at: int | None = None) -> dict[str, Any]:
        """Project canonical committed events; a boundary never imports future rows."""
        events = self.store.read_stream(f"gameplay:combat:encounter:{encounter_ref}")
        state, totals, refs = "unavailable", {}, []
        for event in events:
            if checkpoint_at is not None and event.global_sequence > checkpoint_at:
                continue
            principal = THREAT_PRINCIPAL if event.event_type == THREAT_EVENT else ENCOUNTER_PRINCIPAL
            if (event.schema_version != 1 or event.visibility_policy != "project"
                    or not self.store.transaction_owns_event(transaction_id=event.transaction_id,
                                                            event_id=event.event_id, principal_ref=principal)):
                raise ValueError("combat_projection_source_invalid")
            p = event.payload
            if p.get("encounter_ref") != encounter_ref:
                raise ValueError("combat_projection_scope_invalid")
            if event.event_type in (ENCOUNTER_BEGUN, ENCOUNTER_ENDED):
                if p.get("world_ref") != world_ref or p.get("timeline_ref") != timeline_ref:
                    raise ValueError("combat_projection_scope_invalid")
                if event.event_type == ENCOUNTER_BEGUN:
                    if state != "unavailable":
                        raise ValueError("combat_projection_lifecycle_invalid")
                    state = "active"
                else:
                    if state != "active":
                        raise ValueError("combat_projection_lifecycle_invalid")
                    state, totals = "ended", {}
            elif event.event_type == THREAT_EVENT:
                if state == "ended" or type(p.get("damage")) is not int or p["damage"] <= 0:
                    raise ValueError("combat_projection_lifecycle_invalid")
                faction = self.store.get_event(p["source_event_ids"][-1])
                if faction.payload.get("world_ref") != world_ref or faction.payload.get("timeline_ref") != timeline_ref:
                    raise ValueError("combat_projection_scope_invalid")
                key = (p["actor_ref"], p["target_ref"])
                totals[key] = totals.get(key, 0) + p["damage"]
            else:
                raise ValueError("combat_projection_event_unknown")
            refs.append(event.event_id)
        rows = [{"actor_ref": actor, "target_ref": target, "threat": value}
                for (actor, target), value in sorted(totals.items(), key=lambda pair: (-pair[1], pair[0]))]
        return {"world_ref": world_ref, "timeline_ref": timeline_ref, "encounter_ref": encounter_ref,
                "state": state, "rows": rows, "event_refs": refs}

    def target_eligibility(self, *, attempt: ActionAttempt, **sources) -> dict[str, Any]:
        if len(attempt.target_refs) != 1:
            return {"eligible": False, "reason": "source_unavailable", "source_event_ids": [], "source_revisions": {}}
        return self.source_eligibility(actor_ref=attempt.actor_ref, target_ref=attempt.target_refs[0], **sources)

    def record_confirmed_hit(self, *, attempt: ActionAttempt, authority_result: AuthorityResult,
                             presence_event_ids: tuple[str, str], life_event_ids: tuple[str, str],
                             faction_event_id: str, world_ref: str, timeline_ref: str,
                             encounter_ref: str, actor_incarnation_ref: str,
                             target_incarnation_ref: str, command_id: str, idempotency_key: str) -> AppendBatchResult:
        if (getattr(authority_result, "outcome", None) != "committed" or not isinstance(encounter_ref, str)
                or not encounter_ref.strip() or len(presence_event_ids) != 2 or len(life_event_ids) != 2):
            return self._reject(command_id, "threat_source_unavailable")
        try:
            # A lost response must remain recoverable after sources advance or
            # an encounter ends. Replay is allowed only for the receipt-derived
            # key and an exact payload match; it never appends after end.
            damage = authority_result.committed_projection.get("damage")
            if type(damage) is not int or damage <= 0:
                return self._reject(command_id, "threat_damage_invalid")
            receipt_event_id = authority_result.committed_event_ids[0]
            consumption_key = f"threat:embodied-hit:{receipt_event_id}"
            prior = self.store.get_by_idempotency(THREAT_PRINCIPAL, consumption_key)
            if prior is not None:
                if not self._embodied_receipt_matches(attempt, authority_result):
                    return self._reject(command_id, "embodied_receipt_invalid")
                expected_payload = {
                    "actor_ref": attempt.actor_ref, "target_ref": attempt.target_refs[0],
                    "encounter_ref": encounter_ref, "damage": damage,
                    "source_event_ids": [*presence_event_ids, *life_event_ids, faction_event_id],
                    "policy_revision": "threat:confirmed-hit-1to1@1",
                    "embodied_event_id": receipt_event_id,
                    "embodied_transaction_id": authority_result.transaction_id,
                    "attempt_payload_digest": attempt.payload_digest,
                }
                return self._replay_or_reject(
                    prior, expected_payload, f"gameplay:combat:encounter:{encounter_ref}",
                    consumption_key, consumption_key)
            sources = [self.store.get_event(event_id) for event_id in (*presence_event_ids, *life_event_ids, faction_event_id)]
            # Freeze every source head before revalidation. A revocation or
            # newer source event racing the checks must conflict with append.
            source_revisions = {event.stream_id: self.store.get_stream_head(event.stream_id) for event in sources}
            # LifeState v1 and v2 use different historical stream keys. Both
            # heads participate in the same append CAS as eligibility checks.
            for actor_ref in (attempt.actor_ref, *attempt.target_refs):
                for suffix in {actor_ref, actor_ref.removeprefix("character:")}:
                    stream = f"gameplay:character:life:{suffix}"
                    source_revisions[stream] = self.store.get_stream_head(stream)
            if not self._valid_sources(sources, attempt, world_ref, timeline_ref, actor_incarnation_ref, target_incarnation_ref):
                return self._reject(command_id, "threat_source_unavailable")
            faction = sources[-1]
            if (faction.event_type != FACTION_EVENT or faction.visibility_policy != "project"
                    or not self.store.transaction_owns_event(transaction_id=faction.transaction_id, event_id=faction.event_id, principal_ref=FACTION_PRINCIPAL)
                    or faction.payload.get("hostile") is not True
                    or faction.payload.get("actor_ref") != attempt.actor_ref
                    or faction.payload.get("target_ref") != attempt.target_refs[0]
                    or faction.payload.get("world_ref") != world_ref
                    or faction.payload.get("timeline_ref") != timeline_ref
                    or not self._current_faction(faction, actor_ref=attempt.actor_ref,
                                                 target_ref=attempt.target_refs[0], world_ref=world_ref,
                                                 timeline_ref=timeline_ref)):
                return self._reject(command_id, "target_not_eligible")
            if not self._embodied_receipt_matches(attempt, authority_result):
                return self._reject(command_id, "embodied_receipt_invalid")
            stream_id = f"gameplay:combat:encounter:{encounter_ref}"
            encounter_revision = self.store.get_stream_head(stream_id)
            lifecycle = self.encounter_projection(world_ref=world_ref, timeline_ref=timeline_ref,
                                                  encounter_ref=encounter_ref)
            if lifecycle["state"] == "ended":
                return self._reject(command_id, "encounter_ended")
            payload = {"actor_ref": attempt.actor_ref, "target_ref": attempt.target_refs[0], "encounter_ref": encounter_ref,
                       "damage": damage, "source_event_ids": [event.event_id for event in sources],
                       "policy_revision": "threat:confirmed-hit-1to1@1",
                       "embodied_event_id": authority_result.committed_event_ids[0],
                       "embodied_transaction_id": authority_result.transaction_id,
                       "attempt_payload_digest": attempt.payload_digest}
            return self.store.append_batch(build_atomic_event_batch(
                command_id=consumption_key, principal_ref=THREAT_PRINCIPAL, stream_id=stream_id,
                expected_revision=encounter_revision, event_specs=((THREAT_EVENT, payload),),
                idempotency_key=consumption_key, causation_id=attempt.causation_id, correlation_id=attempt.correlation_id,
                read_stream_revisions=source_revisions,
            ))
        except (KeyError, GameplayEventStoreSnapshotError, TypeError, ValueError):
            return self._reject(command_id, "threat_source_unavailable")

    def _embodied_receipt_matches(self, attempt: ActionAttempt, result: AuthorityResult) -> bool:
        if len(result.committed_event_ids) != 1 or not result.transaction_id:
            return False
        try:
            event = self.store.get_event(result.committed_event_ids[0])
            tx = self.store.get_transaction(result.transaction_id)
        except (IndexError, KeyError, GameplayEventStoreSnapshotError):
            return False
        persisted = event.payload.get("result") if tx is not None else None
        return bool(tx is not None and tx.idempotency_record.principal_ref == EMBODIED_PRINCIPAL
                    and tx.idempotency_record.idempotency_key == attempt.idempotency_key
                    and event.event_type == EMBODIED_EVENT and event.stream_id == "gameplay:embodied:street-owner"
                    and event.command_id == attempt.attempt_id and event.transaction_id == result.transaction_id
                    and self.store.transaction_owns_event(transaction_id=tx.transaction_id, event_id=event.event_id, principal_ref=EMBODIED_PRINCIPAL)
                    and event.payload.get("attempt_payload_digest") == attempt.payload_digest
                    and isinstance(persisted, dict) and persisted == result.model_dump(mode="json"))

    def _replay_or_reject(self, prior: AppendBatchResult, payload: dict[str, Any], stream_id: str, command_id: str, idempotency_key: str) -> AppendBatchResult:
        if not prior.committed or len(prior.committed_event_ids) != 1:
            return self._reject(command_id, "threat_receipt_invalid")
        try:
            event = self.store.get_event(prior.committed_event_ids[0]); tx = self.store.get_transaction(prior.transaction_id)
        except (KeyError, GameplayEventStoreSnapshotError):
            return self._reject(command_id, "threat_receipt_invalid")
        if (tx is None or tx.idempotency_record.principal_ref != THREAT_PRINCIPAL or tx.idempotency_record.idempotency_key != idempotency_key
                or event.event_type != THREAT_EVENT or event.stream_id != stream_id or event.payload != payload
                or not self.store.transaction_owns_event(transaction_id=tx.transaction_id, event_id=event.event_id, principal_ref=THREAT_PRINCIPAL)):
            return self._reject(command_id, "threat_idempotency_key_reused")
        return prior.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True)

    @staticmethod
    def _reject(command_id: str, code: str) -> AppendBatchResult:
        from app.gameplay.models import GameplayFailure
        return AppendBatchResult(committed=False, transaction_id=f"rejected:{command_id}", command_id=command_id,
                                 idempotency_status="rejected", failure=GameplayFailure(error_code=code, message=code, failed_stage="combat_threat"))


__all__ = ["CombatFactionRelationAuthority", "CanonicalCombatThreatAuthority", "FactionRelationRequest"]
