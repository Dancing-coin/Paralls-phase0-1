# Character Director Observatory Finalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the `Character Director Observatory` so it directly reaches the original product expectation: real in-scene multi-role observability with `Siming`, world settlement, and script-style replay all visible on the normal developer runtime path.

**Architecture:** Keep the current structured observatory message family, but move the projection responsibilities into the real backend runtime stages instead of relying primarily on `backend/app/main.py` post-processing. Then upgrade the Godot observatory from text-first scaffolding into a real dramatic workstation with meaningful space overlays, paired dialogue accounting, and director-monitor detail, while preserving `ESM` authority boundaries and developer-only gating.

**Tech Stack:** FastAPI backend, `CharacterAgentRuntime`, `SimingRuntime`, authority event bus, Godot 4.6 scenes and GDScript, `BackendBridge`, `LocalPresentationBus`, pytest, harness verification.

---

## Source Of Truth And Scope Freeze

This plan extends but does not replace:

- `docs/superpowers/specs/2026-06-21-character-director-observatory-design.md`
- `docs/superpowers/plans/2026-06-21-character-director-observatory-implementation-plan.md`
- `docs/character/character-agent-runtime-architecture.md`
- `docs/character/character-actor-migration-status.md`
- `docs/phase1/core/01-运行时核心/司命/19-司命接入事件总线后端设计.md`

This plan exists because the first observatory implementation passed repo verification but still fell short of the original expectation in four ways:

1. projection is still centered in `backend/app/main.py` instead of the real runtime owners
2. default developer runtime path does not automatically receive observatory payloads
3. the Godot observatory surfaces are still mostly text scaffolds rather than a real dramatic workstation
4. there is no observatory-specific runtime proof that the surfaces themselves are populated and usable in-scene

This plan must close those gaps directly. It is not an “improve later” pass.

---

## Required End State

This plan is complete only when all of these are true:

1. `CharacterAgentRuntime` emits structured observatory snapshots/events from its real stage transitions
2. `SimingRuntime` / `SimingEventPipeline` emit structured observatory snapshots/events from their real decision flow
3. world-outcome and script-beat projection remain structured and aligned to actor intent, `Siming`, and settlement
4. the default developer runtime path for `MainDemo` can populate the observatory without requiring a hidden backend-only environment toggle
5. `RelationshipOverlay` uses scene-space geometry / markers rather than only text rows
6. `DirectorMonitorPanel` behaves like a real director workstation with cast, scene, world, and `Siming` detail
7. `ScriptTimelinePanel` supports meaningful beat review, expansion, and filtering
8. `DialogueSceneLedger` supports true per-pair cross-role accounting instead of only single-actor summary echo
9. `Freeze Mode` actually freezes observatory updates while preserving visible inspection state
10. observatory-specific runtime verification proves these surfaces work in-scene
11. developer-only / hidden-by-default remains true
12. backend / docs / Godot verification remain green

---

## Task 1: Move Character Observatory Projection Into The Runtime Owner

**Files:**
- Modify:
  - `backend/app/character_agent/runtime/runtime_loop.py`
  - `backend/app/services/character_agent_runtime.py`
- Reuse:
  - `backend/app/services/character_agent_debug_projection.py`
- Create or modify tests:
  - `backend/tests/test_character_agent_debug_projection.py`
  - `backend/tests/test_character_agent_runtime_memory_integration.py`
  - `backend/tests/test_character_agent_runtime.py`

- [ ] **Step 1.1: Write failing tests that require runtime-owned observatory emission hooks**

The tests must prove observatory projection is triggered from real runtime stages, not only from `backend/app/main.py`.

Required stage coverage:

```text
- character_perceived_event
- self_body_perceived_event
- interpretation
- decision
- execution request
- suggestion packet
- settlement result
- dialogue writeback
```

- [ ] **Step 1.2: Add runtime-owned observatory emission storage/drain surfaces**

Required shape:

```python
class CharacterAgentRuntime:
    def drain_observatory_messages(self, actor_id: str | None = None) -> list[dict[str, object]]:
        ...
```

This queue must be filled inside runtime-stage methods, not reconstructed later from websocket output.

- [ ] **Step 1.3: Call `CharacterAgentDebugProjection` from the real runtime stage transitions**

Implement the stage calls where the runtime already knows:

- snapshot after perception/body/siming update
- interpretation object
- decision object
- execution plan writeback
- suggestion packet writeback
- settlement/dialogue writeback

- [ ] **Step 1.4: Keep compatibility shell behavior intact**

The runtime must still support existing command/suggestion behavior while also owning observatory emission.

- [ ] **Step 1.5: Run focused tests**

Run:

```powershell
python -m pytest -q backend/tests/test_character_agent_debug_projection.py backend/tests/test_character_agent_runtime_memory_integration.py backend/tests/test_character_agent_runtime.py
```

---

## Task 2: Move Siming Observatory Projection Into Runtime / Pipeline Owners

**Files:**
- Modify:
  - `backend/app/services/siming_runtime.py`
  - `backend/app/services/siming_event_pipeline.py`
  - `backend/app/services/siming_event_producer.py`
- Reuse:
  - `backend/app/services/siming_debug_projection.py`
- Create or modify tests:
  - `backend/tests/test_siming_debug_projection.py`
  - `backend/tests/test_siming_event_pipeline.py`
  - `backend/tests/test_siming_authority_bus_provenance.py`

- [ ] **Step 2.1: Write failing tests for real Siming-owned observatory stage emission**

The tests must prove snapshot/event emission from:

```text
- fairness snapshot creation
- intervention candidate creation
- intervention decision creation
- dispatch/no_action finalization
- downstream status / audit linkage
```

- [ ] **Step 2.2: Add pipeline/runtime observatory message queue or return-path support**

The projection result must be available to the websocket path without rebuilding it from `siming_output` envelopes alone.

- [ ] **Step 2.3: Emit structured Siming observatory records during the real decision flow**

Must preserve:

- selected path
- intervention band
- target
- reason
- downstream status
- no-action reason

- [ ] **Step 2.4: Run focused tests**

Run:

```powershell
python -m pytest -q backend/tests/test_siming_debug_projection.py backend/tests/test_siming_event_pipeline.py backend/tests/test_siming_authority_bus_provenance.py
```

---

## Task 3: Narrow `main.py` To Delivery / Aggregation Instead Of Primary Projection Ownership

**Files:**
- Modify:
  - `backend/app/main.py`
- Create or modify tests:
  - `backend/tests/test_observatory_message_delivery_static.py`
  - `backend/tests/test_ws_protocol.py`
  - `backend/tests/test_visual_fact_pipeline.py`

- [ ] **Step 3.1: Write failing tests that reject `main.py` as the primary observatory projection owner**

The tests should require:

```text
- character observatory messages are drained from CharacterAgentRuntime
- siming observatory messages are drained from Siming runtime/pipeline owner
- main.py only serializes and delivers those records
```

- [ ] **Step 3.2: Refactor websocket finalization to consume owner-emitted observatory records**

`main.py` may still aggregate world/script layers, but it must not be the main creator of actor/siming observatory truth.

- [ ] **Step 3.3: Preserve existing websocket ordering guarantees**

Do not regress current runtime ordering expectations for:

- `ack`
- `world_result`
- `siming_output`
- `character_agent_execution`

- [ ] **Step 3.4: Run focused tests**

Run:

```powershell
python -m pytest -q backend/tests/test_observatory_message_delivery_static.py backend/tests/test_ws_protocol.py backend/tests/test_visual_fact_pipeline.py
```

---

## Task 4: Make The Observatory Available On The Normal Developer Runtime Path

**Files:**
- Modify:
  - `backend/app/main.py`
  - `scripts/phase0/MainDemoController.gd`
  - `scripts/ui/CharacterDirectorState.gd`
  - `scripts/ui/ObservatoryInputController.gd`
- Create or modify tests:
  - `backend/tests/test_character_debug_toggle_static.py`
  - `backend/tests/test_observatory_message_delivery_static.py`
  - `backend/tests/test_observatory_input_controller_static.py`

- [ ] **Step 4.1: Write failing tests for developer-visible but hidden-by-default delivery**

The tests must require:

```text
- observatory families are present on the normal developer runtime path
- observatory UI remains hidden until developer toggles it
- no player-facing HUD default regression
```

- [ ] **Step 4.2: Remove the current hidden backend-only delivery gap**

The runtime should not require a private environment-only backend switch just to populate the observatory in developer runs.

Acceptable direction:

- default websocket delivers observatory families
- Godot state center receives them even while observatory panels remain invisible by default

- [ ] **Step 4.3: Preserve developer-only posture**

Keep:

- hidden by default
- explicit input activation
- no player-facing always-on overlay

- [ ] **Step 4.4: Run focused tests**

Run:

```powershell
python -m pytest -q backend/tests/test_character_debug_toggle_static.py backend/tests/test_observatory_message_delivery_static.py backend/tests/test_observatory_input_controller_static.py
```

---

## Task 5: Upgrade `RelationshipOverlay` From Text Rows To Scene-Space Dramatic Geometry

**Files:**
- Modify:
  - `scripts/ui/RelationshipOverlay.gd`
  - `scripts/ui/CharacterDirectorState.gd`
  - `scripts/phase0/MainDemoController.gd`
- Create or modify tests:
  - `backend/tests/test_relationship_overlay_static.py`
  - `backend/tests/test_observatory_scene_mount_static.py`

- [ ] **Step 5.1: Write failing tests that require actual scene-space overlay behavior**

The tests must require code paths for:

```text
- world-space source/target lookup
- attention line rendering
- dialogue line rendering
- action intent line rendering
- blocked line rendering
- Siming influence line rendering
- target marker placement
```

- [ ] **Step 5.2: Add actor/object/environment node resolution**

Use current scene wiring and existing `actor_id` / `object_id` / `environment_id` seams.

- [ ] **Step 5.3: Render real overlay geometry instead of only string rows**

Use:

- line drawing
- color/state distinction
- marker emphasis

- [ ] **Step 5.4: Run focused tests**

Run:

```powershell
python -m pytest -q backend/tests/test_relationship_overlay_static.py backend/tests/test_observatory_scene_mount_static.py
```

---

## Task 6: Turn `DirectorMonitorPanel` And `SimingDirectorBoard` Into A Real Director Workstation

**Files:**
- Modify:
  - `scripts/ui/DirectorMonitorPanel.gd`
  - `scripts/ui/SimingDirectorBoard.gd`
  - `scripts/ui/WorldOutcomeTrace.gd`
  - `scripts/ui/CharacterDirectorState.gd`
- Create or modify tests:
  - `backend/tests/test_director_monitor_panel_static.py`
  - `backend/tests/test_siming_director_board_static.py`

- [ ] **Step 6.1: Write failing tests that require detail-bearing boards, not title-only panels**

The tests must require:

```text
- cast board rows with actor-level state snapshots
- scene state board using live state-center data
- world/constraint board with recent outcome detail
- Siming board with fairness/candidate/decision/path/band/target/reason/downstream status
```

- [ ] **Step 6.2: Implement cast/scene/world director data views**

The director monitor must expose more than counts. It must become an actual operator-facing board.

- [ ] **Step 6.3: Keep `Siming` visibly independent**

`SimingDirectorBoard` must remain a first-class section, not collapsed into generic logs.

- [ ] **Step 6.4: Run focused tests**

Run:

```powershell
python -m pytest -q backend/tests/test_director_monitor_panel_static.py backend/tests/test_siming_director_board_static.py
```

---

## Task 7: Turn `ScriptTimelinePanel` Into Real Beat Review

**Files:**
- Modify:
  - `scripts/ui/ScriptTimelinePanel.gd`
  - `scripts/ui/CharacterDirectorState.gd`
- Create or modify tests:
  - `backend/tests/test_script_timeline_panel_static.py`

- [ ] **Step 7.1: Write failing tests for real beat review behavior**

The tests must require:

```text
- stable beat ordering
- correlation display
- participant display
- beat detail expansion
- actor filter
- participant filter
- meaningful expanded payload view
```

- [ ] **Step 7.2: Implement ordered beat history and richer detail display**

The panel should support dramatic beat review, not just a raw label dump.

- [ ] **Step 7.3: Run focused tests**

Run:

```powershell
python -m pytest -q backend/tests/test_script_timeline_panel_static.py
```

---

## Task 8: Turn `DialogueSceneLedger` Into True Per-Pair Cross-Role Accounting

**Files:**
- Modify:
  - `scripts/ui/DialogueSceneLedger.gd`
  - `scripts/ui/CharacterDirectorState.gd`
  - `backend/app/services/script_beat_projection.py`
  - `backend/app/services/character_agent_debug_projection.py`
- Create or modify tests:
  - `backend/tests/test_dialogue_scene_ledger_static.py`
  - `backend/tests/test_script_beat_projection.py`

- [ ] **Step 8.1: Write failing tests that require true pairwise accounting**

The tests must require:

```text
- pair-key derivation
- both sides' perceived summaries
- both sides' interpreted summaries
- spoken content display
- mismatch/alignment cues from both sides
```

- [ ] **Step 8.2: Extend projection/state storage so pairwise dialogue review is possible**

It is acceptable to enrich beat/event detail payloads if needed, but keep them structured and bounded.

- [ ] **Step 8.3: Implement real pair review UI**

The ledger must no longer be only “current selected actor echoed into a panel”.

- [ ] **Step 8.4: Run focused tests**

Run:

```powershell
python -m pytest -q backend/tests/test_dialogue_scene_ledger_static.py backend/tests/test_script_beat_projection.py
```

---

## Task 9: Make Freeze Mode A Real Inspection Freeze

**Files:**
- Modify:
  - `scripts/ui/CharacterDirectorState.gd`
  - `scripts/ui/ObservatoryInputController.gd`
  - all observatory panel scripts as needed
- Create or modify tests:
  - `backend/tests/test_character_director_state_static.py`
  - `backend/tests/test_observatory_input_controller_static.py`

- [ ] **Step 9.1: Write failing tests that require actual frozen state behavior**

The tests must require:

```text
- incoming observatory payloads ignored while frozen
- visible panel state preserved while frozen
- unfreeze resumes fresh updates
```

- [ ] **Step 9.2: Implement explicit frozen-state semantics**

This is not just a boolean toggle; it must preserve the last inspectable state.

- [ ] **Step 9.3: Run focused tests**

Run:

```powershell
python -m pytest -q backend/tests/test_character_director_state_static.py backend/tests/test_observatory_input_controller_static.py
```

---

## Task 10: Add Observatory-Specific Runtime Verification

**Files:**
- Create or modify:
  - `scripts/verification/CharacterDirectorObservatoryProbe.gd`
  - `scripts/verification/verify_phase0.py`
  - `backend/app/verification_audit.py`
  - `.harness/profiles/phase0.json` only if needed
- Create or modify tests:
  - `backend/tests/test_verification_audit.py`
  - `scripts/verification/tests/test_character_agent_execution_probe_static.py`
  - new focused static tests if needed

- [ ] **Step 10.1: Write failing tests for observatory runtime evidence**

The runtime verification must prove:

```text
- observatory state center receives actor/siming/world/script payloads
- at least one actor panel is populated
- director monitor contains cast/world/siming detail
- script timeline contains multi-role beat content
- dialogue ledger contains pairwise accounting content
- freeze mode can be entered and exited
```

- [ ] **Step 10.2: Implement a dedicated observatory probe scene or probe script**

Do not rely only on current `phase0` evidence that proves the runtime loop in general.

- [ ] **Step 10.3: Feed the new probe evidence into the phase0 audit**

The final `phase0` report must prove observatory usefulness itself, not only the pre-existing runtime loop.

- [ ] **Step 10.4: Run focused tests**

Run:

```powershell
python -m pytest -q backend/tests/test_verification_audit.py scripts/verification/tests/test_character_agent_execution_probe_static.py
```

---

## Task 11: Full Verification And Documentation Sync

**Files:**
- Modify if needed:
  - `docs/character/character-debug-and-verification.md`
  - `docs/current-project-implementation-summary.md`
  - `docs/INDEX.md`

- [ ] **Step 11.1: Run full backend verification**

Run:

```powershell
python -m pytest -v
```

- [ ] **Step 11.2: Run docs verification**

Run:

```powershell
python scripts/verification/harness.py --profile docs
```

- [ ] **Step 11.3: Run Godot project verification**

Run:

```powershell
python scripts/verification/harness.py --profile godot-project
```

- [ ] **Step 11.4: Run strict runtime verification**

Run:

```powershell
python scripts/verification/harness.py --profile phase0
```

- [ ] **Step 11.5: Confirm all original-expectation observatory behaviors are now true**

Checklist:

```text
- real runtime-owned actor observatory stages
- real runtime-owned Siming observatory stages
- default developer runtime path receives observatory data
- hidden-by-default preserved
- scene-space relationship overlay
- rich director monitor
- real beat review
- true pairwise dialogue ledger
- real freeze mode
- observatory-specific runtime proof
```

---

## Exit Conditions

This plan is complete only when the observatory reaches the original target rather than a “close enough” scaffold:

1. observatory data originates from runtime owners instead of primarily from `main.py` post-processing
2. developer runtime path can populate observatory data without hidden backend-only toggles
3. all required observatory surfaces present meaningful dramatic content rather than title/count/text scaffolds
4. `Siming` remains a distinct director seat across monitor, overlay, timeline, and world alignment
5. world outcomes, actor intent, and `Siming` interventions line up in script review
6. freeze mode is usable as an actual inspection tool
7. backend / docs / Godot / runtime verification remain green

---

## Handoff Rule

This finalization plan is successful only if the next implementation can honestly say:

> A developer can launch the Phase 0 scene, toggle the observatory, and read the whole live dramatic runtime as a coherent multi-role authored scene without relying on raw debug strings or placeholder panels.

If the result still mainly behaves like:

- text-only placeholder panels
- post-hoc projection stitched mostly in `main.py`
- observatory data hidden behind backend-only opt-in switches
- single-actor summaries disguised as multi-role replay

then this plan has not been completed.
