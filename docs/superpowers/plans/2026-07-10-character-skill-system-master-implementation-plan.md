# Character Skill System Binding Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the Phase 1 binding contract for the Character Skill System master design: typed skill/action/binding models, registry lookup, effective skill state, affordance summaries, skill evaluation, and L4 shadow proposals without changing current gameplay behavior.

**Architecture:** Add a new `backend/app/character_agent/skills/` package. Keep `CharacterSkillService` independent from L4 and ESM. Phase 1 runs in shadow/contract mode: it can build summaries and evaluate action proposals, but it does not gate settlement or replace existing L4 `action_request_bundle`.

**Tech Stack:** Python 3.13, Pydantic v2, pytest, existing `backend/app/character_agent` runtime models, no new dependencies.

---

## Scope Boundary

This plan implements Phase 1 from `docs/superpowers/specs/2026-07-10-character-skill-system-master-design.md`.

Included:

- Typed contracts for skills, actions, bindings, evaluation, primitive plans, learning policy, and evidence.
- In-memory core/scenario registry composition.
- Effective skill state projection from `capability_constraint_layer`.
- Skill affordance summaries for future L3 consumption.
- CharacterSkillService action evaluation.
- L4 shadow `CompositeActionProposal` output that does not alter existing execution payload behavior.

Excluded from this plan:

- Full L3 prompt integration.
- ESM/physical authoritative gating.
- SkillCandidate promotion, LearnedSkillLayer, or automatic skill learning.
- ObservedSkillBelief inference.
- Live Kimodo runtime integration.
- Large production content libraries.

## File Structure

- `backend/app/character_agent/skills/__init__.py`
  - Public exports for the skill system contracts and service.
- `backend/app/character_agent/skills/models.py`
  - Pydantic contracts: definitions, states, proposals, evaluation results, settlement result shape, learning policy, and evidence.
- `backend/app/character_agent/skills/registry.py`
  - In-memory registry for core/scenario `SkillDefinition`, `ActionDefinition`, and `SkillActionBinding`.
- `backend/app/character_agent/skills/service.py`
  - `CharacterSkillService`, effective skill state projection, affordance summary, and action evaluation.
- `backend/app/character_agent/execution/l4_executor.py`
  - Add a shadow `composite_action_proposal` field to the existing execution plan.
- `backend/tests/test_character_skill_models.py`
  - Contract tests for Pydantic validation and serialization.
- `backend/tests/test_skill_action_binding_registry.py`
  - Registry lookup and overlay tests.
- `backend/tests/test_character_skill_service.py`
  - Effective state, affordance summary, and evaluation tests.
- `backend/tests/test_character_agent_l4_skill_shadow.py`
  - L4 shadow proposal compatibility tests.
- `docs/character/character-mind-core-status.md`
  - Add a status note that Phase 1 skill binding contracts exist in shadow mode.
- `docs/架构/运行时/模块/角色智能体.md`
  - Document the skill system boundary after implementation.

---

### Task 1: Add Skill System Model Contracts

**Files:**
- Create: `backend/app/character_agent/skills/__init__.py`
- Create: `backend/app/character_agent/skills/models.py`
- Test: `backend/tests/test_character_skill_models.py`

- [ ] **Step 1: Write failing model tests**

Create `backend/tests/test_character_skill_models.py`:

```python
import pytest
from pydantic import ValidationError

from app.character_agent.skills.models import (
    ActionDefinition,
    CharacterSkillState,
    CompositeActionProposal,
    PrimitiveActionPlan,
    SkillActionBinding,
    SkillDefinition,
    SkillEvidence,
    SkillEvaluationResult,
    SkillLearningPolicy,
)


def test_skill_definition_tracks_settlement_domains_and_learning_policy() -> None:
    skill = SkillDefinition(
        skill_id="first_aid",
        display_name="First Aid",
        settlement_categories=["cognitive", "tool", "social"],
        domains=["medical", "emergency_response"],
        role_tags=["field_medic"],
        learnability="trained",
        risk_tags=["infection_risk"],
    )

    assert skill.skill_id == "first_aid"
    assert skill.settlement_categories == ["cognitive", "tool", "social"]
    assert skill.learnability == "trained"


def test_action_definition_supports_composite_templates_and_variants() -> None:
    action = ActionDefinition(
        action_id="stabilize_injured_actor",
        kind="composite",
        target_types=["actor"],
        settlement_categories=["cognitive", "physical", "social", "tool"],
        primitive_sequence_templates={
            "first_aid_path": [
                "approach_target",
                "kneel_near_target",
                "inspect_wound",
                "apply_pressure",
                "speak_reassurance",
            ]
        },
        variant_rules=[
            {
                "when": {"outcome_band": "clean_success"},
                "presentation_tags": ["focused_care", "steady_breath"],
                "realization_keys": ["medical_stabilize"],
            }
        ],
    )

    assert action.kind == "composite"
    assert action.primitive_sequence_templates["first_aid_path"][-1] == "speak_reassurance"
    assert action.variant_rules[0]["when"]["outcome_band"] == "clean_success"


def test_skill_action_binding_keeps_eligibility_quality_and_learning_separate() -> None:
    binding = SkillActionBinding(
        binding_id="first_aid_to_stabilize",
        skill_id="first_aid",
        action_id="stabilize_injured_actor",
        skill_path_tags=["medical", "nonviolent", "urgent_care"],
        eligibility={
            "required_rank": "basic",
            "required_world_affordances": ["target.injured"],
            "optional_tools": ["bandage", "clean_cloth"],
        },
        quality={
            "primary_weight": 0.7,
            "supporting_skills": {"triage": 0.2, "emotional_regulation": 0.1},
            "runtime_modifiers": {"stress_load": -0.15, "calm": 0.08},
        },
        learning={
            "evidence_on_attempt": True,
            "evidence_on_blocked": False,
            "evidence_channels": ["improvement", "specialization", "confidence"],
        },
    )

    assert binding.eligibility["required_rank"] == "basic"
    assert binding.quality["supporting_skills"]["triage"] == 0.2
    assert binding.learning["evidence_on_blocked"] is False


def test_character_skill_state_is_actor_specific_and_source_typed() -> None:
    state = CharacterSkillState(
        actor_id="char_a",
        skill_id="first_aid",
        source="authored",
        rank="trained",
        proficiency=0.65,
        confidence=0.7,
        familiarity={"bleeding_control": 0.4},
        visibility={"player_visible": True, "visible_to_actors": ["char_self"]},
    )

    assert state.actor_id == "char_a"
    assert state.proficiency == 0.65
    assert state.visibility["player_visible"] is True


def test_character_skill_state_rejects_out_of_range_proficiency() -> None:
    with pytest.raises(ValidationError):
        CharacterSkillState(
            actor_id="char_a",
            skill_id="first_aid",
            source="authored",
            rank="trained",
            proficiency=1.2,
        )


def test_evaluation_result_carries_viable_and_blocked_paths() -> None:
    result = SkillEvaluationResult(
        actor_id="char_a",
        action_id="stabilize_injured_actor",
        selected_path={"binding_id": "first_aid_to_stabilize", "skill_id": "first_aid"},
        viable_paths=[
            {
                "binding_id": "first_aid_to_stabilize",
                "skill_id": "first_aid",
                "eligibility_status": "eligible",
                "objective_feasibility": 0.72,
                "character_fit": 0.84,
                "expected_quality": "success_with_cost",
                "risk_estimate": {"infection_risk": "medium"},
            }
        ],
        blocked_paths=[
            {
                "binding_id": "healing_magic_to_stabilize",
                "missing_requirements": ["healing_magic.basic"],
            }
        ],
        recommendation_reason=["matches_nonviolent_strategy"],
        learning_policy_snapshot={"promotion_enabled": False},
    )

    assert result.selected_path["skill_id"] == "first_aid"
    assert result.viable_paths[0]["expected_quality"] == "success_with_cost"
    assert result.blocked_paths[0]["missing_requirements"] == ["healing_magic.basic"]


def test_primitive_action_plan_preserves_selected_skill_path() -> None:
    plan = PrimitiveActionPlan(
        composite_action_id="stabilize_injured_actor",
        skill_path_id="first_aid_to_stabilize",
        primitive_actions=[
            "approach_target",
            "kneel_near_target",
            "inspect_wound",
            "apply_pressure",
            "speak_reassurance",
        ],
        realization_keys=["approach_careful", "kneel_inspect", "apply_pressure", "calm_voice"],
    )

    assert plan.skill_path_id == "first_aid_to_stabilize"
    assert "calm_voice" in plan.realization_keys


def test_skill_learning_policy_defaults_to_no_promotion() -> None:
    policy = SkillLearningPolicy()

    assert policy.evidence_collection_enabled is True
    assert policy.candidate_generation_enabled is True
    assert policy.promotion_enabled is False
    assert policy.auto_promotion_enabled is False


def test_skill_evidence_is_directional_and_context_specific() -> None:
    evidence = SkillEvidence(
        evidence_id="skill_evidence:1",
        actor_id="char_a",
        skill_id="first_aid",
        action_id="stabilize_injured_actor",
        binding_id="first_aid_to_stabilize",
        source_settlement_id="settlement:123",
        outcome_band="partial",
        primary_failure_domain="skill_failure",
        failure_domains=["skill_failure", "state_interference"],
        evidence_channels={
            "acquisition": 0.0,
            "improvement": 0.12,
            "confidence": 0.03,
            "specialization": {"bleeding_control": 0.08},
            "tool_familiarity": {"clean_cloth": 0.04},
            "maladaptive_pattern": {},
        },
        eligible_for_candidate=False,
        eligible_for_promotion=False,
    )

    assert evidence.evidence_channels["improvement"] == 0.12
    assert evidence.evidence_channels["specialization"]["bleeding_control"] == 0.08
```

- [ ] **Step 2: Run model tests and verify they fail**

Run: `pytest backend/tests/test_character_skill_models.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'app.character_agent.skills'`.

- [ ] **Step 3: Create the models package**

Create `backend/app/character_agent/skills/models.py`:

```python
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


SettlementCategory = Literal["cognitive", "social", "physical", "tool", "authority", "special"]
ActionKind = Literal["composite", "primitive"]
Learnability = Literal["natural", "trained", "granted", "locked"]
SkillSource = Literal["authored", "learned", "temporary", "equipment", "authority", "scripted", "constrained"]
SkillRank = Literal["none", "novice", "basic", "trained", "expert", "master", "blocked"]
OutcomeBand = Literal["blocked", "failed", "partial", "success_with_cost", "clean_success", "misfire"]
FailureDomain = Literal[
    "none",
    "skill_failure",
    "missing_requirement",
    "world_constraint",
    "physical_failure",
    "authority_policy_failure",
    "social_resistance",
    "state_interference",
    "tool_failure",
    "knowledge_mismatch",
    "realization_failure",
]


class StrictSkillModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SkillDefinition(StrictSkillModel):
    skill_id: str
    display_name: str = ""
    settlement_categories: list[SettlementCategory] = Field(default_factory=list)
    domains: list[str] = Field(default_factory=list)
    role_tags: list[str] = Field(default_factory=list)
    learnability: Learnability = "natural"
    risk_tags: list[str] = Field(default_factory=list)
    visibility_default: dict[str, object] = Field(default_factory=dict)


class ActionDefinition(StrictSkillModel):
    action_id: str
    kind: ActionKind
    target_types: list[str] = Field(default_factory=list)
    settlement_categories: list[SettlementCategory] = Field(default_factory=list)
    primitive_sequence_templates: dict[str, list[str]] = Field(default_factory=dict)
    variant_rules: list[dict[str, object]] = Field(default_factory=list)
    realization_keys: list[str] = Field(default_factory=list)


class SkillActionBinding(StrictSkillModel):
    binding_id: str
    skill_id: str
    action_id: str
    skill_path_tags: list[str] = Field(default_factory=list)
    eligibility: dict[str, object] = Field(default_factory=dict)
    quality: dict[str, object] = Field(default_factory=dict)
    learning: dict[str, object] = Field(default_factory=dict)


class CharacterSkillState(StrictSkillModel):
    actor_id: str
    skill_id: str
    source: SkillSource
    rank: SkillRank = "none"
    proficiency: float = Field(default=0.0, ge=0.0, le=1.0)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    familiarity: dict[str, float] = Field(default_factory=dict)
    restrictions: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    visibility: dict[str, object] = Field(default_factory=dict)


class SkillAffordanceSummary(StrictSkillModel):
    actor_id: str
    available_action_families: dict[str, dict[str, object]] = Field(default_factory=dict)
    blocked_action_families: dict[str, dict[str, object]] = Field(default_factory=dict)
    notable_constraints: list[str] = Field(default_factory=list)
    recent_skill_feedback: list[str] = Field(default_factory=list)


class CompositeActionProposal(StrictSkillModel):
    proposal_id: str
    actor_id: str
    source_intent: str
    action_id: str
    target_refs: dict[str, str] = Field(default_factory=dict)
    preferred_strategy_tags: list[str] = Field(default_factory=list)
    forbidden_strategy_tags: list[str] = Field(default_factory=list)
    desired_outcomes: list[str] = Field(default_factory=list)


class SkillEvaluationRequest(StrictSkillModel):
    actor_id: str
    action_id: str
    target_refs: dict[str, str] = Field(default_factory=dict)
    preferred_strategy_tags: list[str] = Field(default_factory=list)
    forbidden_strategy_tags: list[str] = Field(default_factory=list)
    dynamic_state: dict[str, object] = Field(default_factory=dict)
    equipment_refs: list[str] = Field(default_factory=list)


class SkillEvaluationResult(StrictSkillModel):
    actor_id: str
    action_id: str
    selected_path: dict[str, object] = Field(default_factory=dict)
    viable_paths: list[dict[str, object]] = Field(default_factory=list)
    blocked_paths: list[dict[str, object]] = Field(default_factory=list)
    recommendation_reason: list[str] = Field(default_factory=list)
    learning_policy_snapshot: dict[str, object] = Field(default_factory=dict)


class PrimitiveActionPlan(StrictSkillModel):
    composite_action_id: str
    skill_path_id: str
    primitive_actions: list[str] = Field(default_factory=list)
    realization_keys: list[str] = Field(default_factory=list)


class ActionSettlementResult(StrictSkillModel):
    outcome_band: OutcomeBand
    failure_domains: list[FailureDomain] = Field(default_factory=list)
    primary_failure_domain: FailureDomain = "none"
    semantic_effects: list[str] = Field(default_factory=list)
    physical_effects: list[str] = Field(default_factory=list)
    social_effects: list[str] = Field(default_factory=list)
    costs: list[str] = Field(default_factory=list)
    realization_hints: list[str] = Field(default_factory=list)


class SkillLearningPolicy(StrictSkillModel):
    evidence_collection_enabled: bool = True
    candidate_generation_enabled: bool = True
    promotion_enabled: bool = False
    auto_promotion_enabled: bool = False
    allowed_domains: list[str] = Field(default_factory=list)
    blocked_domains: list[str] = Field(default_factory=lambda: ["authority", "special"])


class SkillEvidence(StrictSkillModel):
    evidence_id: str
    actor_id: str
    skill_id: str
    action_id: str
    binding_id: str = ""
    source_settlement_id: str
    outcome_band: OutcomeBand
    primary_failure_domain: FailureDomain
    failure_domains: list[FailureDomain] = Field(default_factory=list)
    evidence_channels: dict[str, object] = Field(default_factory=dict)
    eligible_for_candidate: bool = False
    eligible_for_promotion: bool = False
```

Create `backend/app/character_agent/skills/__init__.py`:

```python
from app.character_agent.skills.models import (
    ActionDefinition,
    ActionSettlementResult,
    CharacterSkillState,
    CompositeActionProposal,
    PrimitiveActionPlan,
    SkillActionBinding,
    SkillAffordanceSummary,
    SkillDefinition,
    SkillEvaluationRequest,
    SkillEvaluationResult,
    SkillEvidence,
    SkillLearningPolicy,
)

__all__ = [
    "ActionDefinition",
    "ActionSettlementResult",
    "CharacterSkillState",
    "CompositeActionProposal",
    "PrimitiveActionPlan",
    "SkillActionBinding",
    "SkillAffordanceSummary",
    "SkillDefinition",
    "SkillEvaluationRequest",
    "SkillEvaluationResult",
    "SkillEvidence",
    "SkillLearningPolicy",
]
```

- [ ] **Step 4: Run model tests and verify they pass**

Run: `pytest backend/tests/test_character_skill_models.py -v`

Expected: PASS.

- [ ] **Step 5: Commit Task 1**

```bash
git add backend/app/character_agent/skills/__init__.py backend/app/character_agent/skills/models.py backend/tests/test_character_skill_models.py
git commit -m "Add character skill system model contracts"
```

---

### Task 2: Add Skill/Action/Binding Registry

**Files:**
- Create: `backend/app/character_agent/skills/registry.py`
- Modify: `backend/app/character_agent/skills/__init__.py`
- Test: `backend/tests/test_skill_action_binding_registry.py`

- [ ] **Step 1: Write failing registry tests**

Create `backend/tests/test_skill_action_binding_registry.py`:

```python
from app.character_agent.skills.models import ActionDefinition, SkillActionBinding, SkillDefinition
from app.character_agent.skills.registry import CharacterSkillRegistry


def test_registry_composes_core_and_scenario_definitions() -> None:
    core = CharacterSkillRegistry(
        skills=[
            SkillDefinition(skill_id="first_aid", display_name="First Aid", domains=["medical"]),
        ],
        actions=[
            ActionDefinition(
                action_id="stabilize_injured_actor",
                kind="composite",
                settlement_categories=["cognitive", "physical", "social", "tool"],
            ),
        ],
        bindings=[
            SkillActionBinding(
                binding_id="first_aid_to_stabilize",
                skill_id="first_aid",
                action_id="stabilize_injured_actor",
            )
        ],
    )
    scenario = CharacterSkillRegistry(
        skills=[
            SkillDefinition(skill_id="healing_magic", display_name="Healing Magic", domains=["ritual"]),
        ],
        actions=[],
        bindings=[
            SkillActionBinding(
                binding_id="healing_magic_to_stabilize",
                skill_id="healing_magic",
                action_id="stabilize_injured_actor",
            )
        ],
    )

    composed = CharacterSkillRegistry.compose(core, scenario)

    assert composed.skill("first_aid").display_name == "First Aid"
    assert composed.skill("healing_magic").display_name == "Healing Magic"
    assert len(composed.bindings_for_action("stabilize_injured_actor")) == 2


def test_registry_returns_empty_lists_for_unknown_actions() -> None:
    registry = CharacterSkillRegistry()

    assert registry.bindings_for_action("unknown_action") == []


def test_registry_replaces_duplicate_ids_with_later_layer() -> None:
    core = CharacterSkillRegistry(
        skills=[SkillDefinition(skill_id="persuasion", display_name="Persuasion")],
    )
    scenario = CharacterSkillRegistry(
        skills=[SkillDefinition(skill_id="persuasion", display_name="Court Persuasion")],
    )

    composed = CharacterSkillRegistry.compose(core, scenario)

    assert composed.skill("persuasion").display_name == "Court Persuasion"
```

- [ ] **Step 2: Run registry tests and verify they fail**

Run: `pytest backend/tests/test_skill_action_binding_registry.py -v`

Expected: FAIL with `ModuleNotFoundError` for `app.character_agent.skills.registry`.

- [ ] **Step 3: Implement the registry**

Create `backend/app/character_agent/skills/registry.py`:

```python
from __future__ import annotations

from app.character_agent.skills.models import ActionDefinition, SkillActionBinding, SkillDefinition


class CharacterSkillRegistry:
    def __init__(
        self,
        *,
        skills: list[SkillDefinition] | None = None,
        actions: list[ActionDefinition] | None = None,
        bindings: list[SkillActionBinding] | None = None,
    ) -> None:
        self._skills = {item.skill_id: item for item in skills or []}
        self._actions = {item.action_id: item for item in actions or []}
        self._bindings = {item.binding_id: item for item in bindings or []}

    @classmethod
    def compose(cls, *registries: "CharacterSkillRegistry") -> "CharacterSkillRegistry":
        skills: list[SkillDefinition] = []
        actions: list[ActionDefinition] = []
        bindings: list[SkillActionBinding] = []
        for registry in registries:
            skills.extend(registry._skills.values())
            actions.extend(registry._actions.values())
            bindings.extend(registry._bindings.values())
        return cls(skills=skills, actions=actions, bindings=bindings)

    def skill(self, skill_id: str) -> SkillDefinition:
        return self._skills[skill_id]

    def action(self, action_id: str) -> ActionDefinition:
        return self._actions[action_id]

    def skills(self) -> list[SkillDefinition]:
        return list(self._skills.values())

    def actions(self) -> list[ActionDefinition]:
        return list(self._actions.values())

    def bindings(self) -> list[SkillActionBinding]:
        return list(self._bindings.values())

    def bindings_for_action(self, action_id: str) -> list[SkillActionBinding]:
        return [binding for binding in self._bindings.values() if binding.action_id == action_id]
```

Modify `backend/app/character_agent/skills/__init__.py`:

```python
from app.character_agent.skills.models import (
    ActionDefinition,
    ActionSettlementResult,
    CharacterSkillState,
    CompositeActionProposal,
    PrimitiveActionPlan,
    SkillActionBinding,
    SkillAffordanceSummary,
    SkillDefinition,
    SkillEvaluationRequest,
    SkillEvaluationResult,
    SkillEvidence,
    SkillLearningPolicy,
)
from app.character_agent.skills.registry import CharacterSkillRegistry

__all__ = [
    "ActionDefinition",
    "ActionSettlementResult",
    "CharacterSkillRegistry",
    "CharacterSkillState",
    "CompositeActionProposal",
    "PrimitiveActionPlan",
    "SkillActionBinding",
    "SkillAffordanceSummary",
    "SkillDefinition",
    "SkillEvaluationRequest",
    "SkillEvaluationResult",
    "SkillEvidence",
    "SkillLearningPolicy",
]
```

- [ ] **Step 4: Run registry tests and verify they pass**

Run: `pytest backend/tests/test_skill_action_binding_registry.py -v`

Expected: PASS.

- [ ] **Step 5: Commit Task 2**

```bash
git add backend/app/character_agent/skills/__init__.py backend/app/character_agent/skills/registry.py backend/tests/test_skill_action_binding_registry.py
git commit -m "Add character skill action binding registry"
```

---

### Task 3: Add CharacterSkillService Effective State And Evaluation

**Files:**
- Create: `backend/app/character_agent/skills/service.py`
- Modify: `backend/app/character_agent/skills/__init__.py`
- Test: `backend/tests/test_character_skill_service.py`

- [ ] **Step 1: Write failing service tests**

Create `backend/tests/test_character_skill_service.py`:

```python
from app.character_agent.skills.models import ActionDefinition, SkillActionBinding, SkillDefinition
from app.character_agent.skills.registry import CharacterSkillRegistry
from app.character_agent.skills.service import CharacterSkillService


def _registry() -> CharacterSkillRegistry:
    return CharacterSkillRegistry(
        skills=[
            SkillDefinition(skill_id="first_aid", display_name="First Aid", domains=["medical"]),
            SkillDefinition(skill_id="healing_magic", display_name="Healing Magic", domains=["special"]),
        ],
        actions=[
            ActionDefinition(
                action_id="stabilize_injured_actor",
                kind="composite",
                settlement_categories=["cognitive", "physical", "social", "tool"],
                primitive_sequence_templates={
                    "first_aid_to_stabilize": ["approach_target", "kneel_near_target", "apply_pressure"],
                    "healing_magic_to_stabilize": ["raise_hand", "channel_effect"],
                },
            )
        ],
        bindings=[
            SkillActionBinding(
                binding_id="first_aid_to_stabilize",
                skill_id="first_aid",
                action_id="stabilize_injured_actor",
                skill_path_tags=["medical", "nonviolent"],
                eligibility={"required_rank": "basic"},
            ),
            SkillActionBinding(
                binding_id="healing_magic_to_stabilize",
                skill_id="healing_magic",
                action_id="stabilize_injured_actor",
                skill_path_tags=["special"],
                eligibility={"required_rank": "basic"},
            ),
        ],
    )


def test_service_projects_profile_capabilities_to_initial_skill_state() -> None:
    service = CharacterSkillService(registry=_registry())
    states = service.initial_skill_states(
        actor_id="char_a",
        profile={
            "capability_constraint_layer": {
                "skills": ["first_aid"],
                "knowledge_domains": ["medical"],
                "physical_constraints": [],
                "psychological_constraints": [],
                "social_constraints": [],
            }
        },
    )

    assert states[0].actor_id == "char_a"
    assert states[0].skill_id == "first_aid"
    assert states[0].source == "authored"
    assert states[0].rank == "basic"


def test_service_builds_affordance_summary_without_full_registry_payload() -> None:
    service = CharacterSkillService(registry=_registry())

    summary = service.build_affordance_summary(
        actor_id="char_a",
        skill_states=service.initial_skill_states(
            actor_id="char_a",
            profile={"capability_constraint_layer": {"skills": ["first_aid"]}},
        ),
    )

    assert "medical" in summary.available_action_families
    assert summary.available_action_families["medical"]["level"] == "basic"
    assert "stabilize_injured_actor" in summary.available_action_families["medical"]["examples"]
    assert "special" in summary.blocked_action_families


def test_service_evaluates_viable_and_blocked_skill_paths() -> None:
    service = CharacterSkillService(registry=_registry())
    states = service.initial_skill_states(
        actor_id="char_a",
        profile={"capability_constraint_layer": {"skills": ["first_aid"]}},
    )

    result = service.evaluate_action(
        actor_id="char_a",
        action_id="stabilize_injured_actor",
        skill_states=states,
        preferred_strategy_tags=["nonviolent"],
    )

    assert result.selected_path["binding_id"] == "first_aid_to_stabilize"
    assert result.viable_paths[0]["eligibility_status"] == "eligible"
    assert result.blocked_paths[0]["binding_id"] == "healing_magic_to_stabilize"
    assert result.blocked_paths[0]["missing_requirements"] == ["healing_magic.basic"]


def test_service_expands_primitive_plan_for_selected_skill_path() -> None:
    service = CharacterSkillService(registry=_registry())

    plan = service.expand_primitive_plan(
        action_id="stabilize_injured_actor",
        skill_path_id="first_aid_to_stabilize",
    )

    assert plan.composite_action_id == "stabilize_injured_actor"
    assert plan.primitive_actions == ["approach_target", "kneel_near_target", "apply_pressure"]
```

- [ ] **Step 2: Run service tests and verify they fail**

Run: `pytest backend/tests/test_character_skill_service.py -v`

Expected: FAIL with `ModuleNotFoundError` for `app.character_agent.skills.service`.

- [ ] **Step 3: Implement CharacterSkillService**

Create `backend/app/character_agent/skills/service.py`:

```python
from __future__ import annotations

from app.character_agent.skills.models import (
    CharacterSkillState,
    PrimitiveActionPlan,
    SkillAffordanceSummary,
    SkillEvaluationResult,
)
from app.character_agent.skills.registry import CharacterSkillRegistry


class CharacterSkillService:
    def __init__(self, *, registry: CharacterSkillRegistry | None = None) -> None:
        self._registry = registry or CharacterSkillRegistry()

    def initial_skill_states(self, *, actor_id: str, profile: dict[str, object]) -> list[CharacterSkillState]:
        layer = profile.get("capability_constraint_layer", {})
        if not isinstance(layer, dict):
            return []
        authored_skill_names = {str(item) for item in layer.get("skills", []) if str(item)}
        states: list[CharacterSkillState] = []
        for skill in self._registry.skills():
            if skill.skill_id not in authored_skill_names:
                continue
            states.append(
                CharacterSkillState(
                    actor_id=actor_id,
                    skill_id=skill.skill_id,
                    source="authored",
                    rank="basic",
                    proficiency=0.5,
                    confidence=0.5,
                    visibility=dict(skill.visibility_default),
                )
            )
        return states

    def build_affordance_summary(
        self,
        *,
        actor_id: str,
        skill_states: list[CharacterSkillState],
    ) -> SkillAffordanceSummary:
        owned = {state.skill_id: state for state in skill_states if state.rank != "blocked"}
        available: dict[str, dict[str, object]] = {}
        blocked: dict[str, dict[str, object]] = {}
        for binding in self._registry.bindings():
            skill = self._registry.skill(binding.skill_id)
            family = skill.domains[0] if skill.domains else binding.skill_id
            action_examples = available if binding.skill_id in owned else blocked
            entry = action_examples.setdefault(
                family,
                {
                    "level": owned[binding.skill_id].rank if binding.skill_id in owned else "none",
                    "confidence": "medium" if binding.skill_id in owned else "none",
                    "examples": [],
                },
            )
            examples = entry.get("examples", [])
            if isinstance(examples, list) and binding.action_id not in examples:
                examples.append(binding.action_id)
        return SkillAffordanceSummary(
            actor_id=actor_id,
            available_action_families=available,
            blocked_action_families=blocked,
        )

    def evaluate_action(
        self,
        *,
        actor_id: str,
        action_id: str,
        skill_states: list[CharacterSkillState],
        preferred_strategy_tags: list[str] | None = None,
    ) -> SkillEvaluationResult:
        preferred_tags = set(preferred_strategy_tags or [])
        owned = {state.skill_id: state for state in skill_states if state.rank != "blocked"}
        viable: list[dict[str, object]] = []
        blocked: list[dict[str, object]] = []
        for binding in self._registry.bindings_for_action(action_id):
            if binding.skill_id not in owned:
                blocked.append(
                    {
                        "binding_id": binding.binding_id,
                        "skill_id": binding.skill_id,
                        "missing_requirements": [f"{binding.skill_id}.basic"],
                    }
                )
                continue
            state = owned[binding.skill_id]
            character_fit = 0.5 + (0.3 if preferred_tags.intersection(binding.skill_path_tags) else 0.0)
            viable.append(
                {
                    "binding_id": binding.binding_id,
                    "skill_id": binding.skill_id,
                    "eligibility_status": "eligible",
                    "objective_feasibility": state.proficiency,
                    "character_fit": min(1.0, character_fit),
                    "expected_quality": "success_with_cost" if state.proficiency >= 0.5 else "partial",
                    "risk_estimate": {},
                }
            )
        selected_path = viable[0] if viable else {}
        return SkillEvaluationResult(
            actor_id=actor_id,
            action_id=action_id,
            selected_path={
                "binding_id": selected_path.get("binding_id", ""),
                "skill_id": selected_path.get("skill_id", ""),
            }
            if selected_path
            else {},
            viable_paths=viable,
            blocked_paths=blocked,
            recommendation_reason=["matches_preferred_strategy"] if viable and preferred_tags else [],
            learning_policy_snapshot={"promotion_enabled": False, "auto_promotion_enabled": False},
        )

    def expand_primitive_plan(self, *, action_id: str, skill_path_id: str) -> PrimitiveActionPlan:
        action = self._registry.action(action_id)
        primitive_actions = action.primitive_sequence_templates.get(skill_path_id, [])
        return PrimitiveActionPlan(
            composite_action_id=action_id,
            skill_path_id=skill_path_id,
            primitive_actions=list(primitive_actions),
            realization_keys=list(action.realization_keys),
        )
```

Modify `backend/app/character_agent/skills/__init__.py`:

```python
from app.character_agent.skills.models import (
    ActionDefinition,
    ActionSettlementResult,
    CharacterSkillState,
    CompositeActionProposal,
    PrimitiveActionPlan,
    SkillActionBinding,
    SkillAffordanceSummary,
    SkillDefinition,
    SkillEvaluationRequest,
    SkillEvaluationResult,
    SkillEvidence,
    SkillLearningPolicy,
)
from app.character_agent.skills.registry import CharacterSkillRegistry
from app.character_agent.skills.service import CharacterSkillService

__all__ = [
    "ActionDefinition",
    "ActionSettlementResult",
    "CharacterSkillRegistry",
    "CharacterSkillService",
    "CharacterSkillState",
    "CompositeActionProposal",
    "PrimitiveActionPlan",
    "SkillActionBinding",
    "SkillAffordanceSummary",
    "SkillDefinition",
    "SkillEvaluationRequest",
    "SkillEvaluationResult",
    "SkillEvidence",
    "SkillLearningPolicy",
]
```

- [ ] **Step 4: Run service tests and verify they pass**

Run: `pytest backend/tests/test_character_skill_service.py -v`

Expected: PASS.

- [ ] **Step 5: Commit Task 3**

```bash
git add backend/app/character_agent/skills/__init__.py backend/app/character_agent/skills/service.py backend/tests/test_character_skill_service.py
git commit -m "Add character skill service shadow evaluation"
```

---

### Task 4: Add L4 CompositeActionProposal Shadow Output

**Files:**
- Modify: `backend/app/character_agent/execution/l4_executor.py`
- Test: `backend/tests/test_character_agent_l4_skill_shadow.py`

- [ ] **Step 1: Write failing L4 shadow tests**

Create `backend/tests/test_character_agent_l4_skill_shadow.py`:

```python
from app.character_agent.execution.l4_executor import CharacterAgentL4Executor
from app.character_agent.models.private_world_snapshot import CharacterPrivateWorldSnapshot
from app.models.character_agent_runtime import CharacterIntentDecision, CharacterInterpretation


def _snapshot() -> CharacterPrivateWorldSnapshot:
    return CharacterPrivateWorldSnapshot(
        actor_id="char_a",
        room_id="room_demo",
        visible_entities=[],
        audible_entities=[],
        attention_targets=["char_b"],
        current_focus_target="char_b",
        updated_at=10,
    )


def _interpretation() -> CharacterInterpretation:
    return CharacterInterpretation(
        actor_id="char_a",
        interpreted_summary="char_b is injured and anxious",
        interpretation_type="social_signal",
        salience_score=0.8,
        ambiguity_level="low",
        risk_level="medium",
        opportunity_level="medium",
        attention_target="char_b",
        inner_prompt_candidate="help char_b",
    )


def _decision() -> CharacterIntentDecision:
    return CharacterIntentDecision(
        actor_id="char_a",
        selected_intent="share_info",
        persona_passed=True,
        logic_passed=True,
        gain_loss_passed=True,
        rationale="offer help",
    )


def test_l4_execution_plan_includes_composite_action_proposal_without_changing_existing_bundle() -> None:
    plan = CharacterAgentL4Executor().build_execution_plan(
        snapshot=_snapshot(),
        interpretation=_interpretation(),
        decision=_decision(),
    )

    proposal = plan["composite_action_proposal"]

    assert proposal["actor_id"] == "char_a"
    assert proposal["source_intent"] == "share_info"
    assert proposal["action_id"] == "share_info"
    assert proposal["target_refs"] == {"actor": "char_b"}
    assert "action_request_bundle" in plan
    assert plan["action_request_bundle"]["requested_actions"][0]["request_type"] == "share_info"
```

- [ ] **Step 2: Run L4 shadow test and verify it fails**

Run: `pytest backend/tests/test_character_agent_l4_skill_shadow.py -v`

Expected: FAIL with `KeyError: 'composite_action_proposal'`.

- [ ] **Step 3: Add shadow proposal to L4 output**

Modify `backend/app/character_agent/execution/l4_executor.py`.

Add an import near the top:

```python
from app.character_agent.skills.models import CompositeActionProposal
```

Inside `build_execution_plan`, after `target = ...`, add:

```python
        composite_action_proposal = self._composite_action_proposal(
            actor_id=decision.actor_id,
            selected_intent=decision.selected_intent,
            target=target,
            interpretation=interpretation,
            producer_ts=snapshot.updated_at,
        )
```

Inside the returned dict, add:

```python
            "composite_action_proposal": composite_action_proposal.model_dump(),
```

Add this helper method to `CharacterAgentL4Executor`:

```python
    def _composite_action_proposal(
        self,
        *,
        actor_id: str,
        selected_intent: str,
        target: str,
        interpretation: CharacterInterpretation,
        producer_ts: int,
    ) -> CompositeActionProposal:
        target_refs: dict[str, str] = {}
        if target.startswith("char_"):
            target_refs["actor"] = target
        elif target.startswith("obj_"):
            target_refs["object"] = target
        elif target.startswith("env_"):
            target_refs["environment"] = target
        preferred_strategy_tags: list[str] = []
        if selected_intent in {"share_info", "speak_public", "speak_private"}:
            preferred_strategy_tags.append("social")
        if selected_intent in {"withdraw", "break_contact", "self_protect"}:
            preferred_strategy_tags.append("defensive")
        if interpretation.risk_level in {"medium", "high"}:
            preferred_strategy_tags.append("risk_aware")
        return CompositeActionProposal(
            proposal_id=f"composite_action:{producer_ts}:{actor_id}:{selected_intent}",
            actor_id=actor_id,
            source_intent=selected_intent,
            action_id=selected_intent,
            target_refs=target_refs,
            preferred_strategy_tags=preferred_strategy_tags,
            forbidden_strategy_tags=[],
            desired_outcomes=[interpretation.interpreted_summary] if interpretation.interpreted_summary else [],
        )
```

- [ ] **Step 4: Run L4 shadow test and existing L4 tests**

Run:

```bash
pytest backend/tests/test_character_agent_l4_skill_shadow.py backend/tests/test_character_agent_runtime.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit Task 4**

```bash
git add backend/app/character_agent/execution/l4_executor.py backend/tests/test_character_agent_l4_skill_shadow.py
git commit -m "Add L4 composite action proposal shadow output"
```

---

### Task 5: Document Phase 1 Skill Binding Contract

**Files:**
- Modify: `docs/character/character-mind-core-status.md`
- Modify: `docs/架构/运行时/模块/角色智能体.md`

- [ ] **Step 1: Update character mind-core status**

In `docs/character/character-mind-core-status.md`, add a subsection under the runtime/dynamic state or L4 area:

```markdown
### skill/action binding contract

Phase 1 of the Character Skill System is a shadow contract layer.

Current scope:

- `SkillDefinition`, `ActionDefinition`, and `SkillActionBinding` are separate contracts.
- `CharacterSkillService` can evaluate action skill paths without owning world truth.
- `L4` can emit a `CompositeActionProposal` while preserving the existing execution bundle.
- `SkillLearningPolicy` and `SkillEvidence` are schema-level contracts only; promotion remains off by default.

Boundary:

- ESM remains semantic authority.
- Physical channel remains embodied feasibility authority.
- Kimodo/asset realization remains presentation-only.
- Authored profile truth is not modified by skill evidence.
```

- [ ] **Step 2: Update character agent module doc**

In `docs/架构/运行时/模块/角色智能体.md`, add a section near the L3/L4 boundary description:

```markdown
### Character Skill System boundary

The skill system is introduced as an independent character-side service, not as
an ESM responsibility and not as a Kimodo responsibility.

Phase 1 contract flow:

```text
L3 selected_intent
-> L4 CompositeActionProposal
-> CharacterSkillService SkillEvaluationResult
-> existing L4 action_request_bundle remains compatible
```

The service produces advisory/pre-settlement skill information. World truth still
comes from ESM and the physical channel. Realization consumes selected skill path
and settlement result for presentation variants only.
```

- [ ] **Step 3: Run docs harness**

Run: `python scripts/verification/harness.py --profile docs`

Expected: PASS.

- [ ] **Step 4: Commit Task 5**

```bash
git add docs/character/character-mind-core-status.md docs/架构/运行时/模块/角色智能体.md
git commit -m "Document character skill binding contract boundary"
```

---

### Task 6: Final Verification

**Files:**
- No source edits unless verification finds a defect.

- [ ] **Step 1: Run focused skill tests**

Run:

```bash
pytest backend/tests/test_character_skill_models.py backend/tests/test_skill_action_binding_registry.py backend/tests/test_character_skill_service.py backend/tests/test_character_agent_l4_skill_shadow.py -v
```

Expected: PASS.

- [ ] **Step 2: Run related character runtime tests**

Run:

```bash
pytest backend/tests/test_character_agent_runtime.py backend/tests/test_character_agent_l3_planning.py backend/tests/test_character_runtime_needs_affect_flow.py -v
```

Expected: PASS.

- [ ] **Step 3: Run full backend tests**

Run: `python -m pytest backend -q`

Expected: PASS.

- [ ] **Step 4: Run lint for changed Python files**

Run:

```bash
ruff check backend/app/character_agent/skills backend/app/character_agent/execution/l4_executor.py backend/tests/test_character_skill_models.py backend/tests/test_skill_action_binding_registry.py backend/tests/test_character_skill_service.py backend/tests/test_character_agent_l4_skill_shadow.py
```

Expected: PASS.

- [ ] **Step 5: Run docs harness**

Run: `python scripts/verification/harness.py --profile docs`

Expected: PASS.

- [ ] **Step 6: Check diff whitespace and worktree**

Run:

```bash
git diff --check
git status --short
```

Expected:

- `git diff --check` exits 0.
- `git status --short` contains only intentional changes before the final commit, or is clean after committing.

- [ ] **Step 7: Final commit if verification changed files**

If any verification fixes were needed:

```bash
git add <changed-files>
git commit -m "Verify character skill binding contract"
```

If no files changed, do not create an empty commit.

