# Character Actor Stage 2 Closeout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the remaining Stage 2 actor-side convergence gaps so shared ingress and presentation contracts become the active actor-runtime truth, the `CharacterReplica` lineage is the explicit shared host chain, and default runtime execution no longer depends on migration-period diagnostics.

**Architecture:** Build on the already-landed `CharacterControllerPort`, adapter family, `CharacterRuntimeState`, and `CharacterPresentationInput` seams instead of inventing new actor contracts. Keep the frozen host choice intact: `CharacterReplica` lineage remains the shared actor host, while `CharacterBase` stays a player-shell wrapper only. Finish the remaining cleanup by moving residual actor-side consumers onto shared contract helpers, tightening wrapper-to-host ownership boundaries, and deleting or explicitly gating migration diagnostics.

**Tech Stack:** Godot 4.6 scenes, GDScript, current Phase 0 player/actor runtime, existing pytest static checks, harness verification profiles, and current actor-architecture docs under `docs/character/`.

---

## Relationship To The Previous Closeout

This plan is the direct follow-on to:

- `docs/superpowers/plans/2026-06-18-character-agent-stage2-closeout-plan.md`

That earlier closeout already covered:

- gateway/main-path unification work that was still open at the time
- runtime/durability truth tightening on the backend side
- first-batch actor seam tightening around `character_agent_execution`
- verifier alignment work needed to keep current runtime proof honest

This new plan only covers the three remaining actor-side closeout packages still left open in current repo truth:

1. actor ingress final tightening
2. shared actor host convergence
3. diagnostic surface cleanup

It does not reopen provider scope, broader Stage B architecture, or Phase 1 redesign work.

---

## Current Handoff Truth

- `completed but not runtime-verified`
  - these remaining items are planning truth extracted from current docs and landed code; they are not already implemented work
- `blocked`
  - none
- `next step`
  - execute the three work packages below, then rerun focused actor/runtime verification and Phase 0 runtime proof

---

## Scope

This closeout plan covers:

- moving remaining actor-side consumers off `CharacterReplica` local field/helper reads and onto `CharacterRuntimeState` / `CharacterIntentFrame` / `CharacterPresentationInput`
- tightening the final shared actor host chain so the player-only wrapper split stops defining architecture truth
- removing or explicitly debug-gating remaining migration diagnostics so default runtime paths stay clean

This closeout plan does not cover:

- new backend providers or request surfaces
- typed-resource replacement of the current dictionary-based actor contracts unless a touched invariant forces it
- new player-only or agent-only actor species
- broader Phase 1 actor/runtime redesign

---

## Task 1: Actor Ingress Final Tightening

**Files:**
- Modify:
  - `scripts/character/CharacterReplica.gd`
  - `scripts/character/CharacterRuntimeState.gd`
  - `scripts/character/CharacterPresentationInput.gd`
  - `scripts/character/CharacterMotor.gd`
  - `scripts/character/KnightRoleSkin.gd`
- Modify if static tests force remaining ingress consumers into scope:
  - `scripts/player/PlayerShell.gd`
  - `scripts/player/Phase0PlayerBridge.gd`
  - `scripts/player/Phase0ViewAnchorResolver.gd`
- Test:
  - `backend/tests/test_character_final_actor_contracts_static.py`
  - `backend/tests/test_character_shared_ingress_static.py`
  - `backend/tests/test_character_runtime_state_extraction_static.py`

- [ ] Audit the remaining actor-side reads that still unpack normalized intent frames or presentation payloads through `CharacterReplica` shell-local fields, `Dictionary.get(...)` calls, or one-off helper branches.
- [ ] Move remaining ingress reads onto shared contract helpers so actor-side consumers read from `CharacterRuntimeState`, normalized `CharacterIntentFrame` accessors, or `CharacterPresentationInput` accessors instead of reinterpreting frame/presentation shape inline.
- [ ] Keep `CharacterReplica` as scene-local orchestration shell only: it may coordinate host wiring and apply side effects, but it must not regain ownership of raw ingress/presentation parsing that already belongs to shared contracts.
- [ ] Extend the focused static tests so any remaining actor-side bypass of the shared ingress/presentation contract fails explicitly instead of staying as oral-history cleanup debt.
- [ ] Run focused contract tests:

```powershell
python -m pytest -q backend/tests/test_character_final_actor_contracts_static.py backend/tests/test_character_shared_ingress_static.py backend/tests/test_character_runtime_state_extraction_static.py
```

**Exit target:** the shared ingress/presentation contract is no longer only the `character_agent_execution` seam truth; it is the actor-side default contract family.

---

## Task 2: Shared Actor Host Convergence

**Files:**
- Modify:
  - `scenes/phase0/CharacterBase.tscn`
  - `scenes/phase0/CharacterReplica.tscn`
  - `scripts/character/CharacterReplica.gd`
  - `scripts/player/PlayerShell.gd`
  - `scripts/player/Phase0PlayerBridge.gd`
  - `scripts/player/Phase0ViewAnchorResolver.gd`
  - `scripts/player/CameraOcclusionFader.gd`
- Modify docs that freeze or explain host truth:
  - `docs/character/character-actor-migration-status.md`
  - `docs/character/character-control-chain.md`
  - `docs/scene tree.md`
- Test:
  - `backend/tests/test_character_actor_scene_convergence_static.py`
  - `backend/tests/test_player_forward_direction_static.py`

- [ ] Inventory the remaining wrapper-owned responsibilities that still leak actor architecture truth, including wrapper-specific node lookup, wrapper-owned actor-facing helper names, or docs/tests that still describe the wrapper split as the runtime species.
- [ ] Tighten the shared host chain around the already-frozen `CharacterReplica` lineage so `CharacterBase` remains wrapper/player-shell surface only and no longer implicitly defines the shared actor architecture through scene shape or helper ownership.
- [ ] Prefer actor-facing aliases and shared-host seams from `CharacterReplica` and `PlayerShell` over nested wrapper/tree knowledge in bridge, anchor, or camera helper code; keep compatibility fallbacks thin and explicitly migration-only.
- [ ] Update scene/runtime docs and static tests so they enforce the intended host choice and catch any regression where new actor-runtime ownership drifts back onto the player-only wrapper layer.
- [ ] Run focused host-convergence tests:

```powershell
python -m pytest -q backend/tests/test_character_actor_scene_convergence_static.py backend/tests/test_player_forward_direction_static.py
```

**Exit target:** the player-only wrapper split no longer defines actor architecture truth in code, scene shape, or repo-local docs.

---

## Task 3: Diagnostic Surface Cleanup

**Files:**
- Modify runtime/debug surfaces:
  - `scripts/character/CharacterReplica.gd`
  - `scripts/character/KnightRoleSkin.gd`
  - `scripts/autoload/LocalPresentationBus.gd`
  - `scripts/phase0/MainDemoController.gd`
- Modify probe/verification surfaces if retained diagnostics still need harness access:
  - `scripts/verification/verify_character_agent_execution.py`
  - `scripts/verification/tests/test_character_agent_execution_verify.py`
- Modify focused static checks:
  - `backend/tests/test_character_debug_toggle_static.py`
- Modify docs if the surviving debug path needs explicit repo truth:
  - `docs/character/character-actor-migration-status.md`
  - `docs/character/character-debug-and-verification.md`

- [ ] Inventory remaining migration diagnostics across actor runtime, presentation, bus, and verification surfaces with repo-wide search rather than ad-hoc local memory.
- [ ] Delete diagnostics that no longer prove a live invariant or that duplicate stronger harness/runtime evidence already present elsewhere in the repo.
- [ ] Keep only the diagnostics that still carry verification value, and route them through explicit debug/harness toggles such as `set_debug_logging_enabled(...)`, autotest flags, or `PHASE0_DEBUG_LOGGING=1` rather than default runtime execution.
- [ ] Extend focused static tests so the default runtime path fails if always-on migration logs or ungated debug noise are reintroduced.
- [ ] Run focused diagnostic tests:

```powershell
python -m pytest -q backend/tests/test_character_debug_toggle_static.py scripts/verification/tests/test_character_agent_execution_verify.py
```

**Exit target:** runtime default paths no longer depend on migration-period logging surfaces; retained diagnostics are explicit, opt-in verification tools.

---

## Task 4: Verification And Closeout Handoff

**Files:**
- Modify if execution evidence changes the wording:
  - `docs/character/character-actor-migration-status.md`
  - `docs/character/character-actor-final-convergence-gap-report.md`
  - `docs/current-project-implementation-summary.md`

- [ ] Run the focused static checks tied to the three work packages:

```powershell
python -m pytest -q backend/tests/test_character_final_actor_contracts_static.py backend/tests/test_character_shared_ingress_static.py backend/tests/test_character_runtime_state_extraction_static.py backend/tests/test_character_actor_scene_convergence_static.py backend/tests/test_player_forward_direction_static.py backend/tests/test_character_debug_toggle_static.py scripts/verification/tests/test_character_agent_execution_verify.py
```

- [ ] Run documentation freshness verification:

```powershell
python scripts/verification/harness.py --profile docs
```

- [ ] Run the narrow shared-actor runtime proof:

```powershell
python scripts/verification/harness.py --profile character-agent-execution
```

- [ ] Run the broader Phase 0 runtime proof:

```powershell
python scripts/verification/harness.py --profile phase0
```

- [ ] Update migration-status wording only after fresh evidence confirms the closeout state; do not advance Stage B or final `L4 -> CharacterActor` wording ahead of proof.

---

## Constraints

- Do not introduce a parallel actor ingress family beside `CharacterRuntimeState` / `CharacterIntentFrame` / `CharacterPresentationInput`.
- Do not let `CharacterBase` or another player-only wrapper reclaim actor-runtime ownership during cleanup.
- Do not restore default always-on migration logging to make verification easier.
- Do not broaden this closeout into Phase 1 actor redesign or non-actor backend work.
- Keep diffs small, reversible, and consistent with existing repo seam-tightening patterns.

---

## Exit Conditions

This plan is complete when:

1. remaining actor-side consumers read shared ingress/presentation truth through `CharacterRuntimeState`, `CharacterIntentFrame`, and `CharacterPresentationInput` instead of shell-local parsing
2. the shared actor host chain is tighter and the player-only wrapper split no longer defines actor architecture truth
3. migration diagnostics are either deleted or explicitly routed through debug/harness toggles
4. focused static tests are green
5. `character-agent-execution` and `phase0` runtime verification remain green
6. migration docs describe the new closeout state without overstating final Stage B completion

---

## Handoff Rule

After this plan lands, the repo should be able to describe Actor Stage 2 as closed at the remaining-work-package level.

That still does **not** authorize:

- retroactively claiming work that was only planned here
- broadening into Phase 1 architecture cleanup
- overstating full single-path `L4 -> CharacterActor` completion without whatever downstream Stage B proof still remains
