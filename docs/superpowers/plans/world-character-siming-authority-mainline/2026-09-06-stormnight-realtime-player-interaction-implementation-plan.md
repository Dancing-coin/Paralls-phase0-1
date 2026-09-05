# Stormnight Realtime Player Interaction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a separately runnable real-time Stormnight player loop using the shared backend event store and a separate Godot scene.

**Architecture:** A strict, owner-bound realtime session adapter accepts only finite player intents and returns filtered projections through the existing WebSocket bridge. The Godot scene instances PlayerShell and primitive actors but contains no truth writer or knight/church scene reference.

**Tech Stack:** FastAPI/WebSocket, Pydantic, existing GameplayEventStore/P5/Quest/Social/Inventory adapters, Godot 4.6.3, PlayerShell, pytest and Harness.

---

### Task 1: Shared-store realtime session adapter

**Files:**
- Create: `backend/app/gameplay/p5/stormnight_realtime_session.py`
- Create: `backend/tests/test_stormnight_realtime_session.py`

- [ ] Write RED tests for `start`, `inspect`, `question`, `hide`, `pursue`, `accuse`, duplicate replay and zero-write rejection.
- [ ] Implement frozen `StormnightPlayerIntent` and `StormnightRealtimeSessionService` over a supplied existing store.
- [ ] Bind the player identity, admitted clues/statements/actions and source/revision coordinates in the service; reject all caller-selected authority coordinates.
- [ ] Return a projection containing only public case data, player-visible evidence, receipt metadata and a non-canonical NPC proposal.
- [ ] Run `python -m pytest -q backend/tests/test_stormnight_realtime_session.py`.

### Task 2: WebSocket admission

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/app/ws_protocol.py`
- Create: `backend/tests/test_stormnight_realtime_websocket.py`

- [ ] Write RED direct-handler tests for the new envelope, malformed payload, actor impersonation, duplicate and rejected response.
- [ ] Initialize the session service over the already-created `gameplay_event_store` in `reset_runtime_state()`.
- [ ] Add `stormnight_player_intent` handling that validates the strict model and returns `stormnight_case_projection` only.
- [ ] Run the focused WebSocket tests.

### Task 3: Independent Godot playable scene

**Files:**
- Create: `scenes/phase0/StormnightRealtimePlayable.tscn`
- Create: `scripts/phase0/StormnightRealtimePlayable.gd`
- Create: `scripts/phase0/StormnightRealtimeHud.gd`
- Modify: `scripts/autoload/LocalPresentationBus.gd`
- Modify: `scripts/autoload/BackendBridge.gd`
- Create: `backend/tests/test_stormnight_realtime_godot_contract.py`

- [ ] Write RED static tests for PlayerShell, four primitive actors, HUD, finite intent mapping, committed-only response application and absence of knight/church references.
- [ ] Build the scene using PlayerShell plus primitive room/interaction presentation; do not instance the probe or Throne Hall.
- [ ] Add E/Q/H/F/1–4 input mapping to finite envelopes; bind backend responses to committed actor/HUD state and rejection rollback.
- [ ] Run static tests and Godot headless scene load.

### Task 4: End-to-end live smoke and documentation

**Files:**
- Create: `scripts/verification/verify_stormnight_realtime_playable.py`
- Create: `.harness/profiles/stormnight-realtime-playable.json`
- Modify: Stormnight design/audit/readmes and this plan.

- [ ] Write the verifier to launch the local backend, submit finite player envelopes, check accepted/rejected receipts and run Godot headless/desktop probes.
- [ ] Run focused tests, full pytest, compileall, diff check and the new Harness profile.
- [ ] Record the evidence and clearly distinguish local realtime reference play from public multiplayer/live-provider scope.
- [ ] Commit and push each verified slice directly to `main` using Lore protocol.
