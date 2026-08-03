"""Deterministic, read-only effective-stat resolution for gameplay projections."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from hashlib import sha256
import json
from types import MappingProxyType
from typing import Literal, Mapping

from pydantic import ConfigDict, Field

from app.gameplay.models import StrictGameplayModel


ModifierOperation = Literal["additive", "multiplicative", "override", "clamp_min", "clamp_max"]
StackingPolicy = Literal["stack", "highest", "lowest", "exclusive", "replace_same_source"]


class EffectiveStatError(ValueError):
    """Raised when definition-authorized modifiers cannot resolve deterministically."""


class StatBaseline(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    stat_id: str = Field(min_length=1)
    value: Decimal
    source_ref: str = Field(min_length=1)


class StatModifier(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    modifier_id: str = Field(min_length=1)
    stat_id: str = Field(min_length=1)
    operation: ModifierOperation
    value: Decimal
    priority: int = 0
    stacking_key: str = Field(min_length=1)
    stacking_policy: StackingPolicy = "stack"
    source_ref: str = Field(min_length=1)
    source_event_id: str = Field(min_length=1)
    condition_ref: str | None = None


@dataclass(frozen=True)
class EffectiveStatEntry:
    stat_id: str
    baseline: Decimal
    effective_value: Decimal
    accepted_modifier_ids: tuple[str, ...]
    rejected_modifier_reasons: Mapping[str, str]
    explanation_digest: str


class EffectiveStatResolver:
    """Resolves known modifiers; callers own their source lifecycle and conditions."""

    def resolve(
        self,
        baseline: StatBaseline,
        modifiers: list[StatModifier],
        *,
        active_condition_refs: tuple[str, ...] = (),
    ) -> EffectiveStatEntry:
        if any(modifier.stat_id != baseline.stat_id for modifier in modifiers):
            raise EffectiveStatError("modifier_stat_mismatch")
        accepted, rejected = self._filter(modifiers, active_condition_refs)
        value = baseline.value
        for modifier in accepted:
            if modifier.operation == "additive":
                value += modifier.value
        for modifier in accepted:
            if modifier.operation == "multiplicative":
                value *= modifier.value
        overrides = [modifier for modifier in accepted if modifier.operation == "override"]
        if len(overrides) > 1:
            raise EffectiveStatError("modifier_conflict_unresolved")
        if overrides:
            value = overrides[0].value
        for modifier in accepted:
            if modifier.operation == "clamp_min":
                value = max(value, modifier.value)
            elif modifier.operation == "clamp_max":
                value = min(value, modifier.value)
        accepted_ids = tuple(modifier.modifier_id for modifier in accepted)
        explanation = {
            "stat_id": baseline.stat_id,
            "baseline": str(baseline.value),
            "effective_value": str(value),
            "accepted_modifier_ids": accepted_ids,
            "rejected_modifier_reasons": dict(rejected),
        }
        return EffectiveStatEntry(
            stat_id=baseline.stat_id,
            baseline=baseline.value,
            effective_value=value,
            accepted_modifier_ids=accepted_ids,
            rejected_modifier_reasons=MappingProxyType(dict(sorted(rejected.items()))),
            explanation_digest="sha256:" + sha256(
                json.dumps(explanation, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ).hexdigest(),
        )

    @staticmethod
    def _filter(
        modifiers: list[StatModifier], active_condition_refs: tuple[str, ...]
    ) -> tuple[list[StatModifier], dict[str, str]]:
        active_conditions = set(active_condition_refs)
        rejected: dict[str, str] = {}
        candidates = []
        for modifier in modifiers:
            if modifier.condition_ref is not None and modifier.condition_ref not in active_conditions:
                rejected[modifier.modifier_id] = "condition_false"
            else:
                candidates.append(modifier)
        grouped: dict[tuple[str, str, str], list[StatModifier]] = {}
        for modifier in candidates:
            grouped.setdefault((modifier.operation, modifier.stacking_key, modifier.stacking_policy), []).append(modifier)
        accepted: list[StatModifier] = []
        for key in sorted(grouped):
            group = sorted(grouped[key], key=lambda item: (item.priority, item.stacking_key, item.source_ref, item.modifier_id))
            policy = key[2]
            if policy == "stack":
                accepted.extend(group)
            elif policy in {"highest", "lowest"}:
                selected = (max if policy == "highest" else min)(group, key=lambda item: (item.value, item.priority, item.modifier_id))
                accepted.append(selected)
                rejected.update({item.modifier_id: "lower_priority" for item in group if item != selected})
            elif policy == "replace_same_source":
                by_source: dict[str, StatModifier] = {}
                for item in group:
                    by_source[item.source_ref] = item
                accepted.extend(by_source.values())
                rejected.update({item.modifier_id: "replaced_same_source" for item in group if item not in by_source.values()})
            elif policy == "exclusive":
                if len(group) != 1:
                    raise EffectiveStatError("modifier_conflict_unresolved")
                accepted.extend(group)
        return sorted(accepted, key=lambda item: (item.priority, item.stacking_key, item.source_ref, item.modifier_id)), rejected


__all__ = ["EffectiveStatEntry", "EffectiveStatError", "EffectiveStatResolver", "StatBaseline", "StatModifier"]
