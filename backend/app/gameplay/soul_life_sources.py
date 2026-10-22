"""Read-only canonical LifeState evidence for bounded Soul admission."""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from app.gameplay.event_store import GameplayEventStore


@dataclass(frozen=True)
class SoulLifeSource:
    actor_ref: str
    world_ref: str
    incarnation: int
    state: str
    read_revisions: Mapping[str, int]
    source_event_refs: tuple[str, ...]
    last_global_sequence: int


class SoulLifeSourceReader:
    """Reconstruct schema-2 LifeState only from its original owner receipts."""

    def __init__(self, *, store: GameplayEventStore):
        if type(store) is not GameplayEventStore and not all(
            hasattr(store, name) for name in ("get_event", "get_transaction", "get_by_idempotency", "read_stream")
        ):
            raise ValueError("soul_life_source_store")
        self._store = store

    def read(self, *, actor_ref: str, world_ref: str, incarnation: int,
             boundary_revision: int | None = None) -> SoulLifeSource:
        if not isinstance(actor_ref, str) or not actor_ref or actor_ref.strip() != actor_ref:
            raise ValueError("soul_life_source_actor")
        if not isinstance(world_ref, str) or not world_ref or world_ref.strip() != world_ref:
            raise ValueError("soul_life_source_world")
        if type(incarnation) is not int or incarnation < 1:
            raise ValueError("soul_life_source_incarnation")
        stream = f"gameplay:character:life:character:{actor_ref}"
        head = self._store.get_stream_head(stream) if boundary_revision is None else boundary_revision
        if type(head) is not int or head < 0 or head > self._store.get_stream_head(stream):
            raise ValueError("soul_life_source_revision")
        events = self._store.read_stream(stream, to_revision=head)
        if len(events) != head:
            raise ValueError("soul_life_source_history")
        state = "unknown"
        bound_incarnation = None
        refs: list[str] = []
        read_revisions = {stream: head}
        last_sequence = 0
        for revision, event in enumerate(events, 1):
            if (event.stream_revision != revision or event.schema_version != 2
                    or event.event_type != "gameplay.character.life_state_changed"
                    or event.visibility_policy != "project"
                    or event.payload.get("actor_ref") != f"character:{actor_ref}"):
                raise ValueError("soul_life_source_history")
            self._validate_receipt(event)
            payload = event.payload
            target = payload.get("to_state")
            if payload.get("from_state") != state or target not in {"alive", "dead"}:
                raise ValueError("soul_life_source_transition")
            if target == "alive":
                if (state != "unknown" or payload.get("world_ref") != world_ref
                        or payload.get("incarnation") != incarnation
                        or payload.get("policy_revision") != "policy:character-life-state-presence-admission@1"):
                    raise ValueError("soul_life_source_presence_binding")
                self._validate_presence_link(event, payload)
                bound_incarnation = payload["incarnation"]
                source_events = tuple(self._store.get_event(ref) for ref in
                                      (payload["source_activation_event_id"], payload["source_presence_event_id"]))
            else:
                if payload.get("policy_revision") != "policy:character-life-state-case-death@2":
                    raise ValueError("soul_life_source_death_policy")
                self._validate_death_link(event)
                confirmation = self._store.get_event(payload["source_confirmation_event_id"])
                source_events = (self._store.get_event(confirmation.payload["source_event_id"]), confirmation)
            for source in source_events:
                refs.append(source.event_id)
                read_revisions[source.stream_id] = self._store.get_stream_head(source.stream_id)
            state = target
            refs.append(event.event_id)
            last_sequence = event.global_sequence
        if state == "dead" and bound_incarnation != incarnation:
            raise ValueError("soul_life_source_death_scope_unbound")
        return SoulLifeSource(actor_ref, world_ref, incarnation, state, MappingProxyType(read_revisions),
                              tuple(refs), last_sequence)

    def _validate_receipt(self, event) -> None:
        tx = self._store.get_transaction(event.transaction_id)
        if tx is None or event not in tx.events or len(tx.events) != 1:
            raise ValueError("soul_life_source_receipt")
        record = tx.idempotency_record
        receipt = self._store.get_by_idempotency(record.principal_ref, record.idempotency_key)
        if (not receipt or not receipt.committed or receipt.transaction_id != tx.transaction_id
                or receipt.committed_event_ids != [event.event_id]
                or receipt.resulting_stream_revisions != {event.stream_id: event.stream_revision}
                or receipt.global_sequence_range != (event.global_sequence, event.global_sequence)):
            raise ValueError("soul_life_source_receipt")
        if event.payload.get("to_state") == "alive":
            expected = "authority:character:life-state:presence-admission"
        else:
            expected = "authority:character:life-state"
        if record.principal_ref != expected:
            raise ValueError("soul_life_source_owner")

    def _validate_presence_link(self, life_event, event_payload: dict) -> None:
        try:
            presence = self._store.get_event(event_payload["source_presence_event_id"])
            activation = self._store.get_event(event_payload["source_activation_event_id"])
        except (KeyError, TypeError):
            raise ValueError("soul_life_source_presence_link") from None
        if (presence.event_type != "population.presence.spawned"
                or presence.payload.get("world_ref") != event_payload["world_ref"]
                or presence.payload.get("character_ref") != event_payload["actor_ref"]
                or presence.payload.get("incarnation") != event_payload["incarnation"]
                or presence.payload.get("source_activation_event_id") != activation.event_id
                or activation.event_type != "population.activation.committed"
                or activation.payload.get("world_ref") != event_payload["world_ref"]
                or activation.payload.get("profile_ref") != event_payload["actor_ref"]
                or activation.global_sequence >= presence.global_sequence
                or presence.global_sequence >= life_event.global_sequence
                or not self._receipt_matches(presence, "population.presence_authority")
                or not self._activation_receipt_matches(activation)):
            raise ValueError("soul_life_source_presence_link")

    def _validate_death_link(self, event) -> None:
        payload = event.payload
        try:
            source = self._store.get_event(payload["source_confirmation_event_id"])
        except (KeyError, TypeError):
            raise ValueError("soul_life_source_death_link") from None
        if (source.payload.get("target_actor_ref") != payload.get("actor_ref")
                or source.payload.get("confirmed") is not True
                or source.stream_revision != payload.get("source_confirmation_revision")
                or source.payload.get("source_revision") is None
                or not self._receipt_matches(source, "authority:p5:investigation-conflict")):
            raise ValueError("soul_life_source_death_link")
        try:
            terminal = self._store.get_event(source.payload["source_event_id"])
        except (KeyError, TypeError):
            raise ValueError("soul_life_source_death_link") from None
        if (terminal.event_type != "gameplay.conflict.terminal_outcome_recorded"
                or terminal.payload.get("terminal_kind") != "case_death"
                or terminal.payload.get("actor_ref") != payload.get("actor_ref")
                or terminal.stream_id != source.stream_id
                or terminal.stream_revision != source.payload.get("source_revision")
                or terminal.global_sequence >= source.global_sequence
                or not self._receipt_matches(terminal, "authority:p5:investigation-conflict")):
            raise ValueError("soul_life_source_death_link")

    def _activation_receipt_matches(self, event) -> bool:
        tx = self._store.get_transaction(event.transaction_id)
        if tx is None:
            return False
        principal = tx.idempotency_record.principal_ref
        return (principal.startswith("population:") or principal.startswith("world_runtime.")) and self._receipt_matches(event, principal)

    def _receipt_matches(self, event, principal: str) -> bool:
        tx = self._store.get_transaction(event.transaction_id)
        if (tx is None or tx.idempotency_record.principal_ref != principal
                or event not in tx.events):
            return False
        receipt = self._store.get_by_idempotency(principal, tx.idempotency_record.idempotency_key)
        events = tuple(tx.events)
        expected_revisions = {item.stream_id: item.stream_revision for item in events}
        expected_range = (min(item.global_sequence for item in events),
                          max(item.global_sequence for item in events))
        return bool(receipt and receipt.committed
                    and receipt.transaction_id == tx.transaction_id
                    and receipt.committed_event_ids == [item.event_id for item in events]
                    and receipt.resulting_stream_revisions == expected_revisions
                    and receipt.global_sequence_range == expected_range)
