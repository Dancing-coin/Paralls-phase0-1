from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .capability_envelope import CapabilityEnvelope, PlanningHorizon


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


Effort = Literal["low", "medium", "high", "deep", "unsupported", "disabled"]


class MemoryBudget(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    recall_limit: int = Field(ge=0)
    token_budget: int = Field(ge=0)


class ReasoningBudget(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    l2_max_tokens: int = Field(ge=0)
    l3_max_tokens: int = Field(ge=0)
    max_active_hypotheses: int = Field(ge=0)
    max_reasoning_hops: int = Field(ge=0)
    max_candidate_intents: int = Field(ge=0)
    planning_horizon: PlanningHorizon


class DialogueBudget(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    max_tokens: int = Field(ge=0)
    explanation_depth: str = Field(min_length=1)


class CognitionPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    policy_id: str = Field(min_length=1)
    actor_id: str = Field(min_length=1)
    turn_id: str = Field(min_length=1)
    tier: Literal["fast", "balanced", "deep"]
    provider_thinking_effort: Effort
    memory: MemoryBudget
    reasoning: ReasoningBudget
    dialogue: DialogueBudget
    reasons: tuple[str, ...] = ()
    source_refs: tuple[str, ...] = ()
    revision_pins: dict[str, str] = Field(default_factory=dict)
    envelope_digest: str = Field(min_length=1)
    policy_digest: str = ""

    @model_validator(mode="after")
    def _freeze_digest(self) -> "CognitionPolicy":
        expected = self.compute_digest()
        if self.policy_digest and self.policy_digest != expected:
            raise ValueError("cognition_policy_digest_mismatch")
        object.__setattr__(self, "policy_digest", expected)
        return self

    def compute_digest(self) -> str:
        return _digest(self.model_dump(mode="json", exclude={"policy_digest"}))

    def validate_envelope(
        self, envelope: CapabilityEnvelope, *, actor_id: str, turn_id: str,
        turn_actor_id: str, policy_revision: str, source_event_ref: str,
    ) -> None:
        if self.actor_id != actor_id or envelope.actor_id != actor_id or turn_actor_id != actor_id:
            raise ValueError("cognition_contract_actor_mismatch")
        if self.turn_id != turn_id or envelope.turn_id != turn_id:
            raise ValueError("cognition_contract_turn_mismatch")
        if envelope.revision_pins.get("policy_revision") != policy_revision:
            raise ValueError("cognition_contract_policy_revision_mismatch")
        if source_event_ref not in envelope.source_refs:
            raise ValueError("cognition_contract_source_mismatch")
        expected_pins = {"envelope_revision": envelope.envelope_revision,
                         "envelope_digest": envelope.envelope_digest, **envelope.revision_pins}
        if self.envelope_digest != envelope.envelope_digest or self.revision_pins != expected_pins:
            raise ValueError("cognition_contract_pin_mismatch")

    def clamp_request(self, request: Mapping[str, Any]) -> dict[str, Any]:
        """Clamp model supplied budgets while retaining a diagnostic-friendly shape."""
        result = dict(request)
        reasoning = dict(result.get("reasoning") or {})
        reasoning["max_active_hypotheses"] = min(int(reasoning.get("max_active_hypotheses", self.reasoning.max_active_hypotheses)), self.reasoning.max_active_hypotheses)
        reasoning["max_reasoning_hops"] = min(int(reasoning.get("max_reasoning_hops", self.reasoning.max_reasoning_hops)), self.reasoning.max_reasoning_hops)
        reasoning["max_candidate_intents"] = min(int(reasoning.get("max_candidate_intents", self.reasoning.max_candidate_intents)), self.reasoning.max_candidate_intents)
        reasoning["l2_max_tokens"] = min(int(reasoning.get("l2_max_tokens", self.reasoning.l2_max_tokens)), self.reasoning.l2_max_tokens)
        reasoning["l3_max_tokens"] = min(int(reasoning.get("l3_max_tokens", self.reasoning.l3_max_tokens)), self.reasoning.l3_max_tokens)
        result["reasoning"] = reasoning
        memory = dict(result.get("memory") or {})
        memory["recall_limit"] = min(int(memory.get("recall_limit", self.memory.recall_limit)), self.memory.recall_limit)
        memory["token_budget"] = min(int(memory.get("token_budget", self.memory.token_budget)), self.memory.token_budget)
        result["memory"] = memory
        dialogue = dict(result.get("dialogue") or {})
        dialogue["max_tokens"] = min(int(dialogue.get("max_tokens", self.dialogue.max_tokens)), self.dialogue.max_tokens)
        result["dialogue"] = dialogue
        return result

    @classmethod
    def resolve(
        cls,
        *,
        envelope: CapabilityEnvelope,
        requested_tier: str | None = None,
        requested_effort: str | None = None,
        event_complexity: Mapping[str, float] | None = None,
        profile: Mapping[str, Any] | BaseModel | None = None,
        provider_support: bool = True,
        policy_id: str | None = None,
        source_refs: tuple[str, ...] | list[str] = (),
    ) -> "CognitionPolicy":
        p = profile.model_dump(mode="json") if isinstance(profile, BaseModel) else dict(profile or {})
        layer = p.get("cognitive_capability_layer") or {}
        compute = dict(layer.get("compute_defaults") or {})
        complexity = dict(event_complexity or {})
        score = sum(float(complexity.get(key, 0.0)) * weight for key, weight in {
            "ambiguity": .20, "risk": .20, "goal_conflict": .15,
            "actor_count": .15, "domain_crossing": .15, "causal_distance": .15,
        }.items())
        tier = requested_tier if requested_tier in {"fast", "balanced", "deep"} else ("fast" if score < .33 else "balanced" if score < .66 else "deep")
        reasons = [f"event_complexity:{tier}"]
        if score >= .66:
            reasons.append("high_complexity")
        preferred = str(compute.get("preferred_effort", "balanced"))
        maximum = str(compute.get("maximum_effort", "deep"))
        levels = {"low": 0, "medium": 1, "high": 2, "deep": 3}
        requested = requested_effort or preferred
        if requested not in levels:
            requested = "medium"
            reasons.append("unknown_requested_effort")
        max_level = levels.get(maximum, 3)
        actual = min(levels[requested], max_level)
        minimum = {"fast": 0, "balanced": 1, "deep": 2}[tier]
        # A high-complexity event may request deep work, but the authored
        # maximum still wins. Keep the tier as a diagnostic of demand while
        # recording the clamped provider effort.
        if maximum in levels and levels[maximum] < minimum:
            reasons.append("tier_effort_clamped_by_profile")
        actual = min(max(actual, minimum), max_level)
        effort: Effort = ("low", "medium", "high", "deep")[actual]
        if not provider_support:
            effort = "unsupported"
            reasons.append("provider_thinking_effort_unsupported")
        defaults = {
            "fast": (4, 500, 700, 120),
            "balanced": (6, 550, 900, 160),
            "deep": (10, 800, 1200, 220),
        }
        recall, l2, l3, dialogue = defaults[tier]
        limits = envelope.cognitive_limits
        memory = MemoryBudget(recall_limit=min(int(compute.get("memory_recall_limit", recall)), limits.max_context_items), token_budget=int(compute.get("memory_token_budget", recall * 120)))
        reasoning = ReasoningBudget(
            l2_max_tokens=min(int(compute.get("l2_max_tokens", l2)), l2),
            l3_max_tokens=min(int(compute.get("l3_max_tokens", l3)), l3),
            max_active_hypotheses=limits.max_active_hypotheses,
            max_reasoning_hops=limits.max_reasoning_hops,
            max_candidate_intents=limits.max_candidate_intents,
            planning_horizon=limits.planning_horizon,
        )
        dialog = DialogueBudget(max_tokens=int(compute.get("dialogue_max_tokens", dialogue)), explanation_depth=str((layer.get("expression_constraints") or {}).get("explanation_depth", "concrete")))
        pins = {"envelope_revision": envelope.envelope_revision, "envelope_digest": envelope.envelope_digest, **envelope.revision_pins}
        return cls(
            policy_id=policy_id or f"cognition-policy:{envelope.actor_id}:{envelope.turn_id}", actor_id=envelope.actor_id, turn_id=envelope.turn_id,
            tier=tier, provider_thinking_effort=effort, memory=memory, reasoning=reasoning, dialogue=dialog,
            reasons=tuple(dict.fromkeys(reasons)), source_refs=tuple(dict.fromkeys((*envelope.source_refs, *source_refs))),
            revision_pins=pins, envelope_digest=envelope.envelope_digest,
        )

    compile = resolve


__all__ = ["CognitionPolicy", "DialogueBudget", "MemoryBudget", "ReasoningBudget"]
