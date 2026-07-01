# Authority And Settlement Runtime Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Strengthen the request -> authority -> result -> writeback chain without weakening `System L1 / ESM` ownership.

**Architecture:** Keep role runtimes as intent producers and `System L1 / ESM` as settlement owners. Expand action-class support only through structured requests and settlement results, then reflect those results back into the fact and runtime-writeback chains.

**Tech Stack:** Python backend, existing `ESMService`, authority event bus, world-result models, pytest.

**Progress Snapshot (`2026-06-30`):**
- Tasks `1-2` now have direct repository evidence.
- Current proof chain covers:
  - structured social-spatial settlement result semantics
  - runtime-facing `social_spatial_runtime_result` writeback
  - unified mainline verifier result `authority_settlement_writeback=proved`

**Direct Evidence Audit (`2026-06-30`):**
- Required outcome `1. structured settlement semantics for social-spatial requests`
  - Direct evidence:
    - `backend/tests/test_ws_protocol.py::test_approach_settlement_result_preserves_action_profile_and_target_actor`
    - `backend/tests/test_character_agent_action_request_routing.py::test_actor_target_settlements_carry_structured_social_spatial_metadata`
- Required outcome `2. settlement writeback into canonical runtime outputs`
  - Direct evidence:
    - `backend/tests/test_visual_fact_pipeline.py::test_social_spatial_settlement_result_is_projected_back_into_runtime_outputs`
    - `backend/app/main.py::_as_social_spatial_runtime_result(...)`
    - unified verifier result `authority_settlement_writeback=proved`

**Completion Audit Conclusion (`2026-06-30`):**
- Within the current first-pass scope of this plan, both required outcomes now have direct repository evidence.
- Remaining non-goals for this plan:
  - no broader new authority substrate beyond the current `ESMService` / authority event bus path
  - no chained multi-actor settlement simulation beyond the current runtime-facing writeback surfaces

---

### Task 1: Expand settlement result semantics for social-spatial requests

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/app/models/world_result.py`
- Test: `backend/tests/test_ws_protocol.py`

- [x] **Step 1: Write the failing settlement test**

```python
def test_approach_settlement_result_preserves_action_profile_and_target_actor() -> None:
    # build a character_agent_execution payload with request_type=approach
    # assert resulting world_result carries action_profile and target_actor_id
```

- [x] **Step 2: Run test to verify it fails if fields are incomplete**

Run: `pytest backend/tests/test_ws_protocol.py -k approach_settlement -v`
Expected: `FAIL`

- [x] **Step 3: Write minimal implementation**

```python
return {
    "request_ref": request_ref,
    "result_id": result_id,
    "result_type": "action_resolution_result",
    "target_actor_id": target_actor_id,
    "action_profile": request_type,
    "source_action_request_type": request_type,
    "applied_state_changes": ["social_spatial_state_result"],
    ...
}
```

- [x] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_ws_protocol.py -k approach_settlement -v`
Expected: `PASS`

- [x] **Step 5: Commit**

```bash
git add backend/app/main.py backend/app/models/world_result.py backend/tests/test_ws_protocol.py
git commit -m "Broaden structured settlement semantics for social-spatial requests

Constraint: World-truth ownership must stay in authority settlement even for role-driven contact actions
Rejected: Treat approach success as a purely local actor-side fact | loses authority lineage and replayability
Confidence: high
Scope-risk: moderate
Directive: Every new role-driven action class should produce a world-result shape that is as explicit as object and environment settlement
Tested: pytest backend/tests/test_ws_protocol.py -k approach_settlement -v
Not-tested: end-to-end replay"
```

### Task 2: Route settlement results back into canonical world-runtime and role-facing writeback

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/app/services/frontend_authority_event_projection.py`
- Test: `backend/tests/test_visual_fact_pipeline.py`

- [x] **Step 1: Write the failing writeback test**

```python
def test_social_spatial_settlement_result_is_projected_back_into_runtime_outputs() -> None:
    # simulate a settled approach or follow_target result
    # assert projected outbound messages include a structured world-facing follow-up artifact
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_visual_fact_pipeline.py -k social_spatial_settlement -v`
Expected: `FAIL`

- [x] **Step 3: Write minimal implementation**

```python
if result_type == "action_resolution_result" and payload.get("action_profile") in {
    "approach",
    "follow_target",
    "seek_private_distance",
    "withdraw",
    "break_contact",
}:
    projected_messages.append(
        {
            "message_type": "social_spatial_runtime_result",
            "payload": {
                "actor_id": str(payload.get("actor_id", "") or ""),
                "target_actor_id": str(payload.get("target_actor_id", "") or ""),
                "action_profile": str(payload.get("action_profile", "") or ""),
                "settlement_status": str(payload.get("settlement_status", "") or ""),
                "producer_ts": int(payload.get("producer_ts", 0) or 0),
            },
        }
    )
```

- [x] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_visual_fact_pipeline.py -k social_spatial_settlement -v`
Expected: `PASS`

- [x] **Step 5: Commit**

```bash
git add backend/app/main.py backend/app/services/frontend_authority_event_projection.py backend/tests/test_visual_fact_pipeline.py
git commit -m "Project social-spatial settlement results back into runtime outputs

Constraint: Authority outcomes must become structured next-round inputs rather than stopping at one settled result line
Rejected: Keep social-spatial settlement as log-only metadata | too weak for world-loop closure
Confidence: medium
Scope-risk: moderate
Directive: Every settlement family that affects role behavior should have an explicit runtime-facing writeback shape
Tested: pytest backend/tests/test_visual_fact_pipeline.py -k social_spatial_settlement -v
Not-tested: chained multi-actor reactions"
```
