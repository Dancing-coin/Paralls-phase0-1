"""Narrow authority settlement adapter for deterministic Gameplay patch rules.

The first adapter accepts only resource-consumption proposals. Rule evaluation
remains proposal-only; this service revalidates authority pins and resource
state before it appends domain events.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pydantic import ConfigDict, Field

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import AppendBatchResult, StrictGameplayModel
from app.gameplay.patch_runtime import (
    EffectProposal,
    GameplayPatchRegistry,
    GameplayPatchRuntimeError,
    GameplayRuleEvaluator,
    RuleEvaluationRequest,
)
from app.gameplay.resource_body_runtime import ResourceStateProjection


class GameplayPatchRuleSettlementError(ValueError):
    """A patch proposal cannot enter the Gameplay authority ledger."""


class PatchRuleSettlementContext(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    authority_principal: str = Field(min_length=1)
    enabled_group_ids: tuple[str, ...] = ()
    world_config_revision: str = Field(min_length=1)
    policy_revision: str = Field(min_length=1)


class PatchRuleSettlementCommand(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    command_id: str = Field(min_length=1)
    actor_ref: str = Field(min_length=1)
    authority_principal: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    payload_digest: str = Field(min_length=1)
    causation_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
    trigger: str = Field(min_length=1)
    authority_tick: int = Field(ge=0)
    pinned_registry_revision: str = Field(min_length=1)
    pinned_active_patch_set_revision: str = Field(min_length=1)
    projection_inputs: dict[str, object] = Field(default_factory=dict)


class _ResourceConsumeEffect(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    actor_ref: str = Field(min_length=1)
    resource_id: str = Field(min_length=1)
    amount: int = Field(gt=0)


@dataclass(frozen=True)
class GameplayPatchRuleSettlementResult:
    accepted: bool
    changed: bool
    evaluation_output_digest: str
    append_result: AppendBatchResult | None = None


class GameplayPatchRuleSettlementService:
    """Maps a constrained proposal set to one atomic resource authority batch."""

    _PRINCIPAL = "gameplay_patch_rule_settlement_authority"

    def __init__(
        self,
        *,
        store: GameplayEventStore,
        patch_registry: GameplayPatchRegistry,
        evaluator: GameplayRuleEvaluator,
    ) -> None:
        self._store = store
        self._patch_registry = patch_registry
        self._evaluator = evaluator

    def evaluate_and_settle(
        self,
        command: PatchRuleSettlementCommand,
        *,
        context: PatchRuleSettlementContext,
        resources: ResourceStateProjection,
    ) -> GameplayPatchRuleSettlementResult:
        self._validate_command(command, context, resources)
        key = f"{command.actor_ref}:{command.idempotency_key}"
        existing = self._store.get_idempotency_record(self._PRINCIPAL, key)
        if existing is not None:
            if existing.payload_digest != command.payload_digest:
                raise GameplayPatchRuleSettlementError("idempotency_key_reused")
            result = self._store.get_by_idempotency(self._PRINCIPAL, key)
            assert result is not None
            return GameplayPatchRuleSettlementResult(True, False, "duplicate_replayed", result)

        request = RuleEvaluationRequest(
            evaluation_id=f"evaluation:{command.command_id}",
            trigger=command.trigger,
            authority_tick=command.authority_tick,
            pinned_registry_revision=command.pinned_registry_revision,
            pinned_active_patch_set_revision=command.pinned_active_patch_set_revision,
            projection_inputs=command.projection_inputs,
        )
        try:
            evaluation = self._evaluator.evaluate(request)
        except GameplayPatchRuntimeError as exc:
            raise GameplayPatchRuleSettlementError(str(exc)) from exc
        if not evaluation.effect_proposals:
            return GameplayPatchRuleSettlementResult(True, False, evaluation.output_digest)

        effects = self._resource_effects(evaluation.effect_proposals, command.actor_ref)
        self._validate_resources(effects, resources)
        append_result = self._append(command, context, effects, evaluation.output_digest, evaluation.matched_rule_refs)
        if not append_result.committed:
            raise GameplayPatchRuleSettlementError(
                append_result.failure.error_code if append_result.failure is not None else "patch_rule_settlement_failed"
            )
        return GameplayPatchRuleSettlementResult(True, True, evaluation.output_digest, append_result)

    def _validate_command(
        self,
        command: PatchRuleSettlementCommand,
        context: PatchRuleSettlementContext,
        resources: ResourceStateProjection,
    ) -> None:
        if command.authority_principal != context.authority_principal:
            raise GameplayPatchRuleSettlementError("authority_principal_mismatch")
        if "core.resources" not in context.enabled_group_ids:
            raise GameplayPatchRuleSettlementError("state_group_not_enabled")
        if resources.actor_ref != command.actor_ref:
            raise GameplayPatchRuleSettlementError("actor_ref_mismatch")
        resource_stream = _resource_stream(command.actor_ref)
        if resources.source_revision_vector.get(resource_stream, 0) != self._store.get_stream_head(resource_stream):
            raise GameplayPatchRuleSettlementError("state_revision_conflict")
        if command.pinned_registry_revision != self._patch_registry.registry_revision:
            raise GameplayPatchRuleSettlementError("patch_registry_revision_conflict")
        active = self._patch_registry.active_patch_set
        if active is None or command.pinned_active_patch_set_revision != active.active_patch_set_revision:
            raise GameplayPatchRuleSettlementError("patch_active_set_revision_conflict")
        payload = {
            "command_id": command.command_id,
            "actor_ref": command.actor_ref,
            "authority_principal": command.authority_principal,
            "idempotency_key": command.idempotency_key,
            "causation_id": command.causation_id,
            "correlation_id": command.correlation_id,
            "trigger": command.trigger,
            "authority_tick": command.authority_tick,
            "pinned_registry_revision": command.pinned_registry_revision,
            "pinned_active_patch_set_revision": command.pinned_active_patch_set_revision,
            "projection_inputs": command.projection_inputs,
        }
        if command.payload_digest != _digest(payload):
            raise GameplayPatchRuleSettlementError("patch_command_digest_mismatch")

    @staticmethod
    def _resource_effects(proposals: tuple[EffectProposal, ...], actor_ref: str) -> tuple[_ResourceConsumeEffect, ...]:
        effects = []
        for proposal in proposals:
            if proposal.effect_type != "resource.consume":
                raise GameplayPatchRuleSettlementError("patch_effect_type_not_settleable")
            try:
                effect = _ResourceConsumeEffect.model_validate(dict(proposal.payload))
            except ValueError as exc:
                raise GameplayPatchRuleSettlementError("resource_consume_effect_invalid") from exc
            if effect.actor_ref != actor_ref:
                raise GameplayPatchRuleSettlementError("effect_actor_mismatch")
            effects.append(effect)
        return tuple(effects)

    @staticmethod
    def _validate_resources(effects: tuple[_ResourceConsumeEffect, ...], resources: ResourceStateProjection) -> None:
        totals: dict[str, int] = {}
        for effect in effects:
            totals[effect.resource_id] = totals.get(effect.resource_id, 0) + effect.amount
        for resource_id, amount in totals.items():
            entry = resources.entries.get(resource_id)
            if entry is None:
                raise GameplayPatchRuleSettlementError("resource_not_registered")
            if entry.available < amount:
                raise GameplayPatchRuleSettlementError("resource_insufficient")

    def _append(
        self,
        command: PatchRuleSettlementCommand,
        context: PatchRuleSettlementContext,
        effects: tuple[_ResourceConsumeEffect, ...],
        evaluation_output_digest: str,
        matched_rule_refs: tuple[str, ...],
    ) -> AppendBatchResult:
        resource_stream = _resource_stream(command.actor_ref)
        settlement_stream = _settlement_stream(command.actor_ref)
        transaction_id = f"tx:{command.command_id}"
        events: list[dict[str, object]] = []
        for index, effect in enumerate(effects, start=1):
            events.append(
                _event(
                    command,
                    transaction_id,
                    resource_stream,
                    f"evt:{command.command_id}:patch-rule:{index}",
                    "gameplay.resource.adjusted",
                    {
                        "actor_ref": command.actor_ref,
                        "resource_id": effect.resource_id,
                        "delta": -effect.amount,
                        "reason_ref": "patch_rule",
                    },
                )
            )
        events.append(
            _event(
                command,
                transaction_id,
                settlement_stream,
                f"evt:{command.command_id}:patch-rule:settled",
                "gameplay.patch.rule_settled",
                {
                    "actor_ref": command.actor_ref,
                    "registry_revision": command.pinned_registry_revision,
                    "active_patch_set_revision": command.pinned_active_patch_set_revision,
                    "world_config_revision": context.world_config_revision,
                    "policy_revision": context.policy_revision,
                    "evaluation_output_digest": evaluation_output_digest,
                    "matched_rule_refs": list(matched_rule_refs),
                    "settled_effect_types": ["resource.consume" for _ in effects],
                },
            )
        )
        return self._store.append_batch(
            {
                "transaction_id": transaction_id,
                "command_id": command.command_id,
                "expected_stream_revisions": {
                    resource_stream: self._store.get_stream_head(resource_stream),
                    settlement_stream: self._store.get_stream_head(settlement_stream),
                },
                "pinned_revisions": {"resource": self._store.get_stream_head(resource_stream)},
                "events": events,
                "idempotency_record": {
                    "principal_ref": self._PRINCIPAL,
                    "idempotency_key": f"{command.actor_ref}:{command.idempotency_key}",
                    "payload_digest": command.payload_digest,
                },
                "outbox_entries": [],
                "result_digest": _digest(
                    {"evaluation_output_digest": evaluation_output_digest, "effects": [effect.model_dump() for effect in effects]}
                ),
                "projection_refresh_hints": [],
            }
        )


def _event(
    command: PatchRuleSettlementCommand,
    transaction_id: str,
    stream_id: str,
    event_id: str,
    event_type: str,
    payload: dict[str, object],
) -> dict[str, object]:
    return {
        "event_id": event_id,
        "event_type": event_type,
        "schema_version": 1,
        "stream_id": stream_id,
        "stream_revision": 0,
        "global_sequence": 0,
        "transaction_id": transaction_id,
        "command_id": command.command_id,
        "causation_id": command.causation_id,
        "correlation_id": command.correlation_id,
        "visibility_policy": "authority_only",
        "payload": payload,
    }


def _resource_stream(actor_ref: str) -> str:
    return f"gameplay:resources:{actor_ref}"


def _settlement_stream(actor_ref: str) -> str:
    return f"gameplay:patch_rule_settlements:{actor_ref}"


def _digest(payload: object) -> str:
    encoded = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{sha256(encoded).hexdigest()}"


__all__ = [
    "GameplayPatchRuleSettlementError",
    "GameplayPatchRuleSettlementResult",
    "GameplayPatchRuleSettlementService",
    "PatchRuleSettlementCommand",
    "PatchRuleSettlementContext",
]
