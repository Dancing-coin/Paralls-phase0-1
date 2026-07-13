# Character Skill System Runtime Completion Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` or `superpowers:executing-plans` to
> implement this plan task-by-task. Do not combine phases into one large change.

**Goal:** Complete the Character Skill System beyond the Phase 1 binding
contract by adding live shadow integration, settlement integration, evidence
recording, governed learning surfaces, and presentation/realization handoff
without violating world-authority boundaries.

**Source design:** `docs/superpowers/specs/2026-07-10-character-skill-system-master-design.md`

**Relationship to prior plan:** This plan continues after
`docs/superpowers/plans/2026-07-10-character-skill-system-master-implementation-plan.md`.
That earlier plan intentionally implemented only Phase 1: contracts, registry,
service shadow evaluation, and L4 shadow proposal. This plan covers the missing
Phase 2, Phase 3, and Phase 4 work.

---

## Current Baseline

The main runtime already has a character mind affordance/constraint layer:

- `backend/app/character_agent/mind/affordances.py`
- `backend/app/character_agent/mind/frame_builder.py`
- `backend/app/character_agent/mind/view_builder.py`
- `backend/app/character_agent/models/mind_frame.py`
- `backend/app/character_agent/planning/l3_planner.py`
- `backend/app/character_agent/execution/l4_executor.py`
- `backend/app/character_agent/runtime/runtime_loop.py`
- `backend/app/services/interaction_orchestration_service.py`
- `backend/app/services/physical_interaction_channel.py`
- `backend/app/services/esm_service.py`
- `backend/app/character_agent/execution/kimodo_adapter_contract.py`

The Phase 1 branch adds the new skill contract surface:

- `backend/app/character_agent/skills/models.py`
- `backend/app/character_agent/skills/registry.py`
- `backend/app/character_agent/skills/service.py`
- `backend/tests/test_character_skill_models.py`
- `backend/tests/test_skill_action_binding_registry.py`
- `backend/tests/test_character_skill_service.py`
- `backend/tests/test_character_agent_l4_skill_shadow.py`

## Preconditions

Before starting this plan, verify the Phase 1 skill contract is present on the
target branch:

- `backend/app/character_agent/skills/__init__.py`
- `backend/app/character_agent/skills/models.py`
- `backend/app/character_agent/skills/registry.py`
- `backend/app/character_agent/skills/service.py`
- `backend/app/character_agent/execution/l4_executor.py` emits
  `composite_action_proposal`.

If these files are absent, first merge or replay the Phase 1 branch. Do not
reimplement Phase 1 inside this plan.

## Scope Boundary

Included:

- Phase 2 live shadow integration:
  - build `SkillAffordanceSummary` from the skill service and feed it into the
    existing mind-frame / L3 context path
  - run `CharacterSkillService.evaluate_action(...)` in shadow mode from L4
    proposals
  - preserve `action_request_bundle` compatibility
- Phase 3 settlement integration:
  - carry advisory `SkillEvaluationResult` and optional `PrimitiveActionPlan`
    into interaction orchestration requests
  - keep ESM and physical channel authoritative
  - structure skill-aware settlement result metadata without letting skill checks
    decide world truth
  - extract `SkillEvidence` from settlement results
- Phase 4 governed learning / visibility surfaces:
  - implement `SkillEvidenceStore`
  - implement conservative `SkillCandidateStore` and `SkillPromotionGate`
  - add `LearnedSkillLayer` overlay projection while keeping authored profile
    truth immutable
  - add `ObservedSkillBeliefStore` as belief state, not truth
  - add player-facing capability hints as visibility-filtered projections
- Presentation/realization handoff:
  - pass selected skill path and settlement outcome as realization hints
  - keep Kimodo/local asset realization presentation-only

Excluded:

- automatic skill promotion without an explicit gate decision
- learned skills mutating `capability_constraint_layer`
- ESM delegating world-truth authority to skill checks
- physical channel delegating embodied feasibility authority to skill checks
- Kimodo deciding action success
- large production skill/action libraries
- new external dependencies

## Architecture Principles

1. `CharacterSkillService` remains character-side and advisory.
2. ESM remains semantic authority.
3. Physical channel remains embodied feasibility authority.
4. Skill evaluation is a pre-settlement input, not settlement truth.
5. Realization consumes selected skill path and settlement outcome for
   presentation variants only.
6. Authored profile truth, runtime skill state, learned overlays, and observed
   beliefs stay separate.
7. Every live integration must preserve the existing fallback path.

---

## Phase 2: L3/L4 Live Shadow Integration

### Task 1: Add Runtime Skill Registry Provider

**Files:**

- Create or modify: `backend/app/character_agent/skills/catalog.py`
- Modify: `backend/app/character_agent/skills/__init__.py`
- Test: `backend/tests/test_character_skill_catalog.py`

**Implementation:**

- Add a minimal core registry factory that returns only small reusable
  definitions needed by existing character profiles and tests.
- Include no large production library.
- Keep scenario overlays injectable and in-memory.
- Avoid coupling to L3, L4, ESM, or runtime loop.

**Acceptance criteria:**

- A core registry can provide bindings for at least observation/social/procedure
  style actions used by current character profiles.
- Unknown skills are ignored or reported as advisory metadata, not crashes.
- Tests prove duplicate overlay replacement remains deterministic.

**Verification:**

```bash
pytest backend/tests/test_character_skill_catalog.py backend/tests/test_skill_action_binding_registry.py -v
python -m ruff check backend/app/character_agent/skills backend/tests/test_character_skill_catalog.py
```

### Task 2: Feed SkillAffordanceSummary Into Mind Frames

**Files:**

- Modify: `backend/app/character_agent/mind/frame_builder.py`
- Modify: `backend/app/character_agent/mind/view_builder.py`
- Modify: `backend/app/character_agent/runtime/runtime_loop.py`
- Test: `backend/tests/test_character_mind_frame_builder.py`
- Test: `backend/tests/test_character_mind_context_views.py`
- Test: `backend/tests/test_character_skill_runtime_shadow.py`

**Implementation:**

- Build initial skill states from `capability_constraint_layer.skills`.
- Use `CharacterSkillService.build_affordance_summary(...)`.
- Pass the resulting summary into the existing `skill_affordance_summary`
  argument consumed by `CharacterMindAffordanceAdapter`.
- Preserve manually supplied summaries in tests and compatibility paths.
- Do not expose the full registry to L3.

**Acceptance criteria:**

- L3-facing context receives compressed `SkillAffordanceSummary`.
- The full skill/action registry is not present in the L3 prompt context.
- Existing affordance card behavior remains compatible.
- The runtime still works when the skill registry is empty.

**Verification:**

```bash
pytest backend/tests/test_character_mind_frame_builder.py backend/tests/test_character_mind_context_views.py backend/tests/test_character_skill_runtime_shadow.py -v
python -m ruff check backend/app/character_agent/mind backend/app/character_agent/runtime/runtime_loop.py backend/tests/test_character_skill_runtime_shadow.py
```

### Task 3: Run L4 Skill Evaluation In Shadow Mode

**Files:**

- Modify: `backend/app/character_agent/execution/l4_executor.py`
- Modify: `backend/app/character_agent/runtime/runtime_loop.py`
- Test: `backend/tests/test_character_agent_l4_skill_shadow.py`
- Test: `backend/tests/test_character_skill_runtime_shadow.py`

**Implementation:**

- Evaluate `composite_action_proposal` with `CharacterSkillService` after L4
  builds the shadow proposal.
- Add `skill_evaluation_result` and optional `primitive_action_plan` as sibling
  shadow fields in the execution payload.
- Do not alter `action_request_bundle`.
- Do not gate or rewrite selected intent based on skill evaluation.

**Acceptance criteria:**

- L4 output contains:
  - `composite_action_proposal`
  - `skill_evaluation_result`
  - optionally `primitive_action_plan`
- Existing `action_request_bundle` tests still pass unchanged.
- Skill evaluation is labeled advisory/shadow.

**Verification:**

```bash
pytest backend/tests/test_character_agent_l4_skill_shadow.py backend/tests/test_character_agent_runtime.py backend/tests/test_character_skill_runtime_shadow.py -v
```

---

## Phase 3: Settlement Integration And Evidence Extraction

### Task 4: Carry Skill Evaluation Into Interaction Orchestration

**Files:**

- Modify: `backend/app/services/interaction_orchestration_service.py`
- Modify: `backend/app/models/world_result.py` if a typed metadata field is
  needed
- Test: `backend/tests/test_interaction_orchestration_runtime_service.py`
- Test: `backend/tests/test_character_skill_settlement_integration.py`

**Implementation:**

- Add optional `skill_evaluation_result` and `primitive_action_plan` metadata to
  structured interaction requests or envelopes.
- Keep ESM and physical channel outcomes authoritative.
- The skill metadata may affect trace/explanation fields only in this task.
- Do not block settlement solely because a skill path is weak.

**Acceptance criteria:**

- Interaction orchestration can receive skill metadata without changing existing
  result status semantics.
- Semantic channel approval still comes from ESM.
- Physical channel application still depends on semantic approval and physical
  constraints.

**Verification:**

```bash
pytest backend/tests/test_interaction_orchestration_runtime_service.py backend/tests/test_character_skill_settlement_integration.py -v
python scripts/verification/harness.py --profile interaction-orchestration-service
python scripts/verification/harness.py --profile esm-physical-channel-world-actuation
```

### Task 5: Structure Skill-Aware Settlement Result Metadata

**Files:**

- Modify: `backend/app/character_agent/skills/models.py`
- Modify: `backend/app/character_agent/runtime/runtime_loop.py`
- Test: `backend/tests/test_character_skill_settlement_integration.py`

**Implementation:**

- Map existing semantic/physical results into `ActionSettlementResult`
  metadata.
- Preserve separate `outcome_band` and `failure_domains`.
- Skill metadata should describe contribution, cost, risk, or failure domain; it
  must not replace world result status.

**Acceptance criteria:**

- A successful settlement can be summarized as `clean_success` or
  `success_with_cost` without changing source world results.
- A failed settlement can identify `world_constraint`, `physical_failure`,
  `missing_requirement`, or `skill_failure` as metadata.
- Existing settlement result consumers remain compatible.

**Verification:**

```bash
pytest backend/tests/test_character_skill_settlement_integration.py backend/tests/test_character_agent_runtime.py -v
```

### Task 6: Extract SkillEvidence From Settlement Results

**Files:**

- Create: `backend/app/character_agent/skills/evidence.py`
- Modify: `backend/app/character_agent/skills/__init__.py`
- Test: `backend/tests/test_character_skill_evidence_extractor.py`

**Implementation:**

- Add a `SkillEvidenceExtractor` that consumes:
  - actor id
  - selected skill path
  - skill evaluation result
  - settlement result metadata
  - source settlement id
- Produce `SkillEvidence` only when policy allows evidence collection.
- Keep `eligible_for_promotion=False` unless a later promotion gate changes it.

**Acceptance criteria:**

- Evidence is directional and context-specific.
- Evidence can record improvement/confidence/specialization hints.
- Blocked actions can produce evidence only when binding learning policy permits
  blocked evidence.
- No learned skill overlay is modified in this task.

**Verification:**

```bash
pytest backend/tests/test_character_skill_evidence_extractor.py backend/tests/test_character_skill_models.py -v
python -m ruff check backend/app/character_agent/skills backend/tests/test_character_skill_evidence_extractor.py
```

---

## Phase 4: Governed Learning And Visibility

### Task 7: Add SkillEvidenceStore

**Files:**

- Create: `backend/app/character_agent/skills/store.py`
- Test: `backend/tests/test_character_skill_evidence_store.py`

**Implementation:**

- Add an in-memory evidence store with append/query APIs.
- Query by actor, skill, action, binding, and source settlement id.
- De-duplicate by `evidence_id`.
- Keep persistence out of scope unless the repository already has an approved
  storage pattern to reuse.

**Acceptance criteria:**

- Evidence records are immutable after append.
- Queries are actor-scoped.
- Duplicate `evidence_id` does not double-count.

**Verification:**

```bash
pytest backend/tests/test_character_skill_evidence_store.py -v
```

### Task 8: Add Conservative SkillCandidateStore And Promotion Gate

**Files:**

- Create: `backend/app/character_agent/skills/learning.py`
- Modify: `backend/app/character_agent/skills/__init__.py`
- Test: `backend/tests/test_character_skill_learning_gate.py`

**Implementation:**

- Add candidate aggregation from evidence.
- Add `SkillPromotionGate` with explicit checks:
  - promotion policy enabled
  - skill learnability permits it
  - authored profile compatibility
  - sufficient evidence
  - no blocked domain such as `authority` or `special`
  - explicit human/script grant for locked/granted domains
- Default all promotion paths to disabled.

**Acceptance criteria:**

- Promotion is impossible when `promotion_enabled=False`.
- Authority and special domains are not auto-promoted.
- The gate returns explainable rejection reasons.
- No authored profile mutation occurs.

**Verification:**

```bash
pytest backend/tests/test_character_skill_learning_gate.py -v
```

### Task 9: Add LearnedSkillLayer Overlay Projection

**Files:**

- Modify: `backend/app/character_agent/skills/service.py`
- Modify: `backend/app/character_agent/skills/models.py`
- Test: `backend/tests/test_character_skill_learned_overlay.py`

**Implementation:**

- Add a learned overlay input to effective skill state resolution.
- Keep `source="learned"` separate from `source="authored"`.
- Preserve authored profile truth.
- Support temporary/equipment/scripted states without merging them into learned
  state.

**Acceptance criteria:**

- Effective skill state can contain authored and learned rows for the same actor
  without mutating the profile.
- Conflicts are deterministic and visible in metadata.
- Learned overlay can be disabled without breaking authored projection.

**Verification:**

```bash
pytest backend/tests/test_character_skill_learned_overlay.py backend/tests/test_character_skill_service.py -v
```

### Task 10: Add ObservedSkillBeliefStore And Player-Facing Hints

**Files:**

- Create: `backend/app/character_agent/skills/visibility.py`
- Test: `backend/tests/test_character_skill_visibility.py`

**Implementation:**

- Add `ObservedSkillBelief` contracts only if not already present.
- Store observer beliefs separately from actual skill state.
- Add player-facing capability hints that obey skill visibility defaults and
  policy.
- Do not infer beliefs from raw observations in this task unless explicitly
  backed by evidence references.

**Acceptance criteria:**

- Actual skill state and observed belief state are separate.
- Player hints can hide private/locked skills.
- Belief confidence requires evidence refs.

**Verification:**

```bash
pytest backend/tests/test_character_skill_visibility.py -v
```

---

## Presentation / Realization Handoff

### Task 11: Pass Skill Path And Settlement Outcome To Realization

**Files:**

- Modify: `backend/app/character_agent/execution/l4_executor.py`
- Modify: `backend/app/character_agent/execution/l4_adapter.py`
- Modify: `backend/app/character_agent/execution/kimodo_adapter_contract.py`
- Test: `backend/tests/test_character_skill_realization_handoff.py`
- Test: `backend/tests/test_character_agent_runtime.py`

**Implementation:**

- Add selected skill path, primitive action tags, and settlement outcome as
  realization hints.
- Keep realization hints separate from settlement authority.
- Kimodo request/plan contracts may consume hints but must not report success or
  mutate world state.

**Acceptance criteria:**

- Realization can select presentation variants from skill path/outcome metadata.
- Kimodo contracts remain presentation-only.
- Existing presentation plan consumers remain compatible.

**Verification:**

```bash
pytest backend/tests/test_character_skill_realization_handoff.py backend/tests/test_character_agent_runtime.py -v
python scripts/verification/harness.py --profile mainline-unified-runtime
```

---

## Final Verification

Run these after all tasks complete:

```bash
pytest backend/tests/test_character_skill_models.py \
  backend/tests/test_skill_action_binding_registry.py \
  backend/tests/test_character_skill_service.py \
  backend/tests/test_character_agent_l4_skill_shadow.py \
  backend/tests/test_character_skill_catalog.py \
  backend/tests/test_character_skill_runtime_shadow.py \
  backend/tests/test_character_skill_settlement_integration.py \
  backend/tests/test_character_skill_evidence_extractor.py \
  backend/tests/test_character_skill_evidence_store.py \
  backend/tests/test_character_skill_learning_gate.py \
  backend/tests/test_character_skill_learned_overlay.py \
  backend/tests/test_character_skill_visibility.py \
  backend/tests/test_character_skill_realization_handoff.py -v

pytest backend/tests/test_character_agent_runtime.py \
  backend/tests/test_character_agent_l3_planning.py \
  backend/tests/test_character_runtime_needs_affect_flow.py \
  backend/tests/test_interaction_orchestration_runtime_service.py -v

python -m pytest backend -q
python scripts/verification/harness.py --profile docs
python scripts/verification/harness.py --profile interaction-orchestration-service
python scripts/verification/harness.py --profile esm-physical-channel-world-actuation
python scripts/verification/harness.py --profile mainline-unified-runtime
git diff --check
git status --short
```

## Completion Criteria

- L3 receives compressed skill affordance summaries, not full registries.
- L4 can produce a composite proposal and run skill evaluation while preserving
  existing execution fallback.
- Skill evaluation can be carried into settlement as advisory metadata.
- ESM and physical channel remain the only world-truth authorities.
- Settlement metadata can produce `SkillEvidence`.
- Evidence storage, candidate aggregation, promotion gate, learned overlay, and
  observed beliefs exist but remain conservative and policy-gated.
- No automatic promotion occurs with default policy.
- Realization/Kimodo consumes hints only and never decides success.
- Full backend tests, related runtime tests, docs harness, and relevant runtime
  harness profiles pass.

## Risks And Mitigations

- **Risk:** Skill evaluation starts silently gating world truth.
  - **Mitigation:** Tests must prove ESM/physical statuses remain authoritative
    even when skill metadata is weak or missing.
- **Risk:** L3 prompt context receives full registry data.
  - **Mitigation:** Mind-frame tests must assert compressed summaries only.
- **Risk:** Learned skills mutate authored profiles.
  - **Mitigation:** Overlay tests must prove `capability_constraint_layer` is not
    modified.
- **Risk:** Kimodo or local realization becomes authority.
  - **Mitigation:** Realization tests must reject success/status writes from
    presentation contracts.
- **Risk:** Candidate/promotion logic overfits to sparse evidence.
  - **Mitigation:** Promotion gate defaults to off and returns explainable
    rejection reasons until policy explicitly enables promotion.
