# 3D Scripted-Mystery Action Platform Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the existing embodied interaction and P5 conflict surfaces into a reusable one-second-window 3D investigation/pursuit action platform.

**Architecture:** Reuse existing action primitives, embodied controller, asset registry, Skill/Body gates, P5 conflict authority, event store and replay. Add only package-local graph orchestration, window evidence, frozen spatial validation and owner-bound consequence adapters.

**Tech Stack:** Python/Pydantic, existing GameplayEventStore and replay, existing Godot GDScript embodiment/mirror, pytest and Harness.

**Spec:** `docs/superpowers/specs/world-character-siming-authority-mainline/2026-09-04-3d-scripted-mystery-action-platform-design.md`

---

## Global constraints

- Stay on `main`; preserve existing user changes and frozen package revisions.
- Do not add a second runtime, store, bus, clock, scheduler, generic writer or conflict store.
- Do not change old `ActionIntent`, P5 event payloads or existing embodied rows incompatibly.
- New action graphs may only compose registered primitives and owner-approved fragments.
- Client/Godot/Character/Siming output remains intent or evidence, never canonical truth.

### Task 1: Graph content and admission

**Files:**
- Create: `backend/app/gameplay/action_graph_content.py`
- Test: `backend/tests/test_action_graph_content.py`

- [x] Add strict models `ActionGraphDefinition`, `ActionGraphNode`, `ActionGraphEdge` and `ActionGraphAdmissionResult` with frozen fields from the spec.
- [x] Reuse `ActionPrimitiveDefinition` references and existing semantic/policy validators; reject unknown refs, duplicate arrays, unbounded cycles, unreachable terminal nodes and missing recovery.
- [x] Add tests for a valid graph, unknown primitive, duplicate node, cycle without bounded loop, conflicting edge and missing recovery; assert no event-store access occurs during content validation.
- [ ] Run `python -m pytest backend/tests/test_action_graph_content.py -q` and `python -m compileall -q backend`.

### Task 2: Window intent and frozen spatial validation

**Files:**
- Create: `backend/app/gameplay/action_window_runtime.py`
- Modify: `backend/app/gameplay/shared_contracts.py` only for exports/compatibility aliases
- Test: `backend/tests/test_action_window_runtime.py`

- [x] Add strict `ActionWindowIntent`, `SpatialSnapshotRef`, `PerceptionResolution` and `ActionWindowResult` models; keep old `ActionIntent` unchanged.
- [x] Implement a read-only validator that checks window ordering, graph/node membership, target scope, navigation/collision/occlusion/sound revisions and deterministic sample bounds.
- [x] Add tests for valid movement, stale spatial revision, out-of-order window, changed duplicate, private evidence leakage and measurement conflict; all rejection paths must leave the store unchanged.
- [ ] Run the focused test file and existing embodied/action tests.

### Task 3: Reuse the existing local embodied controller

**Files:**
- Modify: `scripts/interaction/EmbodiedActionController.gd`
- Modify: `scripts/character/CharacterReplica.gd` only where needed for first-person camera presentation
- Test: `backend/tests/test_action_window_godot_contract_static.py`

- [x] Add graph-node playback selection, one-second window bookkeeping, interruption and recovery hooks to the existing controller; do not create a second controller.
- [x] Add a presentation-only first-person camera toggle; retain the same actor, action attempt and committed projection identifiers.
- [x] Ensure rejected windows clear speculative movement/action/panel state and return the controller to the last committed phase.
- [ ] Add static tests for controller reuse, camera-only switching, rejection cleanup and absence of direct world writes.
- [ ] Run the focused static tests and the existing embodied interaction Harness.

### Task 4: Extend the existing P5 conflict authority

**Files:**
- Modify: `backend/app/gameplay/p5/investigation_conflict.py`
- Modify: `backend/app/gameplay/p5/contracts.py` only for additive typed request/result fields
- Test: `backend/tests/test_action_conflict_window.py`

- [x] Add a compatibility façade or additive methods that resolve one `ActionWindowIntent` into the bounded window event surface from the spec.
- [x] Reuse current P5 registry, owner-fragment validation, `SettlementPlan`, append-derived receipt, privacy filtering and replay projector.
- [x] Implement movement/visibility/sound/pursuit/contact/control/capture/retreat and case-terminal results as typed sub-results; reject client assertions that disagree with frozen spatial validation.
- [x] Add tests for survivor/pursuer/witness roles, visibility isolation, duplicate/changed duplicate, stale revisions, contact conflict and no partial append.
- [ ] Run P5 regression and focused action-conflict tests.

### Task 5: Owner-bound consequences and two-level death

**Files:**
- Modify: existing Body/Inventory/Quest/Social/Character owner adapters only where required
- Create: `backend/tests/test_action_consequence_boundaries.py`

- [x] Add fixed fragment contracts for Body recovery/control, Inventory condition, Quest/Knowledge exposure, Social witness and Character/World death confirmation.
- [x] Keep case death terminal to the encounter; require an explicit player/story confirmation before persistent death.
- [x] Add zero-write tests for missing confirmation, stale source, private evidence, wrong owner fragment, duplicate and changed duplicate.
- [ ] Run all focused consequence tests plus existing P5 replay tests.

### Task 6: Godot UI/TTS and reference scene

**Files:**
- Create or modify: `scenes/phase0/ScriptedMysteryActionProbe.tscn`
- Create or modify: `scripts/verification/ScriptedMysteryActionProbe.gd`
- Create: `backend/tests/test_scripted_mystery_projection.py`
- Create: `.harness/profiles/3d-scripted-mystery-action-platform.json`
- Create: `scripts/verification/verify_3d_scripted_mystery_action_platform.py`

- [x] Build the three-room reference scene from existing Godot primitives and reviewed affordance bridges; add hide spots, occluders, sound zones, door and clue without external art dependencies.
- [x] Expose committed action/encounter state, current phase, exposure, control, capture/escape and terminal outcome through a read-only projection.
- [x] Add revisioned voice templates for preparing, detected, captured, escaped, rejected and returned states.
- [x] Verify speculative state clears on rejection and committed state survives reconnect/replay.
- [x] Run focused projection tests and the new Harness profile; Godot headless/desktop probes remain environment-gated.

### Task 7: Full replay, docs and release gate

**Files:**
- Create: `backend/tests/test_3d_scripted_mystery_action_replay.py`
- Modify: mainline spec/plan README and August action/P5 mapping docs

- [x] Prove full replay and checkpoint-tail replay equality across three action windows and explicit death confirmation accept/reject paths.
- [x] Prove tampered graph, spatial snapshot, perception sample, policy, event payload and checkpoint rejection through focused validators and replay tests.
- [x] Run full repository pytest (`5092 passed`), compileall, diff check, action/embodied/docs Harness and Godot 4.6.3 headless probe.
- [x] Record a completion audit that distinguishes implemented bounded action platform from future full combat/sports capability; August INF A-D remains not complete.

## Rollout gates

1. Graph admission must pass before window runtime.
2. Window/spatial validation must pass before conflict extension.
3. Conflict replay/privacy must pass before cross-owner consequences.
4. Consequences and death confirmation must pass before Godot reference delivery.
5. All focused, replay, Harness and Godot probes must pass before marking this platform `implemented bounded`.

## Explicit future extension seams

- Sports and combat packages reuse `ActionPrimitiveDefinition`, `ActionGraphDefinition`, `ActionWindowIntent` and frozen spatial snapshots.
- Higher-frequency server authority can replace the window transport without changing graph semantics or owner consequence contracts.
- Creator Skill/Siming Director consume graph/package admission APIs but are not implemented in this plan.
- New facts such as ball possession, hit points, vehicles or league standings require their own owner family and event contract.
