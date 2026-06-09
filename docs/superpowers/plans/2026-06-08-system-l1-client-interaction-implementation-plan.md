# System L1 Client Interaction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Formalize the `System L1` client interaction subsystem so movement, focus, interaction requests, and object/environment execution triggers are represented as explicit low-level execution facts and requests rather than only as scene-local behavior.

**Architecture:** Preserve the current `MainDemoController`-based runtime loop, but isolate and formalize the low-level interaction execution responsibilities and their emitted facts. This plan keeps interaction execution inside `System L1` and preserves `ESM` as the settlement layer.

**Tech Stack:** Godot 4.x GDScript, Python 3.13, FastAPI backend, pytest, current Phase 0 verification harnesses.

---

## Status Snapshot

- Date: `2026-06-10`
- Plan status: repo-local target completed and verified
- Current code truth:
  - `focus_target_change` is explicit and verified
  - `interact` intent emission is explicit and verified
  - `action_request` is now a real runtime/websocket message
  - `move_intent` now also produces a real runtime snapshot proof instead of stopping at `ack + local_motion`
  - movement/focus/interaction outputs are normalized enough for the current L1 slice
- Remaining gap:
  - this child plan is complete for the repo's current minimum interaction normalization target
  - it is not the same thing as a full-volume main-project interaction subsystem with broader fact families, so the parent `system-l1-full-phase1` plan still remains open
- Verification evidence:
  - `backend/tests/test_ws_protocol.py::test_websocket_move_intent_emits_ack_and_runtime_snapshot`
  - `backend/tests/test_ws_protocol.py::test_websocket_focus_target_change_emits_runtime_alignment_messages`
  - `backend/tests/test_ws_protocol.py::test_websocket_interact_intent_emits_ack_action_resolution_transition_object_state_body_state_environment_shift_and_siming_output`
  - `backend/tests/test_ws_protocol.py::test_websocket_interact_intent_emits_constraint_when_player_is_far`
  - latest verified worktree also keeps the runtime verification triad green

### Task 1: Inventory And Normalize Current Interaction Outputs

**Files:**
- Modify: `scripts/phase0/MainDemoController.gd`
- Modify: `backend/tests/test_ws_protocol.py`
- Modify: `backend/tests/test_verification_audit.py`

- [x] **Step 1: Add or strengthen tests for current interaction outputs**

Cover:

- focus target changes
- move intent emission
- interaction request emission

- [x] **Step 2: Run the tests**

Run:

```bash
python -m pytest -v tests/test_ws_protocol.py tests/test_verification_audit.py
```

- [x] **Step 3: Normalize the emitted low-level facts if needed**

Keep outputs deterministic and structured.

- [x] **Step 4: Re-run tests**

Run:

```bash
python -m pytest -v tests/test_ws_protocol.py tests/test_verification_audit.py
```

- Deferred: no repository commit was requested in this session; verified worktree + synced docs are the closure record for this child plan.

```bash
git add scripts/phase0/MainDemoController.gd backend/tests/test_ws_protocol.py backend/tests/test_verification_audit.py
git commit -m "feat: normalize system-l1 client interaction outputs"
```
