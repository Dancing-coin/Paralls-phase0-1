"""Bounded Soul effect owner for the registered binding operation.

This module deliberately owns only Soul effect facts. Resource, Presence and
Soul fact owners remain the sources for the four admission gates.
"""
from __future__ import annotations

from copy import copy
from contextvars import ContextVar
from functools import wraps
from types import MappingProxyType
from typing import Literal, Mapping

from pydantic import ConfigDict, Field, model_validator

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import StrictGameplayModel
from app.gameplay.settlement_plan import build_multi_stream_atomic_event_batch
from app.gameplay.soul_fact_runtime import SoulFactAuthority
from app.gameplay.soul_vulnerability import SoulVulnerabilityReader, SoulVulnerabilityRegistration
from app.population_continuity.activation_sources import ActivationSourceReader


class _ReplayActivationSources(ActivationSourceReader):
    """Original admission at an immutable past cut, never current permission.

    This adapter is constructed only inside the private, disposable replay store.
    It cannot be installed in a production Presence constructor.
    """

    def read(self, event_id, *, world_ref, profile_ref):
        return self.recover(event_id, world_ref=world_ref, profile_ref=profile_ref,
            at_revision=self._store.get_stream_head(f"population:{world_ref}"))


_PRINCIPAL = "soul.effect_authority"
_PREFIX = "gameplay:soul:effect:"
_REPLAY_VALIDATED: ContextVar[set[str] | None] = ContextVar("soul_effect_replay_validated", default=None)


def _replay_scope(method):
    @wraps(method)
    def scoped(*args, **kwargs):
        if _REPLAY_VALIDATED.get() is not None:
            return method(*args, **kwargs)
        token = _REPLAY_VALIDATED.set(set())
        try:
            return method(*args, **kwargs)
        finally:
            _REPLAY_VALIDATED.reset(token)
    return scoped


class SoulEffectRegistration(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    world_ref: str = Field(min_length=1)
    package_ref: str = Field(min_length=1)
    version: str = Field(min_length=1)
    rule_ref: str = Field(min_length=1)
    value_ref: str = Field(min_length=1)
    vulnerability_rule_ref: str = Field(min_length=1)
    link_rule_ref: str = Field(min_length=1)
    grant_rule_ref: str = Field(min_length=1)
    precedence: int = Field(ge=0, strict=True)
    lifetime: Literal["until_revoked"]


class SoulEffectRequest(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    world_ref: str = Field(min_length=1)
    actor_ref: str = Field(min_length=1)
    target_ref: str = Field(min_length=1)
    actor_incarnation: int = Field(ge=1, strict=True)
    target_incarnation: int = Field(ge=1, strict=True)
    package_ref: str = Field(min_length=1)
    version: str = Field(min_length=1)
    rule_ref: str = Field(min_length=1)
    operation: Literal["bind", "unbind"]
    original_effect_ref: str | None = None
    expected_revision: int = Field(ge=0, strict=True)
    idempotency_key: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_operation(self):
        if self.operation == "unbind" and not self.original_effect_ref:
            raise ValueError("soul_effect_original_required")
        if self.operation == "bind" and self.original_effect_ref is not None:
            raise ValueError("soul_effect_original_unexpected")
        return self


class SoulEffectReceipt(StrictGameplayModel):
    committed: bool
    committed_event_ids: tuple[str, ...] = ()
    zero_write: bool = False
    stop_reason: str | None = None


class SoulEffectAuthority:
    def __init__(self, *, facts: SoulFactAuthority,
                 vulnerability: SoulVulnerabilityReader,
                 registrations: tuple[SoulEffectRegistration, ...] = ()) -> None:
        if (type(facts) is not SoulFactAuthority or type(vulnerability) is not SoulVulnerabilityReader
                or vulnerability._anchors is not facts._anchors):
            raise ValueError("soul_effect_sources")
        policies: dict[tuple[str, str, str, str], SoulEffectRegistration] = {}
        for item in registrations:
            row = SoulEffectRegistration.model_validate(item.model_dump(mode="python"))
            key = (row.world_ref, row.package_ref, row.version, row.rule_ref)
            if key in policies:
                raise ValueError("soul_effect_registration_duplicate")
            policies[key] = row
        self._facts = facts
        self._vulnerability = vulnerability
        self.store: GameplayEventStore = facts.store
        self._registrations: Mapping[tuple[str, str, str, str], SoulEffectRegistration] = MappingProxyType(policies)

    @staticmethod
    def stream_id(world_ref: str, target_ref: str) -> str:
        return f"{_PREFIX}{world_ref}:{target_ref}"

    @_replay_scope
    def settle(self, request: SoulEffectRequest) -> SoulEffectReceipt:
        request = SoulEffectRequest.model_validate(request.model_dump(mode="python") if isinstance(request, SoulEffectRequest) else request)
        stream = self.stream_id(request.world_ref, request.target_ref)
        try:
            prior = self.store.get_by_idempotency(_PRINCIPAL, request.idempotency_key)
            if prior is not None:
                event = self._validate_original(request, prior, stream)
                return SoulEffectReceipt(committed=True, zero_write=True, committed_event_ids=(event.event_id,))
            registration = self._registrations.get((request.world_ref, request.package_ref, request.version, request.rule_ref))
            if registration is None:
                return self._reject("soul_effect_registration")
            head = self.store.get_stream_head(stream)
            captured = self.store.get_stream_heads()
            presence_owner = self._facts._anchors._presence._presence
            presence_stream = presence_owner.stream_id(request.world_ref)
            active_actors, _ = presence_owner._history(request.world_ref,
                head=captured.get(presence_stream, 0))
            for profile_ref in active_actors:
                fact_stream = self._facts.stream_id(request.world_ref, profile_ref.removeprefix("character:"))
                captured.setdefault(fact_stream, 0)
            if head != request.expected_revision:
                return self._reject("revision_conflict")
            current = self.projection(world_ref=request.world_ref, target_ref=request.target_ref)
            if request.operation == "bind":
                if current.get("active"):
                    return self._reject("soul_effect_transition")
            elif (not current.get("active") or current.get("original_effect_ref") != request.original_effect_ref
                  or any(current.get(field) != getattr(request, field) for field in
                         ("world_ref", "actor_ref", "target_ref", "actor_incarnation",
                          "target_incarnation", "package_ref", "version", "rule_ref"))
                  or current.get("registration") != registration.model_dump(mode="json")):
                return self._reject("soul_effect_transition")
            actor_anchor = self._facts._anchors.projection(world_ref=request.world_ref, actor_ref=request.actor_ref)
            target_anchor = self._facts._anchors.projection(world_ref=request.world_ref, actor_ref=request.target_ref)
            if not actor_anchor or actor_anchor.get("incarnation") != request.actor_incarnation:
                return self._reject("soul_effect_actor_anchor")
            if not target_anchor or target_anchor.get("incarnation") != request.target_incarnation:
                return self._reject("soul_effect_target_anchor")
            actor_source = self._facts._anchors._presence.read(actor_ref=request.actor_ref, world_ref=request.world_ref,
                                                               expected_incarnation=request.actor_incarnation)
            target_source = self._facts._anchors._presence.read(actor_ref=request.target_ref, world_ref=request.world_ref,
                                                                expected_incarnation=request.target_incarnation)
            link = self._find_fact(request, registration.link_rule_ref, "link", captured)
            if not link or not link.get("active"):
                return self._reject("soul_effect_link")
            grant = self._find_fact(request, registration.grant_rule_ref, "grant", captured)
            if not grant or not grant.get("active"):
                return self._reject("soul_effect_grant")
            blockers = self._protections(request, captured)
            if any(item["precedence"] >= registration.precedence for item in blockers):
                return self._reject("soul_effect_protection")
            vulnerability = self._vulnerability.read(world_ref=request.world_ref, actor_ref=request.target_ref,
                incarnation=request.target_incarnation, package_ref=request.package_ref, version=request.version,
                rule_ref=registration.vulnerability_rule_ref)
            if vulnerability.state != "true":
                return self._reject("soul_effect_vulnerability")
            reads = dict(vulnerability.read_revisions)
            for source in (actor_source, target_source):
                for name, revision in source.read_revisions.items():
                    if name in reads and reads[name] != revision:
                        return self._reject("soul_effect_source_cut")
                    reads[name] = revision
            for anchor in (actor_anchor, target_anchor):
                anchor_stream = self._facts._anchors.stream_id(request.world_ref, anchor["actor_ref"])
                reads[anchor_stream] = captured.get(anchor_stream, 0)
            for participant in (request.actor_ref, request.target_ref):
                fact_stream = self._facts.stream_id(request.world_ref, participant)
                reads[fact_stream] = captured.get(fact_stream, 0)
            # Protection may be issued by another actor. Pin every stream scanned,
            # and the shared Presence head: a new issuer requires Presence admission.
            for name in captured:
                if name.startswith(self._facts.stream_id(request.world_ref, "")):
                    reads[name] = captured[name]
            reads[stream] = head
            if any(captured.get(name, 0) != revision for name, revision in reads.items()):
                return self._reject("soul_effect_source_cut")
            active = request.operation == "bind"
            payload = {"world_ref": request.world_ref, "actor_ref": request.actor_ref, "target_ref": request.target_ref,
                "actor_incarnation": request.actor_incarnation, "target_incarnation": request.target_incarnation,
                "package_ref": request.package_ref, "version": request.version, "rule_ref": request.rule_ref,
                "value_ref": registration.value_ref, "precedence": registration.precedence,
                "lifetime": registration.lifetime, "active": active,
                "original_effect_ref": None if active else request.original_effect_ref,
                "registration": registration.model_dump(mode="json"),
                "vulnerability_registration": self._vulnerability._policies[
                    (request.world_ref, request.package_ref, request.version,
                     registration.vulnerability_rule_ref)].model_dump(mode="json"),
                "vulnerability_projection_revision": vulnerability.projection_revision}
            batch = build_multi_stream_atomic_event_batch(
                command_id=f"soul:effect:{request.world_ref}:{request.target_ref}:{request.idempotency_key}",
                principal_ref=_PRINCIPAL, expected_revisions={stream: head},
                event_specs={stream: [("soul.effect.binding.changed", payload)]},
                event_visibility_policies={stream: ["authority_only"]}, idempotency_key=request.idempotency_key,
                causation_id=f"action:{request.operation}", correlation_id=f"world:{request.world_ref}",
                read_stream_revisions=reads, pinned_revisions=reads)
            result = self.store.append_batch(batch)
            if not result.committed:
                return self._reject(result.failure.error_code if result.failure else "append_rejected")
            return SoulEffectReceipt(committed=True, committed_event_ids=tuple(result.committed_event_ids))
        except (ValueError, KeyError, TypeError, IndexError) as exc:
            return self._reject(str(exc) or "soul_effect_invalid")

    @_replay_scope
    def projection(self, *, world_ref: str, target_ref: str) -> dict[str, object]:
        stream = self.stream_id(world_ref, target_ref)
        events = self.store.read_stream(stream, to_revision=self.store.get_stream_head(stream))
        if not events:
            return {}
        state: dict[str, object] = {}
        for revision, event in enumerate(events, 1):
            transaction = self.store.get_transaction(event.transaction_id)
            if transaction is None or event.stream_revision != revision:
                raise ValueError("soul_effect_history_invalid")
            receipt = self.store.get_by_idempotency(_PRINCIPAL, transaction.idempotency_record.idempotency_key)
            payload = dict(event.payload)
            request = SoulEffectRequest(**{field: payload[field] for field in
                ("world_ref", "actor_ref", "target_ref", "actor_incarnation", "target_incarnation",
                 "package_ref", "version", "rule_ref", "original_effect_ref")},
                operation="bind" if payload["active"] else "unbind", expected_revision=revision - 1,
                idempotency_key=transaction.idempotency_record.idempotency_key)
            self._validate_original(request, receipt, stream)
            if payload["active"]:
                if state.get("active"):
                    raise ValueError("soul_effect_history_transition")
            elif (not state.get("active") or payload["original_effect_ref"] != state["original_effect_ref"]
                  or payload["registration"] != state["registration"]):
                raise ValueError("soul_effect_history_transition")
            state = payload
            if state.get("active"):
                state["original_effect_ref"] = state.get("original_effect_ref") or event.event_id
        return state

    def _fact_states(self, stream, head):
        states = {}
        events = self.store.read_stream(stream, to_revision=head) if head else []
        if len(events) != head:
            raise ValueError("soul_effect_fact_history")
        for revision, event in enumerate(events, 1):
            transaction = self.store.get_transaction(event.transaction_id)
            receipt = (self.store.get_by_idempotency("soul.fact_authority",
                transaction.idempotency_record.idempotency_key) if transaction else None)
            if event.stream_revision != revision or receipt is None:
                raise ValueError("soul_effect_fact_history")
            self._facts._original_from_event(event, receipt, stream)
            payload = dict(event.payload)
            key = tuple(payload[field] for field in ("world_ref", "actor_ref", "target_ref",
                "actor_incarnation", "target_incarnation", "package_ref", "version", "rule_ref"))
            previous = states.get(key, {})
            if payload["active"]:
                if previous.get("active"):
                    raise ValueError("soul_effect_fact_transition")
                payload["original_fact_ref"] = event.event_id
            elif (not previous.get("active")
                  or previous.get("original_fact_ref") != payload.get("original_fact_ref")
                  or previous.get("registration") != payload.get("registration")):
                raise ValueError("soul_effect_fact_transition")
            states[key] = payload
        return tuple(states.values())

    def _find_fact(self, request, rule_ref, kind, captured):
        stream = self._facts.stream_id(request.world_ref, request.actor_ref)
        for payload in self._fact_states(stream, captured.get(stream, 0)):
            if (payload["kind"] == kind and payload["rule_ref"] == rule_ref
                    and all(payload[field] == getattr(request, field) for field in
                        ("world_ref", "actor_ref", "target_ref", "actor_incarnation",
                         "target_incarnation", "package_ref", "version"))
                    and request.operation in payload["registration"]["operations"]):
                return payload
        return None

    def _protections(self, request, captured):
        blockers = []
        presence = self._facts._anchors._presence._presence
        active, _ = presence._history(request.world_ref,
            head=captured.get(presence.stream_id(request.world_ref), 0))
        prefix = self._facts.stream_id(request.world_ref, "")
        for stream, head in captured.items():
            if not stream.startswith(prefix):
                continue
            for payload in self._fact_states(stream, head):
                if (payload["kind"] == "protection" and payload["active"]
                        and active.get(f"character:{payload['actor_ref']}") == payload["actor_incarnation"]
                        and payload["world_ref"] == request.world_ref
                        and payload["target_ref"] == request.target_ref
                        and payload["target_incarnation"] == request.target_incarnation
                        and request.operation in payload["registration"]["operations"]):
                    blockers.append(payload)
        return blockers

    def _validate_original(self, request, receipt, stream):
        if (receipt is None or not receipt.committed or receipt.failure is not None
                or receipt.idempotency_status != "new_commit" or receipt.projection_refresh_hints):
            raise ValueError("soul_effect_original_invalid")
        batch = self.store.get_transaction(receipt.transaction_id)
        if batch is None or len(batch.events) != 1:
            raise ValueError("soul_effect_original_invalid")
        event = batch.events[0]
        if (event.stream_id != stream or event.event_type != "soul.effect.binding.changed"
                or event.visibility_policy != "authority_only" or event.event_id not in receipt.committed_event_ids
                or any(event.payload.get(field) != getattr(request, field) for field in
                       ("world_ref", "actor_ref", "target_ref", "actor_incarnation",
                        "target_incarnation", "package_ref", "version", "rule_ref", "original_effect_ref"))
                or event.payload.get("active") is not (request.operation == "bind")
                or batch.idempotency_record.idempotency_key != request.idempotency_key):
            raise ValueError("soul_effect_original_invalid")
        if (self.store.get_event(event.event_id) != event or event.schema_version != 1
                or batch.idempotency_record.principal_ref != _PRINCIPAL
                or self.store.get_idempotency_record(_PRINCIPAL, request.idempotency_key) != batch.idempotency_record
                or receipt.command_id != batch.command_id or receipt.transaction_id != batch.transaction_id
                or receipt.committed_event_ids != [event.event_id]
                or receipt.resulting_stream_revisions != {stream: event.stream_revision}
                or receipt.global_sequence_range != (event.global_sequence, event.global_sequence)
                or batch.expected_stream_revisions != {stream: event.stream_revision - 1}
                or batch.read_stream_revisions != batch.pinned_revisions
                or batch.outbox_entries or batch.projection_refresh_hints):
            raise ValueError("soul_effect_original_invalid")
        # Nested reconstruction sees the same immutable original transactions.
        # Share only within this synchronous public call; later reads must
        # validate again, including after a store reopen or corruption.
        validated = _REPLAY_VALIDATED.get()
        identity = batch.model_dump_json()
        if validated is None or identity not in validated:
            self._replay_original(request, event, batch)
            if validated is not None:
                validated.add(identity)
        return event

    def _replay_original(self, request, event, batch):
        # Keep original positions by replaying complete transactions in order.
        # This is bounded correctness evidence, not a common-cut/checkpoint API.
        past = GameplayEventStore()
        for transaction in self.store.read_transactions():
            if transaction.events[-1].global_sequence >= event.global_sequence:
                break
            result = past.append_batch(transaction)
            record = transaction.idempotency_record
            original = self.store.get_by_idempotency(record.principal_ref, record.idempotency_key)
            if (not result.committed or past.get_transaction(transaction.transaction_id) != transaction
                    or original != result
                    or self.store.get_idempotency_record(record.principal_ref, record.idempotency_key) != record
                    or any(self.store.get_event(item.event_id) != item for item in transaction.events)):
                raise ValueError("soul_effect_source_history")
        old_anchors = self._facts._anchors
        old_presence = old_anchors._presence._presence
        old_activation_sources = old_presence._sources
        activation = copy(old_activation_sources._authority)
        activation.store = past
        activation_sources = _ReplayActivationSources(authority=activation,
            producer_ref=old_activation_sources._producer)
        presence = copy(old_presence)
        presence.store, presence._sources = past, activation_sources
        presence_sources = copy(old_anchors._presence)
        presence_sources._store, presence_sources._presence = past, presence
        resources = copy(old_anchors._resources)
        resources._store = past
        anchors = copy(old_anchors)
        anchors.store, anchors._presence, anchors._resources = past, presence_sources, resources
        facts = SoulFactAuthority(anchors=anchors)
        policy = SoulEffectRegistration.model_validate(event.payload["registration"])
        vulnerability = SoulVulnerabilityReader(anchors=anchors, registrations=(
            SoulVulnerabilityRegistration.model_validate(event.payload["vulnerability_registration"]),))
        owner = SoulEffectAuthority(facts=facts, vulnerability=vulnerability, registrations=(policy,))
        replay_request = request.model_copy(update={"expected_revision": event.stream_revision - 1})
        result = owner.settle(replay_request)
        if not result.committed or past.get_transaction(event.transaction_id) != batch:
            raise ValueError("soul_effect_original_replay_invalid")

    @staticmethod
    def _reject(reason):
        return SoulEffectReceipt(committed=False, stop_reason=reason)
