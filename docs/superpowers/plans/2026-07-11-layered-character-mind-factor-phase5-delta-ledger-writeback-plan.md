# Layered Character Mind Factor Phase 5 Delta Ledger Writeback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a typed `MindDeltaLedger` builder and writeback policy router that preserve existing store boundaries while wrapping L2/L3/L4/settlement outputs in one evidence-backed envelope.

**Architecture:** `MindDeltaLedgerBuilder` constructs an envelope without persistence. `MindWritebackPolicyRouter` applies ledgers through existing runtime/store paths. Authored profile truth, social memory, dynamic state, need tension, goal state, skill evidence candidates, and drift candidates stay separated.

**Tech Stack:** Python 3.13, Pydantic v2, pytest, existing `backend/app/character_agent` runtime models, no new dependencies.

---

## Scope Boundary

Included:

- Builder for `MindDeltaLedger` from interpretation, planning decision, execution proposal, settlement result, skill evidence, relationship candidates, drift candidates, and evidence refs.
- Runtime method for applying a ledger through a policy router.
- Tests proving ledger writeback uses current stores and does not mutate authored profile truth.

Excluded:

- Replacing every existing `_apply_cognition_update` call site.
- Promoting drift candidates into authored profile truth.
- Implementing full skill learning.
- Making the ledger directly write stores.

## File Structure

- `backend/app/character_agent/mind/delta_ledger.py`
  - Builder for `MindDeltaLedger`.
- `backend/app/character_agent/mind/writeback_policy.py`
  - Policy router that applies ledgers through existing runtime methods.
- `backend/app/character_agent/runtime/runtime_loop.py`
  - Adds `apply_mind_delta_ledger` and a small event append helper.
- `backend/app/character_agent/mind/__init__.py`
  - Public exports for ledger builder and writeback router.
- `backend/tests/test_character_mind_delta_ledger.py`
  - Ledger construction tests.
- `backend/tests/test_character_mind_writeback_policy.py`
  - Runtime writeback boundary tests.

---

### Task 1: Add Mind Delta Ledger Builder

**Files:**
- Create: `backend/app/character_agent/mind/delta_ledger.py`
- Modify: `backend/app/character_agent/mind/__init__.py`
- Test: `backend/tests/test_character_mind_delta_ledger.py`

- [ ] **Step 1: Write failing ledger tests**

Create `backend/tests/test_character_mind_delta_ledger.py`:

```python
from app.character_agent.mind.delta_ledger import MindDeltaLedgerBuilder
from app.character_agent.models.cognition_delta import (
    CharacterBeliefDelta,
    CharacterDynamicStateDelta,
    CharacterHigherOrderDelta,
    CharacterSocialDelta,
)
from app.models.character_agent_runtime import CharacterInterpretation


def test_delta_ledger_builder_wraps_l2_l3_l4_settlement_and_evidence_separately() -> None:
    interpretation = CharacterInterpretation(
        interpretation_type="social_signal",
        salience=0.8,
        risk_level="medium",
        opportunity_level="low",
        ambiguity_level="medium",
        interpreted_situation="B may be protecting a child.",
        suggested_goal="verify_emergency",
        belief_deltas=[
            CharacterBeliefDelta(
                proposition_key="b_motive",
                proposition="B's motive may be urgent aid",
                state="suspected",
                confidence=0.7,
            )
        ],
        social_deltas=[
            CharacterSocialDelta(entity_id="char_b", trust_baseline=0.75, suspicion_baseline=0.25)
        ],
        higher_order_deltas=[
            CharacterHigherOrderDelta(
                subject_actor_id="char_b",
                proposition_key="b_motive",
                meta_belief="B may believe the theft is justified",
                confidence=0.6,
            )
        ],
        dynamic_state_delta=CharacterDynamicStateDelta(stress_load=0.4),
    )

    ledger = MindDeltaLedgerBuilder().build(
        actor_id="char_a",
        mind_turn_id="mind_turn:char_a:1",
        interpretation=interpretation,
        l3_decision={
            "selected_intent": "speak_private",
            "active_goal_frame": {"primary_goal": "verify_emergency"},
        },
        l4_execution_proposal={"action_request_bundle": {"requested_actions": []}},
        settlement_result={"outcome_band": "partial"},
        skill_evidence=[{"skill_id": "authority_protocol", "outcome_band": "partial"}],
        drift_candidates=[{"key": "public_disclosure_caution", "direction": "up"}],
        evidence_refs=["event:1"],
    )

    assert ledger.belief_deltas[0]["proposition_key"] == "b_motive"
    assert ledger.social_deltas[0]["entity_id"] == "char_b"
    assert ledger.higher_order_deltas[0]["subject_actor_id"] == "char_b"
    assert ledger.dynamic_state_deltas == {"stress_load": 0.4}
    assert ledger.goal_deltas[0]["selected_intent"] == "speak_private"
    assert ledger.memory_write_candidates[0]["evidence_refs"] == ["event:1"]
    assert ledger.skill_evidence_deltas[0]["skill_id"] == "authority_protocol"
    assert ledger.drift_candidates[0]["key"] == "public_disclosure_caution"


def test_delta_ledger_builder_does_not_persist_or_mutate_inputs() -> None:
    l3_decision = {"selected_intent": "observe_target"}
    ledger = MindDeltaLedgerBuilder().build(
        actor_id="char_a",
        mind_turn_id="mind_turn:char_a:2",
        interpretation=None,
        l3_decision=l3_decision,
        evidence_refs=["event:2"],
    )
    l3_decision["selected_intent"] = "mutated"

    assert ledger.goal_deltas[0]["selected_intent"] == "observe_target"
    assert ledger.memory_write_candidates[0]["evidence_refs"] == ["event:2"]
```

- [ ] **Step 2: Run ledger tests and verify they fail**

Run: `pytest backend/tests/test_character_mind_delta_ledger.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'app.character_agent.mind.delta_ledger'`.

- [ ] **Step 3: Implement ledger builder**

Create `backend/app/character_agent/mind/delta_ledger.py`:

```python
from __future__ import annotations

from copy import deepcopy

from app.character_agent.models.mind_frame import MindDeltaLedger
from app.models.character_agent_runtime import CharacterInterpretation


def _model_or_mapping(value: object) -> dict[str, object]:
    if hasattr(value, "model_dump"):
        dumped = value.model_dump()
        return deepcopy(dumped) if isinstance(dumped, dict) else {}
    return deepcopy(value) if isinstance(value, dict) else {}


def _model_list(values: object) -> list[dict[str, object]]:
    if not isinstance(values, list):
        return []
    return [_model_or_mapping(value) for value in values]


class MindDeltaLedgerBuilder:
    def build(
        self,
        *,
        actor_id: str,
        mind_turn_id: str,
        interpretation: CharacterInterpretation | None = None,
        l3_decision: dict[str, object] | None = None,
        l4_execution_proposal: dict[str, object] | None = None,
        settlement_result: dict[str, object] | None = None,
        dialogue_or_action_outcome: dict[str, object] | None = None,
        need_tension_delta: dict[str, object] | None = None,
        skill_evidence: list[dict[str, object]] | None = None,
        relationship_update_candidates: list[dict[str, object]] | None = None,
        drift_candidates: list[dict[str, object]] | None = None,
        evidence_refs: list[str] | None = None,
    ) -> MindDeltaLedger:
        evidence = list(evidence_refs or [])
        l3_payload = deepcopy(l3_decision or {})
        l4_payload = deepcopy(l4_execution_proposal or {})
        settlement_payload = deepcopy(settlement_result or {})
        outcome_payload = deepcopy(dialogue_or_action_outcome or {})
        memory_candidate = {
            "event_type": "character_mind_turn_summary",
            "l3_decision": l3_payload,
            "l4_execution_proposal": l4_payload,
            "settlement_result": settlement_payload,
            "dialogue_or_action_outcome": outcome_payload,
            "evidence_refs": evidence,
        }
        return MindDeltaLedger(
            actor_id=actor_id,
            mind_turn_id=mind_turn_id,
            belief_deltas=_model_list(getattr(interpretation, "belief_deltas", [])),
            social_deltas=_model_list(getattr(interpretation, "social_deltas", [])),
            higher_order_deltas=_model_list(getattr(interpretation, "higher_order_deltas", [])),
            dynamic_state_deltas=self._dynamic_state_delta(interpretation),
            need_tension_deltas=deepcopy(need_tension_delta or {}),
            goal_deltas=[l3_payload] if l3_payload else [],
            skill_evidence_deltas=deepcopy(skill_evidence or []),
            memory_write_candidates=[memory_candidate],
            relationship_update_candidates=deepcopy(relationship_update_candidates or []),
            drift_candidates=deepcopy(drift_candidates or []),
        )

    @staticmethod
    def _dynamic_state_delta(interpretation: CharacterInterpretation | None) -> dict[str, object]:
        if interpretation is None:
            return {}
        delta = getattr(interpretation, "dynamic_state_delta", None)
        if delta is None:
            return {}
        if hasattr(delta, "as_mapping"):
            return deepcopy(delta.as_mapping())
        return _model_or_mapping(delta)
```

Modify `backend/app/character_agent/mind/__init__.py` to export `MindDeltaLedgerBuilder`.

- [ ] **Step 4: Run ledger tests**

Run:

```bash
pytest backend/tests/test_character_mind_delta_ledger.py backend/tests/test_character_mind_frame_models.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit Task 1**

```bash
git add backend/app/character_agent/mind/__init__.py backend/app/character_agent/mind/delta_ledger.py backend/tests/test_character_mind_delta_ledger.py
git commit -m "Wrap cognition outputs in a mind delta ledger" -m "The ledger builder collects L2 deltas, L3 decisions, L4 proposals, settlement outcomes, skill evidence, relationship candidates, drift candidates, and evidence refs without persisting them directly." -m "Constraint: Ledger construction is an envelope, not a writeback policy" -m "Rejected: Let L2/L3 write stores directly through the ledger | persistence must stay policy-gated" -m "Confidence: high" -m "Scope-risk: narrow" -m "Tested: pytest backend/tests/test_character_mind_delta_ledger.py backend/tests/test_character_mind_frame_models.py -v"
```

---

### Task 2: Route Mind Delta Ledger Through Existing Writeback Policies

**Files:**
- Create: `backend/app/character_agent/mind/writeback_policy.py`
- Modify: `backend/app/character_agent/runtime/runtime_loop.py`
- Modify: `backend/app/character_agent/mind/__init__.py`
- Test: `backend/tests/test_character_mind_writeback_policy.py`
- Test: `backend/tests/test_character_agent_cognition_writeback.py`

- [ ] **Step 1: Write failing writeback policy tests**

Create `backend/tests/test_character_mind_writeback_policy.py`:

```python
from app.character_agent.mind.delta_ledger import MindDeltaLedgerBuilder
from app.character_agent.runtime.runtime_loop import CharacterAgentRuntime
from app.character_agent.models.cognition_delta import CharacterBeliefDelta, CharacterDynamicStateDelta
from app.models.character_agent_runtime import CharacterInterpretation


def test_runtime_applies_ledger_writeback_through_existing_store_boundaries() -> None:
    runtime = CharacterAgentRuntime()
    interpretation = CharacterInterpretation(
        interpretation_type="social_signal",
        salience=0.8,
        risk_level="medium",
        opportunity_level="low",
        ambiguity_level="medium",
        interpreted_situation="B may need help.",
        suggested_goal="verify_emergency",
        belief_deltas=[
            CharacterBeliefDelta(
                proposition_key="b_needs_help",
                proposition="B may need help",
                state="suspected",
                confidence=0.8,
            )
        ],
        dynamic_state_delta=CharacterDynamicStateDelta(stress_load=0.5),
    )
    ledger = MindDeltaLedgerBuilder().build(
        actor_id="char_a",
        mind_turn_id="mind_turn:char_a:1",
        interpretation=interpretation,
        l3_decision={"selected_intent": "speak_private"},
        evidence_refs=["event:source"],
    )

    runtime.apply_mind_delta_ledger(
        actor_id="char_a",
        producer_ts=123,
        ledger=ledger,
    )

    timeline = runtime.get_session_timeline("char_a")
    event_types = [entry["event_type"] for entry in timeline]
    assert "knowledge_belief_event" in event_types
    assert "dynamic_state_event" in event_types
    assert "character_mind_turn_summary_event" in event_types
    assert runtime.get_dynamic_state("char_a")["stress_load"] == 0.5


def test_ledger_writeback_does_not_mutate_authored_profile_or_treat_social_graph_as_truth() -> None:
    runtime = CharacterAgentRuntime()
    before_profile = runtime._effective_profile_payload("char_a")
    ledger = MindDeltaLedgerBuilder().build(
        actor_id="char_a",
        mind_turn_id="mind_turn:char_a:2",
        interpretation=None,
        relationship_update_candidates=[
            {"entity_id": "char_b", "trust_baseline": 0.7, "source_refs": ["event:source"]}
        ],
        drift_candidates=[{"key": "caution", "direction": "up"}],
        evidence_refs=["event:source"],
    )

    runtime.apply_mind_delta_ledger(actor_id="char_a", producer_ts=124, ledger=ledger)

    after_profile = runtime._effective_profile_payload("char_a")
    timeline = runtime.get_session_timeline("char_a")

    assert before_profile == after_profile
    assert any(entry["event_type"] == "social_cognition_event" for entry in timeline)
    assert any(entry["event_type"] == "character_drift_candidate_event" for entry in timeline)
```

- [ ] **Step 2: Run writeback tests and verify they fail**

Run: `pytest backend/tests/test_character_mind_writeback_policy.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'app.character_agent.mind.writeback_policy'` or `AttributeError: 'CharacterAgentRuntime' object has no attribute 'apply_mind_delta_ledger'`.

- [ ] **Step 3: Implement writeback policy router**

Create `backend/app/character_agent/mind/writeback_policy.py`:

```python
from __future__ import annotations

from copy import deepcopy
from typing import Protocol

from app.character_agent.models.cognition_delta import (
    CharacterBeliefDelta,
    CharacterDynamicStateDelta,
    CharacterHigherOrderDelta,
    CharacterSocialDelta,
)
from app.character_agent.models.mind_frame import MindDeltaLedger
from app.models.character_agent_runtime import CharacterInterpretation


class MindLedgerRuntimePort(Protocol):
    def _apply_cognition_update(self, *, actor_id: str, producer_ts: int, interpretation: CharacterInterpretation) -> None: ...
    def _session_append_event(self, *, actor_id: str, event_type: str, producer_ts: int, payload: dict[str, object]) -> None: ...


class MindWritebackPolicyRouter:
    def apply(
        self,
        *,
        runtime: MindLedgerRuntimePort,
        actor_id: str,
        producer_ts: int,
        ledger: MindDeltaLedger,
    ) -> None:
        interpretation = CharacterInterpretation(
            interpretation_type="ledger_writeback",
            salience=0.0,
            risk_level="low",
            opportunity_level="low",
            ambiguity_level="low",
            interpreted_situation="mind ledger writeback",
            suggested_goal="",
            belief_deltas=[CharacterBeliefDelta(**delta) for delta in ledger.belief_deltas],
            social_deltas=[
                CharacterSocialDelta(**delta)
                for delta in ledger.social_deltas + ledger.relationship_update_candidates
                if str(delta.get("entity_id", "") or "")
            ],
            higher_order_deltas=[
                CharacterHigherOrderDelta(**delta)
                for delta in ledger.higher_order_deltas
                if str(delta.get("subject_actor_id", "") or "")
            ],
            dynamic_state_delta=CharacterDynamicStateDelta(**ledger.dynamic_state_deltas),
        )
        runtime._apply_cognition_update(
            actor_id=actor_id,
            producer_ts=producer_ts,
            interpretation=interpretation,
        )
        for candidate in ledger.memory_write_candidates:
            runtime._session_append_event(
                actor_id=actor_id,
                event_type="character_mind_turn_summary_event",
                producer_ts=producer_ts,
                payload=deepcopy(candidate),
            )
        for candidate in ledger.skill_evidence_deltas:
            runtime._session_append_event(
                actor_id=actor_id,
                event_type="character_skill_evidence_candidate_event",
                producer_ts=producer_ts,
                payload=deepcopy(candidate),
            )
        for candidate in ledger.drift_candidates:
            runtime._session_append_event(
                actor_id=actor_id,
                event_type="character_drift_candidate_event",
                producer_ts=producer_ts,
                payload=deepcopy(candidate),
            )
```

Modify `backend/app/character_agent/runtime/runtime_loop.py`:

Add imports:

```python
from app.character_agent.mind.writeback_policy import MindWritebackPolicyRouter
from app.character_agent.models.mind_frame import MindDeltaLedger
```

In `__init__`, add:

```python
        self._mind_writeback_policy = MindWritebackPolicyRouter()
```

Add helper methods:

```python
    def apply_mind_delta_ledger(
        self,
        *,
        actor_id: str,
        producer_ts: int,
        ledger: MindDeltaLedger | dict[str, object],
    ) -> None:
        typed_ledger = ledger if isinstance(ledger, MindDeltaLedger) else MindDeltaLedger(**ledger)
        self._mind_writeback_policy.apply(
            runtime=self,
            actor_id=actor_id,
            producer_ts=producer_ts,
            ledger=typed_ledger,
        )

    def _session_append_event(
        self,
        *,
        actor_id: str,
        event_type: str,
        producer_ts: int,
        payload: dict[str, object],
    ) -> None:
        stored = self._session_store.append_event(
            actor_id=actor_id,
            event_type=event_type,
            producer_ts=producer_ts,
            payload=payload,
        )
        self._memory_store.write_event(stored)
```

Do not replace existing `_apply_cognition_update` call sites in this task. This task adds an equivalent typed route for ledger-based writeback and proves boundary behavior.

Modify `backend/app/character_agent/mind/__init__.py` to export `MindWritebackPolicyRouter`.

- [ ] **Step 4: Run writeback policy and existing writeback tests**

Run:

```bash
pytest backend/tests/test_character_mind_writeback_policy.py backend/tests/test_character_agent_cognition_writeback.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit Task 2**

```bash
git add backend/app/character_agent/mind/__init__.py backend/app/character_agent/mind/writeback_policy.py backend/app/character_agent/runtime/runtime_loop.py backend/tests/test_character_mind_writeback_policy.py
git commit -m "Route mind ledgers through existing writeback boundaries" -m "MindDeltaLedger can now be applied through a policy router that delegates cognition deltas, memory summaries, skill evidence candidates, relationship updates, and drift candidates to existing runtime/store paths without mutating authored profile truth." -m "Constraint: Writeback policy owns persistence; ledger construction does not persist" -m "Rejected: Make the ledger directly write stores | would bypass existing boundary checks and evidence paths" -m "Confidence: medium" -m "Scope-risk: moderate" -m "Tested: pytest backend/tests/test_character_mind_writeback_policy.py backend/tests/test_character_agent_cognition_writeback.py -v"
```
