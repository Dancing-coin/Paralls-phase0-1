# Full Character Agent Runtime With LLM Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver the full character-agent runtime defined in `docs/superpowers/specs/2026-06-15-full-character-agent-runtime-with-llm-design.md` while keeping the repository aligned with the shared `CharacterActor` architecture and preserving the proven `Phase 0` loop.

**Architecture:** Execute this work in two linked stages:

1. **Stage A: shared actor-substrate final-state convergence planning and landing**  
   The character-agent `L4` final boundary depends on the shared actor substrate being planned and converged toward its final state. This stage extends the existing `CharacterActor` design/planning truth so the local execution host is no longer treated only as a near-term transitional cleanup target.

2. **Stage B: full character-agent runtime convergence**  
   After Stage A establishes the converged actor-substrate target and execution seams, implement the full `CharacterAgent L1 -> L4` runtime with:
   - `char_a / char_b / char_c`
   - three-layer memory
   - LLM-backed `L2`, `L3`, and dialogue generation
   - `char_c` player-priority assisted control
   - active `ESM`-routed action requests

This plan must not treat actor-substrate convergence as implicit background work.

**Tech Stack:** FastAPI backend, current websocket event chain, Godot 4.6 scenes and GDScript, current `System L1 / ESM / Siming` runtime, pytest, harness verification, current character-actor specs/plans, and online-model-first provider routing with local/hybrid-ready abstractions.

---

## Linked Source Of Truth

This plan depends on and must stay aligned with:

- `docs/superpowers/specs/2026-06-15-full-character-agent-runtime-with-llm-design.md`
- `docs/superpowers/specs/2026-06-15-character-actor-architecture-optimization-design.md`
- `docs/superpowers/plans/2026-06-15-character-actor-architecture-optimization-implementation-plan.md`
- `docs/superpowers/plans/2026-06-15-character-actor-near-term-cleanup-implementation-plan.md`
- `docs/character/character-actor-migration-status.md`

If any of those files are updated during implementation, this plan must be checked and updated before continuing downstream tasks that depend on them.

---

## Stage A: Shared Actor-Substrate Final-State Convergence

### Why Stage A Exists

The current actor side is still explicitly transitional.

The full character-agent spec now freezes that:

- final-state `L4` must enter the shared `CharacterActor` substrate
- final-state character-agent convergence cannot be claimed independently of actor-substrate convergence

So before implementing the full agent runtime, the project needs an explicit actor-substrate final convergence plan above the existing near-term cleanup plans.

### Task A1: Audit Current Actor-Substrate Plan State Against The New Character-Agent Final-State Dependency

**Files:**
- Read: `docs/superpowers/specs/2026-06-15-character-actor-architecture-optimization-design.md`
- Read: `docs/superpowers/plans/2026-06-15-character-actor-architecture-optimization-implementation-plan.md`
- Read: `docs/superpowers/plans/2026-06-15-character-actor-near-term-cleanup-implementation-plan.md`
- Read: `docs/character/character-actor-migration-status.md`
- Read: `docs/superpowers/specs/2026-06-15-full-character-agent-runtime-with-llm-design.md`
- Create: `docs/character/character-actor-final-convergence-gap-report.md`

- [ ] **Step A1.1: Write a focused gap report describing what is still transitional on the actor-substrate side that blocks full character-agent final convergence**

The report must explicitly answer:

```text
- what parts of the current actor substrate are still transitional
- which of those transitions are acceptable temporary bridges for Stage B
- which ones must be resolved before Stage B can claim final-state L4 convergence
- how CharacterAgent L4 should enter the final actor substrate
```

- [ ] **Step A1.2: Include explicit mapping from current actor surfaces to final-state agent execution ingress**

The report must name at least:

```text
- CharacterIntentFrame
- CharacterPresentationInput
- shared control-mode execution path
- CharacterReplica / CharacterMotor / KnightRoleSkin current host chain
```

- [ ] **Step A1.3: Run docs verification**

Run:

```powershell
python scripts/verification/harness.py --profile docs
```

Expected: docs profile remains green or only shows unrelated pre-existing failures.

### Task A2: Add A Final-State Actor-Substrate Convergence Plan

**Files:**
- Create: `docs/superpowers/plans/2026-06-15-character-actor-final-convergence-implementation-plan.md`
- Modify: `docs/INDEX.md`
- Modify: `docs/character/character-actor-migration-status.md`

- [ ] **Step A2.1: Create the final convergence plan for the shared actor substrate**

That plan must sit above the near-term cleanup work and explicitly cover:

```text
- final shared actor scene/runtime target
- removing permanent reliance on transitional CharacterBase / CharacterReplica layering as architecture truth
- final ControllerPort / adapter-family ingress
- final CharacterIntentFrame / CharacterPresentationInput execution seam
- final agent/player/program control unification
- final local embodiment host chain for L4
```

- [ ] **Step A2.2: Mark the relationship between plans**

The repo docs must make clear:

```text
2026-06-15 character-actor architecture optimization plan = historical broader optimization plan
2026-06-15 near-term cleanup plan = current demo-safe cleanup pass
2026-06-15 actor final convergence plan = new final-state actor substrate convergence plan
2026-06-15 full character-agent plan = depends on the actor final convergence plan
```

- [ ] **Step A2.3: Update migration-status doc to reflect the new final convergence planning layer**

- [ ] **Step A2.4: Run docs verification**

Run:

```powershell
python scripts/verification/harness.py --profile docs
```

Expected: docs profile remains healthy.

---

## Stage B: Full Character-Agent Runtime Convergence

### Stage B Scope

Stage B implements:

- `char_a / char_b / char_c`
- full `CharacterAgent L1`
- LLM-backed `L2`
- LLM-backed `L3`
- dialogue generation
- three-layer memory
- session timeline
- model gateway
- `char_c` dual-loop control
- `ESM`-routed action requests
- final-state-oriented `L4` ingress into the shared actor substrate

### Task B1: Create Runtime Domain Skeleton And Compatibility Entry Points

**Files:**
- Create:
  - `backend/app/character_agent/__init__.py`
  - `backend/app/character_agent/runtime/`
  - `backend/app/character_agent/models/`
  - `backend/app/character_agent/memory/`
  - `backend/app/character_agent/reasoning/`
  - `backend/app/character_agent/planning/`
  - `backend/app/character_agent/execution/`
  - `backend/app/character_agent/storage/`
  - `backend/app/character_agent/gateway/`
- Modify:
  - legacy compatibility entrypoints under `backend/app/services/character_agent_*.py` as needed
- Test:
  - `backend/tests/test_character_agent_domain_structure_static.py`

- [ ] **Step B1.1: Write failing static tests that require the new domain structure and compatibility seams**

- [ ] **Step B1.2: Add the new backend directory skeleton and minimal `__init__` exports**

- [ ] **Step B1.3: Keep old service files as compatibility shells where needed instead of breaking imports immediately**

- [ ] **Step B1.4: Run focused static verification**

Run:

```powershell
python -m pytest -q backend\tests\test_character_agent_domain_structure_static.py
```

### Task B2: Implement `CharacterAgent L1` As Full Private Perception Runtime

**Files:**
- Create or migrate:
  - `backend/app/character_agent/runtime/l1_perception.py`
  - `backend/app/character_agent/models/private_world_snapshot.py`
  - `backend/app/character_agent/models/working_memory_state.py`
- Modify:
  - `backend/app/services/candidate_percept_service.py`
  - `backend/app/services/per_character_percept_filter.py`
  - `backend/app/main.py`
- Tests:
  - `backend/tests/test_character_agent_l1_full_runtime.py`
  - `backend/tests/test_character_agent_perception_quality.py`

- [ ] **Step B2.1: Write failing tests for full private snapshot fields and modality handling**

Include tests for:

```text
- visible_entities
- audible_entities
- unresolved_signals
- active_anomalies
- current_attention_targets
- short_horizon_social_presence
- local_spatial_confidence_map
- body_state_hints
- clarity_score / certainty_score
- partial / distorted / missed cases
```

- [ ] **Step B2.2: Extend the candidate/filter path so `CharacterAgent L1` receives all first-stage required modalities through role-private boundaries**

- [ ] **Step B2.3: Ensure `char_c` receives the same private perception treatment and does not bypass straight into L2/L3 just because the player exists**

- [ ] **Step B2.4: Run focused tests**

### Task B3: Implement Three-Layer Memory And Session Timeline

**Files:**
- Create:
  - `backend/app/character_agent/storage/session_store.py`
  - `backend/app/character_agent/storage/memory_store.py`
  - `backend/app/character_agent/memory/working_memory.py`
  - `backend/app/character_agent/memory/episodic_memory.py`
  - `backend/app/character_agent/memory/relational_memory.py`
  - storage schema / migrations or local persistence helpers
- Tests:
  - `backend/tests/test_character_agent_session_store.py`
  - `backend/tests/test_character_agent_episodic_memory.py`
  - `backend/tests/test_character_agent_relational_memory.py`
  - `backend/tests/test_character_agent_memory_writeback.py`

- [ ] **Step B3.1: Write failing tests for event timeline persistence and memory extraction**

- [ ] **Step B3.2: Implement local durable storage with future-db-friendly schema fields**

- [ ] **Step B3.3: Implement memory extraction from timeline events into episodic and relational/factual stores**

- [ ] **Step B3.4: Implement retrieval APIs that return compact structured memory bundles for L2/L3**

- [ ] **Step B3.5: Run focused tests**

### Task B4: Implement Model Gateway, Router, And Context Builder

**Files:**
- Create:
  - `backend/app/character_agent/gateway/model_gateway.py`
  - `backend/app/character_agent/gateway/model_router.py`
  - `backend/app/character_agent/gateway/context_builder.py`
  - `backend/app/character_agent/gateway/prompt_policy.py`
  - `backend/app/character_agent/gateway/output_validator.py`
- Tests:
  - `backend/tests/test_character_model_gateway.py`
  - `backend/tests/test_character_model_router.py`
  - `backend/tests/test_character_context_builder.py`

- [ ] **Step B4.1: Write failing tests for online-default plus local/hybrid-ready routing behavior**

- [ ] **Step B4.2: Implement provider abstraction without tying character logic to one API**

- [ ] **Step B4.3: Implement context assembly from snapshot + working memory + episodic retrieval + relational retrieval + control mode**

- [ ] **Step B4.4: Enforce policy and structured-output validation locally**

- [ ] **Step B4.5: Run focused tests**

### Task B5: Implement Full `L2` Reasoning

**Files:**
- Create:
  - `backend/app/character_agent/reasoning/l2_reasoner.py`
  - `backend/app/character_agent/models/interpretation_frame.py`
- Tests:
  - `backend/tests/test_character_agent_l2_reasoning.py`

- [ ] **Step B5.1: Write failing tests for subjective interpretation outputs**

- [ ] **Step B5.2: Implement `L2` large-model call path using the model gateway**

- [ ] **Step B5.3: Implement structured output mapping into interpretation frames**

- [ ] **Step B5.4: Run focused tests**

### Task B6: Implement Full `L3` Planning

**Files:**
- Create:
  - `backend/app/character_agent/planning/l3_planner.py`
  - `backend/app/character_agent/planning/triple_filter.py`
  - `backend/app/character_agent/models/intent_plan.py`
  - `backend/app/character_agent/models/player_suggestion_packet.py`
- Tests:
  - `backend/tests/test_character_agent_l3_planning.py`
  - `backend/tests/test_character_agent_triple_filter.py`
  - `backend/tests/test_character_agent_char_c_suggestion_mode.py`

- [ ] **Step B6.1: Write failing tests for candidate generation, triple-filter mapping, and `char_c` suggestion mode**

- [ ] **Step B6.2: Implement the model-assisted planning path**

- [ ] **Step B6.3: Keep final viability mapping and action-policy enforcement locally auditable**

- [ ] **Step B6.4: Implement `char_c` suggestion packets instead of forced auto intent in player-priority mode**

- [ ] **Step B6.5: Run focused tests**

### Task B7: Implement Full `L4` Five-Channel Execution Staging

**Files:**
- Create:
  - `backend/app/character_agent/execution/l4_executor.py`
  - `backend/app/character_agent/models/execution_plan.py`
  - `backend/app/character_agent/models/dialogue_act.py`
  - `backend/app/character_agent/models/presentation_plan.py`
  - `backend/app/character_agent/models/action_request_bundle.py`
- Tests:
  - `backend/tests/test_character_agent_l4_execution.py`
  - `backend/tests/test_character_agent_execution_channels.py`

- [ ] **Step B7.1: Write failing tests for the five channels and actor-substrate ingress outputs**

- [ ] **Step B7.2: Implement speech / face / body / social-spatial / physiology plans**

- [ ] **Step B7.3: Ensure local embodiment outputs target the shared actor-substrate seam rather than direct scene-node imperative control**

- [ ] **Step B7.4: Run focused tests**

### Task B8: Integrate `L4` Into The Shared Actor Substrate

**Files:**
- Modify:
  - backend-side actor output adapters
  - websocket envelopes
  - Godot actor-side consumption surfaces
  - shared actor execution contracts as needed
- Read/align with:
  - the actor final convergence plan created in Stage A
- Tests:
  - `backend/tests/test_character_agent_actor_substrate_integration.py`
  - `backend/tests/test_character_actor_bridge_static.py`
  - runtime-facing verification additions

- [ ] **Step B8.1: Write failing tests that prove agent-originated execution enters the shared actor substrate**

- [ ] **Step B8.2: Adapt execution output into the shared actor contracts rather than introducing a parallel path**

- [ ] **Step B8.3: Keep `char_a / char_b / char_c` on the same local embodiment host chain**

- [ ] **Step B8.4: Run focused tests**

### Task B9: Implement `char_c` Control Modes And Away Takeover

**Files:**
- Create or modify:
  - control-mode runtime helpers
  - player-priority arbitration layer
  - away-takeover policy layer
- Tests:
  - `backend/tests/test_character_agent_control_modes.py`
  - `backend/tests/test_character_agent_away_takeover.py`

- [ ] **Step B9.1: Write failing tests for `agent_full_auto`, `player_priority_assisted`, `away_conservative_takeover`, and `scripted_override`**

- [ ] **Step B9.2: Implement explicit player-priority arbitration**

- [ ] **Step B9.3: Implement allowed/forbidden action policy under away takeover**

- [ ] **Step B9.4: Run focused tests**

### Task B10: Implement Active `ESM`-Routed Action Requests

**Files:**
- Modify:
  - planner/executor outputs
  - `backend/app/main.py`
  - `ESM` request integration seams
- Tests:
  - `backend/tests/test_character_agent_action_request_routing.py`

- [ ] **Step B10.1: Write failing tests for agent-originated `action request` routing and settlement writeback**

- [ ] **Step B10.2: Implement allowed first-stage active request classes**

- [ ] **Step B10.3: Prove settlement still belongs to `ESM`**

- [ ] **Step B10.4: Run focused tests**

### Task B11: Full Verification And Alignment Closeout

**Files:**
- Modify if needed:
  - `docs/current-project-implementation-summary.md`
  - `docs/system-l1-current-implementation-summary.md`
  - `docs/character/character-actor-migration-status.md`
  - linked specs/plans if acceptance status needs syncing

- [ ] **Step B11.1: Run full backend and harness verification**

Run:

```powershell
python -m pytest -v
python scripts/verification/verify_phase0.py
python scripts/verification/verify_phase1_slice.py
python scripts/verification/verify_l1_runtime_edges.py
python scripts/verification/harness.py --profile docs
python scripts/verification/harness.py --profile phase0
python scripts/verification/harness.py --profile phase1-slice
```

- [ ] **Step B11.2: Sync docs so project status reflects the linked actor-substrate and character-agent state truth**

- [ ] **Step B11.3: Confirm that implementation reports distinguish clearly between:**

```text
- completed and verified
- completed but not Godot/runtime verified
- blocked
- next step
```

---

## Stage Exit Conditions

### Stage A Exit

Stage A is complete when:

1. the repo has an explicit shared actor-substrate final convergence plan
2. the relationship between actor-substrate convergence and character-agent convergence is documented
3. the full character-agent plan can reference that actor-side plan as a concrete dependency

### Stage B Exit

Stage B is complete only when:

1. `char_a / char_b / char_c` run through one full character-agent runtime species
2. `L4` enters the shared actor substrate
3. memory, model, planning, and control-mode features are implemented and verified
4. `System L1 / ESM` authority boundaries remain green

---

## Planning Notes

- Stage A may partially overlap with Stage B for scaffolding, but Stage B must not claim final-state convergence until Stage A has created the actor-side final convergence truth.
- Transitional bridge files may be used tactically, but every Stage B task must move toward final-state convergence rather than thickening the transition.
- If Stage A reveals that existing actor-side plans are sufficient after explicit linking and status sync, Stage A may close with a lightweight new convergence plan plus dependency report instead of a large code change batch.
