# Layered Character Mind Factor Phase 4 Affordances Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Feed bounded skill, action, environment, equipment, and physical feasibility summaries into planning and execution views without implementing the full skill system or moving settlement authority.

**Architecture:** Add an affordance adapter under `backend/app/character_agent/mind/affordances.py`. `CharacterMindFrameBuilder` accepts optional affordance summaries and emits affordance-layer cards; `LayerContextViewBuilder` exposes only summaries to L3/L4.

**Tech Stack:** Python 3.13, Pydantic v2, pytest, existing `backend/app/character_agent` runtime models, no new dependencies.

---

## Scope Boundary

Included:

- Profile capability constraints summarized as skill affordance hints.
- Supplied skill/action summaries passed through after registry-like internals are stripped.
- Environment, equipment, and physical feasibility summaries.
- L3/L4 views consume summaries only.

Excluded:

- Full Character Skill System implementation.
- Skill registry execution.
- Final action library.
- L4 deciding action success.
- ESM/physical settlement changes.

## File Structure

- `backend/app/character_agent/mind/affordances.py`
  - Affordance adapter and affordance-card projection.
- `backend/app/character_agent/mind/frame_builder.py`
  - Accepts and projects new optional affordance summaries.
- `backend/app/character_agent/mind/view_builder.py`
  - Copies physical feasibility from frame into L4 view.
- `backend/app/character_agent/mind/__init__.py`
  - Public export for `CharacterMindAffordanceAdapter`.
- `backend/tests/test_character_mind_affordances.py`
  - Tests summary boundaries and L3/L4 consumption.

---

### Task 1: Add Skill And Action Affordance Adapter

**Files:**
- Create: `backend/app/character_agent/mind/affordances.py`
- Modify: `backend/app/character_agent/mind/frame_builder.py`
- Modify: `backend/app/character_agent/mind/view_builder.py`
- Modify: `backend/app/character_agent/mind/__init__.py`
- Test: `backend/tests/test_character_mind_affordances.py`

- [ ] **Step 1: Write failing affordance tests**

Create `backend/tests/test_character_mind_affordances.py`:

```python
from app.character_agent.mind.affordances import CharacterMindAffordanceAdapter
from app.character_agent.mind.frame_builder import CharacterMindFrameBuilder
from app.character_agent.mind.view_builder import LayerContextViewBuilder
from app.character_agent.models.mind_frame import CognitionWorkspace


def test_affordance_adapter_summarizes_profile_skills_without_exposing_registry() -> None:
    summary = CharacterMindAffordanceAdapter().build_summary(
        effective_profile={
            "capability_constraint_layer": {
                "skills": ["authority_protocol", "persuasion"],
                "limits": ["cannot_falsify_authority_report"],
            }
        },
        supplied_skill_affordance_summary={
            "available_action_families": {"social_deescalation": {"level": "trained"}},
            "registry": {"internal": "must_not_leak"},
        },
        supplied_action_affordance_summary={"available_actions": ["speak_private"]},
        environment_affordance_summary={"nearby_objects": ["medicine_kit"]},
        equipment_affordance_summary={"held_items": ["lamp"]},
        physical_feasibility_summary={"mobility": "steady"},
    )

    assert summary["skill_affordance"]["profile_skill_ids"] == [
        "authority_protocol",
        "persuasion",
    ]
    assert "registry" not in summary["skill_affordance"]
    assert summary["action_affordance"]["available_actions"] == ["speak_private"]
    assert summary["environment_affordance"]["nearby_objects"] == ["medicine_kit"]
    assert summary["physical_feasibility"]["mobility"] == "steady"


def test_frame_builder_places_all_affordance_cards_in_affordance_layer() -> None:
    frame = CharacterMindFrameBuilder().build_frame(
        actor_id="char_a",
        producer_ts=1,
        effective_profile={
            "capability_constraint_layer": {
                "skills": ["authority_protocol"],
                "limits": ["cannot_falsify_authority_report"],
            }
        },
        skill_affordance_summary={"available_action_families": {"authority": {"level": "strong"}}},
        action_affordance_summary={"available_actions": ["speak_private"]},
        environment_affordance_summary={"nearby_objects": ["medicine_kit"]},
        equipment_affordance_summary={"held_items": ["lamp"]},
        physical_feasibility_summary={"mobility": "steady"},
    )

    cards_by_type = {card.factor_type: card for card in frame.affordances.cards}

    assert sorted(cards_by_type) == [
        "action_affordance",
        "environment_affordance",
        "equipment_affordance",
        "physical_feasibility",
        "skill_affordance",
    ]
    assert all(card.layer == "affordance" for card in frame.affordances.cards)
    assert cards_by_type["skill_affordance"].payload["profile_skill_ids"] == ["authority_protocol"]


def test_l3_and_l4_views_consume_affordance_summaries_without_settlement_authority() -> None:
    frame = CharacterMindFrameBuilder().build_frame(
        actor_id="char_a",
        producer_ts=1,
        skill_affordance_summary={"available_action_families": {"authority": {"level": "strong"}}},
        action_affordance_summary={"available_actions": ["speak_private"]},
        physical_feasibility_summary={"mobility": "steady"},
    )
    builder = LayerContextViewBuilder()

    l3_view = builder.build_l3_view(
        frame,
        interpretation_summary={"risk_level": "medium"},
        workspace=CognitionWorkspace(hard_constraints=["cannot_falsify_authority_report"]),
    )
    l4_view = builder.build_l4_view(
        frame,
        selected_intent="speak_private",
        selected_skill_path={"binding_id": "authority_to_speak_private"},
        target_refs={"actor": "char_b"},
    )

    assert l3_view.skill_affordance_summary["available_action_families"]["authority"]["level"] == "strong"
    assert l3_view.action_affordance_summary["available_actions"] == ["speak_private"]
    assert l4_view.physical_feasibility_summary["mobility"] == "steady"
    assert "settlement_result" not in l3_view.model_dump()
    assert "settlement_result" not in l4_view.model_dump()
```

- [ ] **Step 2: Run affordance tests and verify they fail**

Run: `pytest backend/tests/test_character_mind_affordances.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'app.character_agent.mind.affordances'` or `TypeError` for missing builder keyword arguments.

- [ ] **Step 3: Implement affordance adapter**

Create `backend/app/character_agent/mind/affordances.py`:

```python
from __future__ import annotations

from copy import deepcopy

from app.character_agent.models.mind_frame import MentalFactorProjectionCard


def _mapping(value: object) -> dict[str, object]:
    return deepcopy(value) if isinstance(value, dict) else {}


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item)]


class CharacterMindAffordanceAdapter:
    def build_summary(
        self,
        *,
        effective_profile: dict[str, object] | None = None,
        supplied_skill_affordance_summary: dict[str, object] | None = None,
        supplied_action_affordance_summary: dict[str, object] | None = None,
        environment_affordance_summary: dict[str, object] | None = None,
        equipment_affordance_summary: dict[str, object] | None = None,
        physical_feasibility_summary: dict[str, object] | None = None,
    ) -> dict[str, dict[str, object]]:
        profile = _mapping(effective_profile)
        capability = _mapping(profile.get("capability_constraint_layer"))
        skill_summary = _mapping(supplied_skill_affordance_summary)
        skill_summary.pop("registry", None)
        skill_summary["profile_skill_ids"] = _string_list(capability.get("skills"))
        skill_summary["profile_limits"] = _string_list(capability.get("limits"))
        return {
            "skill_affordance": skill_summary,
            "action_affordance": _mapping(supplied_action_affordance_summary),
            "environment_affordance": _mapping(environment_affordance_summary),
            "equipment_affordance": _mapping(equipment_affordance_summary),
            "physical_feasibility": _mapping(physical_feasibility_summary),
        }

    def project_cards(self, summaries: dict[str, dict[str, object]]) -> list[MentalFactorProjectionCard]:
        cards: list[MentalFactorProjectionCard] = []
        source_map = {
            "skill_affordance": "skill_affordance:summary",
            "action_affordance": "action_affordance:summary",
            "environment_affordance": "environment_affordance:summary",
            "equipment_affordance": "equipment_affordance:summary",
            "physical_feasibility": "physical_feasibility:summary",
        }
        for factor_type in [
            "skill_affordance",
            "action_affordance",
            "environment_affordance",
            "equipment_affordance",
            "physical_feasibility",
        ]:
            payload = _mapping(summaries.get(factor_type))
            cards.append(
                MentalFactorProjectionCard(
                    factor_type=factor_type,
                    layer="affordance",
                    scope="actor_private",
                    horizon="scene",
                    confidence=0.8 if payload else 0.0,
                    freshness="current" if payload else "unknown",
                    summary=f"{factor_type} summary" if payload else "",
                    payload=payload,
                    source_refs=[source_map[factor_type]] if payload else [],
                )
            )
        return cards
```

Modify `CharacterMindFrameBuilder.build_frame` to accept:

```python
        environment_affordance_summary: dict[str, object] | None = None,
        equipment_affordance_summary: dict[str, object] | None = None,
        physical_feasibility_summary: dict[str, object] | None = None,
```

Use `CharacterMindAffordanceAdapter` in `_affordance_layer` to produce all five affordance cards. Keep supplied summaries read-only by deep-copying through the adapter.

Modify `LayerContextViewBuilder.build_l4_view` so `physical_feasibility_summary` is copied from the frame's `physical_feasibility` card instead of always returning `{"status": "advisory"}`. Keep advisory fallback only when the card payload is empty.

Modify `backend/app/character_agent/mind/__init__.py` to export `CharacterMindAffordanceAdapter`.

- [ ] **Step 4: Run affordance and existing view tests**

Run:

```bash
pytest backend/tests/test_character_mind_affordances.py backend/tests/test_character_mind_frame_builder.py backend/tests/test_character_mind_context_views.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit Task 1**

```bash
git add backend/app/character_agent/mind/__init__.py backend/app/character_agent/mind/affordances.py backend/app/character_agent/mind/frame_builder.py backend/app/character_agent/mind/view_builder.py backend/tests/test_character_mind_affordances.py
git commit -m "Feed bounded affordance summaries into mind views" -m "Skill, action, environment, equipment, and physical feasibility inputs now enter the mind frame as affordance-layer summaries without exposing registries or taking settlement authority from ESM and physical channels." -m "Constraint: L3 sees summaries only; L4 does not decide action success" -m "Rejected: Implement full skill binding here | the approved skill system contract remains separate" -m "Confidence: high" -m "Scope-risk: moderate" -m "Tested: pytest backend/tests/test_character_mind_affordances.py backend/tests/test_character_mind_frame_builder.py backend/tests/test_character_mind_context_views.py -v"
```
