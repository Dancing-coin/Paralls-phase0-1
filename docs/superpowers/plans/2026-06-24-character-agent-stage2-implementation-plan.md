# Character Agent Stage 2 Design Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the `2026-06-24` Stage 2 design into an explicit implementation track so the repository can evolve from a runnable character-agent skeleton into a reusable role-mind substrate without drifting outside the Phase 0 demo boundary.

**Architecture:** Keep the current authority boundaries frozen: `System L1 / ESM` remain world-truth authority, `CharacterAgentRuntime` remains the role-mind chain, `Siming` remains catalyst-only, and the Godot actor stack remains the shared embodiment host. Build Stage 2 by layering profile truth, structured memory, knowledge-state progression, and grounded `L2 -> L3 -> L4` decisions on top of the existing runtime rather than introducing a parallel cognition or embodiment path.

**Tech Stack:** Python backend runtime, current character-agent services and models, Godot 4.6 shared actor stack, pytest, and existing harness verification profiles.

---

## Relationship To Existing Plans

This plan is the implementation anchor for:

- `docs/superpowers/specs/2026-06-24-character-agent-stage2-design.md`

It does not replace the already-landed or already-scoped closeout plans:

- `docs/superpowers/plans/2026-06-18-character-agent-stage2-closeout-plan.md`
- `docs/superpowers/plans/2026-06-19-character-actor-stage2-closeout-implementation-plan.md`

Those earlier plans remain valid for:

- runtime closeout on the current backend lane
- actor-side shared-host and ingress tightening
- verification truth alignment for the current repo slice

This new plan is the umbrella for the broader Stage 2 design itself: profile truth, memory, knowledge, grounded interpretation/planning, and legal `Siming` mentality influence.

---

## Scope

This plan covers:

- a structured-file-first `CharacterProfile` system
- four-pool memory state for role continuity
- explicit knowledge-state progression
- grounded `L2` interpretation from profile + memory + knowledge + private snapshot
- grounded `L3` planning from current subjective reality
- minimal but visible `L4` execution that stays inside current actor contracts
- a catalyst-only `Siming -> role mentality` influence protocol

This plan does not cover:

- database persistence as a release requirement
- full facial expression or full binder rollout
- direct world-truth writes from character reasoning
- a second actor species or second embodiment chain
- Phase 1 production redesign work

---

## Task 1: Freeze Stage 2 Profile Truth

**Files:**
- Create or modify:
  - `backend/app/character_agent/**/profile*`
  - `backend/tests/test_character_agent_*profile*`
  - structured profile assets under the current repo conventions

- [ ] Define the runtime `CharacterProfile` object and its read-only subviews.
- [ ] Freeze the required Stage 2 identity, trait, value, constraint, style, and conversation-bias inputs in tests before broad implementation.
- [ ] Keep profile truth immutable at runtime except for load/validation/normalization.

**Exit target:** runtime mind layers no longer read ad-hoc role identity from scattered constants or role-specific branches.

---

## Task 2: Add Four-Pool Memory And Knowledge State

**Files:**
- Create or modify:
  - `backend/app/character_agent/**/memory*`
  - `backend/app/character_agent/**/knowledge*`
  - focused tests under `backend/tests/test_character_agent_*`

- [ ] Add explicit Event / Observation / Knowledge / Social memory pools.
- [ ] Keep `PrivateWorldSnapshot` separate from durable memory state.
- [ ] Define the minimum `KnowledgeState` update path from perception, dialogue, and settlement outcomes.
- [ ] Preserve current runtime compatibility where old call sites still need transitional adapters.

**Exit target:** subjective continuity is represented as structured state instead of only short-horizon snapshot data.

---

## Task 3: Ground `L2 -> L3` In Stage 2 Inputs

**Files:**
- Modify:
  - `backend/app/character_agent/**/interpret*`
  - `backend/app/character_agent/**/plan*`
  - focused tests for interpretation and planning slices

- [ ] Make `L2` consume profile, memory, knowledge, and current private snapshot as first-class inputs.
- [ ] Make `L3` derive intent from `L2` outputs instead of thin command heuristics alone.
- [ ] Keep the output surface compatible with the existing action-request and dialogue-authority boundaries.

**Exit target:** role planning becomes grounded in subjective state rather than only reactive runtime triggers.

---

## Task 4: Legal `Siming` Mentality Influence

**Files:**
- Modify:
  - `backend/app/**/siming*`
  - `backend/app/character_agent/**`
  - tests covering `Siming` catalyst intake and effect boundaries

- [ ] Define how `Siming` changes salience, pressure, mood bias, or attention weighting without replacing final agency.
- [ ] Preserve the rule that `Siming` does not directly drive low-level motion or world truth.
- [ ] Record the catalyst path in memory or runtime state where verification needs evidence.

**Exit target:** `Siming` becomes a legal mentality catalyst rather than an out-of-band direct controller.

---

## Task 5: Visible Minimal `L4` Expression

**Files:**
- Modify:
  - `scripts/character/**`
  - `scripts/ui/**`
  - `scenes/phase0/**`
  - focused static/runtime verification under `backend/tests` and `scripts/verification/tests`

- [ ] Keep `L4` inside the existing shared actor ingress and presentation contracts.
- [ ] Surface a minimal but visible expression set for intent, target, and immediate reason.
- [ ] Avoid introducing a second embodiment protocol or a raw pose-stream dependency.

**Exit target:** Stage 2 decisions are observable in the live scene without breaking the current actor architecture.

---

## Verification Order

1. Focused pytest for each touched Stage 2 slice.
2. `python -m pytest -q`
3. `python scripts/verification/harness.py --profile docs`
4. `python scripts/verification/harness.py --profile character-agent-execution`
5. `python scripts/verification/harness.py --profile phase0`

If a given slice changes authority, message contracts, or runtime proof surfaces, rerun the narrower harness or verifier that directly proves that claim before declaring completion.

---

## Constraints

- Preserve the Phase 0 demo boundary; do not widen into Phase 1 redesign work.
- Preserve the current backend-authority and Godot-embodiment split.
- Do not introduce a second role-mind lane beside the current `CharacterAgentRuntime`.
- Prefer incremental adapters and reuse over large new abstractions.
- Keep verification claims tied to actual runtime or harness evidence.
