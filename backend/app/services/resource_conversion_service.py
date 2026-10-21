"""Resource conversion owner, designed and implemented in stage three.

This is deliberately a same-actor Resource owner.  It reuses the application's
controller binding and the shared event store; it does not grant authority or
create a second clock, ledger, or permission system.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Callable
from pathlib import Path

import yaml

from pydantic import ConfigDict, Field, StrictInt

from app.gameplay.models import AppendBatchResult, StrictGameplayModel
from app.gameplay.resource_body_runtime import ResourceBodyRuntimeProjector, ResourceStateProjection
from app.gameplay.settlement_plan import build_multi_stream_atomic_event_batch
from app.services.embodied_controller_auth_service import EmbodiedControllerAuthService


PRINCIPAL = "actor_gameplay.resource_conversion_domain"


def _digest(value: object) -> str:
    return "sha256:" + sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True)
class ConversionRule:
    rule_id: str
    revision: str
    input_resource_id: str
    output_resource_id: str
    input_amount: int
    output_amount: int
    policy_digest: str
    actor_ref: str
    world_ref: str
    timeline_ref: str

    @classmethod
    def create(cls, *, policy_digest: str | None = None, **kwargs: object) -> "ConversionRule":
        payload = dict(kwargs)
        digest = policy_digest or _digest(payload)
        return cls(policy_digest=digest, **payload)


DEFAULT_POLICY_PATH = Path(__file__).resolve().parents[3] / "assets/gameplay/resource-equipment/resource-conversion.v1.yaml"


class _RevalidatingStore:
    def __init__(self, source, revalidate):
        self._source, self._revalidate = source, revalidate

    def __getattr__(self, name):
        return getattr(self._source, name)

    def append_batch(self, batch):
        if batch.idempotency_record.principal_ref == PRINCIPAL:
            self._revalidate()
        return self._source.append_batch(batch)


def load_conversion_rules(raw: bytes | None = None) -> tuple[ConversionRule, ...]:
    """Parse pinned authored bytes; callers retain/revalidate the exact source."""
    raw = DEFAULT_POLICY_PATH.read_bytes() if raw is None else raw
    document = yaml.safe_load(raw.decode("utf-8"))
    revision = document.get("revision")
    if (not isinstance(revision, str) or not revision.endswith("@1")
            or document.get("fact_owner_ref") != PRINCIPAL
            or document.get("publisher_ref") != "project-content:stage3"):
        raise ValueError("resource_conversion_policy_source_invalid")
    digest = "sha256:" + sha256(raw).hexdigest()
    rules = []
    for item in document.get("rules", []):
        rules.append(ConversionRule.create(
            policy_digest=digest, rule_id=item["rule_id"], revision=revision,
            input_resource_id=item["input_resource_id"], output_resource_id=item["output_resource_id"],
            input_amount=item["input_amount"], output_amount=item["output_amount"],
            actor_ref=document["scope"]["actor_ref"], world_ref=document["scope"]["world_ref"],
            timeline_ref=document["scope"]["timeline_ref"]))
    if len(rules) != 2 or len({rule.rule_id for rule in rules}) != len(rules):
        raise ValueError("resource_conversion_policy_rules_invalid")
    return tuple(rules)


class ResourceConversionCommand(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    command_id: str = Field(min_length=1)
    actor_ref: str = Field(min_length=1)
    world_ref: str = Field(min_length=1)
    timeline_ref: str = Field(min_length=1)
    policy_revision: str = Field(min_length=1)
    policy_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    rule_id: str = Field(min_length=1)
    units: StrictInt = Field(gt=0)
    expected_projection_revision: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    causation_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)


@dataclass(frozen=True)
class ConversionWorldScope:
    world_ref: str
    timeline_ref: str


class ResourceConversionService:
    """Admission plus same-resource conversion settlement."""

    def __init__(self, *, store, controller_auth: EmbodiedControllerAuthService,
                 scope_resolver: Callable[[], ConversionWorldScope | None],
                 policy_source: Callable[[], tuple[ConversionRule, ...]],
                 binding_revision_resolver: Callable[[str], str] | None = None,
                 capability_resolver: Callable[[str, str, str], bool] | None = None):
        self.store = store
        self.auth = controller_auth
        self.scope_resolver = scope_resolver
        self.policy_source = policy_source
        self.admitted_policy = tuple(policy_source())
        if not self.admitted_policy:
            raise ValueError("resource_conversion_policy_source_missing")
        self.binding_revision_resolver = binding_revision_resolver
        self.capability_resolver = capability_resolver

    def submit(self, command: ResourceConversionCommand, *, connection_ref: str,
               resources: ResourceStateProjection) -> AppendBatchResult:
        command = ResourceConversionCommand.model_validate(command.model_dump())
        binding = self.auth.resolve_controller_binding(actor_id=command.actor_ref, connection_ref=connection_ref)
        if not binding.accepted or binding.binding is None:
            raise ValueError(binding.error_code or "resource_conversion_controller_required")
        if self.capability_resolver is None or not self.capability_resolver(binding.binding.authenticated_principal_ref, command.actor_ref, command.policy_revision):
            raise ValueError("resource_conversion_capability_required")
        binding_revision = self.binding_revision_resolver(connection_ref) if self.binding_revision_resolver else binding.binding.binding_id
        scope = self.scope_resolver()
        if scope is None or (scope.world_ref, scope.timeline_ref) != (command.world_ref, command.timeline_ref):
            raise ValueError("resource_conversion_scope_conflict")
        rule = self._rule(command)
        stream = f"gameplay:resources:{command.actor_ref}"
        input_delta = -rule.input_amount * command.units
        output_delta = rule.output_amount * command.units
        key = f"{command.actor_ref}:{command.idempotency_key}"
        prior = self.store.get_idempotency_record(PRINCIPAL, key)
        payload = {"actor_ref": command.actor_ref, "world_ref": command.world_ref, "timeline_ref": command.timeline_ref,
                   "resource_id": rule.input_resource_id,
                   "rule_id": rule.rule_id, "policy_revision": rule.revision, "policy_digest": rule.policy_digest,
                   "input_resource_id": rule.input_resource_id, "output_resource_id": rule.output_resource_id,
                   "input_delta": input_delta, "output_delta": output_delta, "units": command.units,
                   "input_amount_per_unit": rule.input_amount, "output_amount_per_unit": rule.output_amount,
                   "source_projection_revision": command.expected_projection_revision, "binding_id": binding.binding.binding_id,
                   "binding_revision": binding_revision, "request_command_id": command.command_id,
                   "request_causation_id": command.causation_id, "request_correlation_id": command.correlation_id}
        if prior is not None:
            result = self.store.get_by_idempotency(PRINCIPAL, key)
            if result is None:
                raise ValueError("resource_conversion_idempotency_key_reused")
            tx = self.store.get_transaction(result.transaction_id)
            if tx is None or not tx.events:
                raise ValueError("resource_conversion_receipt_invalid")
            payload = tx.events[0].payload
            self._validate_current_command(command, payload, rule, binding.binding.binding_id, binding_revision)
            if payload.get("source_projection_revision") != command.expected_projection_revision:
                raise ValueError("resource_conversion_idempotency_key_reused")
            self._verify_receipt(result, payload, stream, command)
            return result.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True)
        if resources.actor_ref != command.actor_ref or resources.projection_revision != command.expected_projection_revision:
            raise ValueError("resource_conversion_projection_conflict")
        canonical = ResourceBodyRuntimeProjector().rebuild_resources(command.actor_ref, self.store.read_stream(stream))
        if canonical != resources or canonical.projection_revision != command.expected_projection_revision:
            raise ValueError("resource_conversion_projection_not_canonical")
        if self.store.get_stream_head(stream) != resources.source_revision_vector.get(stream, 0):
            raise ValueError("resource_conversion_source_revision_conflict")
        input_entry = resources.entries.get(rule.input_resource_id)
        output_entry = resources.entries.get(rule.output_resource_id)
        if input_entry is None or output_entry is None:
            raise ValueError("resource_conversion_resource_missing")
        # ResourceEntry.available already excludes reservations; lock is a
        # lifecycle facet of a reservation and must not be subtracted twice.
        if input_entry.available < -input_delta:
            raise ValueError("resource_conversion_insufficient_available")
        if output_entry.current + output_delta > output_entry.maximum or (output_entry.capacity is not None and output_entry.current + output_delta > output_entry.capacity):
            raise ValueError("resource_conversion_output_capacity_exceeded")
        batch = build_multi_stream_atomic_event_batch(
            command_id=command.command_id, principal_ref=PRINCIPAL,
            expected_revisions={stream: resources.source_revision_vector.get(stream, 0)},
            event_specs={stream: [("gameplay.resource.converted", payload)]}, idempotency_key=key,
            causation_id=command.causation_id, correlation_id=command.correlation_id,
            read_stream_revisions={stream: resources.source_revision_vector.get(stream, 0)},
            pinned_revisions={f"resource-conversion-policy:{rule.revision}": 1, f"resource-conversion-digest:{rule.policy_digest}": 1},
            event_visibility_policies={stream: ["authority_only"]})
        self._revalidate(command, connection_ref, rule, binding.binding.binding_id, binding_revision)
        guarded_store = _RevalidatingStore(self.store, lambda: self._revalidate(
            command, connection_ref, rule, binding.binding.binding_id, binding_revision))
        result = guarded_store.append_batch(batch)
        if result.committed:
            self._verify_receipt(result, payload, stream, command)
        return result

    def _validate_current_command(self, command, payload, rule, binding_id, binding_revision):
        expected = {"actor_ref": command.actor_ref, "world_ref": command.world_ref, "timeline_ref": command.timeline_ref,
                    "rule_id": rule.rule_id, "policy_revision": rule.revision, "policy_digest": rule.policy_digest,
                    "input_resource_id": rule.input_resource_id, "output_resource_id": rule.output_resource_id,
                    "input_delta": -rule.input_amount * command.units, "output_delta": rule.output_amount * command.units,
                    "input_amount_per_unit": rule.input_amount, "output_amount_per_unit": rule.output_amount,
                    "units": command.units, "binding_id": binding_id, "binding_revision": binding_revision,
                    "request_command_id": command.command_id, "request_causation_id": command.causation_id,
                    "request_correlation_id": command.correlation_id}
        if any(payload.get(key) != value for key, value in expected.items()):
            raise ValueError("resource_conversion_idempotency_key_reused")

    def _revalidate(self, command, connection_ref, rule, binding_id, binding_revision):
        binding = self.auth.resolve_controller_binding(actor_id=command.actor_ref, connection_ref=connection_ref)
        if not binding.accepted or binding.binding is None or binding.binding.binding_id != binding_id:
            raise ValueError(binding.error_code or "resource_conversion_controller_binding_changed")
        if self.capability_resolver is None or not self.capability_resolver(binding.binding.authenticated_principal_ref, command.actor_ref, command.policy_revision):
            raise ValueError("resource_conversion_capability_revoked")
        current = self.binding_revision_resolver(connection_ref) if self.binding_revision_resolver else binding.binding.binding_id
        if current != binding_revision:
            raise ValueError("resource_conversion_binding_revision_conflict")
        scope = self.scope_resolver()
        if scope is None or (scope.world_ref, scope.timeline_ref) != (command.world_ref, command.timeline_ref):
            raise ValueError("resource_conversion_scope_conflict")
        if self._rule(command) != rule:
            raise ValueError("resource_conversion_policy_changed")

    def _rule(self, command: ResourceConversionCommand) -> ConversionRule:
        rules = tuple(self.policy_source())
        if rules != self.admitted_policy:
            raise ValueError("resource_conversion_policy_source_changed")
        matches = [r for r in rules if r.rule_id == command.rule_id and r.revision == command.policy_revision and r.policy_digest == command.policy_digest]
        if len(matches) != 1:
            raise ValueError("resource_conversion_policy_pin_invalid")
        rule = matches[0]
        if (command.actor_ref, command.world_ref, command.timeline_ref) != (rule.actor_ref, rule.world_ref, rule.timeline_ref):
            raise ValueError("resource_conversion_policy_scope_denied")
        if min(rule.input_amount, rule.output_amount) <= 0 or rule.input_resource_id == rule.output_resource_id:
            raise ValueError("resource_conversion_policy_invalid")
        return rule

    def _verify_receipt(self, result, payload, stream, command):
        tx = self.store.get_transaction(result.transaction_id)
        if (not result.committed or tx is None or tx.idempotency_record.principal_ref != PRINCIPAL
                or tx.command_id != command.command_id or tx.transaction_id != result.transaction_id
                or tx.idempotency_record.idempotency_key != f"{command.actor_ref}:{command.idempotency_key}"
                or tx.idempotency_record.payload_digest != tx.result_digest
                or result.committed_event_ids != [e.event_id for e in tx.events] or len(tx.events) != 1
                or not self.store.transaction_owns_event(transaction_id=tx.transaction_id,
                    event_id=tx.events[0].event_id, principal_ref=PRINCIPAL)):
            raise ValueError("resource_conversion_receipt_invalid")
        event = tx.events[0]
        if (self.store.get_event(event.event_id) != event or event.event_type != "gameplay.resource.converted"
                or event.stream_id != stream or event.payload != payload or event.visibility_policy != "authority_only"
                or event.command_id != command.command_id or event.transaction_id != tx.transaction_id
                or event.payload.get("request_causation_id") != command.causation_id
                or event.payload.get("request_correlation_id") != command.correlation_id
                or result.resulting_stream_revisions != {stream: event.stream_revision}
                or result.global_sequence_range != (event.global_sequence, event.global_sequence)
                or tx.pinned_revisions.get(f"resource-conversion-policy:{event.payload.get('policy_revision')}") != 1
                or tx.pinned_revisions.get(f"resource-conversion-digest:{event.payload.get('policy_digest')}") != 1):
            raise ValueError("resource_conversion_receipt_invalid")


__all__ = ["ConversionRule", "ConversionWorldScope", "ResourceConversionCommand", "ResourceConversionService", "load_conversion_rules"]
