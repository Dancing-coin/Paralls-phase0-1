# Character Needs, Personality, and Affect Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add structured needs, temperament response, multi-timescale affect, and conservative long-term personality drift to the character runtime without breaking the current authored-profile truth model.

**Architecture:** Extend the existing `CharacterProfile` truth source with explicit needs and temperament layers, add runtime `NeedTensionState` and richer `CharacterDynamicState` structures, then insert `EffectiveProfileResolver`, `NeedTensionEngine`, `AffectEngine`, and drift accumulation/promotion gates into the current `CharacterAgentRuntime -> L2 -> L3` path. Keep authored profile truth separate from runtime state and write long-term changes only into a drift layer.

**Tech Stack:** Python 3, Pydantic models, existing `CharacterAgentRuntime` / `L2Reasoner` / `L3Planner` / store classes, pytest, harness docs workflow

---

## Status Snapshot

Status: `implemented-and-focused-verified`.

The historical task checkboxes below predate the final code merge. Current main
contains the profile schema, effective-profile resolver, need tension and affect
engines, runtime store/writeback path, L2/L3 consumption, and conservative
drift gate described by this plan. Focused verification is covered by:

- `backend/tests/test_character_profile_needs_schema.py`
- `backend/tests/test_need_tension_engine.py`
- `backend/tests/test_affect_engine.py`
- `backend/tests/test_character_runtime_needs_affect_flow.py`
- `backend/tests/test_personality_drift_gate.py`

Strict long-term personality mutation of authored truth remains guarded by the
drift promotion gate and is not automatic runtime writeback.

## File Structure

### New files

- `backend/app/character_agent/profile/effective_profile.py`
  - Resolve authored profile + drift layer into runtime-effective profile payload.
- `backend/app/character_agent/models/need_tension.py`
  - `NeedTensionState`, `NeedTensionDelta`, and supporting maps.
- `backend/app/character_agent/logic/need_tension_engine.py`
  - Structured demand-pressure computation from profile + event + state.
- `backend/app/character_agent/logic/affect_engine.py`
  - Affect/tension state delta computation from profile + need tension + interpretation precursor.
- `backend/app/character_agent/storage/need_tension_store.py`
  - Runtime storage for `NeedTensionState`.
- `backend/app/character_agent/models/drift_candidate.py`
  - Candidate record for long-term personality drift.
- `backend/app/character_agent/logic/drift_accumulator.py`
  - Collect long-term drift evidence candidates.
- `backend/app/character_agent/logic/drift_promotion_gate.py`
  - Conservative promotion rules for writing drift into profile-layer state.
- `backend/tests/test_character_profile_needs_schema.py`
  - Schema coverage for profile additions.
- `backend/tests/test_need_tension_engine.py`
  - Demand-pressure engine behavior.
- `backend/tests/test_affect_engine.py`
  - Affect/tension delta behavior.
- `backend/tests/test_character_runtime_needs_affect_flow.py`
  - Runtime integration path and store writeback.
- `backend/tests/test_personality_drift_gate.py`
  - Drift accumulation and promotion constraints.

### Modified files

- `backend/app/character_agent/profile/models.py`
  - Add profile-layer Pydantic models and extend `CharacterProfile`.
- `backend/app/character_agent/profile/registry.py`
  - No API change expected; verify new models load through existing registry.
- `backend/app/character_agent/runtime/runtime_loop.py`
  - Wire `EffectiveProfileResolver`, `NeedTensionStore`, `NeedTensionEngine`, `AffectEngine`, and drift helpers into the runtime loop.
- `backend/app/character_agent/models/dynamic_state.py`
  - Expand dynamic state into affect/tension/motivation groups while preserving compatibility fields.
- `backend/app/character_agent/storage/dynamic_state_store.py`
  - Support expanded state merge/write semantics.
- `backend/app/character_agent/reasoning/l2_reasoner.py`
  - Pass effective profile, need tension state, and richer dynamic state into reasoning context.
- `backend/app/character_agent/planning/l3_planner.py`
  - Consume need tension and affect-aware fields in planning inputs and summaries.
- `backend/app/character_agent/gateway/prompt_policy.py`
  - Surface new profile and state summaries to structured model prompts.
- `assets/characters/profiles/char_a.yaml`
- `assets/characters/profiles/char_b.yaml`
- `assets/characters/profiles/char_c.yaml`
  - Add authored example data for new profile layers.
- `assets/characters/profiles/README.md`
  - Update profile authoring guidance.
- `docs/character/character-mind-core-status.md`
  - Align documentation with the new runtime layers after implementation.

---

### Task 1: Extend Profile Schema

**Files:**
- Modify: `backend/app/character_agent/profile/models.py`
- Modify: `assets/characters/profiles/char_a.yaml`
- Modify: `assets/characters/profiles/char_b.yaml`
- Modify: `assets/characters/profiles/char_c.yaml`
- Modify: `assets/characters/profiles/README.md`
- Test: `backend/tests/test_character_profile_needs_schema.py`

- [ ] **Step 1: Write the failing schema test**

```python
from app.character_agent.profile.loader import CharacterProfileLoader


def test_character_profile_loader_accepts_needs_temperament_and_drift_layers(tmp_path):
    profile_path = tmp_path / "char_test.yaml"
    profile_path.write_text(
        """
identity_core:
  character_id: char_test
  canonical_name: Test Person
  aliases: []
  occupation_role: witness
origin_seed:
  homeland: low district
  formative_context: careful upbringing
  current_scene_function: observer
life_memory_backbone:
  defining_memories: []
  unresolved_knots: []
virtue_value_layer:
  value_priorities: [care]
  red_lines: [betray trust]
  forbidden_behaviors: [fabricate authority]
trait_vector_layer:
  courage: 0.4
  scheming: 0.2
  empathy: 0.8
  rationality: 0.7
  sociability: 0.5
capability_constraint_layer:
  skills: []
  knowledge_domains: []
  physical_constraints: []
  psychological_constraints: []
  social_constraints: []
style_expression_bias_layer:
  speech_style: measured
  silence_pattern: guarded
  gesture_bias: contained
  posture_bias: upright
conversation_personality_layer:
  social_openness: 0.5
  privacy_sensitivity: 0.6
  talk_initiative: 0.4
  deception_control: 0.8
  trust_threshold_for_private_talk: 0.7
need_hierarchy_layer:
  base_weights:
    physiological: 0.2
    safety: 0.8
    belonging: 0.6
    esteem: 0.5
    self_actualization: 0.4
  deprivation_sensitivity:
    physiological: 0.2
    safety: 0.8
    belonging: 0.6
    esteem: 0.5
    self_actualization: 0.4
  satisfaction_sensitivity:
    physiological: 0.2
    safety: 0.7
    belonging: 0.7
    esteem: 0.6
    self_actualization: 0.3
  dominant_drives: [preserve_order]
  satisfaction_channels:
    physiological: []
    safety: [predictable_routine]
    belonging: []
    esteem: []
    self_actualization: []
  frustration_channels:
    physiological: []
    safety: [spatial_uncertainty]
    belonging: []
    esteem: []
    self_actualization: []
temperament_response_layer:
  baseline_temperament:
    caution: 0.7
    dominance: 0.3
    attachment: 0.6
    emotional_reactivity: 0.5
    recovery_speed: 0.5
    impulse_control: 0.8
  conflict_style:
    confrontation_tendency: 0.2
    avoidance_tendency: 0.7
    mediation_tendency: 0.8
    escalation_threshold: 0.7
  defense_patterns:
    under_pressure: [procedural_control]
    under_shame: [silence]
    under_threat: [vigilance]
    under_loss: [withdrawal]
  trust_dynamics:
    initial_trust_bias: 0.4
    betrayal_memory_weight: 0.8
    forgiveness_threshold: 0.3
    loyalty_lock_in: 0.6
  expression_bias:
    outward_warmth: 0.4
    emotional_transparency: 0.3
    facial_control: 0.8
    verbal_indirection: 0.7
long_term_personality_drift_layer:
  stable_shifts: []
  reinforced_patterns: []
  weakened_patterns: []
  need_reweights: {}
  trust_reweights: {}
  expression_reweights: {}
  drift_policy:
    minimum_cross_scene_count: 3
    minimum_confirming_events: 8
    minimum_time_span: long_arc
    require_non_transient_evidence: true
runtime_defaults:
  default_control_mode: agent_full_auto
""",
        encoding="utf-8",
    )

    loader = CharacterProfileLoader(tmp_path)
    profile = loader.load("char_test")

    assert profile.need_hierarchy_layer.base_weights.safety == 0.8
    assert profile.temperament_response_layer.defense_patterns.under_shame == ["silence"]
    assert profile.long_term_personality_drift_layer.drift_policy.minimum_confirming_events == 8
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_character_profile_needs_schema.py::test_character_profile_loader_accepts_needs_temperament_and_drift_layers -v`

Expected: FAIL with missing fields on `CharacterProfile`

- [ ] **Step 3: Add profile-layer models and extend `CharacterProfile`**

```python
class NeedWeightMap(StrictProfileModel):
    physiological: float = ProfileScalar
    safety: float = ProfileScalar
    belonging: float = ProfileScalar
    esteem: float = ProfileScalar
    self_actualization: float = ProfileScalar


class NeedChannelMap(StrictProfileModel):
    physiological: list[str] = Field(default_factory=list)
    safety: list[str] = Field(default_factory=list)
    belonging: list[str] = Field(default_factory=list)
    esteem: list[str] = Field(default_factory=list)
    self_actualization: list[str] = Field(default_factory=list)


class NeedHierarchyLayer(StrictProfileModel):
    base_weights: NeedWeightMap
    deprivation_sensitivity: NeedWeightMap
    satisfaction_sensitivity: NeedWeightMap
    dominant_drives: list[str] = Field(default_factory=list)
    satisfaction_channels: NeedChannelMap = Field(default_factory=NeedChannelMap)
    frustration_channels: NeedChannelMap = Field(default_factory=NeedChannelMap)
```

```python
class CharacterProfile(StrictProfileModel):
    identity_core: IdentityCore
    origin_seed: OriginSeed
    life_memory_backbone: LifeMemoryBackbone
    virtue_value_layer: VirtueValueLayer
    trait_vector_layer: TraitVectorLayer
    capability_constraint_layer: CapabilityConstraintLayer
    style_expression_bias_layer: StyleExpressionBiasLayer
    conversation_personality_layer: ConversationPersonalityLayer
    need_hierarchy_layer: NeedHierarchyLayer
    temperament_response_layer: TemperamentResponseLayer
    long_term_personality_drift_layer: LongTermPersonalityDriftLayer = Field(
        default_factory=LongTermPersonalityDriftLayer
    )
    runtime_defaults: RuntimeDefaults = Field(default_factory=RuntimeDefaults)
```

- [ ] **Step 4: Author the new fields in the shipped character YAML files**

```yaml
need_hierarchy_layer:
  base_weights:
    physiological: 0.30
    safety: 0.78
    belonging: 0.62
    esteem: 0.55
    self_actualization: 0.40
  deprivation_sensitivity:
    physiological: 0.20
    safety: 0.85
    belonging: 0.64
    esteem: 0.58
    self_actualization: 0.35
  satisfaction_sensitivity:
    physiological: 0.25
    safety: 0.66
    belonging: 0.72
    esteem: 0.61
    self_actualization: 0.43
  dominant_drives:
    - preserve_order
    - maintain_trust
```

- [ ] **Step 5: Run the schema test and profile loader checks**

Run: `pytest backend/tests/test_character_profile_needs_schema.py -v`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/character_agent/profile/models.py \
        assets/characters/profiles/char_a.yaml \
        assets/characters/profiles/char_b.yaml \
        assets/characters/profiles/char_c.yaml \
        assets/characters/profiles/README.md \
        backend/tests/test_character_profile_needs_schema.py
git commit -m "feat: extend character profile schema with needs and temperament layers"
```

### Task 2: Add Need Tension and Expanded Dynamic State Models

**Files:**
- Create: `backend/app/character_agent/models/need_tension.py`
- Modify: `backend/app/character_agent/models/dynamic_state.py`
- Modify: `backend/app/character_agent/storage/dynamic_state_store.py`
- Create: `backend/app/character_agent/storage/need_tension_store.py`
- Test: `backend/tests/test_affect_engine.py`

- [ ] **Step 1: Write failing tests for expanded state models**

```python
from app.character_agent.models.dynamic_state import CharacterDynamicState
from app.character_agent.models.need_tension import NeedTensionState


def test_character_dynamic_state_supports_affect_tension_and_motivation_groups():
    state = CharacterDynamicState(
        actor_id="char_a",
        vigilance_level=0.4,
        distraction_level=0.2,
        affect_valence=-0.1,
    )

    assert state.affect_state.fear == 0.0
    assert state.tension_state.stress_load == 0.0
    assert state.motivation_state.motivation_stack == []


def test_need_tension_state_defaults_pressures_and_sources():
    state = NeedTensionState(
        actor_id="char_a",
        physiological_pressure=0.0,
        safety_pressure=0.0,
        belonging_pressure=0.0,
        esteem_pressure=0.0,
        self_actualization_pressure=0.0,
    )

    assert state.dominant_need == ""
    assert state.pressure_sources == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest backend/tests/test_affect_engine.py -k "dynamic_state or need_tension_state" -v`

Expected: FAIL with import or attribute errors

- [ ] **Step 3: Implement `NeedTensionState` and delta models**

```python
class NeedTensionState(StrictRuntimeModel):
    actor_id: str
    physiological_pressure: float = RuntimeScalar
    safety_pressure: float = RuntimeScalar
    belonging_pressure: float = RuntimeScalar
    esteem_pressure: float = RuntimeScalar
    self_actualization_pressure: float = RuntimeScalar
    recent_satisfaction: dict[str, float] = Field(default_factory=dict)
    dominant_need: str = ""
    secondary_need: str = ""
    motivation_stack: list[str] = Field(default_factory=list)
    pressure_sources: list[str] = Field(default_factory=list)
```

- [ ] **Step 4: Expand `CharacterDynamicState` to grouped affect/tension/motivation fields**

```python
class AffectState(StrictRuntimeModel):
    fear: float = RuntimeScalar
    anger: float = RuntimeScalar
    shame: float = RuntimeScalar
    sadness: float = RuntimeScalar
    relief: float = RuntimeScalar
    curiosity: float = RuntimeScalar
    affection: float = RuntimeScalar
    joy: float = RuntimeScalar
    calm: float = RuntimeScalar
    trust: float = RuntimeScalar
    gratitude: float = RuntimeScalar
    pride: float = RuntimeScalar
    confidence: float = RuntimeScalar
    hope: float = RuntimeScalar


class CharacterDynamicState(StrictRuntimeModel):
    actor_id: str
    vigilance_level: float = RuntimeScalar
    distraction_level: float = RuntimeScalar
    affect_valence: float = Field(default=0.0, ge=-1.0, le=1.0)
    affect_state: AffectState = Field(default_factory=AffectState)
    tension_state: TensionState = Field(default_factory=TensionState)
    motivation_state: MotivationState = Field(default_factory=MotivationState)
```

Implementation note: `AffectState` is the immediate emotion group. Need pressure remains
in `NeedTensionState`; runtime/chronic stress remains in `TensionState`. Positive need
satisfaction is represented as `recent_satisfaction` on `NeedTensionDelta` and is mapped
by `AffectEngine` into positive affect fields instead of directly modifying authored
profile truth or long-term drift.

- [ ] **Step 5: Add stores for reading, writing, and merging new state**

```python
class CharacterNeedTensionStore:
    def __init__(self) -> None:
        self._by_actor: dict[str, dict[str, object]] = {}

    def read_record(self, actor_id: str) -> NeedTensionState:
        return NeedTensionState(**self.read(actor_id))

    def merge_delta(self, actor_id: str, delta: dict[str, object]) -> dict[str, object]:
        payload = {**self.read(actor_id), **deepcopy(delta), "actor_id": actor_id}
        normalized = NeedTensionState(**payload).model_dump()
        self._by_actor[actor_id] = normalized
        return deepcopy(normalized)
```

- [ ] **Step 6: Run tests to verify state models pass**

Run: `pytest backend/tests/test_affect_engine.py -k "dynamic_state or need_tension_state" -v`

Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add backend/app/character_agent/models/need_tension.py \
        backend/app/character_agent/models/dynamic_state.py \
        backend/app/character_agent/storage/dynamic_state_store.py \
        backend/app/character_agent/storage/need_tension_store.py \
        backend/tests/test_affect_engine.py
git commit -m "feat: add need tension and grouped affect runtime state"
```

### Task 3: Add Effective Profile Resolver

**Files:**
- Create: `backend/app/character_agent/profile/effective_profile.py`
- Modify: `backend/app/character_agent/runtime/runtime_loop.py`
- Test: `backend/tests/test_character_runtime_needs_affect_flow.py`

- [ ] **Step 1: Write failing tests for effective profile resolution**

```python
from app.character_agent.profile.effective_profile import resolve_effective_profile


def test_effective_profile_applies_drift_reweights_without_mutating_base_profile():
    base_profile = {
        "need_hierarchy_layer": {
            "base_weights": {
                "physiological": 0.2,
                "safety": 0.8,
                "belonging": 0.6,
                "esteem": 0.5,
                "self_actualization": 0.4,
            }
        },
        "long_term_personality_drift_layer": {
            "need_reweights": {"safety": 0.1},
            "trust_reweights": {},
            "expression_reweights": {},
            "stable_shifts": [],
            "reinforced_patterns": [],
            "weakened_patterns": [],
            "drift_policy": {
                "minimum_cross_scene_count": 3,
                "minimum_confirming_events": 8,
                "minimum_time_span": "long_arc",
                "require_non_transient_evidence": True,
            },
        },
    }

    effective = resolve_effective_profile(base_profile)

    assert effective["need_hierarchy_layer"]["effective_weights"]["safety"] == 0.9
    assert base_profile["need_hierarchy_layer"]["base_weights"]["safety"] == 0.8
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_character_runtime_needs_affect_flow.py::test_effective_profile_applies_drift_reweights_without_mutating_base_profile -v`

Expected: FAIL with import error for `resolve_effective_profile`

- [ ] **Step 3: Implement effective profile resolver**

```python
from copy import deepcopy


def resolve_effective_profile(profile: dict[str, object]) -> dict[str, object]:
    effective = deepcopy(profile)
    drift = dict(effective.get("long_term_personality_drift_layer", {}) or {})
    base_weights = dict(
        effective.get("need_hierarchy_layer", {}).get("base_weights", {}) or {}
    )
    reweights = dict(drift.get("need_reweights", {}) or {})
    effective_weights = {
        key: max(0.0, min(1.0, float(base_weights.get(key, 0.0)) + float(reweights.get(key, 0.0))))
        for key in ("physiological", "safety", "belonging", "esteem", "self_actualization")
    }
    effective.setdefault("need_hierarchy_layer", {})["effective_weights"] = effective_weights
    return effective
```

- [ ] **Step 4: Cache and expose effective profile in runtime**

```python
from app.character_agent.profile.effective_profile import resolve_effective_profile


def _effective_profile_payload(self, actor_id: str) -> dict[str, object]:
    return resolve_effective_profile(self._profile_payload(actor_id))
```

- [ ] **Step 5: Run the resolver tests**

Run: `pytest backend/tests/test_character_runtime_needs_affect_flow.py::test_effective_profile_applies_drift_reweights_without_mutating_base_profile -v`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/character_agent/profile/effective_profile.py \
        backend/app/character_agent/runtime/runtime_loop.py \
        backend/tests/test_character_runtime_needs_affect_flow.py
git commit -m "feat: resolve effective character profile from base and drift layers"
```

### Task 4: Add NeedTensionEngine and AffectEngine

**Files:**
- Create: `backend/app/character_agent/logic/need_tension_engine.py`
- Create: `backend/app/character_agent/logic/affect_engine.py`
- Test: `backend/tests/test_need_tension_engine.py`
- Test: `backend/tests/test_affect_engine.py`

- [ ] **Step 1: Write failing engine tests**

```python
from app.character_agent.logic.need_tension_engine import NeedTensionEngine


def test_need_tension_engine_raises_safety_and_esteem_pressure_for_public_threat():
    engine = NeedTensionEngine()
    effective_profile = {
        "need_hierarchy_layer": {
            "effective_weights": {
                "physiological": 0.2,
                "safety": 0.8,
                "belonging": 0.6,
                "esteem": 0.7,
                "self_actualization": 0.3,
            },
            "deprivation_sensitivity": {
                "physiological": 0.2,
                "safety": 0.9,
                "belonging": 0.6,
                "esteem": 0.8,
                "self_actualization": 0.2,
            },
        }
    }
    event = {"event_tags": ["public_dismissal", "spatial_uncertainty"]}

    delta = engine.evaluate(effective_profile=effective_profile, event=event)

    assert delta.safety > 0.0
    assert delta.esteem > 0.0
    assert "public_dismissal" in delta.pressure_sources
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest backend/tests/test_need_tension_engine.py backend/tests/test_affect_engine.py -v`

Expected: FAIL with missing engine modules

- [ ] **Step 3: Implement `NeedTensionEngine.evaluate(...)`**

```python
class NeedTensionEngine:
    def evaluate(
        self,
        *,
        effective_profile: dict[str, object],
        event: dict[str, object],
    ) -> NeedTensionDelta:
        tags = set(str(tag) for tag in event.get("event_tags", []))
        profile_layer = dict(effective_profile.get("need_hierarchy_layer", {}) or {})
        weights = dict(profile_layer.get("effective_weights", profile_layer.get("base_weights", {})) or {})
        sensitivity = dict(profile_layer.get("deprivation_sensitivity", {}) or {})
        return NeedTensionDelta(
            safety=(weights.get("safety", 0.0) * sensitivity.get("safety", 0.0) * 0.25)
            if "spatial_uncertainty" in tags else None,
            esteem=(weights.get("esteem", 0.0) * sensitivity.get("esteem", 0.0) * 0.25)
            if "public_dismissal" in tags else None,
            pressure_sources=sorted(tags),
        )
```

- [ ] **Step 4: Implement `AffectEngine.evaluate(...)`**

```python
class AffectEngine:
    def evaluate(
        self,
        *,
        effective_profile: dict[str, object],
        need_delta: NeedTensionDelta,
    ) -> dict[str, object]:
        temperament = dict(
            effective_profile.get("temperament_response_layer", {}).get("baseline_temperament", {}) or {}
        )
        emotional_reactivity = float(temperament.get("emotional_reactivity", 0.5) or 0.5)
        safety_pressure = float(need_delta.safety or 0.0)
        esteem_pressure = float(need_delta.esteem or 0.0)
        return {
            "dynamic_state_delta": {
                "vigilance_level": min(1.0, safety_pressure * emotional_reactivity),
                "stress_load": min(1.0, (safety_pressure + esteem_pressure) * 0.5),
                "affect_valence": max(-1.0, -1.0 * (safety_pressure + esteem_pressure)),
            }
        }
```

- [ ] **Step 5: Run engine tests to verify they pass**

Run: `pytest backend/tests/test_need_tension_engine.py backend/tests/test_affect_engine.py -v`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/character_agent/logic/need_tension_engine.py \
        backend/app/character_agent/logic/affect_engine.py \
        backend/tests/test_need_tension_engine.py \
        backend/tests/test_affect_engine.py
git commit -m "feat: add need tension and affect engines"
```

### Task 5: Wire Needs and Affect into L2 Context

**Files:**
- Modify: `backend/app/character_agent/reasoning/l2_reasoner.py`
- Modify: `backend/app/character_agent/gateway/prompt_policy.py`
- Test: `backend/tests/test_character_runtime_needs_affect_flow.py`

- [ ] **Step 1: Write a failing L2 context test**

```python
from app.character_agent.reasoning.l2_reasoner import CharacterAgentL2Service


def test_l2_reasoning_context_includes_effective_profile_and_need_tension_state():
    service = CharacterAgentL2Service()
    context = service._reasoning_context(
        actor_id="char_a",
        snapshot={"actor_id": "char_a"},
        event={"event_type": "character_perceived_event"},
        memory_bundle={},
        control_mode="agent_full_auto",
        working_memory_state={},
        current_goal_state={},
        goal_state_history=[],
        supervision_state={},
        unresolved_tensions=[],
        background_agenda_state={},
        effective_profile={"identity_core": {"character_id": "char_a"}},
        need_tension_state={"dominant_need": "safety"},
    )

    assert context["effective_profile"]["identity_core"]["character_id"] == "char_a"
    assert context["need_tension_state"]["dominant_need"] == "safety"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_character_runtime_needs_affect_flow.py::test_l2_reasoning_context_includes_effective_profile_and_need_tension_state -v`

Expected: FAIL with unexpected keyword argument or missing context keys

- [ ] **Step 3: Extend `_reasoning_context(...)` and prompt policy**

```python
def _reasoning_context(
    self,
    *,
    actor_id: str,
    snapshot: dict[str, object],
    event: dict[str, object],
    memory_bundle: dict[str, list[dict[str, object]]] | CharacterMemoryRecordBundle | None,
    control_mode: str,
    working_memory_state: dict[str, object] | CharacterWorkingMemoryState | None,
    current_goal_state: dict[str, object] | None,
    goal_state_history: list[dict[str, object]] | None,
    supervision_state: dict[str, object] | None,
    unresolved_tensions: list[dict[str, object]] | None,
    background_agenda_state: dict[str, object] | None,
    effective_profile: dict[str, object],
    need_tension_state: dict[str, object],
) -> dict[str, object]:
    context = self._context_builder.build_context(
        actor_id=actor_id,
        snapshot=snapshot,
        memory_bundle=memory_bundle or {},
        control_mode=control_mode,
        working_memory_state=working_memory_state or {},
        profile=effective_profile,
    )
    context["effective_profile"] = dict(effective_profile)
    context["need_tension_state"] = dict(need_tension_state)
    context["event"] = dict(event)
    return context
```

- [ ] **Step 4: Run the L2 context tests**

Run: `pytest backend/tests/test_character_runtime_needs_affect_flow.py::test_l2_reasoning_context_includes_effective_profile_and_need_tension_state -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/character_agent/reasoning/l2_reasoner.py \
        backend/app/character_agent/gateway/prompt_policy.py \
        backend/tests/test_character_runtime_needs_affect_flow.py
git commit -m "feat: pass effective profile and need tension state into l2 reasoning"
```

### Task 6: Wire Stores and Engines into Runtime Loop

**Files:**
- Modify: `backend/app/character_agent/runtime/runtime_loop.py`
- Modify: `backend/app/character_agent/storage/__init__.py`
- Test: `backend/tests/test_character_runtime_needs_affect_flow.py`

- [ ] **Step 1: Write failing runtime flow tests**

```python
def test_runtime_writes_need_tension_and_dynamic_state_after_perceived_event():
    runtime = CharacterAgentRuntime()
    event = CharacterPerceivedEvent(
        actor_id="char_a",
        producer_ts=100,
        perceived_summary="public dismissal near unstable doorway",
        interpretation_hint="public_dismissal",
    )

    runtime.ingest_character_perceived_event(event)

    need_state = runtime.get_need_tension_state("char_a")
    dynamic_state = runtime.get_dynamic_state("char_a")

    assert "pressure_sources" in need_state
    assert "stress_load" in dynamic_state
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest backend/tests/test_character_runtime_needs_affect_flow.py -v`

Expected: FAIL with missing runtime methods or missing state updates

- [ ] **Step 3: Add runtime members and getters**

```python
self._need_tension_store = CharacterNeedTensionStore()
self._need_tension_engine = NeedTensionEngine()
self._affect_engine = AffectEngine()
```

```python
def get_need_tension_state(self, actor_id: str) -> dict[str, object]:
    return self._need_tension_store.read(actor_id)


def get_need_tension_state_record(self, actor_id: str) -> NeedTensionState:
    return self._need_tension_store.read_record(actor_id)
```

- [ ] **Step 4: Apply engines before L2 reasoning and write back stores**

```python
effective_profile = self._effective_profile_payload(event.actor_id)
need_delta = self._need_tension_engine.evaluate(
    effective_profile=effective_profile,
    event=event.model_dump(),
)
need_state = self._need_tension_store.merge_delta(
    event.actor_id,
    need_delta.as_mapping(),
)
affect_result = self._affect_engine.evaluate(
    effective_profile=effective_profile,
    need_delta=need_delta,
)
dynamic_delta = dict(affect_result.get("dynamic_state_delta", {}))
if dynamic_delta:
    self._dynamic_state_store.merge_delta(event.actor_id, dynamic_delta)
```

- [ ] **Step 5: Run runtime integration tests**

Run: `pytest backend/tests/test_character_runtime_needs_affect_flow.py -v`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/character_agent/runtime/runtime_loop.py \
        backend/app/character_agent/storage/__init__.py \
        backend/tests/test_character_runtime_needs_affect_flow.py
git commit -m "feat: wire need tension and affect state into character runtime"
```

### Task 7: Add Drift Accumulation and Promotion Gate

**Files:**
- Create: `backend/app/character_agent/models/drift_candidate.py`
- Create: `backend/app/character_agent/logic/drift_accumulator.py`
- Create: `backend/app/character_agent/logic/drift_promotion_gate.py`
- Modify: `backend/app/character_agent/runtime/runtime_loop.py`
- Test: `backend/tests/test_personality_drift_gate.py`

- [ ] **Step 1: Write failing drift tests**

```python
from app.character_agent.logic.drift_promotion_gate import DriftPromotionGate
from app.character_agent.models.drift_candidate import DriftCandidateRecord


def test_drift_promotion_gate_rejects_single_scene_short_lived_candidate():
    gate = DriftPromotionGate()
    candidate = DriftCandidateRecord(
        actor_id="char_a",
        key="public_disclosure_caution",
        direction="increased",
        reinforcing_events=2,
        cross_scene_count=1,
        stable_time_span="short_arc",
        confidence=0.9,
        evidence_summary="single incident",
    )

    assert gate.should_promote(candidate) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest backend/tests/test_personality_drift_gate.py -v`

Expected: FAIL with import errors

- [ ] **Step 3: Implement candidate model and gate**

```python
class DriftCandidateRecord(StrictRuntimeModel):
    actor_id: str
    key: str
    direction: str
    reinforcing_events: int = Field(ge=0)
    cross_scene_count: int = Field(ge=0)
    stable_time_span: str
    confidence: float = RuntimeScalar
    evidence_summary: str
```

```python
class DriftPromotionGate:
    def should_promote(self, candidate: DriftCandidateRecord) -> bool:
        return (
            candidate.cross_scene_count >= 3
            and candidate.reinforcing_events >= 8
            and candidate.stable_time_span == "long_arc"
            and candidate.confidence >= 0.7
        )
```

- [ ] **Step 4: Add accumulator hook in runtime without mutating base profile**

```python
candidate = self._drift_accumulator.observe(
    actor_id=actor_id,
    effective_profile=effective_profile,
    interpretation=interpretation,
    dynamic_state=self.get_dynamic_state_record(actor_id),
    need_tension_state=self.get_need_tension_state_record(actor_id),
)
if candidate is not None and self._drift_promotion_gate.should_promote(candidate):
    self._record_drift_promotion(actor_id, producer_ts, candidate)
```

- [ ] **Step 5: Run drift tests**

Run: `pytest backend/tests/test_personality_drift_gate.py -v`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/character_agent/models/drift_candidate.py \
        backend/app/character_agent/logic/drift_accumulator.py \
        backend/app/character_agent/logic/drift_promotion_gate.py \
        backend/app/character_agent/runtime/runtime_loop.py \
        backend/tests/test_personality_drift_gate.py
git commit -m "feat: add conservative long-term personality drift gate"
```

### Task 8: Documentation and Final Verification

**Files:**
- Modify: `docs/character/character-mind-core-status.md`
- Modify: `docs/架构/运行时/模块/角色智能体.md`
- Modify: `docs/INDEX.md`
- Test: `scripts/verification/harness.py`

- [ ] **Step 1: Update character runtime docs**

```markdown
- 新增 `need_hierarchy_layer`
- 新增 `temperament_response_layer`
- `CharacterDynamicState` 拆分为 affect / tension / motivation 三组
- 新增 `NeedTensionState`
- 新增 `L2 -> dynamic_state_delta` 与长期 drift 候选链
```

- [ ] **Step 2: Add focused verification references to docs**

```markdown
- `pytest backend/tests/test_character_profile_needs_schema.py -v`
- `pytest backend/tests/test_need_tension_engine.py -v`
- `pytest backend/tests/test_affect_engine.py -v`
- `pytest backend/tests/test_character_runtime_needs_affect_flow.py -v`
- `pytest backend/tests/test_personality_drift_gate.py -v`
```

- [ ] **Step 3: Run focused backend test suite**

Run: `pytest backend/tests/test_character_profile_needs_schema.py backend/tests/test_need_tension_engine.py backend/tests/test_affect_engine.py backend/tests/test_character_runtime_needs_affect_flow.py backend/tests/test_personality_drift_gate.py -v`

Expected: PASS

- [ ] **Step 4: Run docs harness**

Run: `python scripts/verification/harness.py --profile docs`

Expected: `overall_docs_passed=True`

- [ ] **Step 5: Commit**

```bash
git add docs/character/character-mind-core-status.md \
        docs/架构/运行时/模块/角色智能体.md \
        docs/INDEX.md \
        backend/tests/test_character_profile_needs_schema.py \
        backend/tests/test_need_tension_engine.py \
        backend/tests/test_affect_engine.py \
        backend/tests/test_character_runtime_needs_affect_flow.py \
        backend/tests/test_personality_drift_gate.py
git commit -m "docs: align character runtime docs with needs and affect system"
```

## Self-Review

### Spec coverage

- `need_hierarchy_layer` -> Task 1
- `temperament_response_layer` -> Task 1
- `long_term_personality_drift_layer` -> Task 1 and Task 7
- `NeedTensionState` -> Task 2
- expanded `CharacterDynamicState` -> Task 2
- `EffectiveProfileResolver` -> Task 3
- `NeedTensionEngine` -> Task 4
- `AffectEngine` -> Task 4
- `L2` consumption of effective profile and need tension -> Task 5
- runtime writeback of dynamic/need tension state -> Task 6
- `DriftAccumulator` / `DriftPromotionGate` -> Task 7
- docs and verification coverage -> Task 8

No uncovered spec sections remain.

### Placeholder scan

- No `TBD`, `TODO`, or “implement later” placeholders remain.
- Every code-changing task includes concrete code snippets.
- Every test step includes an explicit command and expected result.

### Type consistency

- `NeedHierarchyLayer`, `TemperamentResponseLayer`, and `LongTermPersonalityDriftLayer` are introduced in Task 1 and referenced consistently later.
- `NeedTensionState`, `NeedTensionDelta`, `AffectEngine`, and `DriftPromotionGate` names are consistent across tasks.
- Runtime methods use `get_need_tension_state(...)`, `get_need_tension_state_record(...)`, and `_effective_profile_payload(...)` consistently.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-08-character-needs-personality-affect-runtime-implementation-plan.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
