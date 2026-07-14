# Character Personality Trait Vector Refactor Implementation Plan

> **For agentic workers:** Use test-first implementation. Keep each task small,
> behavior-preserving until the plan explicitly says to wire projections into
> behavior. Do not change L2/L3 selected-intent behavior in the schema and
> shadow-projection phases.

**Goal:** Refactor the flat `trait_vector_layer` into a Big Five based
personality foundation plus a deduplicated `personality_projection` surface,
while preserving current behavior during migration.

**Architecture:** Add typed personality-layer models and a
`PersonalityProjectionResolver` under `backend/app/character_agent/profile/`.
Support current flat profile YAML as legacy input, generate projections in
shadow mode, expose them through `CharacterMindFrame`, then later migrate L2/L3
to consume projections instead of overlapping raw trait fields.

**Tech Stack:** Python 3.13, Pydantic v2, pytest, existing character-agent
runtime/profile/mind-frame code. No new dependencies.

---

## Scope Boundary

This plan implements the design in:

- `docs/superpowers/specs/2026-07-13-character-personality-trait-vector-refactor-design.md`

Included:

- Big Five and facet profile contracts.
- Backward-compatible loading of existing flat `trait_vector_layer` profiles.
- `PersonalityProjectionResolver` with deterministic projection formulas.
- Shadow projection exposure through profile views and `CharacterMindFrame`.
- Optional profile YAML migration once compatibility is proven.
- Documentation and verification updates.

Excluded from the first implementation pass:

- Changing `NeedTensionEngine` pressure formulas.
- Changing `AffectEngine` formulas.
- Changing L3 selected-intent scoring behavior.
- Implementing MBTI.
- Implementing the full Character Skill System.
- Rewriting authored character identities, values, needs, or memories.

---

## File Structure

- `backend/app/character_agent/profile/models.py`
  - Add Big Five, facets, compatibility, and optional projection models.
- `backend/app/character_agent/profile/personality_projection.py`
  - New resolver that computes deduplicated runtime personality projections.
- `backend/app/character_agent/profile/views.py`
  - Surface projection summaries for read-only profile views.
- `backend/app/character_agent/mind/projectors.py`
  - Include personality projection payloads in the `personality_bias` card.
- `backend/app/character_agent/runtime/runtime_loop.py`
  - No behavior change in initial phases; later phases may pass projection
    summaries to L2/L3 when explicitly implemented.
- `assets/characters/profiles/*.yaml`
  - Optional migration from flat `trait_vector_layer` to `personality_layer`.
- `backend/tests/test_character_personality_profile_models.py`
  - Schema and compatibility tests.
- `backend/tests/test_character_personality_projection.py`
  - Projection formula and duplicate-guard tests.
- `backend/tests/test_character_mind_frame_builder.py`
  - Extend frame tests to assert projection appears in personality cards.
- `docs/架构/运行时/模块/角色智能体.md`
  - Document personality-layer split and projection consumption rule.
- `docs/character/character-mind-core-status.md`
  - Status update after implementation.

---

## Phase 1: Schema Compatibility Foundation

### Task 1: Add Personality Layer Contracts

**Files:**
- Modify: `backend/app/character_agent/profile/models.py`
- Create: `backend/tests/test_character_personality_profile_models.py`

- [ ] **Step 1: Write failing tests for new personality models**

Test cases:

- A profile with current flat `trait_vector_layer` still loads.
- A profile with new `personality_layer.big_five` and facets loads.
- Big Five and facet values reject values outside `[0.0, 1.0]`.
- `trait_vector_layer` is accepted as legacy input but is not required for new
  profiles.
- `CharacterProfile.model_dump()` exposes normalized personality data in a
  stable shape.

- [ ] **Step 2: Implement Big Five and facet models**

Add Pydantic models:

```python
class BigFiveTraits(StrictProfileModel):
    openness: float = ProfileScalar
    conscientiousness: float = ProfileScalar
    extraversion: float = ProfileScalar
    agreeableness: float = ProfileScalar
    neuroticism: float = ProfileScalar
```

Facet groups:

- `OpennessFacets`: `curiosity`, `imagination`, `ambiguity_tolerance`,
  `novelty_seeking`
- `ConscientiousnessFacets`: `orderliness`, `dutifulness`, `deliberation`,
  `persistence`
- `ExtraversionFacets`: `social_energy`, `assertiveness`, `warmth`,
  `activity_level`
- `AgreeablenessFacets`: `compassion`, `trust`, `cooperativeness`,
  `conflict_softening`
- `NeuroticismFacets`: `anxiety`, `shame_sensitivity`, `volatility`,
  `vulnerability`

Add:

```python
class PersonalityLayer(StrictProfileModel):
    big_five: BigFiveTraits
    facets: BigFiveFacetLayer
```

- [ ] **Step 3: Add compatibility normalization**

Current YAML must keep loading. There are two acceptable compatibility options:

1. Keep `trait_vector_layer` as an optional legacy field on `CharacterProfile`.
2. Use a Pydantic `model_validator(mode="before")` to convert old
   `trait_vector_layer` into `personality_layer` defaults.

Preferred first pass: keep legacy `trait_vector_layer` optional and add
`personality_layer` optional with defaults derived by resolver, not by schema.
This is less risky for current profile loading.

- [ ] **Step 4: Run focused tests**

```bash
python -m pytest backend/tests/test_character_personality_profile_models.py backend/tests/test_character_profile_models.py backend/tests/test_character_profile_loader.py -v
```

Expected: all pass, with no profile YAML migration required.

---

## Phase 2: Personality Projection Resolver

### Task 2: Add Projection Resolver

**Files:**
- Create: `backend/app/character_agent/profile/personality_projection.py`
- Modify: `backend/app/character_agent/profile/__init__.py`
- Create: `backend/tests/test_character_personality_projection.py`

- [ ] **Step 1: Write projection formula tests**

Test cases:

- Resolver emits all required projection keys.
- Values are clamped to `[0.0, 1.0]`.
- Legacy flat traits can be used as fallback inputs.
- `scheming` is split into `strategic_planning` and
  `manipulative_tendency` rather than copied directly.
- `empathy` and `agreeableness` are not both emitted as behavior-facing raw
  fields.
- Missing optional layers use neutral defaults and do not crash.

Required projection keys:

- `social_approach_bias`
- `empathic_attunement`
- `analytical_control`
- `courage_bias`
- `strategic_planning`
- `manipulative_tendency`
- `conflict_deescalation_bias`
- `procedural_discipline`
- `public_assertion_bias`
- `avoidance_bias`
- `trust_repair_bias`
- `privacy_guard_bias`
- `stress_vulnerability`

- [ ] **Step 2: Implement resolver**

Implement formulas from the spec. Use helper methods:

- `_bounded_float(value, default=0.5)`
- `_invert(value)`
- `_weighted_sum(parts)`
- `_legacy_trait(profile, key, default=0.5)`
- `_procedural_training_modifier(profile)`
- `_value_commitment_strength(profile)`
- `_virtue_privacy_strength(profile)`

- [ ] **Step 3: Add optional debug/provenance output**

Keep runtime API simple:

```python
resolve_personality_projection(profile: dict[str, object]) -> dict[str, float]
```

Optional internal/test API may return provenance weights, but production callers
should receive a clean mapping.

- [ ] **Step 4: Run focused tests**

```bash
python -m pytest backend/tests/test_character_personality_projection.py -v
```

---

## Phase 3: Shadow Projection In Mind Frame

### Task 3: Surface Projection In Enduring Truth Cards

**Files:**
- Modify: `backend/app/character_agent/mind/projectors.py`
- Modify: `backend/tests/test_character_mind_frame_builder.py`
- Modify: `backend/tests/test_character_mind_context_views.py` if needed

- [ ] **Step 1: Write failing mind-frame tests**

Add tests proving:

- `personality_bias` card payload includes `personality_projection`.
- `effective_profile` card still includes identity, trait keys, and red lines.
- L2 view can see personality projection through `effective_profile_summary` or
  a bounded personality summary, but L3 does not receive raw overlapping trait
  fields as direct scoring inputs.
- Mutating the view does not mutate the frame.

- [ ] **Step 2: Implement shadow projection card payload**

In `EffectiveProfileProjector.project(...)`, call the resolver and include:

```python
payload={
    "conversation_personality_layer": conversation,
    "temperament_response_layer": temperament,
    "personality_projection": projection,
}
```

Do not change behavior yet.

- [ ] **Step 3: Run focused mind-frame tests**

```bash
python -m pytest backend/tests/test_character_mind_frame_builder.py backend/tests/test_character_mind_context_views.py backend/tests/test_character_mind_frame_models.py -v
```

---

## Phase 4: Profile YAML Migration

### Task 4: Migrate Character Profiles To New Personality Layer

**Files:**
- Modify: `assets/characters/profiles/char_a.yaml`
- Modify: `assets/characters/profiles/char_b.yaml`
- Modify: `assets/characters/profiles/char_c.yaml`
- Modify tests that assert exact profile structure only if necessary.

- [ ] **Step 1: Add new `personality_layer` beside legacy flat traits**

For each profile, add:

```yaml
personality_layer:
  big_five:
    openness: ...
    conscientiousness: ...
    extraversion: ...
    agreeableness: ...
    neuroticism: ...
  facets:
    ...
```

Keep the old `trait_vector_layer` for this phase to preserve compatibility and
allow side-by-side comparison.

- [ ] **Step 2: Use current traits as migration hints, not direct copies**

Example guidance for `char_a`:

- High `empathy` -> high `agreeableness.compassion`.
- High `rationality` and procedural role -> high
  `conscientiousness.deliberation` / `orderliness`.
- Moderate `sociability` -> moderate `extraversion.social_energy`.
- Low `scheming` -> low `manipulative_tendency`, not necessarily low
  `strategic_planning`.

- [ ] **Step 3: Run profile and projection tests**

```bash
python -m pytest backend/tests/test_character_profile_loader.py backend/tests/test_character_personality_projection.py -v
```

---

## Phase 5: Optional L2 Prompt Shadow Summary

### Task 5: Include Projection Summary In Prompt Context Without Behavior Claims

**Files:**
- Modify: `backend/app/character_agent/gateway/prompt_policy.py`
- Modify: `backend/tests/test_character_agent_l2_reasoning.py`
- Modify: `backend/tests/test_character_runtime_needs_affect_flow.py` if prompt
  summary assertions change.

- [ ] **Step 1: Add tests for prompt inclusion**

Assert the L2 prompt includes a compact projection summary such as:

```text
personality_projection=conflict_deescalation_bias=0.83|procedural_discipline=0.84|stress_vulnerability=0.31
```

The prompt should not include every raw facet by default.

- [ ] **Step 2: Implement prompt summary**

Add a bounded summary helper in `CharacterPromptPolicy`.

- [ ] **Step 3: Run L2 prompt tests**

```bash
python -m pytest backend/tests/test_character_agent_l2_reasoning.py backend/tests/test_character_runtime_needs_affect_flow.py -v
```

---

## Phase 6: L3 Projection Consumption Gate

### Task 6: Replace Raw Trait Bias Reads With Projection Reads

**Files:**
- Modify: `backend/app/character_agent/planning/l3_planner.py`
- Modify: `backend/tests/test_character_agent_l3_planning.py`

This phase changes behavior and should only start after Phase 1-5 are stable.

- [ ] **Step 1: Audit current L3 scoring for raw profile trait usage**

Identify all direct use of:

- `trait_vector_layer`
- `conversation_personality_layer`
- `temperament_response_layer`

Some conversation/temperament fields may remain legitimate direct inputs if
they do not duplicate a projection. If a field contributes to an already
projected meaning, prefer the projection.

- [ ] **Step 2: Add duplicate-guard tests**

Test that a de-escalation scoring path uses `conflict_deescalation_bias` rather
than independently summing `agreeableness`, `empathy`, and
`mediation_tendency`.

- [ ] **Step 3: Wire projection into selected scoring paths**

Start with narrow paths:

- `positive_affect` remains affect-owned and should not be replaced.
- `pressure_bias` remains need/dynamic-state owned and should not be replaced.
- Use projection only for personality-style candidate preferences, such as
  de-escalation, public assertion, avoidance, or procedural discipline.

- [ ] **Step 4: Run L3 focused tests**

```bash
python -m pytest backend/tests/test_character_agent_l3_planning.py -v
```

If behavior changes are expected, document the exact selected-intent changes and
why they are desired.

---

## Phase 7: Documentation And Deprecation

### Task 7: Update Architecture Docs And Status

**Files:**
- Modify: `docs/架构/运行时/模块/角色智能体.md`
- Modify: `docs/character/character-mind-core-status.md`

- [ ] **Step 1: Document personality layer split**

Add a concise section explaining:

- Big Five/facets are the personality foundation.
- Legacy flat traits are migration inputs or derived concepts.
- `personality_projection` is the behavior-facing surface.
- MBTI is not a numeric runtime basis.

- [ ] **Step 2: Document duplicate-weight guard**

State that L2/L3/L4 should not consume overlapping raw fields directly when a
projection exists.

- [ ] **Step 3: Run docs harness**

```bash
python scripts/verification/harness.py --profile docs
```

---

## Final Verification

Run the focused suite:

```bash
python -m pytest \
  backend/tests/test_character_personality_profile_models.py \
  backend/tests/test_character_personality_projection.py \
  backend/tests/test_character_profile_models.py \
  backend/tests/test_character_profile_loader.py \
  backend/tests/test_character_mind_frame_models.py \
  backend/tests/test_character_mind_frame_builder.py \
  backend/tests/test_character_mind_context_views.py \
  backend/tests/test_character_agent_l2_reasoning.py \
  backend/tests/test_character_agent_l3_planning.py \
  backend/tests/test_character_runtime_needs_affect_flow.py -v
```

Run docs harness:

```bash
python scripts/verification/harness.py --profile docs
```

For broad completion claims, run:

```bash
python scripts/verification/harness.py --profile all
```

---

## Rollback Strategy

- Phase 1-3 are additive and shadow-mode. Rollback is deleting the new models,
  resolver, tests, and mind-frame payload additions.
- Phase 4 profile YAML migration should keep legacy fields until all tests and
  consumers support the new schema.
- Phase 6 is behavior-affecting. Keep it in a separate commit so selected-intent
  changes can be reverted independently.

---

## Commit Guidance

Use Lore-style commit messages. Suggested split:

1. `Define Big Five personality profile contracts`
2. `Project personality into deduplicated runtime biases`
3. `Expose personality projections in mind frames`
4. `Migrate character profiles to personality layers`
5. `Summarize personality projections for L2 reasoning`
6. `Use personality projections for L3 preference scoring`
7. `Document personality projection boundaries`

Keep Phase 6 separate from schema/projection work because it changes behavior.

