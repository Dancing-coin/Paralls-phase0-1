# Character Reasoning And Siming Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ground `L2` and `L3` in profile + memory + knowledge inputs, replace placeholder persona/logic filtering, and deepen the merged `Siming` path into a legal mentality influence protocol.

**Architecture:** Reuse the current `CharacterModelGateway`, but change the context contract so `L2` and `L3` receive structured profile views, Stage 2 memory pools, and explicit knowledge/social state. Keep `SimingCharacterCompatibilityInput` and `ingest_siming_output(...)` as the merged ingress, but normalize the catalyst semantics before planning.

**Tech Stack:** Python, current gateway/provider path, current Siming bridge, current runtime loop, pytest.

---

### Task 1: Thread profile and Stage 2 memory into gateway context

**Files:**
- Modify: `backend/app/character_agent/gateway/context_builder.py`
- Modify: `backend/app/character_agent/gateway/prompt_policy.py`
- Modify: `backend/app/character_agent/reasoning/l2_reasoner.py`
- Test: `backend/tests/test_character_context_builder.py`
- Test: `backend/tests/test_character_agent_l2_reasoning.py`

- [ ] **Step 1: Write failing context tests**

```python
from app.character_agent.gateway.context_builder import CharacterContextBuilder


def test_context_builder_includes_profile_and_stage2_memory() -> None:
    builder = CharacterContextBuilder()
    context = builder.build_context(
        actor_id="char_a",
        control_mode="agent_full_auto",
        snapshot={"actor_id": "char_a"},
        memory_bundle={
            "working_memory": [],
            "event_memories": [],
            "observation_memories": [],
            "knowledge_memories": [],
            "social_memories": [],
        },
        profile={"identity_core": {"character_id": "char_a"}},
        working_memory_state={},
    )
    assert "profile" in context
    assert "knowledge_memories" in context["memory"]
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest backend/tests/test_character_context_builder.py::test_context_builder_includes_profile_and_stage2_memory -v`
Expected: FAIL because context builder still lacks profile and Stage 2 memory keys.

- [ ] **Step 3: Extend context contract**

```python
context = {
    "actor_id": actor_id,
    "control_mode": control_mode,
    "snapshot": dict(snapshot),
    "profile": dict(profile),
    "memory": {
        "working_memory": list(memory_bundle.get("working_memory", [])),
        "event_memories": list(memory_bundle.get("event_memories", [])),
        "observation_memories": list(memory_bundle.get("observation_memories", [])),
        "knowledge_memories": list(memory_bundle.get("knowledge_memories", [])),
        "social_memories": list(memory_bundle.get("social_memories", [])),
    },
    "working_memory_state": dict(working_memory_state or {}),
}
```

- [ ] **Step 4: Update `L2` tests to assert profile-aware requests**

```python
assert run_request["context"]["profile"]["identity_core"]["character_id"] == "char_a"
assert "knowledge_memories" in run_request["context"]["memory"]
```

- [ ] **Step 5: Run L2/context tests**

Run: `pytest backend/tests/test_character_context_builder.py backend/tests/test_character_agent_l2_reasoning.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/character_agent/gateway/context_builder.py backend/app/character_agent/gateway/prompt_policy.py backend/app/character_agent/reasoning/l2_reasoner.py backend/tests/test_character_context_builder.py backend/tests/test_character_agent_l2_reasoning.py
git commit -m "Thread profile and Stage 2 memory into L2 context

Constraint: L2 cannot become a real interpretation layer without profile and knowledge-aware context
Rejected: Keep current snapshot-only emphasis and patch behavior in provider heuristics | preserves thin cognition
Confidence: high
Scope-risk: moderate
Directive: Any future reasoning task must receive profile and Stage 2 memory through the same context contract
Tested: pytest backend/tests/test_character_context_builder.py backend/tests/test_character_agent_l2_reasoning.py -v
Not-tested: end-to-end runtime effects"
```

### Task 2: Replace placeholder persona/logic filtering in L3

**Files:**
- Modify: `backend/app/character_agent/planning/triple_filter.py`
- Modify: `backend/app/character_agent/planning/l3_planner.py`
- Test: `backend/tests/test_character_agent_l3_planning.py`
- Test: `backend/tests/test_character_agent_triple_filter.py`

- [ ] **Step 1: Write failing L3 filter tests**

```python
from app.character_agent.planning.l3_planner import CharacterAgentL3Service
from app.models.character_agent_runtime import CharacterInterpretation


def test_l3_persona_filter_can_reject_share_info_for_guarded_private_role() -> None:
    service = CharacterAgentL3Service()
    interpretation = CharacterInterpretation(
        actor_id="char_a",
        interpreted_summary="someone is asking for private information",
        interpretation_type="social_probe",
        salience_score=0.8,
        ambiguity_level="low",
        risk_level="medium",
        opportunity_level="low",
        attention_target="char_b",
    )
    decision = service.select_intent(
        interpretation,
        snapshot={"vigilance_level": "elevated"},
        memory_bundle={
            "working_memory": [],
            "event_memories": [],
            "observation_memories": [],
            "knowledge_memories": [],
            "social_memories": [{"entity_id": "char_b", "trust_baseline": "guarded"}],
        },
        profile={
            "conversation_personality_layer": {"privacy_sensitivity": 0.9},
            "virtue_value_layer": {"value_priorities": ["self_protection"]},
        },
    )
    assert decision.selected_intent != "share_info"
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest backend/tests/test_character_agent_l3_planning.py::test_l3_persona_filter_can_reject_share_info_for_guarded_private_role -v`
Expected: FAIL because planner still hardcodes `persona_ok = True`.

- [ ] **Step 3: Replace placeholder filter scoring**

```python
def _score_candidate(self, candidate: str, interpretation: CharacterInterpretation, *, snapshot: dict[str, object], memory_bundle: dict[str, list[dict[str, object]]], profile: dict[str, object]) -> dict[str, object]:
    persona_ok = self._persona_allows(candidate, profile=profile)
    logic_ok = self._logic_allows(candidate, interpretation=interpretation, snapshot=snapshot, memory_bundle=memory_bundle)
    gain_loss_score = self._gain_loss_score(candidate, interpretation=interpretation, snapshot=snapshot, memory_bundle=memory_bundle, profile=profile)
    return self._triple_filter.evaluate_candidate(
        candidate=candidate,
        persona_ok=persona_ok,
        logic_ok=logic_ok,
        gain_loss_score=gain_loss_score,
    )
```

- [ ] **Step 4: Add minimal concrete rules**

```python
def _persona_allows(self, candidate: str, profile: dict[str, object]) -> bool:
    conversation = profile.get("conversation_personality_layer", {})
    if candidate == "share_info" and float(conversation.get("privacy_sensitivity", 0.0) or 0.0) >= 0.8:
        return False
    return True
```

Expected next step: grow these rules across value priorities, forbidden behaviors, and social memory.

- [ ] **Step 5: Run planner/filter tests**

Run: `pytest backend/tests/test_character_agent_l3_planning.py backend/tests/test_character_agent_triple_filter.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/character_agent/planning/triple_filter.py backend/app/character_agent/planning/l3_planner.py backend/tests/test_character_agent_l3_planning.py backend/tests/test_character_agent_triple_filter.py
git commit -m "Replace placeholder L3 filters with profile- and memory-aware scoring

Constraint: Stage 2 requires real persona/logic/gain-loss filtering instead of always-true placeholders
Rejected: Hide filtering only inside model-provider heuristics | removes local auditability
Confidence: medium
Scope-risk: broad
Directive: Keep filter outcomes locally explainable even when model guidance exists
Tested: pytest backend/tests/test_character_agent_l3_planning.py backend/tests/test_character_agent_triple_filter.py -v
Not-tested: full candidate diversity in scene runtime"
```

### Task 3: Deepen merged Siming input into a mentality protocol

**Files:**
- Modify: `backend/app/models/siming_character_bridge.py`
- Modify: `backend/app/character_agent/reasoning/l1_perception.py`
- Modify: `backend/app/character_agent/runtime/runtime_loop.py`
- Modify: `backend/app/character_agent/gateway/model_provider.py`
- Test: `backend/tests/test_siming_character_bridge_models.py`
- Test: `backend/tests/test_character_agent_runtime.py`
- Test: `backend/tests/test_siming_llm_runtime.py`

- [ ] **Step 1: Write the failing Siming mentality tests**

```python
from app.models.siming_character_bridge import SimingCharacterCompatibilityInput
from app.services.character_agent_runtime import CharacterAgentRuntime


def test_siming_message_carries_stage2_band_and_hint_fields() -> None:
    message = SimingCharacterCompatibilityInput(
        message_id="msg-1",
        delivery_id="delivery-1",
        actor_id="char_a",
        input_type="siming_high_level_message",
        band="fact_reveal",
        producer_ts=10,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        causation_id="cause-1",
        correlation_id="corr-1",
        presentation_hint="watch the letter",
    )
    assert message.band == "fact_reveal"


def test_siming_ingest_elevates_attention_without_bypassing_planning() -> None:
    runtime = CharacterAgentRuntime()
    runtime.ingest_siming_output(
        {
            "actor_id": "char_a",
            "target_actor_id": "char_a",
            "presentation_hint": "watch the letter",
            "target_object_id": "obj_letter",
            "producer_ts": 10,
        }
    )
    snapshot = runtime.get_private_snapshot("char_a")
    assert snapshot.vigilance_level == "elevated"
    assert snapshot.current_attention_targets == ["obj_letter"]
```

- [ ] **Step 2: Run tests to verify current gaps**

Run: `pytest backend/tests/test_siming_character_bridge_models.py backend/tests/test_character_agent_runtime.py -v`
Expected: mixed FAIL/weak assertions because current Siming path raises vigilance but does not yet encode fuller mentality semantics.

- [ ] **Step 3: Extend bridge semantics without breaking legality**

```python
class SimingCharacterCompatibilityInput(BaseModel):
    ...
    pressure_hint: str | None = None
    salience_boost: float | None = None
    reason_scope: str | None = None
```

Rule: keep forbidden low-level control fields forbidden.

- [ ] **Step 4: Extend `L1` and runtime interpretation handoff**

```python
snapshot.last_siming_catalyst = str(payload.get("presentation_hint", "") or "")
if snapshot.last_siming_catalyst != "":
    snapshot.vigilance_level = "elevated"
if str(payload.get("pressure_hint", "") or "") != "":
    snapshot.distraction_level = "elevated"
```

Expected next change: thread `pressure_hint`/`salience_boost` into `L2` request context and `L3` rank ordering instead of only toggling snapshot flags.

- [ ] **Step 5: Run Siming/runtime tests**

Run: `pytest backend/tests/test_siming_character_bridge_models.py backend/tests/test_character_agent_runtime.py backend/tests/test_siming_llm_runtime.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/models/siming_character_bridge.py backend/app/character_agent/reasoning/l1_perception.py backend/app/character_agent/runtime/runtime_loop.py backend/app/character_agent/gateway/model_provider.py backend/tests/test_siming_character_bridge_models.py backend/tests/test_character_agent_runtime.py backend/tests/test_siming_llm_runtime.py
git commit -m "Deepen merged Siming input into a legal mentality protocol

Constraint: Siming is now mainline truth but must remain upstream catalyst, not agency bypass
Rejected: Let Siming inject direct action choices or low-level control hints | violates Stage 2 role-agency boundaries
Confidence: medium
Scope-risk: broad
Directive: Any new Siming field must remain high-level and mentality-facing
Tested: pytest backend/tests/test_siming_character_bridge_models.py backend/tests/test_character_agent_runtime.py backend/tests/test_siming_llm_runtime.py -v
Not-tested: broad Godot scene verification"
```
