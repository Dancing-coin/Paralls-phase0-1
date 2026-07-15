# Layered Character Mind Factor Architecture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the first shadow-mode slice of the layered character mind factor architecture: typed `CharacterMindFrame` contracts, factor projection cards, L2/L3/L4 view models, a frame builder from existing runtime inputs, and a typed delta ledger without changing current character behavior.

**Architecture:** Add contracts under `backend/app/character_agent/models/` and builder/view helpers under a new `backend/app/character_agent/mind/` package. The first slice is read-only and shadow-mode: existing `CharacterAgentRuntime`, `L2`, `L3`, and `L4` keep their current behavior while the new contracts prove the future layered interface. No graph store, skill registry execution, or settlement behavior is introduced in this foundation plan.

**Tech Stack:** Python 3.13, Pydantic v2, pytest, existing `backend/app/character_agent` runtime models, no new dependencies.

---

## Status Snapshot

Status: `implemented-and-verified-foundation`.

The historical task checkboxes below are superseded by the current main branch:
Phase 1/2 shadow `CharacterMindFrame`, layer context views, runtime shadow
accessor, and delta-ledger foundation are implemented and covered by focused
mind-frame/runtime tests. Phase 3-6 follow-up plans are complete and summarized
in `docs/superpowers/plans/2026-07-11-layered-character-mind-factor-plan-series.md`.

## Scope Boundary

This plan implements Phase 1 and Phase 2 foundations from `docs/superpowers/specs/2026-07-11-layered-character-mind-factor-architecture-design.md`.

Included:

- `CharacterMindFrame` and layer section contracts.
- `MentalFactorProjectionCard` contract with provenance.
- `CognitionWorkspace` contract.
- `L2InterpretationView`, `L3PlanningView`, `L4ExecutionView`, and `WritebackView` contracts.
- `MindDeltaLedger` contract wrapping current cognition, state, goal, skill, relationship, and drift deltas.
- A shadow `CharacterMindFrameBuilder` that summarizes existing profile, memory, relationship, need, dynamic state, goal, unresolved tension, supervision, and optional skill/action affordance inputs.
- View builders that derive layer-specific consumption views from a frame and workspace.
- A runtime shadow accessor for observability and tests, without feeding the frame into current L2/L3 prompts.
- Documentation sync and docs harness verification.

Excluded:

- Replacing existing `L2.prepare_reasoning_request` payloads.
- Replacing existing `L3.build_intent_plan` context payloads.
- Implementing graph-backed knowledge/social/higher-order memory.
- Implementing the Character Skill System binding contract.
- Introducing an action library or changing `L4` action routing.
- Changing ESM, System L6, physical channel, Godot, Kimodo, or settlement authority.

## File Structure

- `backend/app/character_agent/models/mind_frame.py`
  - Pydantic contracts for projection cards, mind frame layers, workspace, layer views, writeback view, and delta ledger.
- `backend/app/character_agent/models/__init__.py`
  - Public exports for the new contracts.
- `backend/app/character_agent/mind/__init__.py`
  - Public exports for mind-frame helpers.
- `backend/app/character_agent/mind/frame_builder.py`
  - Shadow `CharacterMindFrameBuilder` that converts current runtime inputs into layered projection cards.
- `backend/app/character_agent/mind/view_builder.py`
  - `LayerContextViewBuilder` that builds L2/L3/L4/writeback views from the frame.
- `backend/app/character_agent/runtime/runtime_loop.py`
  - Adds a read-only `build_shadow_mind_frame` accessor and initializes the frame builder.
- `backend/tests/test_character_mind_frame_models.py`
  - Contract and validation tests for schemas.
- `backend/tests/test_character_mind_frame_builder.py`
  - Builder tests proving memory, relationship, state, goal, and affordance summaries are layered.
- `backend/tests/test_character_mind_context_views.py`
  - View builder tests proving each layer receives only its intended view.
- `backend/tests/test_character_runtime_shadow_mind_frame.py`
  - Runtime accessor tests proving shadow frame construction does not alter command output.
- `docs/character/character-mind-core-status.md`
  - Status note that a shadow factor-frame contract exists above the existing four-layer runtime.
- `docs/架构/运行时/模块/角色智能体.md`
  - Module doc note for factor projection and shadow-frame boundaries.

---

### Task 1: Add Mind Frame Model Contracts

**Files:**
- Create: `backend/app/character_agent/models/mind_frame.py`
- Modify: `backend/app/character_agent/models/__init__.py`
- Test: `backend/tests/test_character_mind_frame_models.py`

- [ ] **Step 1: Write failing schema tests**

Create `backend/tests/test_character_mind_frame_models.py`:

```python
import pytest
from pydantic import ValidationError

from app.character_agent.models.mind_frame import (
    CharacterMindFrame,
    CharacterMindFrameTrigger,
    CognitionWorkspace,
    L2InterpretationView,
    L3PlanningView,
    L4ExecutionView,
    MentalFactorProjectionCard,
    MindDeltaLedger,
    MindFrameLayer,
    MindFrameProvenance,
    WritebackView,
)


def _card(factor_type: str, summary: str) -> MentalFactorProjectionCard:
    return MentalFactorProjectionCard(
        factor_type=factor_type,
        layer="memory_evidence",
        scope="actor_private",
        horizon="scene",
        confidence=0.8,
        freshness="current",
        summary=summary,
        source_refs=[f"{factor_type}:source"],
        risk_notes=[],
    )


def test_projection_card_is_typed_traceable_and_bounded() -> None:
    card = _card("relationship", "A trusts B but carries tension.")

    assert card.factor_type == "relationship"
    assert card.scope == "actor_private"
    assert card.confidence == 0.8
    assert card.source_refs == ["relationship:source"]


def test_projection_card_rejects_invalid_confidence() -> None:
    with pytest.raises(ValidationError):
        MentalFactorProjectionCard(
            factor_type="relationship",
            layer="memory_evidence",
            scope="actor_private",
            confidence=1.5,
            summary="bad confidence",
        )


def test_mind_frame_keeps_layers_separate() -> None:
    frame = CharacterMindFrame(
        actor_id="char_a",
        mind_turn_id="mind_turn:char_a:123",
        producer_ts=123,
        trigger=CharacterMindFrameTrigger(
            event_id="event:456",
            event_type="character_perceived_event",
        ),
        enduring_truth=MindFrameLayer(cards=[_card("effective_profile", "profile summary")]),
        memory_evidence=MindFrameLayer(cards=[_card("relationship", "relationship summary")]),
        runtime_state=MindFrameLayer(cards=[_card("need_pressure", "need summary")]),
        affordances=MindFrameLayer(cards=[_card("skill_affordance", "skill summary")]),
        provenance=MindFrameProvenance(
            source_refs=["profile:char_a", "memory:event:1"],
        ),
    )

    assert frame.enduring_truth.cards[0].factor_type == "effective_profile"
    assert frame.memory_evidence.cards[0].factor_type == "relationship"
    assert frame.runtime_state.cards[0].factor_type == "need_pressure"
    assert frame.affordances.cards[0].factor_type == "skill_affordance"


def test_cognition_workspace_is_turn_local_not_memory() -> None:
    workspace = CognitionWorkspace(
        active_anchors=["B once saved A"],
        dominant_drivers=["preserve_order"],
        active_conflicts=["order_vs_loyalty"],
        decision_biases=["avoid_direct_deception"],
        hard_constraints=["cannot_falsify_authority_report"],
        candidate_questions=["Is the emergency real?"],
    )

    assert workspace.active_anchors == ["B once saved A"]
    assert "order_vs_loyalty" in workspace.active_conflicts


def test_layer_views_have_distinct_payloads() -> None:
    l2_view = L2InterpretationView(
        actor_id="char_a",
        mind_turn_id="mind_turn:char_a:123",
        perception_context={"focus_target": "char_b"},
        effective_profile_summary={"summary": "order-valuing"},
        memory_activation_summary={"count": 2},
        cognitive_anchor_summary={"anchors": ["B saved A"]},
        relationship_context_summary={"target": "char_b", "trust_band": "high"},
        need_pressure_summary={"dominant_need": "esteem"},
        affective_body_summary={"stress_load": 0.4},
        goal_context_summary={"primary_goal": "preserve_order"},
        unresolved_tension_summary={"count": 1},
        supervision_summary={"mode": "none"},
    )
    l3_view = L3PlanningView(
        actor_id="char_a",
        mind_turn_id="mind_turn:char_a:123",
        interpretation_summary={"risk_level": "medium"},
        cognition_workspace=CognitionWorkspace(active_conflicts=["order_vs_loyalty"]),
        goal_context_summary={"primary_goal": "preserve_order"},
        need_pressure_summary={"dominant_need": "esteem"},
        affective_body_summary={"stress_load": 0.4},
        skill_affordance_summary={"available_action_families": {}},
        action_affordance_summary={"available_actions": []},
        relationship_affordance_summary={"trust_band": "high"},
        hard_constraints=["cannot_falsify_authority_report"],
        unresolved_tension_summary={"count": 1},
        supervision_summary={"mode": "none"},
    )
    l4_view = L4ExecutionView(
        actor_id="char_a",
        mind_turn_id="mind_turn:char_a:123",
        selected_intent="speak_private",
        target_refs={"actor": "char_b"},
        affective_body_summary={"stress_load": 0.4},
        presentation_constraints=["low_voice"],
        realization_hints=["controlled_posture"],
        physical_feasibility_summary={"status": "advisory"},
    )

    assert l2_view.relationship_context_summary["trust_band"] == "high"
    assert l3_view.cognition_workspace.active_conflicts == ["order_vs_loyalty"]
    assert l4_view.selected_intent == "speak_private"


def test_delta_ledger_keeps_writeback_candidates_separate() -> None:
    ledger = MindDeltaLedger(
        actor_id="char_a",
        mind_turn_id="mind_turn:char_a:123",
        belief_deltas=[{"proposition_key": "b_motive", "state": "suspected"}],
        social_deltas=[{"entity_id": "char_b", "trust_baseline": 0.7}],
        dynamic_state_deltas={"stress_load": 0.4},
        goal_deltas=[{"goal": "verify_emergency"}],
        skill_evidence_deltas=[{"skill_id": "persuasion", "outcome_band": "partial"}],
        memory_write_candidates=[{"event_type": "character_interpretation_event"}],
        relationship_update_candidates=[{"entity_id": "char_b", "unresolved_tension": 0.2}],
        drift_candidates=[{"key": "conflict_style", "direction": "avoidance_up"}],
    )

    assert ledger.skill_evidence_deltas[0]["skill_id"] == "persuasion"
    assert ledger.relationship_update_candidates[0]["entity_id"] == "char_b"


def test_writeback_view_wraps_settlement_and_delta_context() -> None:
    view = WritebackView(
        actor_id="char_a",
        mind_turn_id="mind_turn:char_a:123",
        l2_deltas={"belief_deltas": []},
        l3_decision={"selected_intent": "speak_private"},
        l4_execution_proposal={"action_request_bundle": {"requested_actions": []}},
        settlement_result={"outcome_band": "partial"},
        evidence_refs=["event:1"],
    )

    assert view.l3_decision["selected_intent"] == "speak_private"
    assert view.evidence_refs == ["event:1"]
```

- [ ] **Step 2: Run schema tests and verify they fail**

Run: `pytest backend/tests/test_character_mind_frame_models.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'app.character_agent.models.mind_frame'`.

- [ ] **Step 3: Implement mind frame contracts**

Create `backend/app/character_agent/models/mind_frame.py`:

```python
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


MindFactorLayer = Literal[
    "enduring_truth",
    "memory_evidence",
    "runtime_state",
    "affordance",
    "cognition_process",
    "writeback_learning",
]


class StrictMindFrameModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MentalFactorProjectionCard(StrictMindFrameModel):
    factor_type: str
    layer: MindFactorLayer
    scope: Literal["actor_private", "public", "system", "scenario"] = "actor_private"
    horizon: Literal["instant", "scene", "arc", "long_term"] = "scene"
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    freshness: Literal["current", "recent", "stale", "unknown"] = "unknown"
    summary: str
    payload: dict[str, object] = Field(default_factory=dict)
    source_refs: list[str] = Field(default_factory=list)
    risk_notes: list[str] = Field(default_factory=list)


class MindFrameLayer(StrictMindFrameModel):
    cards: list[MentalFactorProjectionCard] = Field(default_factory=list)
    summary: dict[str, object] = Field(default_factory=dict)


class CharacterMindFrameTrigger(StrictMindFrameModel):
    event_id: str = ""
    event_type: str = ""
    source_stage: str = ""


class MindFrameProvenance(StrictMindFrameModel):
    source_refs: list[str] = Field(default_factory=list)
    builder_version: str = "mind_frame_builder.v1"


class CognitionWorkspace(StrictMindFrameModel):
    active_anchors: list[str] = Field(default_factory=list)
    dominant_drivers: list[str] = Field(default_factory=list)
    active_conflicts: list[str] = Field(default_factory=list)
    decision_biases: list[str] = Field(default_factory=list)
    hard_constraints: list[str] = Field(default_factory=list)
    candidate_questions: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class CharacterMindFrame(StrictMindFrameModel):
    actor_id: str
    mind_turn_id: str
    producer_ts: int = 0
    trigger: CharacterMindFrameTrigger = Field(default_factory=CharacterMindFrameTrigger)
    enduring_truth: MindFrameLayer = Field(default_factory=MindFrameLayer)
    memory_evidence: MindFrameLayer = Field(default_factory=MindFrameLayer)
    runtime_state: MindFrameLayer = Field(default_factory=MindFrameLayer)
    affordances: MindFrameLayer = Field(default_factory=MindFrameLayer)
    cognition_workspace: CognitionWorkspace = Field(default_factory=CognitionWorkspace)
    provenance: MindFrameProvenance = Field(default_factory=MindFrameProvenance)


class L2InterpretationView(StrictMindFrameModel):
    actor_id: str
    mind_turn_id: str
    perception_context: dict[str, object] = Field(default_factory=dict)
    effective_profile_summary: dict[str, object] = Field(default_factory=dict)
    memory_activation_summary: dict[str, object] = Field(default_factory=dict)
    cognitive_anchor_summary: dict[str, object] = Field(default_factory=dict)
    relationship_context_summary: dict[str, object] = Field(default_factory=dict)
    need_pressure_summary: dict[str, object] = Field(default_factory=dict)
    affective_body_summary: dict[str, object] = Field(default_factory=dict)
    goal_context_summary: dict[str, object] = Field(default_factory=dict)
    unresolved_tension_summary: dict[str, object] = Field(default_factory=dict)
    supervision_summary: dict[str, object] = Field(default_factory=dict)


class L3PlanningView(StrictMindFrameModel):
    actor_id: str
    mind_turn_id: str
    interpretation_summary: dict[str, object] = Field(default_factory=dict)
    cognition_workspace: CognitionWorkspace = Field(default_factory=CognitionWorkspace)
    goal_context_summary: dict[str, object] = Field(default_factory=dict)
    need_pressure_summary: dict[str, object] = Field(default_factory=dict)
    affective_body_summary: dict[str, object] = Field(default_factory=dict)
    skill_affordance_summary: dict[str, object] = Field(default_factory=dict)
    action_affordance_summary: dict[str, object] = Field(default_factory=dict)
    relationship_affordance_summary: dict[str, object] = Field(default_factory=dict)
    hard_constraints: list[str] = Field(default_factory=list)
    unresolved_tension_summary: dict[str, object] = Field(default_factory=dict)
    supervision_summary: dict[str, object] = Field(default_factory=dict)


class L4ExecutionView(StrictMindFrameModel):
    actor_id: str
    mind_turn_id: str
    selected_intent: str = ""
    selected_skill_path: dict[str, object] = Field(default_factory=dict)
    target_refs: dict[str, str] = Field(default_factory=dict)
    affective_body_summary: dict[str, object] = Field(default_factory=dict)
    presentation_constraints: list[str] = Field(default_factory=list)
    realization_hints: list[str] = Field(default_factory=list)
    physical_feasibility_summary: dict[str, object] = Field(default_factory=dict)


class WritebackView(StrictMindFrameModel):
    actor_id: str
    mind_turn_id: str
    l2_deltas: dict[str, object] = Field(default_factory=dict)
    l3_decision: dict[str, object] = Field(default_factory=dict)
    l4_execution_proposal: dict[str, object] = Field(default_factory=dict)
    settlement_result: dict[str, object] = Field(default_factory=dict)
    dialogue_or_action_outcome: dict[str, object] = Field(default_factory=dict)
    evidence_refs: list[str] = Field(default_factory=list)


class MindDeltaLedger(StrictMindFrameModel):
    actor_id: str
    mind_turn_id: str
    belief_deltas: list[dict[str, object]] = Field(default_factory=list)
    social_deltas: list[dict[str, object]] = Field(default_factory=list)
    higher_order_deltas: list[dict[str, object]] = Field(default_factory=list)
    dynamic_state_deltas: dict[str, object] = Field(default_factory=dict)
    need_tension_deltas: dict[str, object] = Field(default_factory=dict)
    goal_deltas: list[dict[str, object]] = Field(default_factory=list)
    skill_evidence_deltas: list[dict[str, object]] = Field(default_factory=list)
    memory_write_candidates: list[dict[str, object]] = Field(default_factory=list)
    relationship_update_candidates: list[dict[str, object]] = Field(default_factory=list)
    drift_candidates: list[dict[str, object]] = Field(default_factory=list)
```

Modify `backend/app/character_agent/models/__init__.py`:

```python
from app.character_agent.models.cognition_update import CharacterCognitionUpdate
from app.character_agent.models.dynamic_state import CharacterDynamicState
from app.character_agent.models.event_memory import CharacterEventMemoryRecord
from app.character_agent.models.goal_runtime import (
    CharacterActiveGoalFrame,
    CharacterGoalHint,
    CharacterGoalStateRecord,
)
from app.character_agent.models.higher_order_memory import CharacterHigherOrderMemoryRecord
from app.character_agent.models.knowledge_memory import CharacterKnowledgeMemoryRecord
from app.character_agent.models.memory_record_bundle import CharacterMemoryRecordBundle
from app.character_agent.models.mind_frame import (
    CharacterMindFrame,
    CharacterMindFrameTrigger,
    CognitionWorkspace,
    L2InterpretationView,
    L3PlanningView,
    L4ExecutionView,
    MentalFactorProjectionCard,
    MindDeltaLedger,
    MindFrameLayer,
    MindFrameProvenance,
    WritebackView,
)
from app.character_agent.models.observation_memory import CharacterObservationMemoryRecord
from app.character_agent.models.social_memory import CharacterSocialMemoryRecord
from app.character_agent.models.working_memory_state import CharacterWorkingMemoryState

__all__ = [
    "CharacterActiveGoalFrame",
    "CharacterCognitionUpdate",
    "CharacterDynamicState",
    "CharacterEventMemoryRecord",
    "CharacterGoalHint",
    "CharacterGoalStateRecord",
    "CharacterHigherOrderMemoryRecord",
    "CharacterKnowledgeMemoryRecord",
    "CharacterMemoryRecordBundle",
    "CharacterMindFrame",
    "CharacterMindFrameTrigger",
    "CharacterObservationMemoryRecord",
    "CharacterPrivateWorldSnapshot",
    "CharacterSocialMemoryRecord",
    "CharacterWorkingMemoryState",
    "CognitionWorkspace",
    "L2InterpretationView",
    "L3PlanningView",
    "L4ExecutionView",
    "MentalFactorProjectionCard",
    "MindDeltaLedger",
    "MindFrameLayer",
    "MindFrameProvenance",
    "WritebackView",
]


def __getattr__(name: str) -> object:
    if name == "CharacterPrivateWorldSnapshot":
        from app.character_agent.models.private_world_snapshot import CharacterPrivateWorldSnapshot

        return CharacterPrivateWorldSnapshot
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
```

- [ ] **Step 4: Run schema tests and verify they pass**

Run: `pytest backend/tests/test_character_mind_frame_models.py -v`

Expected: PASS.

- [ ] **Step 5: Commit Task 1**

```bash
git add backend/app/character_agent/models/__init__.py backend/app/character_agent/models/mind_frame.py backend/tests/test_character_mind_frame_models.py
git commit -m "Define the character mind frame contracts" -m "The layered mind factor architecture needs typed contracts before runtime integration. This adds projection cards, frame layers, layer views, workspace, and delta ledger models without changing behavior." -m "Constraint: Keep the existing L1-L4 runtime primary" -m "Rejected: A generic dict-only context | loses factor ownership and validation" -m "Confidence: high" -m "Scope-risk: narrow" -m "Tested: pytest backend/tests/test_character_mind_frame_models.py -v"
```

---

### Task 2: Add Shadow CharacterMindFrameBuilder

**Files:**
- Create: `backend/app/character_agent/mind/__init__.py`
- Create: `backend/app/character_agent/mind/frame_builder.py`
- Test: `backend/tests/test_character_mind_frame_builder.py`

- [ ] **Step 1: Write failing builder tests**

Create `backend/tests/test_character_mind_frame_builder.py`:

```python
from app.character_agent.mind.frame_builder import CharacterMindFrameBuilder


def test_builder_places_profile_memory_state_goal_and_affordance_cards_in_separate_layers() -> None:
    frame = CharacterMindFrameBuilder().build_frame(
        actor_id="char_a",
        producer_ts=123,
        trigger_event={"event_id": "event:1", "event_type": "character_perceived_event"},
        snapshot={"current_focus_target": "char_b", "visible_entities": ["char_b"]},
        effective_profile={
            "identity_core": {"canonical_name": "A"},
            "trait_vector_layer": {"empathy": 0.8, "rationality": 0.7},
            "virtue_value_layer": {"red_lines": ["do_not_falsify_authority_report"]},
        },
        memory_bundle={
            "event_memories": [{"memory_id": "event:old", "summary": "B once saved A"}],
            "knowledge_memories": [{"proposition_key": "medicine:urgent", "proposition": "medicine can save a child"}],
            "social_memories": [
                {
                    "memory_id": "social:char_a:char_b",
                    "actor_id": "char_a",
                    "entity_id": "char_b",
                    "trust_baseline": 0.8,
                    "suspicion_baseline": 0.2,
                    "intimacy": 0.6,
                    "dependency": 0.3,
                    "unresolved_tension": 0.1,
                    "shared_secret_refs": ["secret:1"],
                    "source_event_id": "event:old",
                    "producer_ts": 12,
                }
            ],
            "higher_order_memories": [{"meta_belief": "B may know A is conflicted"}],
        },
        need_tension_state={"dominant_need": "esteem", "esteem_pressure": 0.4},
        dynamic_state={"stress_load": 0.5, "affect_state": {"concern": 0.7}},
        current_goal_state={"primary_goal": "preserve_order", "goal_portfolio": []},
        goal_state_history=[{"primary_goal": "protect_friend"}],
        unresolved_tensions=[{"summary": "order versus loyalty"}],
        supervision_state={"authorization_level": "none"},
        skill_affordance_summary={"available_action_families": {"social_deescalation": {"level": "trained"}}},
        action_affordance_summary={"available_actions": ["speak_private"]},
    )

    assert frame.actor_id == "char_a"
    assert frame.trigger.event_id == "event:1"
    assert frame.enduring_truth.cards[0].factor_type == "effective_profile"
    assert frame.memory_evidence.summary["event_memory_count"] == 1
    assert frame.runtime_state.summary["dominant_need"] == "esteem"
    assert frame.affordances.summary["has_skill_affordance"] is True
    assert "profile:char_a" in frame.provenance.source_refs


def test_builder_summarizes_relationship_as_memory_owned_actor_private_projection() -> None:
    frame = CharacterMindFrameBuilder().build_frame(
        actor_id="char_a",
        producer_ts=123,
        trigger_event={"event_id": "event:1", "event_type": "character_perceived_event"},
        snapshot={},
        effective_profile={},
        memory_bundle={
            "social_memories": [
                {
                    "memory_id": "social:char_a:char_b",
                    "entity_id": "char_b",
                    "trust_baseline": 0.75,
                    "suspicion_baseline": 0.25,
                    "intimacy": 0.5,
                    "dependency": 0.2,
                    "unresolved_tension": 0.4,
                    "shared_secret_refs": [],
                    "source_event_id": "event:old",
                    "producer_ts": 1,
                }
            ]
        },
    )

    relationship_cards = [
        card for card in frame.memory_evidence.cards if card.factor_type == "relationship_context"
    ]

    assert len(relationship_cards) == 1
    assert relationship_cards[0].scope == "actor_private"
    assert relationship_cards[0].payload["target_count"] == 1
    assert relationship_cards[0].payload["top_target"] == "char_b"
    assert "social_memory:char_a:char_b" in relationship_cards[0].source_refs
```

- [ ] **Step 2: Run builder tests and verify they fail**

Run: `pytest backend/tests/test_character_mind_frame_builder.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'app.character_agent.mind'`.

- [ ] **Step 3: Implement the shadow builder**

Create `backend/app/character_agent/mind/frame_builder.py`:

```python
from __future__ import annotations

from app.character_agent.gateway.context_builder import CharacterContextBuilder
from app.character_agent.models.mind_frame import (
    CharacterMindFrame,
    CharacterMindFrameTrigger,
    MentalFactorProjectionCard,
    MindFrameLayer,
    MindFrameProvenance,
)


class CharacterMindFrameBuilder:
    def build_frame(
        self,
        *,
        actor_id: str,
        producer_ts: int,
        trigger_event: dict[str, object] | None = None,
        snapshot: dict[str, object] | None = None,
        effective_profile: dict[str, object] | None = None,
        memory_bundle: dict[str, list[dict[str, object]]] | None = None,
        need_tension_state: dict[str, object] | None = None,
        dynamic_state: dict[str, object] | None = None,
        current_goal_state: dict[str, object] | None = None,
        goal_state_history: list[dict[str, object]] | None = None,
        unresolved_tensions: list[dict[str, object]] | None = None,
        supervision_state: dict[str, object] | None = None,
        skill_affordance_summary: dict[str, object] | None = None,
        action_affordance_summary: dict[str, object] | None = None,
    ) -> CharacterMindFrame:
        trigger_payload = trigger_event or {}
        normalized_memory = CharacterContextBuilder.normalize_memory_bundle(memory_bundle)
        effective_profile_payload = effective_profile or {}
        snapshot_payload = snapshot or {}
        need_payload = need_tension_state or {}
        dynamic_payload = dynamic_state or {}
        goal_payload = current_goal_state or {}
        goal_history_payload = goal_state_history or []
        tensions_payload = unresolved_tensions or []
        supervision_payload = supervision_state or {}
        skill_payload = skill_affordance_summary or {}
        action_payload = action_affordance_summary or {}
        mind_turn_id = f"mind_turn:{actor_id}:{producer_ts}"

        return CharacterMindFrame(
            actor_id=actor_id,
            mind_turn_id=mind_turn_id,
            producer_ts=producer_ts,
            trigger=CharacterMindFrameTrigger(
                event_id=str(trigger_payload.get("event_id", "") or trigger_payload.get("source_event_id", "") or ""),
                event_type=str(trigger_payload.get("event_type", "") or trigger_payload.get("type", "") or ""),
                source_stage=str(trigger_payload.get("source_stage", "") or ""),
            ),
            enduring_truth=self._enduring_truth_layer(actor_id, effective_profile_payload),
            memory_evidence=self._memory_evidence_layer(actor_id, normalized_memory),
            runtime_state=self._runtime_state_layer(
                snapshot=snapshot_payload,
                need_tension_state=need_payload,
                dynamic_state=dynamic_payload,
                current_goal_state=goal_payload,
                goal_state_history=goal_history_payload,
                unresolved_tensions=tensions_payload,
                supervision_state=supervision_payload,
            ),
            affordances=self._affordance_layer(
                skill_affordance_summary=skill_payload,
                action_affordance_summary=action_payload,
            ),
            provenance=MindFrameProvenance(
                source_refs=self._source_refs(actor_id, normalized_memory, goal_payload),
            ),
        )

    def _enduring_truth_layer(self, actor_id: str, effective_profile: dict[str, object]) -> MindFrameLayer:
        identity = effective_profile.get("identity_core", {})
        if not isinstance(identity, dict):
            identity = {}
        trait_vector = effective_profile.get("trait_vector_layer", {})
        if not isinstance(trait_vector, dict):
            trait_vector = {}
        values = effective_profile.get("virtue_value_layer", {})
        if not isinstance(values, dict):
            values = {}
        card = MentalFactorProjectionCard(
            factor_type="effective_profile",
            layer="enduring_truth",
            scope="actor_private",
            horizon="long_term",
            confidence=1.0,
            freshness="current",
            summary=str(identity.get("canonical_name", "") or actor_id),
            payload={
                "identity_core": identity,
                "trait_vector_keys": sorted(trait_vector),
                "red_lines": list(values.get("red_lines", [])) if isinstance(values.get("red_lines", []), list) else [],
            },
            source_refs=[f"profile:{actor_id}"],
        )
        return MindFrameLayer(cards=[card], summary={"profile_actor_id": actor_id})

    def _memory_evidence_layer(self, actor_id: str, memory: dict[str, list[dict[str, object]]]) -> MindFrameLayer:
        event_memories = memory.get("event_memories", [])
        observation_memories = memory.get("observation_memories", [])
        knowledge_memories = memory.get("knowledge_memories", [])
        social_memories = memory.get("social_memories", [])
        higher_order_memories = memory.get("higher_order_memories", [])
        cards = [
            MentalFactorProjectionCard(
                factor_type="memory_activation",
                layer="memory_evidence",
                scope="actor_private",
                horizon="scene",
                confidence=0.8,
                freshness="recent",
                summary=self._first_summary(event_memories, "summary"),
                payload={
                    "event_memory_count": len(event_memories),
                    "observation_memory_count": len(observation_memories),
                    "knowledge_memory_count": len(knowledge_memories),
                    "higher_order_memory_count": len(higher_order_memories),
                },
                source_refs=self._memory_refs("memory", event_memories + observation_memories + knowledge_memories + higher_order_memories),
            ),
            MentalFactorProjectionCard(
                factor_type="relationship_context",
                layer="memory_evidence",
                scope="actor_private",
                horizon="scene",
                confidence=0.8,
                freshness="recent",
                summary=self._relationship_summary(social_memories),
                payload={
                    "target_count": len(social_memories),
                    "top_target": str(social_memories[0].get("entity_id", "") or "") if social_memories else "",
                },
                source_refs=[
                    f"social_memory:{actor_id}:{entry.get('entity_id', '')}"
                    for entry in social_memories
                    if str(entry.get("entity_id", "") or "")
                ],
            ),
        ]
        return MindFrameLayer(
            cards=cards,
            summary={
                "event_memory_count": len(event_memories),
                "observation_memory_count": len(observation_memories),
                "knowledge_memory_count": len(knowledge_memories),
                "social_memory_count": len(social_memories),
                "higher_order_memory_count": len(higher_order_memories),
            },
        )

    def _runtime_state_layer(
        self,
        *,
        snapshot: dict[str, object],
        need_tension_state: dict[str, object],
        dynamic_state: dict[str, object],
        current_goal_state: dict[str, object],
        goal_state_history: list[dict[str, object]],
        unresolved_tensions: list[dict[str, object]],
        supervision_state: dict[str, object],
    ) -> MindFrameLayer:
        cards = [
            MentalFactorProjectionCard(
                factor_type="perception_context",
                layer="runtime_state",
                summary=str(snapshot.get("current_focus_target", "") or snapshot.get("attention_target", "") or ""),
                payload=snapshot,
                source_refs=[],
            ),
            MentalFactorProjectionCard(
                factor_type="need_pressure",
                layer="runtime_state",
                summary=str(need_tension_state.get("dominant_need", "") or ""),
                payload=need_tension_state,
                source_refs=["need_tension_state:current"],
            ),
            MentalFactorProjectionCard(
                factor_type="affective_body_state",
                layer="runtime_state",
                summary=f"stress_load={dynamic_state.get('stress_load', 0.0)}",
                payload=dynamic_state,
                source_refs=["dynamic_state:current"],
            ),
            MentalFactorProjectionCard(
                factor_type="goal_context",
                layer="runtime_state",
                summary=str(current_goal_state.get("primary_goal", "") or ""),
                payload={
                    "current_goal_state": current_goal_state,
                    "goal_state_history_count": len(goal_state_history),
                },
                source_refs=["goal_state:current"],
            ),
            MentalFactorProjectionCard(
                factor_type="unresolved_tension",
                layer="runtime_state",
                summary=self._first_summary(unresolved_tensions, "summary"),
                payload={"unresolved_tension_count": len(unresolved_tensions)},
                source_refs=["unresolved_tensions:current"] if unresolved_tensions else [],
            ),
            MentalFactorProjectionCard(
                factor_type="supervision",
                layer="runtime_state",
                summary=str(supervision_state.get("authorization_level", "") or supervision_state.get("mode", "") or ""),
                payload=supervision_state,
                source_refs=["supervision_state:current"] if supervision_state else [],
            ),
        ]
        return MindFrameLayer(
            cards=cards,
            summary={
                "focus_target": str(snapshot.get("current_focus_target", "") or snapshot.get("attention_target", "") or ""),
                "dominant_need": str(need_tension_state.get("dominant_need", "") or ""),
                "primary_goal": str(current_goal_state.get("primary_goal", "") or ""),
                "unresolved_tension_count": len(unresolved_tensions),
            },
        )

    def _affordance_layer(
        self,
        *,
        skill_affordance_summary: dict[str, object],
        action_affordance_summary: dict[str, object],
    ) -> MindFrameLayer:
        cards = [
            MentalFactorProjectionCard(
                factor_type="skill_affordance",
                layer="affordance",
                summary="skill affordance summary",
                payload=skill_affordance_summary,
                source_refs=["skill_affordance:shadow"] if skill_affordance_summary else [],
            ),
            MentalFactorProjectionCard(
                factor_type="action_affordance",
                layer="affordance",
                summary="action affordance summary",
                payload=action_affordance_summary,
                source_refs=["action_affordance:shadow"] if action_affordance_summary else [],
            ),
        ]
        return MindFrameLayer(
            cards=cards,
            summary={
                "has_skill_affordance": bool(skill_affordance_summary),
                "has_action_affordance": bool(action_affordance_summary),
            },
        )

    def _source_refs(
        self,
        actor_id: str,
        memory: dict[str, list[dict[str, object]]],
        current_goal_state: dict[str, object],
    ) -> list[str]:
        refs = [f"profile:{actor_id}"]
        refs.extend(self._memory_refs("event_memory", memory.get("event_memories", [])))
        refs.extend(self._memory_refs("knowledge_memory", memory.get("knowledge_memories", [])))
        refs.extend(self._memory_refs("higher_order_memory", memory.get("higher_order_memories", [])))
        if current_goal_state:
            refs.append(f"goal_state:{actor_id}:current")
        return refs

    @staticmethod
    def _memory_refs(prefix: str, entries: list[dict[str, object]]) -> list[str]:
        refs: list[str] = []
        for entry in entries:
            value = str(entry.get("memory_id", "") or entry.get("source_event_id", "") or entry.get("proposition_key", "") or "")
            if value:
                refs.append(f"{prefix}:{value}")
        return refs

    @staticmethod
    def _first_summary(entries: list[dict[str, object]], key: str) -> str:
        if not entries:
            return ""
        first = entries[0]
        return str(first.get(key, "") or first.get("observation_summary", "") or first.get("proposition", "") or first.get("meta_belief", "") or "")

    @staticmethod
    def _relationship_summary(entries: list[dict[str, object]]) -> str:
        if not entries:
            return ""
        first = entries[0]
        return "target=%s trust=%s suspicion=%s" % (
            str(first.get("entity_id", "") or ""),
            str(first.get("trust_baseline", "") or ""),
            str(first.get("suspicion_baseline", "") or ""),
        )
```

Create `backend/app/character_agent/mind/__init__.py`:

```python
from app.character_agent.mind.frame_builder import CharacterMindFrameBuilder

__all__ = ["CharacterMindFrameBuilder"]
```

- [ ] **Step 4: Run builder tests and verify they pass**

Run: `pytest backend/tests/test_character_mind_frame_builder.py -v`

Expected: PASS.

- [ ] **Step 5: Commit Task 2**

```bash
git add backend/app/character_agent/mind/__init__.py backend/app/character_agent/mind/frame_builder.py backend/tests/test_character_mind_frame_builder.py
git commit -m "Build shadow character mind frames from existing inputs" -m "The frame builder turns the current distributed runtime inputs into read-only layered projections. This keeps profile, memory, state, goal, and affordance summaries separate while preserving current behavior." -m "Constraint: The builder is shadow-only and does not feed L2/L3 prompts" -m "Rejected: Wiring the frame directly into L2 immediately | would mix contract work with behavior changes" -m "Confidence: high" -m "Scope-risk: narrow" -m "Tested: pytest backend/tests/test_character_mind_frame_builder.py -v"
```

---

### Task 3: Add Layer Context View Builders

**Files:**
- Modify: `backend/app/character_agent/mind/__init__.py`
- Create: `backend/app/character_agent/mind/view_builder.py`
- Test: `backend/tests/test_character_mind_context_views.py`

- [ ] **Step 1: Write failing view builder tests**

Create `backend/tests/test_character_mind_context_views.py`:

```python
from app.character_agent.mind.frame_builder import CharacterMindFrameBuilder
from app.character_agent.mind.view_builder import LayerContextViewBuilder
from app.character_agent.models.mind_frame import CognitionWorkspace


def _frame():
    return CharacterMindFrameBuilder().build_frame(
        actor_id="char_a",
        producer_ts=123,
        trigger_event={"event_id": "event:1", "event_type": "character_perceived_event"},
        snapshot={"current_focus_target": "char_b", "visible_entities": ["char_b"]},
        effective_profile={
            "identity_core": {"canonical_name": "A"},
            "virtue_value_layer": {"red_lines": ["do_not_falsify_authority_report"]},
        },
        memory_bundle={
            "event_memories": [{"memory_id": "event:old", "summary": "B once saved A"}],
            "social_memories": [
                {
                    "memory_id": "social:char_a:char_b",
                    "entity_id": "char_b",
                    "trust_baseline": 0.8,
                    "suspicion_baseline": 0.2,
                    "intimacy": 0.6,
                    "dependency": 0.3,
                    "unresolved_tension": 0.1,
                    "shared_secret_refs": [],
                    "source_event_id": "event:old",
                    "producer_ts": 12,
                }
            ],
        },
        need_tension_state={"dominant_need": "esteem", "esteem_pressure": 0.4},
        dynamic_state={"stress_load": 0.5},
        current_goal_state={"primary_goal": "preserve_order"},
        unresolved_tensions=[{"summary": "order versus loyalty"}],
        supervision_state={"authorization_level": "none"},
        skill_affordance_summary={"available_action_families": {"social_deescalation": {"level": "trained"}}},
        action_affordance_summary={"available_actions": ["speak_private"]},
    )


def test_l2_view_contains_interpretation_inputs_but_not_affordance_registry() -> None:
    view = LayerContextViewBuilder().build_l2_view(_frame())

    assert view.actor_id == "char_a"
    assert view.perception_context["focus_target"] == "char_b"
    assert view.relationship_context_summary["top_target"] == "char_b"
    assert view.need_pressure_summary["dominant_need"] == "esteem"
    assert "available_action_families" not in view.model_dump()


def test_l3_view_contains_workspace_goals_state_and_affordance_summaries() -> None:
    workspace = CognitionWorkspace(
        active_conflicts=["order_vs_loyalty"],
        hard_constraints=["cannot_falsify_authority_report"],
    )

    view = LayerContextViewBuilder().build_l3_view(
        _frame(),
        interpretation_summary={"risk_level": "medium"},
        workspace=workspace,
    )

    assert view.interpretation_summary["risk_level"] == "medium"
    assert view.cognition_workspace.active_conflicts == ["order_vs_loyalty"]
    assert view.goal_context_summary["primary_goal"] == "preserve_order"
    assert view.skill_affordance_summary["available_action_families"]["social_deescalation"]["level"] == "trained"
    assert view.hard_constraints == ["cannot_falsify_authority_report"]


def test_l4_view_is_small_and_execution_focused() -> None:
    view = LayerContextViewBuilder().build_l4_view(
        _frame(),
        selected_intent="speak_private",
        selected_skill_path={"binding_id": "persuasion_to_speak_private"},
        target_refs={"actor": "char_b"},
    )

    assert view.selected_intent == "speak_private"
    assert view.selected_skill_path["binding_id"] == "persuasion_to_speak_private"
    assert view.target_refs == {"actor": "char_b"}
    assert "memory_activation_summary" not in view.model_dump()


def test_writeback_view_wraps_existing_outputs_without_persisting_them() -> None:
    view = LayerContextViewBuilder().build_writeback_view(
        _frame(),
        l2_deltas={"belief_deltas": [{"proposition_key": "b_motive"}]},
        l3_decision={"selected_intent": "speak_private"},
        l4_execution_proposal={"action_request_bundle": {"requested_actions": []}},
        settlement_result={"outcome_band": "partial"},
        evidence_refs=["event:1"],
    )

    assert view.l2_deltas["belief_deltas"][0]["proposition_key"] == "b_motive"
    assert view.settlement_result["outcome_band"] == "partial"
```

- [ ] **Step 2: Run view tests and verify they fail**

Run: `pytest backend/tests/test_character_mind_context_views.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'app.character_agent.mind.view_builder'`.

- [ ] **Step 3: Implement view builder**

Create `backend/app/character_agent/mind/view_builder.py`:

```python
from __future__ import annotations

from app.character_agent.models.mind_frame import (
    CharacterMindFrame,
    CognitionWorkspace,
    L2InterpretationView,
    L3PlanningView,
    L4ExecutionView,
    MentalFactorProjectionCard,
    WritebackView,
)


class LayerContextViewBuilder:
    def build_l2_view(self, frame: CharacterMindFrame) -> L2InterpretationView:
        return L2InterpretationView(
            actor_id=frame.actor_id,
            mind_turn_id=frame.mind_turn_id,
            perception_context=self._payload_for(frame.runtime_state.cards, "perception_context"),
            effective_profile_summary=self._payload_for(frame.enduring_truth.cards, "effective_profile"),
            memory_activation_summary=frame.memory_evidence.summary,
            cognitive_anchor_summary=self._payload_for(frame.memory_evidence.cards, "memory_activation"),
            relationship_context_summary=self._payload_for(frame.memory_evidence.cards, "relationship_context"),
            need_pressure_summary=self._payload_for(frame.runtime_state.cards, "need_pressure"),
            affective_body_summary=self._payload_for(frame.runtime_state.cards, "affective_body_state"),
            goal_context_summary=self._goal_context_summary(frame),
            unresolved_tension_summary=self._payload_for(frame.runtime_state.cards, "unresolved_tension"),
            supervision_summary=self._payload_for(frame.runtime_state.cards, "supervision"),
        )

    def build_l3_view(
        self,
        frame: CharacterMindFrame,
        *,
        interpretation_summary: dict[str, object],
        workspace: CognitionWorkspace,
    ) -> L3PlanningView:
        return L3PlanningView(
            actor_id=frame.actor_id,
            mind_turn_id=frame.mind_turn_id,
            interpretation_summary=interpretation_summary,
            cognition_workspace=workspace,
            goal_context_summary=self._goal_context_summary(frame),
            need_pressure_summary=self._payload_for(frame.runtime_state.cards, "need_pressure"),
            affective_body_summary=self._payload_for(frame.runtime_state.cards, "affective_body_state"),
            skill_affordance_summary=self._payload_for(frame.affordances.cards, "skill_affordance"),
            action_affordance_summary=self._payload_for(frame.affordances.cards, "action_affordance"),
            relationship_affordance_summary=self._payload_for(frame.memory_evidence.cards, "relationship_context"),
            hard_constraints=list(workspace.hard_constraints),
            unresolved_tension_summary=self._payload_for(frame.runtime_state.cards, "unresolved_tension"),
            supervision_summary=self._payload_for(frame.runtime_state.cards, "supervision"),
        )

    def build_l4_view(
        self,
        frame: CharacterMindFrame,
        *,
        selected_intent: str,
        selected_skill_path: dict[str, object] | None = None,
        target_refs: dict[str, str] | None = None,
    ) -> L4ExecutionView:
        return L4ExecutionView(
            actor_id=frame.actor_id,
            mind_turn_id=frame.mind_turn_id,
            selected_intent=selected_intent,
            selected_skill_path=selected_skill_path or {},
            target_refs=target_refs or {},
            affective_body_summary=self._payload_for(frame.runtime_state.cards, "affective_body_state"),
            presentation_constraints=[],
            realization_hints=[],
            physical_feasibility_summary={"status": "advisory"},
        )

    def build_writeback_view(
        self,
        frame: CharacterMindFrame,
        *,
        l2_deltas: dict[str, object] | None = None,
        l3_decision: dict[str, object] | None = None,
        l4_execution_proposal: dict[str, object] | None = None,
        settlement_result: dict[str, object] | None = None,
        dialogue_or_action_outcome: dict[str, object] | None = None,
        evidence_refs: list[str] | None = None,
    ) -> WritebackView:
        return WritebackView(
            actor_id=frame.actor_id,
            mind_turn_id=frame.mind_turn_id,
            l2_deltas=l2_deltas or {},
            l3_decision=l3_decision or {},
            l4_execution_proposal=l4_execution_proposal or {},
            settlement_result=settlement_result or {},
            dialogue_or_action_outcome=dialogue_or_action_outcome or {},
            evidence_refs=evidence_refs or [],
        )

    @staticmethod
    def _payload_for(cards: list[MentalFactorProjectionCard], factor_type: str) -> dict[str, object]:
        for card in cards:
            if card.factor_type == factor_type:
                return dict(card.payload)
        return {}

    def _goal_context_summary(self, frame: CharacterMindFrame) -> dict[str, object]:
        payload = self._payload_for(frame.runtime_state.cards, "goal_context")
        current = payload.get("current_goal_state", {})
        if isinstance(current, dict):
            return dict(current)
        return {}
```

Modify `backend/app/character_agent/mind/__init__.py`:

```python
from app.character_agent.mind.frame_builder import CharacterMindFrameBuilder
from app.character_agent.mind.view_builder import LayerContextViewBuilder

__all__ = ["CharacterMindFrameBuilder", "LayerContextViewBuilder"]
```

- [ ] **Step 4: Run view tests and verify they pass**

Run: `pytest backend/tests/test_character_mind_context_views.py -v`

Expected: PASS.

- [ ] **Step 5: Commit Task 3**

```bash
git add backend/app/character_agent/mind/__init__.py backend/app/character_agent/mind/view_builder.py backend/tests/test_character_mind_context_views.py
git commit -m "Add layer-specific mind context views" -m "Layer views keep L2, L3, L4, and writeback consumption bounded instead of passing the whole frame everywhere." -m "Constraint: L2 must not consume skill/action registries through this view" -m "Rejected: One shared view for every layer | would reintroduce a monolithic context" -m "Confidence: high" -m "Scope-risk: narrow" -m "Tested: pytest backend/tests/test_character_mind_context_views.py -v"
```

---

### Task 4: Add Runtime Shadow Mind Frame Accessor

**Files:**
- Modify: `backend/app/character_agent/runtime/runtime_loop.py`
- Test: `backend/tests/test_character_runtime_shadow_mind_frame.py`

- [ ] **Step 1: Write failing runtime accessor tests**

Create `backend/tests/test_character_runtime_shadow_mind_frame.py`:

```python
from app.character_agent.runtime.runtime_loop import CharacterAgentRuntime
from app.models.character_perceived import CharacterPerceivedEvent


def _event() -> CharacterPerceivedEvent:
    return CharacterPerceivedEvent(
        actor_id="char_b",
        percept_channel="visual",
        producer_ts=100,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_demo",
        perceived_summary="char_a moves quietly near the medicine kit",
        source_candidate_event_id="event:shadow:1",
        source_actor_id="char_a",
        target_actor_id="char_a",
        clarity_score=0.9,
        certainty_score=0.8,
    )


def test_runtime_can_build_shadow_mind_frame_without_changing_command_output() -> None:
    runtime = CharacterAgentRuntime()

    commands = runtime.ingest_character_perceived_event(_event())
    frame = runtime.build_shadow_mind_frame(
        actor_id="char_b",
        producer_ts=101,
        trigger_event={"event_id": "event:shadow:manual", "event_type": "shadow_probe"},
    )

    assert isinstance(commands, list)
    assert frame["actor_id"] == "char_b"
    assert frame["trigger"]["event_id"] == "event:shadow:manual"
    assert frame["memory_evidence"]["summary"]["event_memory_count"] >= 1
    assert frame["runtime_state"]["summary"]["focus_target"]


def test_runtime_shadow_mind_frame_is_read_only_snapshot() -> None:
    runtime = CharacterAgentRuntime()
    runtime.ingest_character_perceived_event(_event())

    before = runtime.get_memory_bundle("char_b")
    frame = runtime.build_shadow_mind_frame(
        actor_id="char_b",
        producer_ts=102,
        trigger_event={"event_id": "event:shadow:manual", "event_type": "shadow_probe"},
    )
    after = runtime.get_memory_bundle("char_b")

    assert frame["mind_turn_id"] == "mind_turn:char_b:102"
    assert before == after
```

- [ ] **Step 2: Run runtime accessor tests and verify they fail**

Run: `pytest backend/tests/test_character_runtime_shadow_mind_frame.py -v`

Expected: FAIL with `AttributeError: 'CharacterAgentRuntime' object has no attribute 'build_shadow_mind_frame'`.

- [ ] **Step 3: Add shadow frame builder to runtime**

Modify `backend/app/character_agent/runtime/runtime_loop.py`.

Add this import near the other character-agent imports:

```python
from app.character_agent.mind.frame_builder import CharacterMindFrameBuilder
```

In `CharacterAgentRuntime.__init__`, after `self._l4_executor = CharacterAgentL4Executor()`, add:

```python
        self._mind_frame_builder = CharacterMindFrameBuilder()
```

Add this public method near the other read/query methods:

```python
    def build_shadow_mind_frame(
        self,
        *,
        actor_id: str,
        producer_ts: int,
        trigger_event: dict[str, object] | None = None,
    ) -> dict[str, object]:
        snapshot = self._l1.get_snapshot(actor_id)
        snapshot_payload = snapshot.model_dump() if snapshot is not None else {}
        frame = self._mind_frame_builder.build_frame(
            actor_id=actor_id,
            producer_ts=producer_ts,
            trigger_event=trigger_event or {},
            snapshot=snapshot_payload,
            effective_profile=self._effective_profile_payload(actor_id),
            memory_bundle=self.get_memory_bundle(actor_id),
            need_tension_state=self.get_need_tension_state(actor_id),
            dynamic_state=self.get_dynamic_state(actor_id),
            current_goal_state=self.get_goal_state(actor_id),
            goal_state_history=self.get_goal_state_history(actor_id),
            unresolved_tensions=self.get_unresolved_tensions(actor_id),
            supervision_state=self.get_supervision_state(actor_id),
        )
        return frame.model_dump()
```

Use the existing `_effective_profile_payload`, `get_memory_bundle`,
`get_need_tension_state`, `get_dynamic_state`, `get_goal_state`,
`get_goal_state_history`, `get_unresolved_tensions`, and `get_supervision_state`
methods. Do not add a duplicate effective-profile helper.

- [ ] **Step 4: Run runtime accessor tests and related runtime tests**

Run:

```bash
pytest backend/tests/test_character_runtime_shadow_mind_frame.py backend/tests/test_character_agent_runtime.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit Task 4**

```bash
git add backend/app/character_agent/runtime/runtime_loop.py backend/tests/test_character_runtime_shadow_mind_frame.py
git commit -m "Expose shadow mind frames from character runtime" -m "The runtime can now assemble a read-only CharacterMindFrame from existing stores for tests and observability without feeding it into L2 or L3 behavior." -m "Constraint: Shadow frame construction must not write memory, state, or goal records" -m "Rejected: Replacing current L2/L3 payloads in this task | too broad for the contract slice" -m "Confidence: medium" -m "Scope-risk: moderate" -m "Tested: pytest backend/tests/test_character_runtime_shadow_mind_frame.py backend/tests/test_character_agent_runtime.py -v"
```

---

### Task 5: Document Shadow Frame Boundary

**Files:**
- Modify: `docs/character/character-mind-core-status.md`
- Modify: `docs/架构/运行时/模块/角色智能体.md`

- [ ] **Step 1: Update character mind-core status**

In `docs/character/character-mind-core-status.md`, add this section after the paragraph that lists `CharacterDynamicState` affect dimensions:

```markdown
### 分层心智因子投影

当前角色心智核心仍以 `L1 -> L2 -> L3 -> L4` 为主链。

`CharacterMindFrame` 是新增的 shadow contract，用于把长期档案、记忆证据、
运行态、可供性、认知工作区和回写候选分层表达。它不是新的心智中枢，也不替代
`L2/L3`。

边界：

- authored profile truth 仍由 `CharacterProfile` 和长期 drift overlay 表达。
- memory evidence 仍由五池记忆表达。
- social relationship network 仍属于 social memory，可在后续图谱化投影。
- runtime state 仍由 `NeedTensionState`、`CharacterDynamicState`、goal state 和 unresolved tension 表达。
- `CharacterMindFrame` 当前只作为 shadow read model，不改变既有决策行为。
```

- [ ] **Step 2: Update character agent runtime module doc**

In `docs/架构/运行时/模块/角色智能体.md`, add this section near the L2/L3 runtime context description:

```markdown
### Layered mind factor frame

The character agent keeps the existing four-layer runtime:

```text
L1 private perception
-> L2 subjective interpretation and cognition update
-> L3 goal arbitration and planning
-> L4 execution contract
```

The layered mind factor frame is a shadow read model above existing stores:

```text
profile + memory + relationship/social memory + need tension + dynamic state
+ goal state + unresolved tensions + supervision + affordances
-> CharacterMindFrame
-> L2/L3/L4 layer views
```

It does not make ESM responsible for cognition, does not make System L6 a mind
bus, and does not move skill state into L4.
```

- [ ] **Step 3: Run docs harness**

Run: `python scripts/verification/harness.py --profile docs`

Expected: PASS.

- [ ] **Step 4: Commit Task 5**

```bash
git add docs/character/character-mind-core-status.md docs/架构/运行时/模块/角色智能体.md
git commit -m "Document shadow mind frame boundaries" -m "The status and runtime module docs now describe CharacterMindFrame as a layered read model around the existing L1-L4 runtime instead of a replacement mind center." -m "Constraint: L1RuntimePerceptionBridge, System L6, ESM, and L4 ownership boundaries remain unchanged" -m "Confidence: high" -m "Scope-risk: narrow" -m "Tested: python scripts/verification/harness.py --profile docs"
```

---

### Task 6: Final Verification

**Files:**
- No source edits unless a verification command exposes a defect.

- [ ] **Step 1: Run focused mind-frame tests**

Run:

```bash
pytest backend/tests/test_character_mind_frame_models.py backend/tests/test_character_mind_frame_builder.py backend/tests/test_character_mind_context_views.py backend/tests/test_character_runtime_shadow_mind_frame.py -v
```

Expected: PASS.

- [ ] **Step 2: Run related character runtime tests**

Run:

```bash
pytest backend/tests/test_character_agent_runtime.py backend/tests/test_character_agent_l2_reasoning.py backend/tests/test_character_agent_l3_planning.py backend/tests/test_character_runtime_needs_affect_flow.py -v
```

Expected: PASS.

- [ ] **Step 3: Run docs harness**

Run: `python scripts/verification/harness.py --profile docs`

Expected: PASS.

- [ ] **Step 4: Run backend contract harness**

Run: `python scripts/verification/harness.py --profile backend-contract`

Expected: PASS.

- [ ] **Step 5: Run diff and worktree checks**

Run:

```bash
git diff --check
git status --short
```

Expected:

- `git diff --check` exits 0.
- `git status --short` is clean after all task commits.

- [ ] **Step 6: Record final verification in the task report**

Report these exact verification lines in the completion message:

```text
Focused mind-frame tests: passed
Related character runtime tests: passed
Docs harness: passed
Backend-contract harness: passed
git diff --check: passed
Worktree: clean
```

If a command fails, fix the defect in the smallest relevant task scope and rerun the same command before reporting completion.

---

## Follow-up Plan Series

Tasks 1-6 are the Phase 1/2 shadow-mode foundation. The remaining spec phases are split into a separate plan series so each phase can be executed, verified, and committed independently without rewriting this completed foundation plan.

Use the series index:

- `docs/superpowers/plans/2026-07-11-layered-character-mind-factor-plan-series.md`

The follow-up plans cover:

- Phase 3 projection services.
- Phase 4 skill/action affordance summaries.
- Phase 5 delta ledger and writeback policy routing.
- Phase 6 optional graph-backed memory projections.
