# Layered Character Mind Factor Phase 3 Projection Services Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add projection services that convert owned profile, memory, relationship, need, affect, goal, tension, and supervision sources into read-only `CharacterMindFrame` cards.

**Architecture:** Add projector classes under `backend/app/character_agent/mind/projectors.py` and make `CharacterMindFrameBuilder` delegate card creation to them. Source stores remain authoritative; projectors only summarize source payloads into layer-aware cards.

**Tech Stack:** Python 3.13, Pydantic v2, pytest, existing `backend/app/character_agent` runtime models, no new dependencies.

---

## Scope Boundary

Included:

- Effective profile projection.
- Memory activation, cognitive anchor, knowledge context, relationship context, and higher-order belief projection.
- Need pressure, affective body state, goal context, unresolved tension, and supervision projection.
- Existing frame builder continues to return the same public frame shape.

Excluded:

- Graph-backed projection provider.
- Skill/action affordance adapter.
- Ledger writeback.
- L2/L3 prompt-path replacement.

## File Structure

- `backend/app/character_agent/mind/projectors.py`
  - Read-only projector services that convert owned source payloads into `MentalFactorProjectionCard` objects.
- `backend/app/character_agent/mind/frame_builder.py`
  - Delegates card construction to projector services while preserving the existing `build_frame` signature.
- `backend/app/character_agent/mind/__init__.py`
  - Public exports for projector classes.
- `backend/tests/test_character_mind_projectors.py`
  - Projection service tests proving layer ownership and source refs.

---

### Task 1: Add Projection Services

**Files:**
- Create: `backend/app/character_agent/mind/projectors.py`
- Modify: `backend/app/character_agent/mind/frame_builder.py`
- Modify: `backend/app/character_agent/mind/__init__.py`
- Test: `backend/tests/test_character_mind_projectors.py`

- [ ] **Step 1: Write failing projector tests**

Create `backend/tests/test_character_mind_projectors.py`:

```python
from app.character_agent.mind.projectors import (
    AffectiveBodyStateProjector,
    EffectiveProfileProjector,
    GoalContextProjector,
    MemoryActivationProjector,
    NeedPressureProjector,
    RelationshipContextProjector,
    SupervisionProjector,
    UnresolvedTensionProjector,
)
from app.character_agent.models.mind_frame import MentalFactorProjectionCard


def test_effective_profile_projector_emits_enduring_truth_cards() -> None:
    cards = EffectiveProfileProjector().project(
        actor_id="char_a",
        effective_profile={
            "identity_core": {"canonical_name": "A"},
            "virtue_value_layer": {"red_lines": ["do_not_falsify_authority_report"]},
            "trait_vector_layer": {"openness": 0.4},
            "conversation_personality_layer": {"tone": "formal"},
        },
    )

    assert [card.factor_type for card in cards] == [
        "effective_profile",
        "authored_constraint",
        "personality_bias",
    ]
    assert all(card.layer == "enduring_truth" for card in cards)
    assert cards[0].source_refs == ["profile:char_a"]
    assert cards[1].payload["red_lines"] == ["do_not_falsify_authority_report"]


def test_memory_projectors_keep_memory_and_relationship_context_memory_owned() -> None:
    memory_bundle = {
        "event_memories": [{"memory_id": "event:1", "summary": "B once saved A"}],
        "knowledge_memories": [{"memory_id": "knowledge:1", "proposition": "B is a medic"}],
        "higher_order_memories": [
            {
                "memory_id": "higher:1",
                "subject_actor_id": "char_b",
                "proposition_key": "b_motive",
                "meta_belief": "B may be protecting a child",
            }
        ],
        "social_memories": [
            {
                "memory_id": "social:char_a:char_b",
                "entity_id": "char_b",
                "trust_baseline": 0.8,
                "suspicion_baseline": 0.2,
            }
        ],
    }

    memory_cards = MemoryActivationProjector().project(memory_bundle)
    relationship_cards = RelationshipContextProjector().project(
        actor_id="char_a",
        social_memories=memory_bundle["social_memories"],
    )

    assert [card.factor_type for card in memory_cards] == [
        "memory_activation",
        "cognitive_anchor",
        "knowledge_context",
        "higher_order_belief",
    ]
    assert all(card.layer == "memory_evidence" for card in memory_cards)
    assert relationship_cards[0].factor_type == "relationship_context"
    assert relationship_cards[0].layer == "memory_evidence"
    assert relationship_cards[0].source_refs == ["social_memory:char_a:char_b"]


def test_runtime_state_projectors_emit_need_affect_goal_tension_and_supervision_cards() -> None:
    cards: list[MentalFactorProjectionCard] = []
    cards.extend(NeedPressureProjector().project({"dominant_need": "esteem", "esteem_pressure": 0.4}))
    cards.extend(AffectiveBodyStateProjector().project({"stress_load": 0.6, "affect_valence": -0.2}))
    cards.extend(
        GoalContextProjector().project(
            current_goal_state={"primary_goal": "verify_emergency"},
            goal_state_history=[{"primary_goal": "preserve_order"}],
        )
    )
    cards.extend(UnresolvedTensionProjector().project([{"summary": "order versus loyalty"}]))
    cards.extend(SupervisionProjector().project({"authorization_level": "none"}))

    assert [card.factor_type for card in cards] == [
        "need_pressure",
        "affective_body_state",
        "goal_context",
        "unresolved_tension",
        "supervision",
    ]
    assert all(card.layer == "runtime_state" for card in cards)
    assert cards[2].payload["goal_state_history_count"] == 1
```

- [ ] **Step 2: Run projector tests and verify they fail**

Run: `pytest backend/tests/test_character_mind_projectors.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'app.character_agent.mind.projectors'`.

- [ ] **Step 3: Implement projector services**

Create `backend/app/character_agent/mind/projectors.py`:

```python
from __future__ import annotations

from copy import deepcopy
from typing import Iterable

from app.character_agent.models.mind_frame import MentalFactorProjectionCard


def _mapping(value: object) -> dict[str, object]:
    return deepcopy(value) if isinstance(value, dict) else {}


def _dict_list(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    return [deepcopy(item) for item in value if isinstance(item, dict)]


def _first_text(entries: Iterable[dict[str, object]], *keys: str) -> str:
    for entry in entries:
        for key in keys:
            text = str(entry.get(key, "") or "")
            if text:
                return text
    return ""


def _memory_ref(prefix: str, entry: dict[str, object]) -> str:
    value = str(
        entry.get("memory_id", "")
        or entry.get("source_event_id", "")
        or entry.get("proposition_key", "")
        or ""
    )
    return f"{prefix}:{value}" if value else ""


class EffectiveProfileProjector:
    def project(
        self,
        *,
        actor_id: str,
        effective_profile: dict[str, object] | None,
    ) -> list[MentalFactorProjectionCard]:
        profile = _mapping(effective_profile)
        identity = _mapping(profile.get("identity_core"))
        values = _mapping(profile.get("virtue_value_layer"))
        trait_vector = _mapping(profile.get("trait_vector_layer"))
        conversation = _mapping(profile.get("conversation_personality_layer"))
        temperament = _mapping(profile.get("temperament_response_layer"))
        red_lines = values.get("red_lines", [])
        red_lines = deepcopy(red_lines) if isinstance(red_lines, list) else []
        return [
            MentalFactorProjectionCard(
                factor_type="effective_profile",
                layer="enduring_truth",
                scope="actor_private",
                horizon="long_term",
                confidence=1.0,
                freshness="current",
                summary=str(identity.get("canonical_name", "") or actor_id),
                payload={
                    "identity_core": identity,
                    "trait_vector_keys": sorted(str(key) for key in trait_vector),
                    "red_lines": red_lines,
                },
                source_refs=[f"profile:{actor_id}"],
            ),
            MentalFactorProjectionCard(
                factor_type="authored_constraint",
                layer="enduring_truth",
                scope="actor_private",
                horizon="long_term",
                confidence=1.0,
                freshness="current",
                summary=", ".join(str(item) for item in red_lines),
                payload={"red_lines": red_lines},
                source_refs=[f"profile:{actor_id}:virtue_value_layer"],
            ),
            MentalFactorProjectionCard(
                factor_type="personality_bias",
                layer="enduring_truth",
                scope="actor_private",
                horizon="long_term",
                confidence=0.9,
                freshness="current",
                summary=str(conversation.get("tone", "") or temperament.get("default_reactivity", "") or ""),
                payload={
                    "conversation_personality_layer": conversation,
                    "temperament_response_layer": temperament,
                },
                source_refs=[f"profile:{actor_id}:personality_layers"],
            ),
        ]


class MemoryActivationProjector:
    def project(self, memory_bundle: dict[str, object] | None) -> list[MentalFactorProjectionCard]:
        bundle = _mapping(memory_bundle)
        events = _dict_list(bundle.get("event_memories"))
        observations = _dict_list(bundle.get("observation_memories"))
        knowledge = _dict_list(bundle.get("knowledge_memories"))
        higher_order = _dict_list(bundle.get("higher_order_memories"))
        refs = [
            ref
            for ref in [_memory_ref("memory", entry) for entry in events + observations + knowledge + higher_order]
            if ref
        ]
        return [
            MentalFactorProjectionCard(
                factor_type="memory_activation",
                layer="memory_evidence",
                scope="actor_private",
                horizon="scene",
                confidence=0.8,
                freshness="recent",
                summary=_first_text(events, "summary"),
                payload={
                    "event_memory_count": len(events),
                    "observation_memory_count": len(observations),
                    "knowledge_memory_count": len(knowledge),
                    "higher_order_memory_count": len(higher_order),
                },
                source_refs=refs,
            ),
            MentalFactorProjectionCard(
                factor_type="cognitive_anchor",
                layer="memory_evidence",
                scope="actor_private",
                horizon="scene",
                confidence=0.75,
                freshness="recent",
                summary=_first_text(events + observations, "summary", "observation_summary"),
                payload={"active_anchors": [entry.get("summary", "") for entry in events if entry.get("summary")]},
                source_refs=refs,
            ),
            MentalFactorProjectionCard(
                factor_type="knowledge_context",
                layer="memory_evidence",
                scope="actor_private",
                horizon="scene",
                confidence=0.75,
                freshness="recent",
                summary=_first_text(knowledge, "proposition", "summary"),
                payload={"knowledge_memory_count": len(knowledge)},
                source_refs=[ref for ref in [_memory_ref("knowledge_memory", entry) for entry in knowledge] if ref],
            ),
            MentalFactorProjectionCard(
                factor_type="higher_order_belief",
                layer="memory_evidence",
                scope="actor_private",
                horizon="scene",
                confidence=0.75,
                freshness="recent",
                summary=_first_text(higher_order, "meta_belief", "summary"),
                payload={"higher_order_memory_count": len(higher_order)},
                source_refs=[ref for ref in [_memory_ref("higher_order_memory", entry) for entry in higher_order] if ref],
            ),
        ]


class RelationshipContextProjector:
    def project(
        self,
        *,
        actor_id: str,
        social_memories: list[dict[str, object]] | None,
    ) -> list[MentalFactorProjectionCard]:
        memories = _dict_list(social_memories)
        top_target = str(memories[0].get("entity_id", "") or "") if memories else ""
        return [
            MentalFactorProjectionCard(
                factor_type="relationship_context",
                layer="memory_evidence",
                scope="actor_private",
                horizon="scene",
                confidence=0.8,
                freshness="recent",
                summary=f"target={top_target}" if top_target else "",
                payload={"target_count": len(memories), "top_target": top_target},
                source_refs=[
                    f"social_memory:{actor_id}:{entry.get('entity_id', '')}"
                    for entry in memories
                    if str(entry.get("entity_id", "") or "")
                ],
            )
        ]


class NeedPressureProjector:
    def project(self, need_tension_state: dict[str, object] | None) -> list[MentalFactorProjectionCard]:
        payload = _mapping(need_tension_state)
        return [
            MentalFactorProjectionCard(
                factor_type="need_pressure",
                layer="runtime_state",
                summary=str(payload.get("dominant_need", "") or ""),
                payload=payload,
                source_refs=["need_tension_state:current"] if payload else [],
            )
        ]


class AffectiveBodyStateProjector:
    def project(self, dynamic_state: dict[str, object] | None) -> list[MentalFactorProjectionCard]:
        payload = _mapping(dynamic_state)
        return [
            MentalFactorProjectionCard(
                factor_type="affective_body_state",
                layer="runtime_state",
                summary=f"stress_load={payload.get('stress_load', 0.0)}",
                payload=payload,
                source_refs=["dynamic_state:current"] if payload else [],
            )
        ]


class GoalContextProjector:
    def project(
        self,
        *,
        current_goal_state: dict[str, object] | None,
        goal_state_history: list[dict[str, object]] | None,
    ) -> list[MentalFactorProjectionCard]:
        current = _mapping(current_goal_state)
        history = _dict_list(goal_state_history)
        return [
            MentalFactorProjectionCard(
                factor_type="goal_context",
                layer="runtime_state",
                summary=str(current.get("primary_goal", "") or ""),
                payload={"current_goal_state": current, "goal_state_history_count": len(history)},
                source_refs=["goal_state:current"] if current else [],
            )
        ]


class UnresolvedTensionProjector:
    def project(self, unresolved_tensions: list[dict[str, object]] | None) -> list[MentalFactorProjectionCard]:
        tensions = _dict_list(unresolved_tensions)
        return [
            MentalFactorProjectionCard(
                factor_type="unresolved_tension",
                layer="runtime_state",
                summary=_first_text(tensions, "summary"),
                payload={"unresolved_tension_count": len(tensions)},
                source_refs=["unresolved_tensions:current"] if tensions else [],
            )
        ]


class SupervisionProjector:
    def project(self, supervision_state: dict[str, object] | None) -> list[MentalFactorProjectionCard]:
        payload = _mapping(supervision_state)
        return [
            MentalFactorProjectionCard(
                factor_type="supervision",
                layer="runtime_state",
                summary=str(payload.get("authorization_level", "") or payload.get("mode", "") or ""),
                payload=payload,
                source_refs=["supervision_state:current"] if payload else [],
            )
        ]
```

Modify `backend/app/character_agent/mind/frame_builder.py` so `_enduring_truth_layer`, `_memory_evidence_layer`, and `_runtime_state_layer` delegate card creation to these projectors while preserving existing public `build_frame` signature and layer summaries. Do not change `CharacterAgentRuntime` behavior in this task.

Modify `backend/app/character_agent/mind/__init__.py`:

```python
from app.character_agent.mind.frame_builder import CharacterMindFrameBuilder
from app.character_agent.mind.projectors import (
    AffectiveBodyStateProjector,
    EffectiveProfileProjector,
    GoalContextProjector,
    MemoryActivationProjector,
    NeedPressureProjector,
    RelationshipContextProjector,
    SupervisionProjector,
    UnresolvedTensionProjector,
)
from app.character_agent.mind.view_builder import LayerContextViewBuilder

__all__ = [
    "AffectiveBodyStateProjector",
    "CharacterMindFrameBuilder",
    "EffectiveProfileProjector",
    "GoalContextProjector",
    "LayerContextViewBuilder",
    "MemoryActivationProjector",
    "NeedPressureProjector",
    "RelationshipContextProjector",
    "SupervisionProjector",
    "UnresolvedTensionProjector",
]
```

- [ ] **Step 4: Run projector and existing builder tests**

Run:

```bash
pytest backend/tests/test_character_mind_projectors.py backend/tests/test_character_mind_frame_builder.py backend/tests/test_character_mind_context_views.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit Task 1**

```bash
git add backend/app/character_agent/mind/__init__.py backend/app/character_agent/mind/frame_builder.py backend/app/character_agent/mind/projectors.py backend/tests/test_character_mind_projectors.py
git commit -m "Project mind factors through owned source services" -m "Projection services now build read-only mind frame cards from profile, memory, relationship, need, affect, goal, tension, and supervision sources while keeping those stores authoritative." -m "Constraint: Projection is a read model and must not become a second truth source" -m "Rejected: Move projection logic into L2 or L3 | would blur cognition with source-store summarization" -m "Confidence: high" -m "Scope-risk: moderate" -m "Tested: pytest backend/tests/test_character_mind_projectors.py backend/tests/test_character_mind_frame_builder.py backend/tests/test_character_mind_context_views.py -v"
```
