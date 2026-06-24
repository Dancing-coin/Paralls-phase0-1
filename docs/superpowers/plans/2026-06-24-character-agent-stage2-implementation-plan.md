# Character Agent Stage 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver the full `2026-06-24` Stage 2 character-agent spec on current mainline by completing profile/generalization, four-pool memory + knowledge state, grounded `L2/L3` with legal `Siming` influence, and visible minimal `L4` scene expression.

**Architecture:** Do not build a second runtime. Keep `CharacterAgentRuntime` as the one role-mind chain, keep `System L1 / ESM` as settlement authority, keep the Godot shared actor ingress as the only embodiment path, and deepen the merged `Siming` path into a legal mentality input. Replace transitional truths in-place: hardcoded actors, thin memory layering, placeholder persona/logic filtering, and shallow execution semantics.

**Tech Stack:** Python backend runtime, Pydantic models, YAML/JSON profile assets, current `CharacterAgentRuntime`, current `Siming` bridge/runtime, Godot 4.6 shared actor stack, pytest, and existing verification harness profiles.

---

## Why This Plan Is Split

The Stage 2 spec is too large for a single implementation plan without losing execution clarity.

Current mainline already contains:

- merged `Siming` runtime + character dispatch
- current `CharacterAgentRuntime`
- working/suggestion control-mode split
- shared actor ingress

But it still lacks:

- generalized role registration
- real structured profile truth
- explicit observation/knowledge/social memory layers
- explicit knowledge-state progression
- real persona/logic/gain-loss filtering grounded in profile + memory + knowledge
- scene-visible basic `L4` semantics beyond the current thin execution bridge

So Stage 2 is split into four dependent plans plus this roadmap:

1. `2026-06-24-character-profile-generalization-implementation-plan.md`
2. `2026-06-24-character-memory-knowledge-implementation-plan.md`
3. `2026-06-24-character-reasoning-siming-implementation-plan.md`
4. `2026-06-24-character-l4-scene-expression-implementation-plan.md`

## Execution Order

- [ ] Execute Plan 1 first: profile truth + role generalization.
- [ ] Execute Plan 2 second: four-pool memory + knowledge state.
- [ ] Execute Plan 3 third: `L2/L3` grounding + merged `Siming` mentality protocol.
- [ ] Execute Plan 4 fourth: `L4` basic expression + Godot/runtime verification.
- [ ] Re-run broad verification after all four plans land.

## Cross-Plan Constraints

- [ ] Do not keep `SUPPORTED_ACTORS = {"char_a", "char_b", "char_c"}` as architecture truth after Plan 1.
- [ ] Do not collapse `Observation Memory` and `Knowledge Memory` back into episodic or working memory during Plans 2 and 3.
- [ ] Do not let `Siming` bypass `L2/L3`; all Plan 3 work must preserve merged-bridge legality constraints.
- [ ] Do not introduce a second embodiment path; all Plan 4 work must continue through `CharacterRuntimeState` and `CharacterPresentationInput`.
- [ ] Keep `Phase 0` loop working after each plan, not only at the end.

## Coverage Map

| Spec area | Owning plan |
| --- | --- |
| Structured-file-first profile system | Plan 1 |
| Arbitrary-role runtime generalization | Plan 1 |
| Four-pool memory | Plan 2 |
| Knowledge-state progression | Plan 2 |
| `L2` profile + memory + knowledge grounding | Plan 3 |
| `L3` real persona/logic/gain-loss filtering | Plan 3 |
| Legal `Siming` mentality influence | Plan 3 |
| Visible minimal `L4` expression | Plan 4 |
| Godot shared-ingress preservation | Plan 4 |
| End-to-end verification | Plan 4 + final sweep |

## Final Verification Sweep

- [ ] Run targeted pytest suites from each sub-plan.
- [ ] Run `python -m pytest -q`.
- [ ] Run `python scripts/verification/harness.py --profile docs`.
- [ ] Run `python scripts/verification/harness.py --profile character-agent-execution`.
- [ ] Run `python scripts/verification/harness.py --profile phase0`.
- [ ] Run `python scripts/verification/verify_phase1_slice.py` if Plan 3 or Plan 4 changed runtime proof surfaces.

## Commit Strategy

- [ ] Commit after each plan lands and passes its local verification set.
- [ ] Keep profile/generalization, memory/knowledge, reasoning/Siming, and L4/Godot work in separate lore-style commits.
- [ ] Do not batch multiple plans into one commit unless unavoidable due to shared-file sequencing.

## Handoff

- [ ] Use this roadmap only as the ordering and coverage index.
- [ ] Implement from the four detailed sub-plans below, not from this file alone.
