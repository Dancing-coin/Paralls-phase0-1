# Character Director Observatory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the full developer-only `Character Director Observatory` so real-machine Godot testing can show role behavior, intent, thought summaries, perception, `Siming` direction, world outcomes, and script-like multi-role interaction traces in one coherent observability system.

**Architecture:** Implement a structured backend-to-Godot observatory path rather than extending the current free-form debug overlay. Add projection layers for character-agent, `Siming`, world-outcome, and script-beat summaries; add a Godot-side observatory state center; then add the full UI surfaces: actor state tags, relationship overlay, role observer panel, director monitor, `Siming` director board, script timeline, dialogue ledger, and freeze-mode controls.

**Tech Stack:** FastAPI backend, current `CharacterAgentRuntime`, current `SimingRuntime`, `ESM` / authority event chain, Godot 4.6 scenes and GDScript, websocket delivery through `BackendBridge` / `LocalPresentationBus`, pytest, harness docs verification.

---

## Linked Source Of Truth

This plan depends on and must stay aligned with:

- `docs/superpowers/specs/2026-06-21-character-director-observatory-design.md`
- `docs/superpowers/specs/2026-06-15-full-character-agent-runtime-with-llm-design.md`
- `docs/character/character-agent-runtime-architecture.md`
- `docs/character/character-actor-migration-status.md`
- `docs/phase1/core/01-运行时核心/司命/19-司命接入事件总线后端设计.md`

---

## Task 1: Freeze Observatory Schemas And Backend Projection Contracts

**Files:**
- Create:
  - `backend/app/models/observatory.py`
- Modify if needed:
  - `backend/tests/test_architecture_entrypoints.py`
- Create or modify tests:
  - `backend/tests/test_observatory_models.py`

- [ ] **Step 1.1: Write failing tests for the observatory schema objects**

The tests must require:

```text
- ActorDramaticState
- ActorDramaticEvent
- SimingDramaticState
- SimingDramaticEvent
- WorldOutcomeEvent
- ScriptBeat
```

- [ ] **Step 1.2: Implement the observatory schema objects with stable dramatic/debug fields**

The schema must include:

```text
- producer_ts
- causation_id
- correlation_id
- participants when relevant
- concise summary fields
```

- [ ] **Step 1.3: Run focused tests**

Run:

```powershell
python -m pytest -q backend/tests/test_observatory_models.py
```

---

## Task 2: Implement Character-Agent Observatory Projection

**Files:**
- Create:
  - `backend/app/services/character_agent_debug_projection.py`
- Modify:
  - `backend/app/character_agent/runtime/runtime_loop.py`
- Create or modify tests:
  - `backend/tests/test_character_agent_debug_projection.py`
  - `backend/tests/test_character_agent_runtime_memory_integration.py`

- [ ] **Step 2.1: Write failing tests that require role snapshot and role event projections**

Tests must prove projection of:

```text
- current perception summary
- current memory summary
- current interpretation summary
- current decision summary
- current execution summary
- latest outcome summary
- latest Siming influence summary
```

- [ ] **Step 2.2: Implement a dedicated character-agent projection service**

- [ ] **Step 2.3: Call the projection service from the role runtime after key stages**

Key stages:

```text
- character_perceived_event
- self_body_perceived_event
- interpretation
- decision
- execution request
- suggestion packet
- settlement / dialogue writeback
```

- [ ] **Step 2.4: Run focused tests**

Run:

```powershell
python -m pytest -q backend/tests/test_character_agent_debug_projection.py backend/tests/test_character_agent_runtime_memory_integration.py
```

---

## Task 3: Implement Siming Observatory Projection

**Files:**
- Create:
  - `backend/app/services/siming_debug_projection.py`
- Modify:
  - `backend/app/services/siming_event_pipeline.py`
  - `backend/app/services/siming_runtime.py`
- Create or modify tests:
  - `backend/tests/test_siming_debug_projection.py`
  - `backend/tests/test_siming_event_pipeline.py`

- [ ] **Step 3.1: Write failing tests for Siming director-seat snapshot and event projections**

Tests must prove projection of:

```text
- fairness summary
- intervention candidate
- intervention decision
- selected path
- intervention band
- target
- reason
- downstream status
- no_action reason
```

- [ ] **Step 3.2: Implement Siming debug projection service**

- [ ] **Step 3.3: Wire projection calls into Siming runtime/pipeline**

- [ ] **Step 3.4: Run focused tests**

Run:

```powershell
python -m pytest -q backend/tests/test_siming_debug_projection.py backend/tests/test_siming_event_pipeline.py
```

---

## Task 4: Implement World Outcome And Script Beat Projection

**Files:**
- Create:
  - `backend/app/services/world_outcome_debug_projection.py`
  - `backend/app/services/script_beat_projection.py`
- Modify:
  - `backend/app/main.py`
- Create or modify tests:
  - `backend/tests/test_world_outcome_debug_projection.py`
  - `backend/tests/test_script_beat_projection.py`

- [ ] **Step 4.1: Write failing tests for world-outcome dramatic projection**

The tests must require structured projection of:

```text
- action request / target
- settlement acceptance or rejection
- constraint result
- object/environment change summary
- dramatic consequence summary
```

- [ ] **Step 4.2: Write failing tests for script beat aggregation**

The tests must require:

```text
- correlation-based grouping
- participant list
- readable dramatic summary
- references back to role / Siming / world events
```

- [ ] **Step 4.3: Implement the two projection services and wire them into the backend message path**

- [ ] **Step 4.4: Run focused tests**

Run:

```powershell
python -m pytest -q backend/tests/test_world_outcome_debug_projection.py backend/tests/test_script_beat_projection.py
```

---

## Task 5: Extend Websocket Delivery For Observatory Messages

**Files:**
- Modify:
  - `backend/app/main.py`
  - `scripts/autoload/BackendBridge.gd`
  - `scripts/autoload/LocalPresentationBus.gd`
- Create or modify tests:
  - `backend/tests/test_observatory_message_delivery_static.py`
  - `backend/tests/test_character_actor_bridge_static.py`

- [ ] **Step 5.1: Write failing tests for all observatory message families**

Required families:

```text
- character_agent_debug_snapshot
- character_agent_debug_event
- siming_debug_snapshot
- siming_debug_event
- world_outcome_trace
- script_beat_event
```

- [ ] **Step 5.2: Add websocket emission support on the backend**

- [ ] **Step 5.3: Add `BackendBridge` parsing and `LocalPresentationBus` signals**

- [ ] **Step 5.4: Run focused tests**

Run:

```powershell
python -m pytest -q backend/tests/test_observatory_message_delivery_static.py backend/tests/test_character_actor_bridge_static.py
```

---

## Task 6: Implement Godot Observatory State Center

**Files:**
- Create:
  - `scripts/ui/CharacterDirectorState.gd`
- Create or modify tests:
  - `backend/tests/test_character_director_state_static.py`

- [ ] **Step 6.1: Write failing static tests for the Godot-side state center**

It must cache:

```text
- latest role dramatic state by actor
- recent role dramatic events by actor
- latest Siming dramatic state
- recent Siming dramatic events
- recent world outcome events
- recent script beats
```

- [ ] **Step 6.2: Implement the state center and wire it to `LocalPresentationBus`**

- [ ] **Step 6.3: Run focused tests**

Run:

```powershell
python -m pytest -q backend/tests/test_character_director_state_static.py
```

---

## Task 7: Implement In-Scene Observatory Surfaces

**Files:**
- Create:
  - `scripts/ui/ActorStateTags.gd`
  - `scripts/ui/RelationshipOverlay.gd`
- Create or modify tests:
  - `backend/tests/test_actor_state_tags_static.py`
  - `backend/tests/test_relationship_overlay_static.py`

- [ ] **Step 7.1: Write failing static tests for actor tags**

Actor tags must expose:

```text
- actor name
- current intent
- focus
- state
- why now
- Siming marker
```

- [ ] **Step 7.2: Write failing static tests for relationship overlay**

Overlay must support:

```text
- attention lines
- dialogue lines
- action intent lines
- blocked lines
- Siming influence lines
- target markers
```

- [ ] **Step 7.3: Implement both in-scene observability surfaces**

- [ ] **Step 7.4: Run focused tests**

Run:

```powershell
python -m pytest -q backend/tests/test_actor_state_tags_static.py backend/tests/test_relationship_overlay_static.py
```

---

## Task 8: Implement Character Observer, Director Monitor, And Siming Director Board

**Files:**
- Create:
  - `scripts/ui/CharacterObserverPanel.gd`
  - `scripts/ui/DirectorMonitorPanel.gd`
  - `scripts/ui/SimingDirectorBoard.gd`
- Create or modify tests:
  - `backend/tests/test_character_observer_panel_static.py`
  - `backend/tests/test_director_monitor_panel_static.py`
  - `backend/tests/test_siming_director_board_static.py`

- [ ] **Step 8.1: Write failing static tests for the single-role observer panel**

The panel must show:

```text
- perception
- internal state
- memory
- interpretation
- decision
- execution
- outcome
- Siming trace
```

- [ ] **Step 8.2: Write failing static tests for the global director monitor**

It must show:

```text
- cast board
- scene state
- world/constraint status
- embedded Siming director board
```

- [ ] **Step 8.3: Write failing static tests for the Siming board**

It must show:

```text
- fairness summary
- intervention candidate
- decision
- selected path
- intervention band
- target
- reason
- downstream status
```

- [ ] **Step 8.4: Implement the three panels**

- [ ] **Step 8.5: Run focused tests**

Run:

```powershell
python -m pytest -q backend/tests/test_character_observer_panel_static.py backend/tests/test_director_monitor_panel_static.py backend/tests/test_siming_director_board_static.py
```

---

## Task 9: Implement Script Timeline, Dialogue Ledger, And Freeze Mode

**Files:**
- Create:
  - `scripts/ui/ScriptTimelinePanel.gd`
  - `scripts/ui/DialogueSceneLedger.gd`
  - `scripts/ui/ObservatoryInputController.gd`
- Create or modify tests:
  - `backend/tests/test_script_timeline_panel_static.py`
  - `backend/tests/test_dialogue_scene_ledger_static.py`
  - `backend/tests/test_observatory_input_controller_static.py`

- [ ] **Step 9.1: Write failing static tests for the script timeline panel**

It must support:

```text
- beat list
- correlation / participant display
- beat detail expansion
- role / scene filtering
```

- [ ] **Step 9.2: Write failing static tests for the dialogue ledger**

It must support:

```text
- per-pair dialogue review
- what each side perceived
- what each side interpreted
- what was said
- mismatch / alignment cues
```

- [ ] **Step 9.3: Write failing static tests for the observatory input controller**

It must support:

```text
- F6 master toggle
- F7 mode switch
- F8 script mode
- Tab / Shift+Tab actor cycling
- click-to-lock actor
- Space freeze
- Esc unfreeze
```

- [ ] **Step 9.4: Implement all three modules**

- [ ] **Step 9.5: Run focused tests**

Run:

```powershell
python -m pytest -q backend/tests/test_script_timeline_panel_static.py backend/tests/test_dialogue_scene_ledger_static.py backend/tests/test_observatory_input_controller_static.py
```

---

## Task 10: Mount The Full Observatory Into The Phase 0 Scene

**Files:**
- Create:
  - `scenes/phase0/ObservatoryRoot.tscn`
- Modify:
  - `scenes/phase0/MainDemo.tscn`
  - `scripts/phase0/MainDemoController.gd`
- Create or modify tests:
  - `backend/tests/test_observatory_scene_mount_static.py`

- [ ] **Step 10.1: Write failing static tests for observatory scene mounting**

The tests must require:

```text
- ObservatoryRoot scene exists
- MainDemo mounts it
- CharacterDirectorState exists in-scene
- all key observatory surfaces are wired
```

- [ ] **Step 10.2: Create the observatory root scene and mount it into `MainDemo`**

- [ ] **Step 10.3: Add controller glue only where needed for developer-only enable/disable behavior**

- [ ] **Step 10.4: Run focused tests**

Run:

```powershell
python -m pytest -q backend/tests/test_observatory_scene_mount_static.py
```

---

## Task 11: Full Verification And Doc Sync

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

- [ ] **Step 11.2: Run documentation verification**

Run:

```powershell
python scripts/verification/harness.py --profile docs
```

- [ ] **Step 11.3: Run relevant Godot/runtime verification**

Run:

```powershell
python scripts/verification/harness.py --profile godot-project
python scripts/verification/harness.py --profile phase0
```

- [ ] **Step 11.4: Verify the observatory is developer-only and hidden by default**

- [ ] **Step 11.5: Update docs to describe the observatory as a developer observability surface, not a player-facing HUD**

---

## Exit Conditions

This plan is complete when:

1. backend emits the full structured observatory message family
2. Godot has a unified observatory state center
3. in-scene actor tags and relationship overlays work
4. single-role observer, director monitor, and Siming board work
5. script timeline and dialogue ledger support multi-role dramatic review
6. freeze mode works
7. the whole system remains developer-only and hidden by default
8. backend / docs / Godot verification remain green

---

## Handoff Rule

This observatory is complete only when it makes the live role runtime readable as a coherent dramatic system.

It is not complete if it only:

- extends the existing debug overlay
- dumps raw JSON without scene meaning
- shows role thought summaries without `Siming` and world-outcome alignment
- shows per-role state without script-like multi-role playback
