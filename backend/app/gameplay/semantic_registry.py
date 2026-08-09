from __future__ import annotations

from hashlib import sha256
import json
from typing import Any

from pydantic import ConfigDict, Field, model_validator

from app.gameplay.models import StrictGameplayModel
from app.gameplay.shared_contracts import (
    ActionIntent,
    EffectProposal,
    SemanticDefinition,
    SemanticSnapshot,
)


def _stable_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _stable_digest(value: object) -> str:
    return f"sha256:{sha256(_stable_json(value).encode('utf-8')).hexdigest()}"


class SemanticRegistryError(ValueError):
    pass


class MetaRuleDefinition(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    rule_ref: str = Field(min_length=1)
    rule_version: str = Field(min_length=1)
    trigger_selectors: tuple[str, ...] = Field(min_length=1)
    guard_expression: str = Field(min_length=1)
    phase: str = Field(min_length=1)
    priority: int
    conflict_policy: str = Field(min_length=1)
    evaluation_budget: int = Field(gt=0)
    proposal_templates: tuple[EffectProposal, ...] = Field(default_factory=tuple)
    trace_policy: str = Field(min_length=1)
    source_revision: str = Field(min_length=1)

    @model_validator(mode="after")
    def _unique_selectors(self) -> "MetaRuleDefinition":
        if len(set(self.trigger_selectors)) != len(self.trigger_selectors):
            raise ValueError("semantic_rule_trigger_selector_duplicate")
        return self


class RuleEvaluationInput(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    trigger_ref: str = Field(min_length=1)
    semantic_snapshot: SemanticSnapshot
    causal_event_ref: str | None = None
    action_intent: ActionIntent | None = None
    pinned_revisions: dict[str, int] = Field(default_factory=dict)
    explicit_time_inputs: dict[str, object] = Field(default_factory=dict)
    evidence_refs: tuple[str, ...] = Field(default_factory=tuple)


class RuleEvaluationTrace(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    evaluation_id: str = Field(min_length=1)
    rule_refs: tuple[str, ...] = Field(default_factory=tuple)
    matched_selectors: tuple[str, ...] = Field(default_factory=tuple)
    guard_results: dict[str, bool] = Field(default_factory=dict)
    conflict_decisions: dict[str, str] = Field(default_factory=dict)
    budget_usage: dict[str, int] = Field(default_factory=dict)
    proposal_digests: tuple[str, ...] = Field(default_factory=tuple)
    explanation_visibility: str = Field(min_length=1)
    input_digest: str = Field(min_length=1)
    output_digest: str = Field(min_length=1)


class SemanticRegistry:
    """Revisioned semantic declarations and deterministic rule-trace evaluation."""

    def __init__(self) -> None:
        self._definitions: dict[str, SemanticDefinition] = {}
        self._rules: dict[str, MetaRuleDefinition] = {}

    def register(self, definition: SemanticDefinition) -> None:
        existing = self._definitions.get(definition.semantic_id)
        if existing is not None:
            if existing.namespace != definition.namespace:
                raise SemanticRegistryError("semantic_namespace_collision")
            if existing != definition:
                raise SemanticRegistryError("semantic_definition_conflict")
            raise SemanticRegistryError("semantic_definition_duplicate")
        self._definitions[definition.semantic_id] = definition

    def register_meta_rule(self, definition: MetaRuleDefinition) -> None:
        existing = self._rules.get(definition.rule_ref)
        if existing is not None:
            if existing != definition:
                raise SemanticRegistryError("semantic_meta_rule_conflict")
            raise SemanticRegistryError("semantic_meta_rule_duplicate")
        self._rules[definition.rule_ref] = definition

    def get(self, semantic_id: str) -> SemanticDefinition:
        try:
            return self._definitions[semantic_id]
        except KeyError as exc:
            raise SemanticRegistryError("semantic_definition_unknown") from exc

    def get_meta_rule(self, rule_ref: str) -> MetaRuleDefinition:
        try:
            return self._rules[rule_ref]
        except KeyError as exc:
            raise SemanticRegistryError("semantic_meta_rule_unknown") from exc

    def evaluate(self, evaluation: RuleEvaluationInput) -> RuleEvaluationTrace:
        input_digest = _stable_digest(evaluation.model_dump(mode="json"))
        self._ensure_snapshot_semantics_known(evaluation.semantic_snapshot)
        matched_rules = self._matched_rules(evaluation)
        self._ensure_no_ambiguous_priority(matched_rules)
        budget_usage = {
            "registered_rules": len(self._rules),
            "matched_rules": len(matched_rules),
            "proposal_count": sum(len(rule.proposal_templates) for rule in matched_rules),
        }
        total_budget = sum(rule.evaluation_budget for rule in matched_rules)
        if budget_usage["proposal_count"] > total_budget:
            raise SemanticRegistryError("semantic_evaluation_budget_exhausted")
        guard_results = {rule.rule_ref: self._evaluate_guard(rule.guard_expression) for rule in matched_rules}
        conflict_decisions = {
            rule.rule_ref: (
                "rejected_by_guard"
                if not guard_results[rule.rule_ref]
                else "proposal_only" if rule.proposal_templates else "no_proposal"
            )
            for rule in matched_rules
        }
        matched_selectors = tuple(
            selector
            for rule in matched_rules
            for selector in rule.trigger_selectors
            if self._selector_matches(selector, evaluation)
        )
        proposal_digests = tuple(
            _stable_digest(proposal.model_dump(mode="json"))
            for rule in matched_rules
            if guard_results[rule.rule_ref]
            for proposal in rule.proposal_templates
        )
        explanation_visibility = self._explanation_visibility(matched_rules)
        output_payload = {
            "rule_refs": [rule.rule_ref for rule in matched_rules],
            "matched_selectors": list(matched_selectors),
            "guard_results": guard_results,
            "conflict_decisions": conflict_decisions,
            "budget_usage": budget_usage,
            "proposal_digests": list(proposal_digests),
            "explanation_visibility": explanation_visibility,
            "input_digest": input_digest,
        }
        output_digest = _stable_digest(output_payload)
        return RuleEvaluationTrace(
            evaluation_id=_stable_digest({"input_digest": input_digest, "output_digest": output_digest}),
            rule_refs=tuple(rule.rule_ref for rule in matched_rules),
            matched_selectors=matched_selectors,
            guard_results=guard_results,
            conflict_decisions=conflict_decisions,
            budget_usage=budget_usage,
            proposal_digests=proposal_digests,
            explanation_visibility=explanation_visibility,
            input_digest=input_digest,
            output_digest=output_digest,
        )

    def export_snapshot(self) -> dict[str, Any]:
        return {
            "registry_schema_version": 1,
            "definitions": [
                definition.model_dump(mode="json")
                for definition in sorted(
                    self._definitions.values(),
                    key=lambda item: (item.namespace, item.semantic_id, item.semantic_version),
                )
            ],
            "meta_rules": [
                definition.model_dump(mode="json")
                for definition in sorted(
                    self._rules.values(),
                    key=lambda item: (item.phase, -item.priority, item.rule_ref, item.rule_version),
                )
            ],
        }

    @classmethod
    def from_snapshot(cls, snapshot: object) -> "SemanticRegistry":
        if not isinstance(snapshot, dict) or snapshot.get("registry_schema_version") != 1:
            raise SemanticRegistryError("semantic_registry_snapshot_unsupported")
        definitions = snapshot.get("definitions")
        meta_rules = snapshot.get("meta_rules")
        if not isinstance(definitions, list) or not isinstance(meta_rules, list):
            raise SemanticRegistryError("semantic_registry_snapshot_invalid")
        registry = cls()
        try:
            for value in definitions:
                registry.register(SemanticDefinition.model_validate(value))
            for value in meta_rules:
                registry.register_meta_rule(MetaRuleDefinition.model_validate(value))
        except (TypeError, ValueError, SemanticRegistryError) as exc:
            if isinstance(exc, SemanticRegistryError):
                raise SemanticRegistryError("semantic_registry_snapshot_invalid") from exc
            raise SemanticRegistryError("semantic_registry_snapshot_invalid") from exc
        return registry

    def _ensure_snapshot_semantics_known(self, snapshot: SemanticSnapshot) -> None:
        if not self._definitions:
            return
        unknown = [semantic_id for semantic_id in snapshot.resolved_tags if semantic_id not in self._definitions]
        if unknown:
            raise SemanticRegistryError("semantic_definition_unknown")

    def _matched_rules(self, evaluation: RuleEvaluationInput) -> list[MetaRuleDefinition]:
        return sorted(
            [
                rule
                for rule in self._rules.values()
                if any(self._selector_matches(selector, evaluation) for selector in rule.trigger_selectors)
            ],
            key=lambda rule: (rule.phase, -rule.priority, rule.rule_ref, rule.rule_version),
        )

    def _ensure_no_ambiguous_priority(self, rules: list[MetaRuleDefinition]) -> None:
        seen: set[tuple[str, int]] = set()
        for rule in rules:
            key = (rule.phase, rule.priority)
            if key in seen:
                raise SemanticRegistryError("semantic_priority_ambiguous")
            seen.add(key)

    @staticmethod
    def _evaluate_guard(guard_expression: str) -> bool:
        normalized = guard_expression.strip().lower()
        if normalized in {"true", "always", "1"}:
            return True
        if normalized in {"false", "never", "0"}:
            return False
        raise SemanticRegistryError("semantic_guard_expression_unsupported")

    @staticmethod
    def _selector_matches(selector: str, evaluation: RuleEvaluationInput) -> bool:
        candidates = {
            evaluation.trigger_ref,
            evaluation.action_intent.action_ref if evaluation.action_intent is not None else None,
        }
        normalized_selector = selector.strip()
        if normalized_selector in candidates:
            return True
        if normalized_selector.endswith(".*"):
            prefix = normalized_selector[:-2]
            return any(isinstance(candidate, str) and candidate.startswith(prefix) for candidate in candidates if candidate is not None)
        return False

    @staticmethod
    def _explanation_visibility(rules: list[MetaRuleDefinition]) -> str:
        if any(rule.trace_policy == "full" for rule in rules):
            return "full"
        if any(rule.trace_policy for rule in rules):
            return "summary"
        return "none"


__all__ = [
    "MetaRuleDefinition",
    "RuleEvaluationInput",
    "RuleEvaluationTrace",
    "SemanticDefinition",
    "SemanticRegistry",
    "SemanticRegistryError",
    "SemanticSnapshot",
]
