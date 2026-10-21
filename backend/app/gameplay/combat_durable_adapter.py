"""Durable adapter for the existing bounded street-combat owner.

This adapter records an already committed embodied settlement.  It deliberately
does not claim ThreatRelation or TargetEligibility: those require admitted
Presence/LifeState/incarnation/encounter and faction owners, which are not part
of ``ActionAttempt`` or the current street caller.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.gameplay.event_store import GameplayEventStore, GameplayEventStoreSnapshotError
from app.gameplay.models import AppendBatchResult
from app.gameplay.settlement_plan import build_atomic_event_batch
from app.gameplay.canonical_combat_authority import CanonicalCombatThreatAuthority
from app.models.embodied_interaction import ActionAttempt, AuthorityResult
from app.services.embodied_authority_settlement_service import EmbodiedAuthoritySettlementService


COMBAT_SETTLEMENT_EVENT = "gameplay.combat.embodied_settlement_recorded"
COMBAT_SETTLEMENT_PRINCIPAL = "authority:embodied:street-combat-settlement"
PRESENCE_SOURCE_PRINCIPAL = "population.presence_authority"
LIFE_STATE_SOURCE_PRINCIPAL = "authority:character:life-state"
# No canonical faction relation owner is registered in this repository.  Keep
# this explicit so a fixture or arbitrary transaction principal cannot become
# an implicit authority by merely containing the expected event type.
FACTION_SOURCE_PRINCIPAL: str | None = None


@dataclass(frozen=True)
class CombatSourceContext:
    """Explicit scope pins required before a durable record is admitted."""

    world_ref: str
    timeline_ref: str
    encounter_ref: str
    actor_incarnation_ref: str
    target_incarnation_ref: str
    presence_source_event_ids: tuple[str, str]
    life_state_source_event_ids: tuple[str, str]
    faction_source_event_id: str

    def valid(self) -> bool:
        if len(self.presence_source_event_ids) != 2 or len(self.life_state_source_event_ids) != 2:
            return False
        values = [
            self.world_ref, self.timeline_ref, self.encounter_ref,
            self.actor_incarnation_ref, self.target_incarnation_ref,
            *self.life_state_source_event_ids, self.faction_source_event_id,
            *self.presence_source_event_ids,
        ]
        return all(isinstance(value, str) and bool(value.strip()) for value in values)


@dataclass(frozen=True)
class CombatDurableResult:
    authority_result: AuthorityResult
    append_result: AppendBatchResult | None = None
    error_code: str = ""


class DurableEmbodiedCombatAdapter:
    """Persist existing street settlement with source pins and receipt lookup.

    The wrapped embodied service remains the only action owner.  This adapter
    writes one event after that owner commits and uses the same event store for
    idempotency and durable recovery.
    """

    def __init__(self, *, authority: EmbodiedAuthoritySettlementService, store: GameplayEventStore) -> None:
        self._authority = authority
        self._store = store
        # The canonical owner is the only writer of confirmed-hit Threat and
        # shares the existing store; this adapter adds no second ledger.
        self._threat_authority = CanonicalCombatThreatAuthority(store=store)

    def consume_committed_hit(
        self,
        attempt: ActionAttempt,
        *,
        source: CombatSourceContext | None,
        command_id: str,
        idempotency_key: str,
        authority_result: AuthorityResult | None = None,
    ) -> AppendBatchResult:
        """Consume a real embodied settlement through the canonical Threat owner.

        This is deliberately a consumer boundary: it never settles the embodied
        action and never fabricates source facts. A missing or non-committed
        owner receipt is rejected before the Threat owner is called. The owner
        then revalidates every source pin and performs its own Durable CAS and
        idempotency checks.
        """
        if source is None or not source.valid():
            return self._threat_rejection(command_id, "threat_source_unavailable")
        if not all(isinstance(value, str) and value.strip() for value in (command_id, idempotency_key)):
            return self._threat_rejection(command_id, "threat_request_invalid")
        try:
            receipt = authority_result or self._authority.query_street_combat_receipt(attempt)
        except (GameplayEventStoreSnapshotError, KeyError, TypeError, ValueError):
            return self._threat_rejection(command_id, "embodied_receipt_invalid")
        if receipt is None or receipt.outcome != "committed":
            return self._threat_rejection(command_id, "embodied_receipt_invalid")
        # Do not trust a caller-supplied projection: compare it with the
        # durable owner receipt recovered from the same owner when available.
        try:
            durable_receipt = self._authority.query_street_combat_receipt(attempt)
        except (GameplayEventStoreSnapshotError, KeyError, TypeError, ValueError):
            return self._threat_rejection(command_id, "embodied_receipt_invalid")
        if durable_receipt is None or durable_receipt != receipt:
            return self._threat_rejection(command_id, "embodied_receipt_invalid")
        if len(receipt.committed_event_ids) != 1:
            return self._threat_rejection(command_id, "embodied_receipt_invalid")
        # Consumption identity belongs to the committed business fact, not
        # the transport request. A new caller key must not award Threat twice
        # for the same hit or move it to a different encounter on retry.
        consumption_key = f"threat:embodied-hit:{receipt.committed_event_ids[0]}"
        return self._threat_authority.record_confirmed_hit(
            attempt=attempt,
            authority_result=receipt,
            presence_event_ids=source.presence_source_event_ids,
            life_event_ids=source.life_state_source_event_ids,
            faction_event_id=source.faction_source_event_id,
            world_ref=source.world_ref,
            timeline_ref=source.timeline_ref,
            encounter_ref=source.encounter_ref,
            actor_incarnation_ref=source.actor_incarnation_ref,
            target_incarnation_ref=source.target_incarnation_ref,
            command_id=consumption_key,
            idempotency_key=consumption_key,
        )

    @staticmethod
    def _threat_rejection(command_id: str, code: str) -> AppendBatchResult:
        from app.gameplay.models import GameplayFailure
        return AppendBatchResult(
            committed=False,
            transaction_id=f"rejected:{command_id}",
            command_id=command_id,
            idempotency_status="rejected",
            failure=GameplayFailure(error_code=code, message=code, failed_stage="combat_threat_consumer"),
        )

    def settle_and_record(
        self,
        attempt: ActionAttempt,
        *,
        source: CombatSourceContext | None,
        command_id: str,
        idempotency_key: str,
    ) -> CombatDurableResult:
        if source is None or not source.valid():
            return CombatDurableResult(
                authority_result=self._reject(attempt, "combat_truth_source_unavailable"),
                error_code="combat_truth_source_unavailable",
            )
        # Resolve an existing durable commit before invoking the embodied owner.
        # The in-memory owner may have restarted, and replay must never apply
        # the same physical settlement twice.
        try:
            prior = self.receipt(idempotency_key)
        except (GameplayEventStoreSnapshotError, KeyError, TypeError, ValueError):
            return CombatDurableResult(
                authority_result=self._reject(attempt, "recovery_required"),
                error_code="recovery_required",
            )
        if prior is not None:
            owner_receipt = self._authority.query_street_combat_receipt(attempt)
            if owner_receipt is None:
                return CombatDurableResult(
                    authority_result=self._reject(attempt, "recovery_required"),
                    error_code="recovery_required",
                )
            return self.record_committed_settlement(
                attempt, authority_result=owner_receipt, source=source,
                command_id=command_id, idempotency_key=idempotency_key,
            )
        try:
            source_valid = self._validate_source(source, attempt)
        except (GameplayEventStoreSnapshotError, KeyError, TypeError, ValueError):
            return CombatDurableResult(
                authority_result=self._reject(attempt, "recovery_required"),
                error_code="recovery_required",
            )
        if not source_valid:
            return CombatDurableResult(
                authority_result=self._reject(attempt, "combat_truth_source_unavailable"),
                error_code="combat_truth_source_unavailable",
            )
        authority_result = self._authority.settle_street_combat(attempt)
        if authority_result.outcome != "committed":
            return CombatDurableResult(authority_result=authority_result, error_code=authority_result.failed_code or "combat_rejected")

        return self.record_committed_settlement(
            attempt,
            authority_result=authority_result,
            source=source,
            command_id=command_id,
            idempotency_key=idempotency_key,
        )

    def record_committed_settlement(
        self,
        attempt: ActionAttempt,
        *,
        authority_result: AuthorityResult,
        source: CombatSourceContext | None,
        command_id: str,
        idempotency_key: str,
    ) -> CombatDurableResult:
        """Recover only the durable append for an already committed owner result.

        This method never calls the embodied authority. Callers use it after a
        durable persistence failure; the existing embodied receipt remains the
        source of truth for the already applied effect.
        """
        if authority_result.outcome != "committed":
            return CombatDurableResult(authority_result=authority_result, error_code="embodied_result_not_committed")
        if source is None or not source.valid():
            return CombatDurableResult(authority_result=authority_result, error_code="combat_truth_source_unavailable")
        # A committed durable receipt is immutable evidence for an exact retry.
        # Check it before requiring the old source set to remain current: its
        # purpose is to recover a lost append response, and the original
        # source read-set was already atomically pinned at commit time.
        try:
            prior = self.receipt(idempotency_key)
        except (GameplayEventStoreSnapshotError, KeyError, TypeError, ValueError):
            return CombatDurableResult(authority_result=authority_result, error_code="receipt_invalid")
        if prior is not None:
            return self._replay_prior_receipt(
                prior, attempt=attempt, authority_result=authority_result, source=source,
                command_id=command_id, idempotency_key=idempotency_key,
            )
        try:
            # Capture heads before revalidation: changes after this point must
            # conflict atomically with the append rather than bless stale pins.
            source_revisions = self._source_read_revisions(source)
            source_valid = self._validate_source(source, attempt)
        except (GameplayEventStoreSnapshotError, KeyError, TypeError, ValueError):
            return CombatDurableResult(authority_result=authority_result, error_code="recovery_required")
        if not source_valid:
            try:
                prior = self.receipt(idempotency_key)
            except (GameplayEventStoreSnapshotError, KeyError, TypeError, ValueError):
                return CombatDurableResult(authority_result=authority_result, error_code="receipt_invalid")
            return CombatDurableResult(
                authority_result=authority_result,
                error_code="idempotency_key_reused" if prior is not None else "combat_truth_source_unavailable",
            )
        owner_receipt = self._authority.query_street_combat_receipt(attempt)
        if owner_receipt is None or not self._receipt_matches_attempt(owner_receipt, attempt, authority_result):
            return CombatDurableResult(authority_result=authority_result, error_code="embodied_receipt_invalid")

        payload = self._settlement_payload(attempt, authority_result, source)
        stream_id = f"gameplay:combat:encounter:{source.encounter_ref}"
        revision = self._store.get_stream_head(stream_id)
        batch = build_atomic_event_batch(
            command_id=command_id,
            principal_ref=COMBAT_SETTLEMENT_PRINCIPAL,
            stream_id=stream_id,
            expected_revision=revision,
            event_specs=((COMBAT_SETTLEMENT_EVENT, payload),),
            idempotency_key=idempotency_key,
            causation_id=attempt.causation_id,
            correlation_id=attempt.correlation_id,
            read_stream_revisions=source_revisions,
            pinned_revisions={
                "embodied_authority": int(authority_result.resulting_revisions.get(attempt.actor_ref, 0)),
                "physics_tick": attempt.physics_tick,
            },
        )
        append_result = self._store.append_batch(batch)
        if not append_result.committed:
            return CombatDurableResult(
                authority_result=authority_result,
                append_result=append_result,
                error_code=append_result.failure.error_code if append_result.failure else "combat_durable_append_failed",
            )
        return CombatDurableResult(authority_result=authority_result, append_result=append_result)

    def _replay_prior_receipt(
        self, prior: AppendBatchResult, *, attempt: ActionAttempt,
        authority_result: AuthorityResult, source: CombatSourceContext, command_id: str,
        idempotency_key: str,
    ) -> CombatDurableResult:
        expected_payload = self._settlement_payload(attempt, authority_result, source)
        try:
            transaction = self._store.get_transaction(prior.transaction_id)
            events = [self._store.get_event(event_id) for event_id in prior.committed_event_ids]
            event = events[0] if len(events) == 1 else None
            idempotency = self._store.get_idempotency_record(COMBAT_SETTLEMENT_PRINCIPAL, idempotency_key)
            valid = (
                prior.committed and prior.failure is None
                and transaction is not None and event is not None and idempotency is not None
                and transaction.transaction_id == prior.transaction_id
                and transaction.command_id == command_id == prior.command_id
                and transaction.idempotency_record.principal_ref == COMBAT_SETTLEMENT_PRINCIPAL
                and transaction.idempotency_record.idempotency_key == idempotency_key
                and transaction.idempotency_record.payload_digest == idempotency.payload_digest
                and transaction.events == events
                and self._store.transaction_owns_event(transaction_id=prior.transaction_id,
                                                       event_id=event.event_id, principal_ref=COMBAT_SETTLEMENT_PRINCIPAL)
                and event.event_type == COMBAT_SETTLEMENT_EVENT
                and event.stream_id == f"gameplay:combat:encounter:{source.encounter_ref}"
                and event.payload == expected_payload
                and event.command_id == command_id
                and event.causation_id == attempt.causation_id
                and event.correlation_id == attempt.correlation_id
                # build_atomic_event_batch's established visibility contract is
                # project; replay must verify what was actually committed.
                and event.visibility_policy == "project"
                and prior.committed_event_ids == [event.event_id]
                and prior.resulting_stream_revisions == {event.stream_id: event.stream_revision}
                and prior.global_sequence_range == (event.global_sequence, event.global_sequence)
            )
        except (GameplayEventStoreSnapshotError, KeyError, TypeError, ValueError):
            return CombatDurableResult(authority_result=authority_result, error_code="receipt_invalid")
        if not valid:
            return CombatDurableResult(authority_result=authority_result, error_code="idempotency_key_reused")
        return CombatDurableResult(authority_result=authority_result,
                                   append_result=prior.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True))

    @staticmethod
    def _settlement_payload(attempt: ActionAttempt, authority_result: AuthorityResult, source: CombatSourceContext) -> dict[str, Any]:
        return {
            "attempt_id": attempt.attempt_id, "action_instance_id": attempt.action_instance_id,
            "actor_ref": attempt.actor_ref, "target_refs": list(attempt.target_refs),
            "action_id": attempt.semantic_action_id,
            "damage": int(authority_result.committed_projection.get("damage", 0)),
            "source": {
                "world_ref": source.world_ref, "timeline_ref": source.timeline_ref,
                "encounter_ref": source.encounter_ref,
                "actor_incarnation_ref": source.actor_incarnation_ref,
                "target_incarnation_ref": source.target_incarnation_ref,
                "presence_source_event_ids": list(source.presence_source_event_ids),
                "life_state_source_event_ids": list(source.life_state_source_event_ids),
                "faction_source_event_id": source.faction_source_event_id,
            },
            "embodied_event_ids": list(authority_result.committed_event_ids),
            "authority_transaction_id": authority_result.transaction_id,
            "attempt_payload_digest": attempt.payload_digest,
        }

    def _validate_source(self, source: CombatSourceContext, attempt: ActionAttempt) -> bool:
        """Re-read all source events before the embodied owner is admitted."""
        if len(attempt.target_refs) != 1:
            return False
        try:
            presence_events = [self._store.get_event(event_id) for event_id in source.presence_source_event_ids]
            life_events = [self._store.get_event(event_id) for event_id in source.life_state_source_event_ids]
            faction = self._store.get_event(source.faction_source_event_id)
        except KeyError:
            return False
        actor_ref = attempt.actor_ref.removeprefix("character:")
        target_ref = attempt.target_refs[0].removeprefix("character:") if len(attempt.target_refs) == 1 else ""
        expected_presence = ((presence_events[0], actor_ref, source.actor_incarnation_ref),
                             (presence_events[1], target_ref, source.target_incarnation_ref))
        expected_life = ((life_events[0], attempt.actor_ref),
                         (life_events[1], attempt.target_refs[0] if attempt.target_refs else ""))
        return (
            self._event_has_committed_provenance(presence_events[0], PRESENCE_SOURCE_PRINCIPAL)
            and self._event_has_committed_provenance(presence_events[1], PRESENCE_SOURCE_PRINCIPAL)
            and self._event_has_committed_provenance(life_events[0], LIFE_STATE_SOURCE_PRINCIPAL)
            and self._event_has_committed_provenance(life_events[1], LIFE_STATE_SOURCE_PRINCIPAL)
            and FACTION_SOURCE_PRINCIPAL is not None
            and self._event_has_committed_provenance(faction, FACTION_SOURCE_PRINCIPAL)
            and all(event.payload.get("timeline_ref") == source.timeline_ref for event in (*presence_events, *life_events, faction))
            and all(event.event_type == "population.presence.spawned" and event.visibility_policy == "project" for event in presence_events)
            and all(event.payload.get("world_ref") == source.world_ref for event in presence_events)
            and all(event.schema_version == 1 and event.stream_id == f"presence:{source.world_ref}" for event in presence_events)
            and all(
                str(event.payload.get("character_ref")) == character_ref
                and f"character:{event.payload.get('character_ref')}@{event.payload.get('incarnation')}" == incarnation_ref
                for event, character_ref, incarnation_ref in expected_presence
            )
            and self._current_presence(source.world_ref, actor_ref, source.presence_source_event_ids[0])
            and self._current_presence(source.world_ref, target_ref, source.presence_source_event_ids[1])
            and all(event.event_type == "gameplay.character.life_state_changed" and event.visibility_policy == "project" and event.schema_version == 1 for event in life_events)
            and all(str(event.payload.get("actor_ref")) == actor_ref for event, actor_ref in expected_life)
            and life_events[0].stream_id == f"gameplay:character:life:{actor_ref}"
            and life_events[1].stream_id == f"gameplay:character:life:{target_ref}"
            and all(event.payload.get("to_state") not in {"dead", "despawned"} for event in life_events)
            and all(self._store.read_stream(event.stream_id)[-1].event_id == event.event_id for event in life_events)
            and faction.visibility_policy == "project"
            and faction.payload.get("hostile") is True
            and faction.payload.get("actor_ref") == attempt.actor_ref
            and faction.payload.get("target_ref") == attempt.target_refs[0]
            and self._current_faction(faction.stream_id, faction.event_id, attempt.actor_ref, attempt.target_refs[0])
        )

    def _event_has_committed_provenance(self, event: Any, owner_principal: str | None) -> bool:
        if not owner_principal:
            return False
        transaction = self._store.get_transaction(event.transaction_id)
        if (transaction is None or transaction.command_id != event.command_id
                or transaction.idempotency_record.principal_ref != owner_principal):
            return False
        return any(
            committed.event_id == event.event_id
            and committed.transaction_id == event.transaction_id
            and committed.stream_id == event.stream_id
            and committed.stream_revision == event.stream_revision
            for committed in transaction.events
        )

    def _source_read_revisions(self, source: CombatSourceContext) -> dict[str, int]:
        source_ids = (*source.presence_source_event_ids, *source.life_state_source_event_ids, source.faction_source_event_id)
        streams = {self._store.get_event(event_id).stream_id for event_id in source_ids}
        streams.add(f"presence:{source.world_ref}")
        return {stream: self._store.get_stream_head(stream) for stream in streams}

    def _current_faction(self, stream_id: str, event_id: str, actor_ref: str, target_ref: str) -> bool:
        events = self._store.read_stream(stream_id)
        return bool(events) and events[-1].event_id == event_id and events[-1].event_type == "gameplay.combat.faction_relation_recorded" and events[-1].payload.get("hostile") is True

    def _current_presence(self, world_ref: str, character_ref: str, source_event_id: str) -> bool:
        events = [event for event in self._store.read_stream(f"presence:{world_ref}") if event.payload.get("character_ref") == character_ref]
        return bool(events) and events[-1].event_id == source_event_id and events[-1].event_type == "population.presence.spawned"

    @staticmethod
    def _receipt_matches_attempt(receipt: AuthorityResult, attempt: ActionAttempt, expected: AuthorityResult) -> bool:
        return (
            receipt.outcome == "committed"
            and receipt.attempt_id == attempt.attempt_id == expected.attempt_id
            and receipt.action_instance_id == attempt.action_instance_id == expected.action_instance_id
            and receipt.causation_id == attempt.causation_id == expected.causation_id
            and receipt.correlation_id == attempt.correlation_id == expected.correlation_id
            and receipt.transaction_id == expected.transaction_id
            and receipt.committed_event_ids == expected.committed_event_ids
            and receipt == expected
        )

    def receipt(self, idempotency_key: str) -> AppendBatchResult | None:
        return self._store.get_by_idempotency(COMBAT_SETTLEMENT_PRINCIPAL, idempotency_key)

    def replay_settlements(self, encounter_ref: str) -> list[dict[str, Any]]:
        """Rebuild the bounded embodied settlement view from durable events."""
        if not isinstance(encounter_ref, str) or not encounter_ref.strip():
            return []
        stream_id = f"gameplay:combat:encounter:{encounter_ref}"
        rows = []
        for event in self._store.read_stream(stream_id, event_type=COMBAT_SETTLEMENT_EVENT):
            source = event.payload.get("source")
            if not isinstance(source, dict) or source.get("encounter_ref") != encounter_ref:
                continue
            rows.append({
                "event_id": event.event_id,
                "stream_revision": event.stream_revision,
                "actor_ref": event.payload.get("actor_ref"),
                "target_refs": list(event.payload.get("target_refs", [])),
                "damage": int(event.payload.get("damage", 0)),
                "source": dict(source),
            })
        return rows

    @staticmethod
    def _reject(attempt: ActionAttempt, code: str) -> AuthorityResult:
        return AuthorityResult(
            attempt_id=attempt.attempt_id,
            action_instance_id=attempt.action_instance_id,
            outcome="rejected",
            failed_stage="combat_source_admission",
            failed_code=code,
            recovery_action="provide_admitted_source_pins",
            causation_id=attempt.causation_id,
            correlation_id=attempt.correlation_id,
            authority_scope="embodied",
        )


__all__ = ["COMBAT_SETTLEMENT_EVENT", "COMBAT_SETTLEMENT_PRINCIPAL", "CombatSourceContext", "CombatDurableResult", "DurableEmbodiedCombatAdapter"]


