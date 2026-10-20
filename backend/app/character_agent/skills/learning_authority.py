"""Registered, receipt-backed learned facts on the shared gameplay ledger."""
from __future__ import annotations

import hashlib
import json
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.character_agent.skills.models import CharacterSkillState
from app.character_agent.skills.registry import CharacterSkillRegistry
from app.gameplay.event_schema_registry import EventSchemaRegistration
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.settlement_plan import build_multi_stream_atomic_event_batch


def _digest(value):
    return "sha256:" + hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False).encode()).hexdigest()


class _Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class LearningSourceRule(_Contract):
    event_type: str = Field(min_length=1)
    schema_version: int = Field(ge=1, strict=True)
    principal_ref: str = Field(min_length=1)
    subject_field: str = Field(min_length=1)
    world_field: str = Field(min_length=1)
    success_field: str = Field(min_length=1)
    success_value: bool | str


class LearningObjectRule(_Contract):
    object_id: str = Field(min_length=1)
    world_ref: str = Field(min_length=1)
    revision: int = Field(ge=1, strict=True)
    skill_id: str = Field(min_length=1)
    operation: Literal["upgrade", "branch", "mutation", "fusion", "evolution"]
    stage: Literal["noticed", "observed", "imitated", "structured", "practiced", "operational",
                   "stable", "integrated", "personalized", "complete", "evolved"]
    method: Literal["observation", "imitation", "guidance", "practice", "combat", "review", "research", "mentorship", "transfer"]
    caller_principal: str = Field(min_length=1)
    source: LearningSourceRule
    minimum_evidence: int = Field(default=1, ge=1, strict=True)
    prerequisite_skill_ids: tuple[str, ...] = ()
    rank: Literal["none", "novice", "basic", "trained", "expert", "master"]
    proficiency: float = Field(ge=0, le=1, allow_inf_nan=False)
    confidence: float = Field(ge=0, le=1, allow_inf_nan=False)

    @property
    def digest(self):
        return _digest(self.model_dump(mode="json"))


class LearningCommitRequest(_Contract):
    command_id: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    actor_id: str = Field(min_length=1)
    world_ref: str = Field(min_length=1)
    object_id: str = Field(min_length=1)
    rule_digest: str = Field(min_length=1)
    operation: Literal["upgrade", "branch", "mutation", "fusion", "evolution"]
    stage: str = Field(min_length=1)
    method: str = Field(min_length=1)
    evidence_refs: tuple[str, ...] = Field(min_length=1)
    expected_source_revisions: dict[str, Annotated[int, Field(strict=True, ge=0)]] = Field(min_length=1)
    expected_revision: int = Field(ge=0, strict=True)
    causation_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)


class RegisteredLearningAuthority:
    PRINCIPAL = "authority:character:learning"
    EVENT = "gameplay.character.skill_learned"
    SCHEMA = EventSchemaRegistration(EVENT, 1, "sha256:character-skill-learned-v1")

    def __init__(self, *, store: GameplayEventStore, registry: CharacterSkillRegistry, rules):
        self._store, self._registry = store, registry
        self._rules = {}
        for raw in rules:
            rule = LearningObjectRule.model_validate(raw.model_dump() if isinstance(raw, LearningObjectRule) else raw)
            key = (rule.world_ref, rule.object_id)
            if key in self._rules:
                raise ValueError("learning_registration_duplicate")
            self._require_learnable(rule.skill_id)
            for skill in rule.prerequisite_skill_ids:
                registry.skill(skill)
            if (rule.operation == "evolution" or rule.stage == "evolved") and not rule.source.principal_ref.startswith("authority:siming:"):
                raise ValueError("learning_evolution_requires_siming_owner")
            self._rules[key] = rule

    def _require_learnable(self, skill_id):
        # Grants require their own authority proof; an object rule is not one.
        if self._registry.skill(skill_id).learnability not in {"natural", "trained"}:
            raise ValueError("learning_learnability_requires_authority")

    @staticmethod
    def stream_id(world_ref, actor_id):
        return "gameplay:character:learned:" + _digest([world_ref, actor_id])[7:]

    def _sources(self, request, rule, *, historical_sequence=None):
        refs = request.evidence_refs
        if (len(refs) != len(set(refs)) or any(not ref for ref in refs)
                or len(refs) < rule.minimum_evidence):
            raise ValueError("learning_source_count_invalid")
        streams = {}
        for ref in refs:
            try:
                event = self._store.get_event(ref)
            except KeyError as exc:
                raise ValueError("learning_source_missing") from exc
            tx = self._store.get_transaction(event.transaction_id)
            receipt = (self._store.get_by_idempotency(rule.source.principal_ref, tx.idempotency_record.idempotency_key)
                       if tx is not None else None)
            visibility = event.visibility_policy in {"project", f"actor_private:{request.actor_id}"}
            if (event.event_type != rule.source.event_type or event.schema_version != rule.source.schema_version
                    or tx is None or tx.idempotency_record.principal_ref != rule.source.principal_ref
                    or event not in tx.events or receipt is None or not receipt.committed
                    or receipt.transaction_id != tx.transaction_id or ref not in receipt.committed_event_ids
                    or not visibility or event.payload.get(rule.source.subject_field) != request.actor_id
                    or event.payload.get(rule.source.world_field) != request.world_ref
                    or type(event.payload.get(rule.source.success_field)) is not type(rule.source.success_value)
                    or event.payload.get(rule.source.success_field) != rule.source.success_value
                    or historical_sequence is not None and event.global_sequence >= historical_sequence):
                raise ValueError("learning_source_invalid")
            expected = request.expected_source_revisions.get(event.stream_id)
            if type(expected) is not int or expected < event.stream_revision:
                raise ValueError("learning_source_revision_invalid")
            streams[event.stream_id] = expected
        if streams != request.expected_source_revisions:
            raise ValueError("learning_source_read_set_invalid")
        if historical_sequence is None and any(self._store.get_stream_head(s) != r for s, r in streams.items()):
            raise ValueError("learning_source_stale")
        return streams

    @staticmethod
    def _state(request, rule):
        return CharacterSkillState(actor_id=request.actor_id, skill_id=rule.skill_id, source="learned",
            rank=rule.rank, proficiency=float(rule.proficiency), confidence=float(rule.confidence),
            evidence_refs=list(request.evidence_refs), visibility={"scope": f"actor_private:{request.actor_id}"})

    def _batch(self, request, caller, rule):
        stream = self.stream_id(request.world_ref, request.actor_id)
        payload = dict(request=request.model_dump(mode="json"), caller_principal=caller,
                       registration=rule.model_dump(mode="json"), state=self._state(request, rule).model_dump(mode="json"))
        return build_multi_stream_atomic_event_batch(command_id=request.command_id, principal_ref=self.PRINCIPAL,
            expected_revisions={stream: request.expected_revision},
            event_specs={stream: ((self.EVENT, payload),)},
            event_visibility_policies={stream: (f"actor_private:{request.actor_id}",)},
            read_stream_revisions=request.expected_source_revisions, idempotency_key=request.idempotency_key,
            causation_id=request.causation_id, correlation_id=request.correlation_id)

    def _history(self, world_ref, actor_id):
        stream = self.stream_id(world_ref, actor_id)
        events = self._store.read_stream(stream)
        states, used = {}, set()
        for revision, event in enumerate(events, 1):
            try:
                request = LearningCommitRequest.model_validate(event.payload["request"])
                rule = LearningObjectRule.model_validate(event.payload["registration"])
                caller = event.payload["caller_principal"]
                if (request.actor_id != actor_id or request.world_ref != world_ref
                        or request.expected_revision != revision - 1 or event.stream_revision != revision):
                    raise ValueError("learning_replay_scope_or_revision_invalid")
                self._validate_rule(request, caller, rule)
                self._sources(request, rule, historical_sequence=event.global_sequence)
                if not set(rule.prerequisite_skill_ids).issubset(states):
                    raise ValueError("learning_replay_prerequisite_missing")
                keys = {(request.object_id, ref) for ref in request.evidence_refs}
                if keys & used:
                    raise ValueError("learning_replay_evidence_reused")
                rebuilt = self._batch(request, caller, rule)
                rebuilt.events[0].stream_revision = revision
                rebuilt.events[0].global_sequence = event.global_sequence
                tx = self._store.get_transaction(event.transaction_id)
                receipt = self._store.get_by_idempotency(self.PRINCIPAL, request.idempotency_key)
                if (tx != rebuilt or event != rebuilt.events[0] or receipt is None or not receipt.committed
                        or receipt.transaction_id != tx.transaction_id
                        or receipt.committed_event_ids != [event.event_id]
                        or receipt.resulting_stream_revisions != {stream: revision}
                        or receipt.global_sequence_range != (event.global_sequence, event.global_sequence)):
                    raise ValueError("learning_replay_receipt_invalid")
                states[rule.skill_id] = self._state(request, rule)
                used.update(keys)
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError("learning_replay_invalid") from exc
        return states, used

    @staticmethod
    def _validate_rule(request, caller, rule):
        if (rule.digest != request.rule_digest or rule.world_ref != request.world_ref
                or rule.object_id != request.object_id or caller != rule.caller_principal
                or (request.operation, request.stage, request.method) != (rule.operation, rule.stage, rule.method)):
            raise ValueError("learning_registration_or_caller_invalid")
        if (rule.operation == "evolution" or rule.stage == "evolved") and not rule.source.principal_ref.startswith("authority:siming:"):
            raise ValueError("learning_evolution_requires_siming_owner")

    def settle(self, request, *, caller_principal):
        # Revalidate frozen request dictionaries as well as model_copy callers.
        request = LearningCommitRequest.model_validate(request.model_dump())
        prior = self._store.get_by_idempotency(self.PRINCIPAL, request.idempotency_key)
        if prior is not None:
            if not prior.committed or len(prior.committed_event_ids) != 1:
                raise ValueError("learning_prior_receipt_invalid")
            event = self._store.get_event(prior.committed_event_ids[0])
            if (event.stream_id != self.stream_id(request.world_ref, request.actor_id)
                    or event.event_type != self.EVENT or event.schema_version != 1
                    or event.transaction_id != prior.transaction_id):
                raise ValueError("learning_prior_receipt_invalid")
            if (event.payload.get("request") != request.model_dump(mode="json")
                    or event.payload.get("caller_principal") != caller_principal):
                raise ValueError("learning_idempotency_conflict")
            self._history(request.world_ref, request.actor_id)
            return prior
        rule = self._rules.get((request.world_ref, request.object_id))
        if rule is None:
            raise ValueError("learning_registration_missing")
        self._validate_rule(request, caller_principal, rule)
        self._require_learnable(rule.skill_id)
        states, used = self._history(request.world_ref, request.actor_id)
        stream = self.stream_id(request.world_ref, request.actor_id)
        if self._store.get_stream_head(stream) != request.expected_revision:
            raise ValueError("learning_revision_conflict")
        if not set(rule.prerequisite_skill_ids).issubset(states):
            raise ValueError("learning_prerequisite_missing")
        if {(request.object_id, ref) for ref in request.evidence_refs} & used:
            raise ValueError("learning_evidence_reused")
        self._sources(request, rule)
        return self._store.append_batch(self._batch(request, caller_principal, rule))

    def states(self, *, world_ref, actor_id):
        states, _ = self._history(world_ref, actor_id)
        return [states[key].model_copy(deep=True) for key in sorted(states)]
