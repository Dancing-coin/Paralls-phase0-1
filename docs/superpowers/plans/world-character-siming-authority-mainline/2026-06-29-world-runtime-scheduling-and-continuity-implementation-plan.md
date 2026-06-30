# World Runtime Scheduling And Continuity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make long-running multi-role operation stable through explicit cadence, wake-up, cooldown, and continuity policies.

**Architecture:** Introduce explicit scheduling and continuity policy objects before adding a heavy scheduler. Keep the first pass declarative and replay-friendly so actor-local sampling, cognition refresh, and social-contact continuity can be tuned without hardwiring one global loop implementation too early.

**Tech Stack:** Python policy objects, backend runtime services, pytest, existing observability/timeline surfaces.

**Progress Snapshot (`2026-06-30`):**
- Tasks `1-26` have implementation evidence in the current worktree.
- The active lane has moved from feature addition into completion-audit style proof strengthening.
- Current proof chain already covers:
  - cadence / wake-up / cooldown / recovery behavior
  - multi-actor scheduling selection and degraded scaling
  - unified scheduling state and round identifiers
  - round summaries / reason tags / round events
  - debug-stream propagation
  - outbound replay trace delivery
  - real websocket delivery
  - frontend signal/state chain
- Remaining work should prefer direct-evidence closure over adding new runtime surfaces.

**Verification Snapshot (`2026-06-30`):**
- Focused runtime/state proof:
  - `pytest backend/tests/test_character_agent_runtime_memory_integration.py -v`
- Focused verifier proof:
  - `pytest scripts/verification/tests/test_mainline_unified_runtime_verify.py -v`
- Focused frontend inspection proof:
  - `pytest backend/tests/test_debug_panel.py backend/tests/test_observatory_message_delivery_static.py backend/tests/test_character_director_state_static.py -v`
- Focused websocket replay proof:
  - `pytest backend/tests/test_ws_protocol.py -k "websocket_character_agent_execution_emits_scheduling_round_trace or websocket_interact_intent_emits_scheduling_round_trace_after_character_agent_execution" -v`
- Unified runtime proof:
  - `python scripts/verification/verify_mainline_unified_runtime.py`
- Harness entrypoint proof:
  - `python scripts/verification/harness.py --profile mainline-unified-runtime`

**Direct Evidence Audit (`2026-06-30`):**
- Required outcome `1. multi-actor scheduling semantics`
  - Direct evidence:
    - `backend/tests/test_world_runtime_scheduling.py::test_select_schedulable_actor_ids_prioritizes_wake_up_and_recovery_under_population_pressure`
    - `backend/tests/test_character_agent_runtime_memory_integration.py::test_runtime_exposes_unified_scheduling_state_for_population_tick`
    - `backend/tests/test_character_agent_runtime_memory_integration.py::test_runtime_scheduling_state_exposes_round_summary_and_reason_tags_for_active_actor_set`
    - `backend/tests/test_character_agent_action_request_routing.py::test_character_agent_execution_route_emits_scheduling_round_trace`
    - `backend/tests/test_ws_protocol.py::test_websocket_character_agent_execution_emits_scheduling_round_trace`
- Required outcome `2. perception/cognition cadence policy`
  - Direct evidence:
    - `backend/tests/test_world_runtime_scheduling.py::test_runtime_cadence_policy_tracks_perception_and_cognition_intervals`
    - `backend/tests/test_character_agent_runtime_memory_integration.py::test_runtime_degraded_mode_defers_second_cognition_pass_inside_cadence_window`
    - `backend/tests/test_character_agent_runtime_memory_integration.py::test_runtime_degraded_mode_defers_second_perception_pass_inside_perception_window`
    - `backend/tests/test_character_agent_runtime_memory_integration.py::test_runtime_wake_up_high_salience_siming_input_bypasses_degraded_cognition_deferral`
    - `backend/tests/test_character_agent_runtime_memory_integration.py::test_runtime_degraded_mode_defers_repeated_social_spatial_request_inside_cooldown_window`
- Required outcome `3. continuity and interrupted-action recovery semantics`
  - Direct evidence:
    - `backend/tests/test_world_runtime_continuity.py::test_runtime_continuity_state_tracks_ongoing_contact_and_interrupted_action`
    - `backend/tests/test_character_agent_runtime_memory_integration.py::test_runtime_tracks_cadence_policy_and_contact_continuity_state`
    - `backend/tests/test_character_agent_action_request_routing.py::test_social_spatial_settlement_updates_runtime_continuity_state`
    - `backend/tests/test_character_agent_runtime_memory_integration.py::test_runtime_marks_recovering_when_approach_restarts_after_terminal_transition`
    - `backend/tests/test_character_agent_action_request_routing.py::test_social_spatial_continuity_marks_recovering_when_contact_resumes`
- Required outcome `4. scaling policy for larger role populations`
  - Direct evidence:
    - `backend/tests/test_world_runtime_scheduling.py::test_select_schedulable_actor_ids_prioritizes_wake_up_and_recovery_under_population_pressure`
    - `backend/tests/test_character_agent_runtime_memory_integration.py::test_runtime_observatory_snapshot_carries_scheduling_summary_for_degraded_population`
    - `backend/tests/test_character_agent_runtime_memory_integration.py::test_runtime_emits_scheduling_state_event_for_selected_actor_under_population_pressure`
    - `backend/tests/test_character_director_state_static.py::test_character_director_state_bottom_strip_stays_single_merged_builder`
    - `backend/tests/test_debug_panel.py::test_debug_ws_replays_scheduling_round_trace_event`
- Unified proof status:
  - `.harness/verification/mainline-unified-runtime-report.json` currently records:
    - `mainline_world_runtime_suite=proved`
    - `runtime_cadence_continuity_observatory=proved`
    - `continuity_recovery_runtime=proved`

**Completion Audit Conclusion (`2026-06-30`):**
- Within the current first-pass scope of this plan, the four required outcomes now have direct repository evidence.
- The proof chain is no longer limited to internal unit logic:
  - runtime observatory snapshots and events are proved
  - outbound replay messages are proved
  - `/debug/ws` propagation is proved
  - `/ws` delivery is proved
  - frontend signal/state chain is proved
- Remaining non-goals for this plan:
  - no heavy global scheduler implementation
  - no production-scale population benchmark
  - no cross-process replay service beyond the current observability/replay surfaces

---

### Task 1: Add runtime scheduling policy objects

**Files:**
- Create: `backend/app/world_runtime/scheduling.py`
- Test: `backend/tests/test_world_runtime_scheduling.py`

- [x] **Step 1: Write the failing scheduling-policy test**

```python
from app.world_runtime.scheduling import RuntimeCadencePolicy


def test_runtime_cadence_policy_tracks_perception_and_cognition_intervals() -> None:
    policy = RuntimeCadencePolicy(
        perception_interval_ms=200,
        cognition_interval_ms=500,
        degraded_mode=False,
    )
    assert policy.perception_interval_ms == 200
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_world_runtime_scheduling.py -v`
Expected: `FAIL`

- [x] **Step 3: Write minimal implementation**

```python
from pydantic import BaseModel, ConfigDict


class RuntimeCadencePolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    perception_interval_ms: int
    cognition_interval_ms: int
    degraded_mode: bool = False
```

- [x] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_world_runtime_scheduling.py -v`
Expected: `PASS`

- [x] **Step 5: Commit**

```bash
git add backend/app/world_runtime/scheduling.py backend/tests/test_world_runtime_scheduling.py
git commit -m "Add world-runtime cadence policy objects

Constraint: Multi-role continuity needs explicit cadence semantics before a heavier scheduler is introduced
Rejected: Hardcode cadence inside individual services only | too opaque to tune and replay
Confidence: high
Scope-risk: narrow
Directive: New scheduling behavior must begin as explicit policy objects before execution logic expands
Tested: pytest backend/tests/test_world_runtime_scheduling.py -v
Not-tested: live scheduler"
```

### Task 2: Add continuity-state helpers for interrupted contact and action recovery

**Files:**
- Create: `backend/app/world_runtime/continuity.py`
- Test: `backend/tests/test_world_runtime_continuity.py`

- [x] **Step 1: Write the failing continuity tests**

```python
from app.world_runtime.continuity import RuntimeContinuityState


def test_runtime_continuity_state_tracks_ongoing_contact_and_interrupted_action() -> None:
    state = RuntimeContinuityState(
        actor_id="char_a",
        ongoing_contact_target="char_c",
        interrupted_action="approach",
        last_transition_kind="paused",
    )
    assert state.ongoing_contact_target == "char_c"
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_world_runtime_continuity.py -v`
Expected: `FAIL`

- [x] **Step 3: Write minimal implementation**

```python
from pydantic import BaseModel, ConfigDict


class RuntimeContinuityState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    actor_id: str
    ongoing_contact_target: str = ""
    interrupted_action: str = ""
    last_transition_kind: str = ""
```

- [x] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_world_runtime_continuity.py -v`
Expected: `PASS`

- [x] **Step 5: Commit**

```bash
git add backend/app/world_runtime/continuity.py backend/tests/test_world_runtime_continuity.py
git commit -m "Add world-runtime continuity state helpers

Constraint: Long-running world operation needs explicit continuity surfaces before scheduler behavior deepens
Rejected: Leave continuity implicit in scattered runtime locals only | too hard to replay and recover
Confidence: high
Scope-risk: narrow
Directive: Contact and interruption continuity should live in dedicated runtime state objects before policy logic expands
Tested: pytest backend/tests/test_world_runtime_continuity.py -v
Not-tested: live contact recovery"
```

### Task 3: Add unified mainline runtime verifier and harness profile

**Files:**
- Create: `scripts/verification/verify_mainline_unified_runtime.py`
- Create: `.harness/profiles/mainline-unified-runtime.json`
- Modify: `scripts/verification/tests/test_harness_registry.py`
- Modify: `docs/harness.md`
- Modify: `docs/INDEX.md`

- [x] **Step 1: Write the failing profile/verifier test**

```python
def test_load_profile_registry_reads_mainline_unified_runtime_profile() -> None:
    registry = load_profile_registry(Path(__file__).resolve().parents[3])
    assert registry.profiles["mainline-unified-runtime"]["script"] == "scripts/verification/verify_mainline_unified_runtime.py"
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest scripts/verification/tests/test_harness_registry.py -k mainline_unified_runtime -v`
Expected: `FAIL`

- [x] **Step 3: Write minimal implementation**

```python
# verify_mainline_unified_runtime.py
# run actor-local perception, autonomous social contact,
# character-agent execution, and phase1-slice verifiers
# then aggregate their report JSON files into one unified report
```

```json
{
  "schema_version": 1,
  "name": "mainline-unified-runtime",
  "order": 61,
  "script": "scripts/verification/verify_mainline_unified_runtime.py",
  "requires_godot": true,
  "description": "Unified runtime proof across actor-local perception, autonomous contact, execution ingress, and phase1-shaped writeback"
}
```

- [x] **Step 4: Run test to verify it passes**

Run: `pytest scripts/verification/tests/test_harness_registry.py -k mainline_unified_runtime -v`
Expected: `PASS`

- [x] **Step 5: Run the unified verifier**

Run: `python scripts/verification/verify_mainline_unified_runtime.py`
Expected: initial `PASS` if all dependent verifiers remain green.

### Task 4: Thread cadence and continuity policies into runtime-loop state

**Files:**
- Modify: `backend/app/character_agent/runtime/runtime_loop.py`
- Test: `backend/tests/test_character_agent_runtime_memory_integration.py`

- [x] **Step 1: Write the failing runtime policy test**

```python
def test_runtime_tracks_cadence_policy_and_contact_continuity_state() -> None:
    # assert default cadence exists
    # assert approach execution request updates continuity state
    # assert settlement result updates transition kind
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_character_agent_runtime_memory_integration.py -k continuity_state -v`
Expected: `FAIL`

- [x] **Step 3: Write minimal implementation**

```python
self._cadence_policy = RuntimeCadencePolicy(...)
self._continuity_state: dict[str, RuntimeContinuityState] = {}
```

```python
def get_runtime_cadence_policy(self) -> dict[str, object]: ...
def get_runtime_continuity_state(self, actor_id: str) -> dict[str, object]: ...
```

```python
# update continuity on execution_request / settlement_result
```

- [x] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_character_agent_runtime_memory_integration.py -k continuity_state -v`
Expected: `PASS`

### Task 5: Apply degraded-mode cadence as real cognition deferral behavior

**Files:**
- Modify: `backend/app/character_agent/runtime/runtime_loop.py`
- Modify: `scripts/verification/verify_mainline_unified_runtime.py`
- Test: `backend/tests/test_character_agent_runtime_memory_integration.py`

- [x] **Step 1: Write the failing degraded-mode cadence test**

```python
def test_runtime_degraded_mode_defers_second_cognition_pass_inside_cadence_window() -> None:
    # set degraded_mode=True with cognition interval 500ms
    # send two perceived events inside that window
    # assert only one execution request is produced and a cognition_deferred observatory event is recorded
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_character_agent_runtime_memory_integration.py -k degraded_mode -v`
Expected: `FAIL`

- [x] **Step 3: Write minimal implementation**

```python
self._last_cognition_tick_ms: dict[str, int] = {}

def _should_defer_cognition(...):
    ...
```

```python
if self._should_defer_cognition(actor_id, producer_ts):
    self._queue_observatory_stage_event(... stage="cognition_deferred" ...)
    return []
```

- [x] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_character_agent_runtime_memory_integration.py -k degraded_mode -v`
Expected: `PASS`

- [x] **Step 5: Include the new evidence in unified runtime verification**

Run: `python scripts/verification/verify_mainline_unified_runtime.py`
Expected: `PASS`

### Task 6: Carry continuity through real action-request and settlement routing

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/tests/test_character_agent_action_request_routing.py`

- [x] **Step 1: Write the failing continuity routing test**

```python
def test_social_spatial_settlement_updates_runtime_continuity_state() -> None:
    # send character_agent_execution with approach request
    # assert runtime continuity state keeps contact target and accepted transition after settlement
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_character_agent_action_request_routing.py -k continuity_state -v`
Expected: `FAIL`

- [x] **Step 3: Write minimal implementation**

```python
# keep continuity updates aligned with the real action-request/settlement routing path
# for actor-targeted social-spatial requests
```

- [x] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_character_agent_action_request_routing.py -k continuity_state -v`
Expected: `PASS`

### Task 7: Mark continuity recovery when contact resumes after interruption

**Files:**
- Modify: `backend/app/character_agent/runtime/runtime_loop.py`
- Modify: `backend/tests/test_character_agent_action_request_routing.py`

- [x] **Step 1: Write the failing recovery test**

```python
def test_social_spatial_continuity_marks_recovering_when_contact_resumes() -> None:
    # approach -> break_contact -> approach
    # assert last_transition_kind becomes "recovering"
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_character_agent_action_request_routing.py -k recovering -v`
Expected: `FAIL`

- [x] **Step 3: Write minimal implementation**

```python
# if a new social-spatial execution request reuses the previous contact target after
# a terminal transition, continuity.last_transition_kind should become "recovering"
```

- [x] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_character_agent_action_request_routing.py -k recovering -v`
Expected: `PASS`

### Task 8: Apply degraded-mode perception deferral from perception cadence

**Files:**
- Modify: `backend/app/character_agent/runtime/runtime_loop.py`
- Modify: `backend/tests/test_character_agent_runtime_memory_integration.py`

- [x] **Step 1: Write the failing perception deferral test**

```python
def test_runtime_degraded_mode_defers_second_perception_pass_inside_perception_window() -> None:
    # degraded_mode=True with perception interval
    # second perceived event inside the window should not record a second perceived event
    # and should emit a perception_deferred observatory event
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_character_agent_runtime_memory_integration.py -k perception_deferred -v`
Expected: `FAIL`

- [x] **Step 3: Write minimal implementation**

```python
self._last_perception_tick_ms: dict[str, int] = {}

def _should_defer_perception(...):
    ...
```

```python
if self._should_defer_perception(actor_id, producer_ts):
    self._queue_observatory_stage_event(... stage="perception_deferred" ...)
    return []
```

- [x] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_character_agent_runtime_memory_integration.py -k perception_deferred -v`
Expected: `PASS`

### Task 9: Apply cooldown semantics to repeated social-spatial execution requests

**Files:**
- Modify: `backend/app/character_agent/runtime/runtime_loop.py`
- Modify: `backend/tests/test_character_agent_runtime_memory_integration.py`

- [x] **Step 1: Write the failing cooldown test**

```python
def test_runtime_degraded_mode_defers_repeated_social_spatial_request_inside_cooldown_window() -> None:
    # repeated approach/follow request in degraded mode
    # should emit cooldown_deferred instead of recording a second execution request
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_character_agent_runtime_memory_integration.py -k cooldown_deferred -v`
Expected: `FAIL`

- [x] **Step 3: Write minimal implementation**

```python
self._last_social_request_tick_ms: dict[tuple[str, str, str], int] = {}

def _should_defer_social_request(...):
    ...
```

```python
if self._should_defer_social_request(...):
    self._queue_observatory_stage_event(... stage="cooldown_deferred" ...)
    return
```

- [x] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_character_agent_runtime_memory_integration.py -k cooldown_deferred -v`
Expected: `PASS`

### Task 10: Add wake-up semantics for high-salience recovery inputs

**Files:**
- Modify: `backend/app/character_agent/runtime/runtime_loop.py`
- Modify: `backend/tests/test_character_agent_runtime_memory_integration.py`
- Modify: `scripts/verification/verify_mainline_unified_runtime.py`

- [x] **Step 1: Write the failing wake-up test**

```python
def test_runtime_high_salience_siming_input_bypasses_degraded_cognition_deferral() -> None:
    # degraded_mode=True with cognition interval 500ms
    # first perceived event consumes the cadence slot
    # high-salience siming input inside the same window should still produce an execution request
    # and should emit a wake_up observatory event instead of cognition_deferred
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_character_agent_runtime_memory_integration.py -k wake_up -v`
Expected: `FAIL`

- [x] **Step 3: Write minimal implementation**

```python
def _is_wake_up_input(payload: dict[str, object]) -> bool:
    # treat high-salience siming input as an explicit wake-up signal
```

```python
if self._should_defer_cognition(...) and not self._is_wake_up_input(...):
    ...
elif self._is_wake_up_input(...):
    self._queue_observatory_stage_event(... stage="wake_up" ...)
```

- [x] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_character_agent_runtime_memory_integration.py -k wake_up -v`
Expected: `PASS`

- [x] **Step 5: Include the new evidence in unified runtime verification**

Run: `python scripts/verification/verify_mainline_unified_runtime.py`
Expected: `PASS`

### Task 11: Add multi-actor scheduling semantics and degraded scaling policy

**Files:**
- Modify: `backend/app/world_runtime/scheduling.py`
- Modify: `backend/tests/test_world_runtime_scheduling.py`

- [x] **Step 1: Write the failing multi-actor scheduling test**

```python
def test_select_schedulable_actor_ids_prioritizes_wake_up_and_recovery_under_population_pressure() -> None:
    # define a population policy with a degraded threshold and reduced wake-up batch
    # provide multiple actor candidates with different wake_up / continuity / salience scores
    # assert degraded scheduling chooses the highest-priority recovery and wake-up actors first
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_world_runtime_scheduling.py -k schedulable_actor_ids -v`
Expected: `FAIL`

- [x] **Step 3: Write minimal implementation**

```python
class RuntimeWakeUpCandidate(BaseModel): ...
class RuntimePopulationPolicy(BaseModel): ...

def select_schedulable_actor_ids(...):
    # choose a bounded active set using explicit wake-up / continuity / salience ordering
```

- [x] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_world_runtime_scheduling.py -k schedulable_actor_ids -v`
Expected: `PASS`

- [x] **Step 5: Re-run the world-runtime suite evidence**

Run: `python scripts/verification/verify_mainline_unified_runtime.py`
Expected: `PASS`

### Task 12: Thread scheduling policy into runtime observability

**Files:**
- Modify: `backend/app/character_agent/runtime/runtime_loop.py`
- Modify: `backend/app/models/observatory.py`
- Modify: `backend/app/services/character_agent_debug_projection.py`
- Modify: `backend/tests/test_character_agent_runtime_memory_integration.py`

- [x] **Step 1: Write the failing runtime scheduling observability test**

```python
def test_runtime_observatory_snapshot_carries_scheduling_summary_for_degraded_population() -> None:
    # configure a degraded population policy
    # create one recovery-priority actor and one wake-up actor
    # assert the latest snapshot exposes the selected active actors and degraded population state
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_character_agent_runtime_memory_integration.py -k scheduling_summary -v`
Expected: `FAIL`

- [x] **Step 3: Write minimal implementation**

```python
self._population_policy = RuntimePopulationPolicy(...)

def get_runtime_population_policy(self) -> dict[str, object]: ...
def set_runtime_population_policy(...): ...
def get_schedulable_actor_ids(self) -> list[str]: ...
```

```python
# include scheduling_summary in observatory snapshots
```

- [x] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_character_agent_runtime_memory_integration.py -k scheduling_summary -v`
Expected: `PASS`

- [x] **Step 5: Re-run runtime evidence**

Run: `python scripts/verification/verify_mainline_unified_runtime.py`
Expected: `PASS`

### Task 13: Add unified verifier coverage for runtime scheduling evidence

**Files:**
- Modify: `scripts/verification/verify_mainline_unified_runtime.py`
- Modify: `scripts/verification/tests/test_mainline_unified_runtime_verify.py`

- [x] **Step 1: Write the failing verifier coverage test**

```python
def test_mainline_unified_runtime_verifier_includes_scheduling_summary_runtime_evidence() -> None:
    # assert the continuity observatory verifier command includes the scheduling_summary runtime test
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest scripts/verification/tests/test_mainline_unified_runtime_verify.py -k scheduling_summary -v`
Expected: `FAIL`

- [x] **Step 3: Write minimal implementation**

```python
# include test_runtime_observatory_snapshot_carries_scheduling_summary_for_degraded_population
# in the continuity/observatory verifier command
```

- [x] **Step 4: Run test to verify it passes**

Run: `pytest scripts/verification/tests/test_mainline_unified_runtime_verify.py -k scheduling_summary -v`
Expected: `PASS`

- [x] **Step 5: Re-run unified proof**

Run: `python scripts/verification/verify_mainline_unified_runtime.py`
Expected: `PASS`

### Task 14: Add event-level scheduling evidence to runtime observability

**Files:**
- Modify: `backend/app/character_agent/runtime/runtime_loop.py`
- Modify: `backend/tests/test_character_agent_runtime_memory_integration.py`
- Modify: `scripts/verification/verify_mainline_unified_runtime.py`
- Modify: `scripts/verification/tests/test_mainline_unified_runtime_verify.py`

- [x] **Step 1: Write the failing runtime and verifier coverage tests**

```python
def test_runtime_emits_scheduling_state_event_for_selected_actor_under_population_pressure() -> None:
    # degraded population policy
    # recovery-priority actor plus wake-up actor
    # assert scheduling_state event records selected active set and actor-local selection role
```

```python
def test_mainline_unified_runtime_verifier_includes_scheduling_state_runtime_evidence() -> None:
    # assert the continuity observatory verifier command includes the scheduling_state runtime test
```

- [x] **Step 2: Run tests to verify they fail**

Run: `pytest backend/tests/test_character_agent_runtime_memory_integration.py -k scheduling_state -v`
Expected: `FAIL`

Run: `pytest scripts/verification/tests/test_mainline_unified_runtime_verify.py -k scheduling_state -v`
Expected: `FAIL`

- [x] **Step 3: Write minimal implementation**

```python
# emit scheduling_state observatory events with active_actor_ids, degraded_population,
# actor_selected, wake_up_requested, continuity_priority, and salience
```

```python
# include the scheduling_state runtime test in unified verifier continuity coverage
```

- [x] **Step 4: Run tests to verify they pass**

Run: `pytest backend/tests/test_character_agent_runtime_memory_integration.py -k scheduling_state -v`
Expected: `PASS`

Run: `pytest scripts/verification/tests/test_mainline_unified_runtime_verify.py -k scheduling_state -v`
Expected: `PASS`

- [x] **Step 5: Re-run unified proof**

Run: `python scripts/verification/verify_mainline_unified_runtime.py`
Expected: `PASS`

### Task 15: Add unified runtime scheduling state surface

**Files:**
- Modify: `backend/app/character_agent/runtime/runtime_loop.py`
- Modify: `backend/tests/test_character_agent_runtime_memory_integration.py`
- Modify: `scripts/verification/verify_mainline_unified_runtime.py`
- Modify: `scripts/verification/tests/test_mainline_unified_runtime_verify.py`

- [x] **Step 1: Write the failing runtime and verifier coverage tests**

```python
def test_runtime_exposes_unified_scheduling_state_for_population_tick() -> None:
    # degraded population policy
    # recovery-priority actor plus wake-up actor
    # assert unified scheduling state exposes active_actor_ids and per-actor selected flags
```

```python
def test_mainline_unified_runtime_verifier_includes_unified_scheduling_state_runtime_evidence() -> None:
    # assert the continuity observatory verifier command includes the unified scheduling state runtime test
```

- [x] **Step 2: Run tests to verify they fail**

Run: `pytest backend/tests/test_character_agent_runtime_memory_integration.py -k unified_scheduling_state -v`
Expected: `FAIL`

Run: `pytest scripts/verification/tests/test_mainline_unified_runtime_verify.py -k unified_scheduling_state -v`
Expected: `FAIL`

- [x] **Step 3: Write minimal implementation**

```python
def get_runtime_scheduling_state(self) -> dict[str, object]:
    # return actor_population, active_limit, degraded_population,
    # active_actor_ids, and per_actor candidate state
```

```python
# include the unified scheduling state runtime test in unified verifier continuity coverage
```

- [x] **Step 4: Run tests to verify they pass**

Run: `pytest backend/tests/test_character_agent_runtime_memory_integration.py -k unified_scheduling_state -v`
Expected: `PASS`

Run: `pytest scripts/verification/tests/test_mainline_unified_runtime_verify.py -k unified_scheduling_state -v`
Expected: `PASS`

- [x] **Step 5: Re-run unified proof**

Run: `python scripts/verification/verify_mainline_unified_runtime.py`
Expected: `PASS`

### Task 16: Add replayable scheduling-round identifiers

**Files:**
- Modify: `backend/app/character_agent/runtime/runtime_loop.py`
- Modify: `backend/tests/test_character_agent_runtime_memory_integration.py`
- Modify: `scripts/verification/verify_mainline_unified_runtime.py`
- Modify: `scripts/verification/tests/test_mainline_unified_runtime_verify.py`

- [x] **Step 1: Write the failing runtime and verifier coverage tests**

```python
def test_runtime_scheduling_state_advances_round_id_when_new_runtime_tick_arrives() -> None:
    # first runtime event creates round 1
    # second later runtime event creates round 2
    # assert scheduling state exposes round_id and round_started_at for the latest tick
```

```python
def test_mainline_unified_runtime_verifier_includes_scheduling_round_runtime_evidence() -> None:
    # assert the continuity observatory verifier command includes the scheduling round runtime test
```

- [x] **Step 2: Run tests to verify they fail**

Run: `pytest backend/tests/test_character_agent_runtime_memory_integration.py -k scheduling_round -v`
Expected: `FAIL`

Run: `pytest scripts/verification/tests/test_mainline_unified_runtime_verify.py -k scheduling_round -v`
Expected: `FAIL`

- [x] **Step 3: Write minimal implementation**

```python
self._scheduling_round_id = 0
self._scheduling_round_started_at = 0

def _refresh_scheduling_round(...):
    # bump round when a new producer_ts drives scheduling state
```

```python
def get_runtime_scheduling_state(self) -> dict[str, object]:
    # include round_id and round_started_at
```

```python
# include the scheduling-round runtime test in unified verifier continuity coverage
```

- [x] **Step 4: Run tests to verify they pass**

Run: `pytest backend/tests/test_character_agent_runtime_memory_integration.py -k scheduling_round -v`
Expected: `PASS`

Run: `pytest scripts/verification/tests/test_mainline_unified_runtime_verify.py -k scheduling_round -v`
Expected: `PASS`

- [x] **Step 5: Re-run unified proof**

Run: `python scripts/verification/verify_mainline_unified_runtime.py`
Expected: `PASS`

### Task 17: Add scheduling selection-reason evidence

**Files:**
- Modify: `backend/app/character_agent/runtime/runtime_loop.py`
- Modify: `backend/tests/test_character_agent_runtime_memory_integration.py`
- Modify: `scripts/verification/verify_mainline_unified_runtime.py`
- Modify: `scripts/verification/tests/test_mainline_unified_runtime_verify.py`

- [x] **Step 1: Write the failing runtime and verifier coverage tests**

```python
def test_runtime_scheduling_state_exposes_selection_reason_tags_for_active_actor_set() -> None:
    # recovery-priority actor plus wake-up actor
    # assert unified scheduling state explains why each selected actor entered the active set
```

```python
def test_mainline_unified_runtime_verifier_includes_scheduling_selection_reason_runtime_evidence() -> None:
    # assert the continuity observatory verifier command includes the selection-reason runtime test
```

- [x] **Step 2: Run tests to verify they fail**

Run: `pytest backend/tests/test_character_agent_runtime_memory_integration.py -k selection_reason -v`
Expected: `FAIL`

Run: `pytest scripts/verification/tests/test_mainline_unified_runtime_verify.py -k selection_reason -v`
Expected: `FAIL`

- [x] **Step 3: Write minimal implementation**

```python
def _scheduling_reason_tags(...):
    # continuity_recovery, wake_up_signal, salience_priority, etc.
```

```python
def get_runtime_scheduling_state(self) -> dict[str, object]:
    # include per-actor selection_reason_tags and active_actor_reason_map
```

```python
# include the scheduling selection-reason runtime test in unified verifier continuity coverage
```

- [x] **Step 4: Run tests to verify they pass**

Run: `pytest backend/tests/test_character_agent_runtime_memory_integration.py -k selection_reason -v`
Expected: `PASS`

Run: `pytest scripts/verification/tests/test_mainline_unified_runtime_verify.py -k selection_reason -v`
Expected: `PASS`

- [x] **Step 5: Re-run unified proof**

Run: `python scripts/verification/verify_mainline_unified_runtime.py`
Expected: `PASS`

### Task 18: Add round-level scheduling causation summary

**Files:**
- Modify: `backend/app/character_agent/runtime/runtime_loop.py`
- Modify: `backend/tests/test_character_agent_runtime_memory_integration.py`
- Modify: `scripts/verification/verify_mainline_unified_runtime.py`
- Modify: `scripts/verification/tests/test_mainline_unified_runtime_verify.py`

- [x] **Step 1: Write the failing runtime and verifier coverage tests**

```python
def test_runtime_scheduling_state_exposes_round_summary_and_reason_tags() -> None:
    # recovery-priority actor plus wake-up actor
    # assert unified scheduling state exposes round_summary, round_reason_tags, and lead_actor_id
```

```python
def test_mainline_unified_runtime_verifier_includes_scheduling_round_summary_runtime_evidence() -> None:
    # assert the continuity observatory verifier command includes the round-summary runtime test
```

- [x] **Step 2: Run tests to verify they fail**

Run: `pytest backend/tests/test_character_agent_runtime_memory_integration.py -k round_summary -v`
Expected: `FAIL`

Run: `pytest scripts/verification/tests/test_mainline_unified_runtime_verify.py -k round_summary -v`
Expected: `FAIL`

- [x] **Step 3: Write minimal implementation**

```python
def _round_reason_tags(...):
    # aggregate unique scheduling causes across active actors
```

```python
def get_runtime_scheduling_state(self) -> dict[str, object]:
    # include lead_actor_id, round_reason_tags, and round_summary
```

```python
# include the scheduling round-summary runtime test in unified verifier continuity coverage
```

- [x] **Step 4: Run tests to verify they pass**

Run: `pytest backend/tests/test_character_agent_runtime_memory_integration.py -k round_summary -v`
Expected: `PASS`

Run: `pytest scripts/verification/tests/test_mainline_unified_runtime_verify.py -k round_summary -v`
Expected: `PASS`

- [x] **Step 5: Re-run unified proof**

Run: `python scripts/verification/verify_mainline_unified_runtime.py`
Expected: `PASS`

### Task 19: Add unified scheduling-round observatory event

**Files:**
- Modify: `backend/app/character_agent/runtime/runtime_loop.py`
- Modify: `backend/tests/test_character_agent_runtime_memory_integration.py`
- Modify: `scripts/verification/verify_mainline_unified_runtime.py`
- Modify: `scripts/verification/tests/test_mainline_unified_runtime_verify.py`

- [x] **Step 1: Write the failing runtime and verifier coverage tests**

```python
def test_runtime_emits_single_scheduling_round_state_event_with_unified_summary() -> None:
    # produce one degraded scheduling round with two active actors
    # assert one scheduling_round_state event is emitted with round_summary,
    # round_reason_tags, active_actor_ids, and lead_actor_id
```

```python
def test_mainline_unified_runtime_verifier_includes_scheduling_round_state_runtime_evidence() -> None:
    # assert the continuity observatory verifier command includes the scheduling_round_state runtime test
```

- [x] **Step 2: Run tests to verify they fail**

Run: `pytest backend/tests/test_character_agent_runtime_memory_integration.py -k scheduling_round_state -v`
Expected: `FAIL`

Run: `pytest scripts/verification/tests/test_mainline_unified_runtime_verify.py -k scheduling_round_state -v`
Expected: `FAIL`

- [x] **Step 3: Write minimal implementation**

```python
def _queue_scheduling_round_event_if_needed(...):
    # emit one unified scheduling_round_state event per round
```

```python
# include the scheduling_round_state runtime test in unified verifier continuity coverage
```

- [x] **Step 4: Run tests to verify they pass**

Run: `pytest backend/tests/test_character_agent_runtime_memory_integration.py -k scheduling_round_state -v`
Expected: `PASS`

Run: `pytest scripts/verification/tests/test_mainline_unified_runtime_verify.py -k scheduling_round_state -v`
Expected: `PASS`

- [x] **Step 5: Re-run unified proof**

Run: `python scripts/verification/verify_mainline_unified_runtime.py`
Expected: `PASS`

### Task 20: Route scheduling-round observatory events into debug stream

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/tests/test_debug_panel.py`
- Modify: `scripts/verification/verify_mainline_unified_runtime.py`
- Modify: `scripts/verification/tests/test_mainline_unified_runtime_verify.py`

- [x] **Step 1: Write the failing debug-stream and verifier coverage tests**

```python
def test_debug_ws_replays_scheduling_round_state_observatory_event() -> None:
    # emit a character_agent_debug_event with stage scheduling_round_state
    # assert /debug/ws replays it from debug stream history
```

```python
def test_mainline_unified_runtime_verifier_includes_scheduling_round_debug_stream_evidence() -> None:
    # assert the continuity observatory verifier command includes the scheduling-round debug-stream test
```

- [x] **Step 2: Run tests to verify they fail**

Run: `pytest backend/tests/test_debug_panel.py -k scheduling_round_state -v`
Expected: `FAIL`

Run: `pytest scripts/verification/tests/test_mainline_unified_runtime_verify.py -k scheduling_round_debug_stream -v`
Expected: `FAIL`

- [x] **Step 3: Write minimal implementation**

```python
# in _emit_debug_from_messages, map character_agent_debug_event into build_debug_event
# so scheduling_round_state reaches debug_stream and /debug/ws
```

```python
# include the debug-stream runtime test in unified verifier continuity coverage
```

- [x] **Step 4: Run tests to verify they pass**

Run: `pytest backend/tests/test_debug_panel.py -k scheduling_round_state -v`
Expected: `PASS`

Run: `pytest scripts/verification/tests/test_mainline_unified_runtime_verify.py -k scheduling_round_debug_stream -v`
Expected: `PASS`

- [x] **Step 5: Re-run unified proof**

Run: `python scripts/verification/verify_mainline_unified_runtime.py`
Expected: `PASS`

### Task 21: Route scheduling round script beats into debug stream

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/tests/test_debug_panel.py`
- Modify: `scripts/verification/verify_mainline_unified_runtime.py`
- Modify: `scripts/verification/tests/test_mainline_unified_runtime_verify.py`

- [x] **Step 1: Write the failing debug-stream and verifier coverage tests**

```python
def test_debug_ws_replays_script_beat_event_for_scheduling_round_summary() -> None:
    # emit a script_beat_event carrying scheduling-round dramatic_summary
    # assert /debug/ws replays it from debug stream history
```

```python
def test_mainline_unified_runtime_verifier_includes_scheduling_round_script_beat_debug_stream_evidence() -> None:
    # assert the continuity observatory verifier command includes the scheduling round script-beat debug-stream test
```

- [x] **Step 2: Run tests to verify they fail**

Run: `pytest backend/tests/test_debug_panel.py -k script_beat_event_for_scheduling_round -v`
Expected: `FAIL`

Run: `pytest scripts/verification/tests/test_mainline_unified_runtime_verify.py -k script_beat_debug_stream -v`
Expected: `FAIL`

- [x] **Step 3: Write minimal implementation**

```python
# in _emit_debug_from_messages, map script_beat_event into build_debug_event
# so scheduling round script beats reach debug_stream and /debug/ws
```

```python
# include the scheduling round script-beat debug-stream test in unified verifier continuity coverage
```

- [x] **Step 4: Run tests to verify they pass**

Run: `pytest backend/tests/test_debug_panel.py -k script_beat_event_for_scheduling_round -v`
Expected: `PASS`

Run: `pytest scripts/verification/tests/test_mainline_unified_runtime_verify.py -k script_beat_debug_stream -v`
Expected: `PASS`

- [x] **Step 5: Re-run unified proof**

Run: `python scripts/verification/verify_mainline_unified_runtime.py`
Expected: `PASS`

### Task 22: Add scheduling round trace outbound replay surface

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/tests/test_character_agent_action_request_routing.py`
- Modify: `scripts/verification/verify_mainline_unified_runtime.py`
- Modify: `scripts/verification/tests/test_mainline_unified_runtime_verify.py`

- [x] **Step 1: Write the failing routing and verifier coverage tests**

```python
def test_character_agent_execution_route_emits_scheduling_round_trace() -> None:
    # run one actor-targeted social-spatial execution route
    # assert outbound messages include scheduling_round_trace with round_id and lead_actor_id
```

```python
def test_mainline_unified_runtime_verifier_includes_scheduling_round_trace_runtime_evidence() -> None:
    # assert the continuity observatory verifier command includes the scheduling_round_trace runtime test
```

- [x] **Step 2: Run tests to verify they fail**

Run: `pytest backend/tests/test_character_agent_action_request_routing.py -k scheduling_round_trace -v`
Expected: `FAIL`

Run: `pytest scripts/verification/tests/test_mainline_unified_runtime_verify.py -k scheduling_round_trace -v`
Expected: `FAIL`

- [x] **Step 3: Write minimal implementation**

```python
# derive scheduling_round_trace from scheduling_round_state observatory payloads
# inside _observatory_messages_from_outbound
```

```python
# include the scheduling_round_trace runtime test in unified verifier continuity coverage
```

- [x] **Step 4: Run tests to verify they pass**

Run: `pytest backend/tests/test_character_agent_action_request_routing.py -k scheduling_round_trace -v`
Expected: `PASS`

Run: `pytest scripts/verification/tests/test_mainline_unified_runtime_verify.py -k scheduling_round_trace -v`
Expected: `PASS`

- [x] **Step 5: Re-run unified proof**

Run: `python scripts/verification/verify_mainline_unified_runtime.py`
Expected: `PASS`

### Task 23: Route scheduling round traces into debug stream

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/tests/test_debug_panel.py`
- Modify: `scripts/verification/verify_mainline_unified_runtime.py`
- Modify: `scripts/verification/tests/test_mainline_unified_runtime_verify.py`

- [x] **Step 1: Write the failing debug-stream and verifier coverage tests**

```python
def test_debug_ws_replays_scheduling_round_trace_event() -> None:
    # emit a scheduling_round_trace outbound payload through _emit_debug_from_messages
    # assert /debug/ws replays it from debug stream history
```

```python
def test_mainline_unified_runtime_verifier_includes_scheduling_round_trace_debug_stream_evidence() -> None:
    # assert the continuity observatory verifier command includes the scheduling_round_trace debug-stream test
```

- [x] **Step 2: Run tests to verify they fail**

Run: `pytest backend/tests/test_debug_panel.py -k scheduling_round_trace_event -v`
Expected: `FAIL`

Run: `pytest scripts/verification/tests/test_mainline_unified_runtime_verify.py -k scheduling_round_trace_debug_stream -v`
Expected: `FAIL`

- [x] **Step 3: Write minimal implementation**

```python
# in _emit_debug_from_messages, map scheduling_round_trace into build_debug_event
# so it reaches debug_stream and /debug/ws
```

```python
# include the scheduling_round_trace debug-stream test in unified verifier continuity coverage
```

- [x] **Step 4: Run tests to verify they pass**

Run: `pytest backend/tests/test_debug_panel.py -k scheduling_round_trace_event -v`
Expected: `PASS`

Run: `pytest scripts/verification/tests/test_mainline_unified_runtime_verify.py -k scheduling_round_trace_debug_stream -v`
Expected: `PASS`

- [x] **Step 5: Re-run unified proof**

Run: `python scripts/verification/verify_mainline_unified_runtime.py`
Expected: `PASS`

### Task 24: Add websocket-level scheduling round trace evidence

**Files:**
- Modify: `backend/tests/test_ws_protocol.py`
- Modify: `scripts/verification/verify_mainline_unified_runtime.py`
- Modify: `scripts/verification/tests/test_mainline_unified_runtime_verify.py`

- [x] **Step 1: Write the failing websocket and verifier coverage tests**

```python
def test_websocket_character_agent_execution_emits_scheduling_round_trace() -> None:
    # send one social-spatial character_agent_execution over /ws
    # assert the outbound stream includes scheduling_round_trace
```

```python
def test_mainline_unified_runtime_verifier_includes_websocket_scheduling_round_trace_evidence() -> None:
    # assert the continuity observatory verifier command includes the websocket scheduling_round_trace test
```

- [x] **Step 2: Run tests to verify they fail**

Run: `pytest backend/tests/test_ws_protocol.py -k websocket_character_agent_execution_emits_scheduling_round_trace -v`
Expected: `FAIL`

Run: `pytest scripts/verification/tests/test_mainline_unified_runtime_verify.py -k websocket_scheduling_round_trace -v`
Expected: `FAIL`

- [x] **Step 3: Write minimal implementation**

```python
# if needed, adjust outbound message sequencing so scheduling_round_trace is preserved on /ws
```

```python
# include the websocket scheduling_round_trace test in unified verifier continuity coverage
```

- [x] **Step 4: Run tests to verify they pass**

Run: `pytest backend/tests/test_ws_protocol.py -k websocket_character_agent_execution_emits_scheduling_round_trace -v`
Expected: `PASS`

Run: `pytest scripts/verification/tests/test_mainline_unified_runtime_verify.py -k websocket_scheduling_round_trace -v`
Expected: `PASS`

- [x] **Step 5: Re-run unified proof**

Run: `python scripts/verification/verify_mainline_unified_runtime.py`
Expected: `PASS`

### Task 25: Prove scheduling round trace on the real interact websocket chain

**Files:**
- Modify: `backend/tests/test_ws_protocol.py`
- Modify: `scripts/verification/verify_mainline_unified_runtime.py`
- Modify: `scripts/verification/tests/test_mainline_unified_runtime_verify.py`

- [x] **Step 1: Write the failing websocket/verifier coverage tests**

```python
def test_websocket_interact_intent_emits_scheduling_round_trace_after_character_agent_execution() -> None:
    # run the real player_input -> interact_intent -> siming -> character_agent_execution chain
    # assert the outbound websocket stream includes scheduling_round_trace
```

```python
def test_mainline_unified_runtime_verifier_includes_interact_websocket_scheduling_round_trace_evidence() -> None:
    # assert the continuity observatory verifier command includes the real interact websocket trace test
```

- [x] **Step 2: Run tests to verify they fail**

Run: `pytest backend/tests/test_ws_protocol.py -k interact_intent_emits_scheduling_round_trace_after_character_agent_execution -v`
Expected: `FAIL`

Run: `pytest scripts/verification/tests/test_mainline_unified_runtime_verify.py -k interact_websocket_scheduling_round_trace -v`
Expected: `FAIL`

- [x] **Step 3: Write minimal implementation**

```python
# if needed, include the real interact websocket trace test in unified verifier continuity coverage
```

- [x] **Step 4: Run tests to verify they pass**

Run: `pytest backend/tests/test_ws_protocol.py -k interact_intent_emits_scheduling_round_trace_after_character_agent_execution -v`
Expected: `PASS`

Run: `pytest scripts/verification/tests/test_mainline_unified_runtime_verify.py -k interact_websocket_scheduling_round_trace -v`
Expected: `PASS`

- [x] **Step 5: Re-run unified proof**

Run: `python scripts/verification/verify_mainline_unified_runtime.py`
Expected: `PASS`


### Task 26: Add unified verifier coverage for frontend scheduling trace chain

**Files:**
- Modify: `scripts/verification/verify_mainline_unified_runtime.py`
- Modify: `scripts/verification/tests/test_mainline_unified_runtime_verify.py`

- [x] **Step 1: Write the failing verifier coverage test**

```python
def test_mainline_unified_runtime_verifier_includes_frontend_scheduling_round_trace_chain_evidence() -> None:
    # assert the continuity observatory verifier command includes the static frontend signal/state tests
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest scripts/verification/tests/test_mainline_unified_runtime_verify.py -k frontend_scheduling_round_trace_chain -v`
Expected: `FAIL`

- [x] **Step 3: Write minimal implementation**

```python
# include:
# backend/tests/test_observatory_message_delivery_static.py
# backend/tests/test_character_director_state_static.py
# in unified verifier continuity coverage
```

- [x] **Step 4: Run test to verify it passes**

Run: `pytest scripts/verification/tests/test_mainline_unified_runtime_verify.py -k frontend_scheduling_round_trace_chain -v`
Expected: `PASS`

- [x] **Step 5: Re-run unified proof**

Run: `python scripts/verification/verify_mainline_unified_runtime.py`
Expected: `PASS`
