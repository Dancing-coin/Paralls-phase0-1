# Character Turn Continuity and Embodied Episode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make one CharacterAgent behavior turn durable, recoverable, evidence-backed, and the sole semantic precursor to later embodied action work; prove it with one authority-confirmed archive-door episode.

**Architecture:** Introduce an actor-private `CharacterTurnContext` that is created before L1 and carried through L4, authority settlement, evaluation, policy, and checkpoint. Persist its stage records in the existing session/graph continuity seams, reconcile interrupted turns rather than reissuing them, and make L3 policy use durable. A VLA result remains advisory and may only nominate a candidate that becomes an ordinary actor intent; an episode joins that candidate, execution, authority receipt, and post-action observation without granting VLA body or world-write authority.

**Tech Stack:** Python 3.13, Pydantic v2, existing CharacterAgent runtime/session timeline/Heavenly Graph continuity stores, existing VLA advisory provider, FastAPI/WebSocket boundary, Godot 4.6, pytest, repository Harness.

**Spec:** `docs/superpowers/specs/2026-09-23-character-turn-continuity-and-embodied-episode-design.md`

## Global Constraints

- Preserve `CharacterAgentRuntime` as the cognition/intent owner; do not make Heavenly Graph a cognition or settlement owner.
- Use the existing `CharacterAgentSessionStore` and `CharacterGraphContinuityStore`; do not add a second database or cross-store ACID fiction.
- ESM, Gameplay, or a registered Composite owner remains the only authority that can commit world truth.
- Godot owns local embodiment and presentation only. Local success, an animation marker, a VLA result, or a post-action capture never substitutes for an authority result.
- VLA remains `advisory_only`: it may not emit transform, velocity, bone pose, animation state, impulse, damage, status, inventory, or world mutation fields.
- All new actor-private records must validate actor scope, branch/valid-time scope, causation, correlation, idempotency, and revision metadata before persistence.
- Extend existing message/contract paths rather than creating a competing action, transport, or policy runtime.
- Do not add dependencies. Do not broaden into Siming story/obligation migration, generic VLA action chunks, generic navigation/IK, asset qualification, weapons, rollback, or physical networking.
- Backend changes require `python -m pytest -v`; Godot/integration claims require a running backend, real boundary traffic, and visible scene evidence.

---

## File Structure

| Area | Files | Responsibility |
| --- | --- | --- |
| Turn contracts | `backend/app/character_agent/models/turn_context.py`, `backend/app/models/behavior_turn.py` | Closed lifecycle, stage payloads, receipts, validation. |
| Turn coordination | `backend/app/character_agent/services/character_turn_coordinator.py`, `runtime/runtime_loop.py` | Begin/advance/reconcile a canonical turn and write session events. |
| Continuity | `storage/graph_continuity_store.py`, `services/character_turn_recovery.py` | Persist complete turn/checkpoint state and recover interrupted work. |
| Policy/evaluation | `models/behavior_policy.py`, `storage/behavior_policy_store.py`, `services/character_behavior_evaluation.py`, `planning/l3_planner.py` | Durable policy lifecycle and evidence-based next-turn selection. |
| Recall | `services/character_semantic_recall.py`, `gateway/memory_recall.py` | Bounded graph-aware recall facade with scope/conflict metadata. |
| Execution | `models/character_execution.py`, `execution/l4_executor.py`, `execution/l4_adapter.py` | Sole production-shaped execution contract and one-way legacy translation. |
| VLA episode | `models/embodied_episode.py`, `services/embodied_episode_service.py`, `world_runtime/vla_percept_bridge.py` | Advisory candidate normalization, input conflict records, post-action comparison. |
| Evidence | `backend/tests/test_*.py`, `scripts/verification/verify_character_turn_embodied_episode.py`, `.harness/profiles/character-turn-embodied-episode.json` | Unit, restart, authority, VLA boundary, Godot, and replay proof. |
| Sequencing | `docs/character/*.md`, action-foundation master plan | Record the completion gate consumed by later action work. |

## Delivery Order

```text
turn identity/lifecycle
  -> session stage records and restart reconciliation
  -> durable policy + evaluation
  -> semantic recall
  -> sole execution contract
  -> advisory candidate + episode record
  -> archive-door live proof
  -> action-foundation implementation resumes
```

### Task 1: Add the canonical turn context and closed lifecycle contract

**Files:**
- Create: `backend/app/character_agent/models/turn_context.py`
- Modify: `backend/app/models/behavior_turn.py`
- Modify: `backend/app/character_agent/models/__init__.py`
- Test: `backend/tests/test_character_turn_context.py`

**Interfaces:**
- Produces `CharacterTurnContext`, `CharacterTurnStageEvent`, and `CharacterTurnReceipt`.
- `CharacterTurnContext.begin(actor_id, source_event_ref, producer_ts, *, causation_id, correlation_id, input_revision_vector, memory_revision_vector, policy_revision, snapshot_revision, branch_id=None) -> CharacterTurnContext`.
- `context.advance(stage, *, stage_ref, idempotency_key, producer_ts) -> CharacterTurnContext` accepts only the next legal stage/lifecycle transition.
- `BehaviorTurnRecordRequest` consumes canonical stage records; it no longer accepts a missing `turn_id` inferred after settlement. A continuity checkpoint is a separately typed snapshot/receipt record, not a `BehaviorTurnStage`.

- [ ] **Step 1: Write lifecycle contract tests**

```python
from app.character_agent.models.turn_context import CharacterTurnContext, TurnLifecycleError


def test_turn_carries_one_identity_from_context_to_awaiting_settlement() -> None:
    turn = CharacterTurnContext.begin(
        actor_id="char_b",
        source_event_ref="event:perception:1",
        producer_ts=100,
        causation_id="cause:1",
        correlation_id="corr:1",
        input_revision_vector={"l1": 4},
        memory_revision_vector={"memory": 9},
        policy_revision="policy:char_b:3",
        snapshot_revision=12,
    )
    for stage in ("context", "interpretation", "goal", "intent", "execution"):
        turn = turn.advance(stage, stage_ref=f"event:{stage}:1", idempotency_key=f"key:{stage}", producer_ts=101)
    assert turn.turn_id == "turn:char_b:event:perception:1"
    assert turn.lifecycle == "awaiting_settlement"


def test_turn_rejects_out_of_order_or_changed_idempotent_stage() -> None:
    turn = CharacterTurnContext.begin(
        actor_id="char_b", source_event_ref="event:perception:2", producer_ts=1,
        causation_id="cause:2", correlation_id="corr:2",
        input_revision_vector={"l1": 1}, memory_revision_vector={"memory": 1},
        policy_revision="policy:char_b:1", snapshot_revision=1,
    )
    with pytest.raises(TurnLifecycleError, match="expected context"):
        turn.advance("execution", stage_ref="event:execution:1", idempotency_key="k", producer_ts=1)
```

- [ ] **Step 2: Run the new tests to confirm the contract is absent**

Run: `python -m pytest backend/tests/test_character_turn_context.py -v`

Expected: FAIL because `turn_context` does not yet exist.

- [ ] **Step 3: Implement immutable, validated turn models**

```python
class CharacterTurnContext(BaseModel):
    turn_id: str
    actor_id: str
    source_event_ref: str
    causation_id: str
    correlation_id: str
    lifecycle: Literal["prepared", "running", "awaiting_settlement", "settled", "evaluated", "committed", "rejected", "recovery_required", "abandoned", "failed"]
    stage_refs: dict[str, str] = Field(default_factory=dict)
    stage_idempotency_keys: dict[str, str] = Field(default_factory=dict)
    input_revision_vector: dict[str, int]
    memory_revision_vector: dict[str, int]
    policy_revision: str
    snapshot_revision: int

    def advance(self, stage: CharacterTurnStage, *, stage_ref: str, idempotency_key: str, producer_ts: int) -> "CharacterTurnContext":
        expected_stage = expected_next_stage(self.stage_refs, self.lifecycle)
        if stage != expected_stage:
            raise TurnLifecycleError(f"expected {expected_stage}, got {stage}")
        if stage in self.stage_idempotency_keys:
            if self.stage_idempotency_keys[stage] != idempotency_key:
                raise TurnLifecycleError("stage idempotency payload mismatch")
            return self
        return self.model_copy(update={
            "stage_refs": {**self.stage_refs, stage: stage_ref},
            "stage_idempotency_keys": {**self.stage_idempotency_keys, stage: idempotency_key},
            "lifecycle": lifecycle_after(stage),
        })
```

Use `model_copy(update=changed_fields)` where `changed_fields` contains only the lifecycle and stage fields shown in the method; do not mutate caller-owned dictionaries. Define a
single stage/lifecycle transition table and reuse it in the graph projection
validator.

- [ ] **Step 4: Make the behavior-turn model consume canonical stage identity**

Require every canonical session stage event to carry `turn_id`, `actor_id`,
and `correlation_id`. Make `BehaviorTurnRecordRequest` reject a canonical
projection whose stage-event identity differs from its request-level scope and
provenance. Keep the compact graph `BehaviorTurnStageRecord` as the projected
stage payload, with its identity inherited from the validated request. Keep
existing historical records readable through an explicit legacy-reader path;
do not reinterpret historical data as canonical live turns.

- [ ] **Step 5: Run focused contract and existing projection tests**

Run: `python -m pytest backend/tests/test_character_turn_context.py backend/tests/test_behavior_turn_recorder.py -v`

Expected: PASS, including existing rejected-settlement and interleaved-turn
regressions.

- [ ] **Step 6: Commit the isolated contract change**

```bash
git add backend/app/character_agent/models/turn_context.py backend/app/character_agent/models/__init__.py backend/app/models/behavior_turn.py backend/tests/test_character_turn_context.py
git commit -m "feat: add canonical character turn lifecycle"
```

### Task 2: Coordinate stage records from input through authority submission

**Files:**
- Create: `backend/app/character_agent/services/character_turn_coordinator.py`
- Modify: `backend/app/character_agent/runtime/runtime_loop.py`
- Modify: `backend/app/character_agent/services/behavior_turn_projection.py`
- Test: `backend/tests/test_character_turn_coordinator.py`
- Test: `backend/tests/test_character_agent_runtime.py`

**Interfaces:**
- Consumes `CharacterTurnContext` and `CharacterAgentSessionStore`.
- `CharacterTurnCoordinator.begin_or_replay(actor_id, source_event_ref, producer_ts, causation_id, correlation_id, input_revision_vector, memory_revision_vector, policy_revision, snapshot_revision, branch_id=None) -> CharacterTurnContext` appends one `character_turn_context_created` session event or returns the byte-identical existing turn.
- `append_stage(turn, stage, payload, producer_ts) -> CharacterTurnContext` appends `character_turn_stage_recorded` before returning a new context.
- `mark_awaiting_settlement(turn, execution_ref, authority_request_ref) -> CharacterTurnContext` persists before the outgoing authority call.
- `CharacterBehaviorTurnProjection.record_context(turn, timeline) -> None` projects existing canonical stage records rather than searching a producer timestamp window.

- [ ] **Step 1: Write an integration test that proves one input has one turn across L1--L4**

```python
def test_runtime_attaches_one_turn_id_to_every_pre_settlement_stage(tmp_path: Path) -> None:
    runtime = CharacterAgentRuntime(session_store=CharacterAgentSessionStore(tmp_path))
    runtime.ingest_character_perceived_event(perceived_event(actor_id="char_b", event_id="p-1"))
    entries = runtime.get_session_timeline("char_b")
    stages = [entry for entry in entries if entry["event_type"] == "character_turn_stage_recorded"]
    assert [entry["payload"]["stage"] for entry in stages] == ["context", "interpretation", "goal", "intent", "execution"]
    assert {entry["payload"]["turn_id"] for entry in stages} == {"turn:char_b:p-1"}
```

- [ ] **Step 2: Run it to confirm current timeline records have no canonical pre-settlement turn**

Run: `python -m pytest backend/tests/test_character_turn_coordinator.py::test_runtime_attaches_one_turn_id_to_every_pre_settlement_stage -v`

Expected: FAIL because no coordinator/stage records exist.

- [ ] **Step 3: Implement a narrow coordinator over the existing session store**

```python
class CharacterTurnCoordinator:
    def begin_or_replay(self, *, actor_id: str, source_event_ref: str, producer_ts: int, causation_id: str, correlation_id: str, input_revision_vector: dict[str, int], memory_revision_vector: dict[str, int], policy_revision: str, snapshot_revision: int, branch_id: str | None = None) -> CharacterTurnContext:
        return self._load_or_append_context(actor_id, source_event_ref, producer_ts, causation_id, correlation_id, input_revision_vector, memory_revision_vector, policy_revision, snapshot_revision, branch_id)

    def append_stage(self, *, context: CharacterTurnContext, stage: CharacterTurnStage, payload: Mapping[str, object], producer_ts: int) -> CharacterTurnContext:
        return self._append_validated_stage(context, stage, payload, producer_ts)

    def mark_awaiting_settlement(self, *, context: CharacterTurnContext, execution_ref: str, authority_request_ref: str, producer_ts: int) -> CharacterTurnContext:
        return self._append_execution_submission(context, execution_ref, authority_request_ref, producer_ts)
```

Use `expected_revision` for every append. If the session append fails, do not
advance in-memory goal, execution, or turn state. Reuse a stable stage
idempotency key derived from `turn_id + stage + canonical payload digest`.

- [ ] **Step 4: Wire all three runtime ingress paths through the coordinator**

Apply it to character perceived events, self-body perceived events, and
Siming-delivered catalyst events. Each path must create the context before L1,
append its L1 input snapshot as the `context` stage, append the L2/L3/L4 stage
outputs through the coordinator, and pass the same IDs to the execution
request. Do not change which source is allowed to settle a world result.

- [ ] **Step 5: Refactor behavior-turn projection to read canonical records**

Replace `_latest_chain(timeline, producer_ts, correlation_id)` as the primary live
path with retrieval by exact `turn_id`. Retain the old search only in a
clearly-named legacy projection helper for pre-migration timeline entries.

- [ ] **Step 6: Run focused runtime/projection regressions**

Run: `python -m pytest backend/tests/test_character_turn_coordinator.py backend/tests/test_character_agent_runtime.py backend/tests/test_behavior_turn_recorder.py -v`

Expected: PASS. A duplicate source event must produce no second L4 execution
or authority request.

- [ ] **Step 7: Commit the coordinator wiring**

```bash
git add backend/app/character_agent/services/character_turn_coordinator.py backend/app/character_agent/runtime/runtime_loop.py backend/app/character_agent/services/behavior_turn_projection.py backend/tests/test_character_turn_coordinator.py backend/tests/test_character_agent_runtime.py
git commit -m "feat: coordinate canonical character turn stages"
```

### Task 3: Persist pending turn state and reconcile restart safely

**Files:**
- Create: `backend/app/character_agent/services/character_turn_recovery.py`
- Modify: `backend/app/character_agent/storage/graph_continuity_store.py`
- Modify: `backend/app/character_agent/runtime/runtime_loop.py`
- Test: `backend/tests/test_character_turn_recovery.py`
- Test: `backend/tests/test_character_graph_continuity_store.py`

**Interfaces:**
- `CharacterTurnRecoveryService.reconcile(actor_id) -> CharacterTurnRecoveryResult` returns `resumed|recovery_required|already_committed|no_pending_turn`.
- Complete continuity snapshots add `active_turns`, `pending_execution`, `policy_state`, and `last_committed_turn_id` to the existing required snapshot fields.
- An unresolved execution has `authority_request_ref`, expected revision, idempotency key, and no receipt; it is never automatically resent.
- `CharacterAgentRuntime.begin_test_turn_awaiting_settlement(actor_id, request_ref) -> CharacterTurnContext`, `flush_continuity_snapshot(actor_id) -> None`, `reconcile_character_turn(actor_id) -> CharacterTurnRecoveryResult`, and `outgoing_authority_request_count(turn_id) -> int` are test-only helpers added in this task; production paths use the coordinator/recovery service.

- [ ] **Step 1: Write restart and receipt mismatch tests**

```python
def test_restart_marks_unreceipted_execution_recovery_required(tmp_path: Path) -> None:
    runtime = runtime_with_graph_and_session(tmp_path)
    turn = runtime.begin_test_turn_awaiting_settlement("char_b", request_ref="request:door:1")
    runtime.flush_continuity_snapshot("char_b")

    restored = runtime_with_graph_and_session(tmp_path)
    result = restored.reconcile_character_turn("char_b")

    assert result.status == "recovery_required"
    assert result.turn_id == turn.turn_id
    assert restored.outgoing_authority_request_count(turn.turn_id) == 0
```

- [ ] **Step 2: Run it to confirm incomplete pending execution is not represented durably**

Run: `python -m pytest backend/tests/test_character_turn_recovery.py::test_restart_marks_unreceipted_execution_recovery_required -v`

Expected: FAIL because recovery service and required snapshot fields do not
exist.

- [ ] **Step 3: Extend only the complete continuity snapshot contract**

Add the fields to `CharacterGraphContinuityStore.REQUIRED_SNAPSHOT_FIELDS` and
the runtime snapshot builder. Preserve `write_current_state()` as a hot read
model; do not falsely label it a complete recovery checkpoint. Include schema
version, session timeline checkpoint index, graph source event ref, and a
stable snapshot digest.

- [ ] **Step 4: Implement deterministic reconciliation**

```python
def reconcile(self, actor_id: str) -> CharacterTurnRecoveryResult:
    snapshot = self._continuity_store.read_snapshot(actor_id)
    timeline = self._session_store.list_events(actor_id)
    context = self._latest_pending_context(snapshot, timeline)
    receipt = self._authority_receipt_for(context, timeline)
    if receipt is not None:
        return self._commit_original_turn(context, receipt)
    return self._mark_recovery_required(context, reason="authority_receipt_missing")
```

Validate timeline continuity, context lifecycle/stage order, graph revision,
and exact authority-receipt correlation before advancing. Invalid state blocks
new actor execution but preserves audit records.

- [ ] **Step 5: Run continuity/replay regressions**

Run: `python -m pytest backend/tests/test_character_turn_recovery.py backend/tests/test_character_graph_continuity_store.py backend/tests/test_character_agent_runtime_persistence_wiring.py -v`

Expected: PASS for a settled turn, missing receipt, changed receipt identity,
and session-file-loss recovery from graph state.

- [ ] **Step 6: Commit snapshot/recovery work**

```bash
git add backend/app/character_agent/services/character_turn_recovery.py backend/app/character_agent/storage/graph_continuity_store.py backend/app/character_agent/runtime/runtime_loop.py backend/tests/test_character_turn_recovery.py backend/tests/test_character_graph_continuity_store.py
git commit -m "feat: recover pending character turns safely"
```

### Task 4: Replace ephemeral policy consumption with a durable policy lifecycle

**Files:**
- Create: `backend/app/character_agent/models/behavior_policy.py`
- Create: `backend/app/character_agent/storage/behavior_policy_store.py`
- Modify: `backend/app/character_agent/planning/l3_planner.py`
- Modify: `backend/app/character_agent/runtime/runtime_loop.py`
- Test: `backend/tests/test_behavior_policy_lifecycle.py`
- Test: `backend/tests/test_character_agent_l3_planning.py`

**Interfaces:**
- `BehaviorPolicyRecord` has the fields and closed statuses specified by the design.
- `BehaviorPolicyStore.propose(record) -> BehaviorPolicyRecord`, `consume(actor_id, policy_id, turn_id, now) -> BehaviorPolicyConsumption`, and `reconcile_outcome(actor_id, policy_id, source_turn_id, outcome, now) -> BehaviorPolicyRecord` are idempotent.
- `CharacterAgentL3Service.build_intent_plan(snapshot, interpretation, profile, current_goal_state, memory_bundle, turn_context) -> dict[str, object]` reads an actor-private policy snapshot; it no longer owns `_consumed_behavior_policy_ids`.

- [ ] **Step 1: Write policy persistence, TTL, and repeated-failure tests**

```python
def test_policy_consumption_is_idempotent_across_restart(tmp_path: Path) -> None:
    store = BehaviorPolicyStore(tmp_path)
    policy = store.propose(recovery_policy(actor_id="char_b", max_consumptions=2, expires_at=300))
    assert store.consume("char_b", policy.policy_id, "turn:char_b:2", now=200).applied

    restored = BehaviorPolicyStore(tmp_path)
    replay = restored.consume("char_b", policy.policy_id, "turn:char_b:2", now=200)
    assert replay.replayed is True
    assert replay.record.consumed_count == 1
```

- [ ] **Step 2: Run the test to demonstrate the current in-memory set is insufficient**

Run: `python -m pytest backend/tests/test_behavior_policy_lifecycle.py -v`

Expected: FAIL because the durable policy model/store does not exist.

- [ ] **Step 3: Implement actor-private, append-only policy records**

Persist records as session events plus graph-backed continuity snapshot state;
do not create a separate writer to world truth. Reject cross-actor reads,
expired records, altered policy payload under the same idempotency key, and
consumption after the declared limit. Implement `candidate -> accepted ->
applied`, `expired`, `superseded`, `rolled_back`, and `rejected` transitions.

- [ ] **Step 4: Connect evaluator candidates and L3 selection**

Only an evidence-qualified accepted policy appears in L3's policy snapshot.
For recovery policies, exclude the failed intent only for the current eligible
turn; for recall policies, increase bounded recall requirements without
changing world facts. Remove `_consumed_behavior_policy_ids` after the store
is the sole consumption owner.

- [ ] **Step 5: Run focused planner and policy tests**

Run: `python -m pytest backend/tests/test_behavior_policy_lifecycle.py backend/tests/test_character_agent_l3_planning.py backend/tests/test_character_behavior_evaluation.py -v`

Expected: PASS for expiry, supersession, duplicate consume, successful
de-escalation, and a failed intent changing the next eligible L3 choice.

- [ ] **Step 6: Commit policy lifecycle work**

```bash
git add backend/app/character_agent/models/behavior_policy.py backend/app/character_agent/storage/behavior_policy_store.py backend/app/character_agent/planning/l3_planner.py backend/app/character_agent/runtime/runtime_loop.py backend/tests/test_behavior_policy_lifecycle.py backend/tests/test_character_agent_l3_planning.py
git commit -m "feat: persist character behavior policy lifecycle"
```

### Task 5: Make evaluation evidence-backed and multi-dimensional

**Files:**
- Create: `backend/app/character_agent/models/behavior_evaluation.py`
- Modify: `backend/app/character_agent/services/character_behavior_evaluation.py`
- Modify: `backend/app/character_agent/services/behavior_turn_projection.py`
- Modify: `backend/app/character_agent/runtime/runtime_loop.py`
- Test: `backend/tests/test_character_behavior_evaluation.py`
- Test: `backend/tests/test_behavior_turn_recorder.py`

**Interfaces:**
- `BehaviorEvaluation` exposes six optional score dimensions, confidence,
  evidence refs, unknown dimension refs, and candidate policy.
- `CharacterBehaviorEvaluationService.evaluate(turn: CharacterTurnContext, settlement_event, timeline) -> BehaviorEvaluation`.
- The graph projection records `evaluation` from the canonical turn, including
  unknown dimensions, without translating them into a synthetic score.

- [ ] **Step 1: Extend the evaluator tests with divergent outcomes**

```python
def test_evaluation_marks_unprovable_social_effect_unknown_not_neutral() -> None:
    result = CharacterBehaviorEvaluationService().evaluate(
        turn=settled_turn(), settlement_event=accepted_door_event(), timeline=turn_timeline()
    )
    assert result.execution_quality_score == 1.0
    assert result.social_consequence_score is None
    assert "social_consequence" in result.unknown_dimensions
    assert result.evidence_refs
```

- [ ] **Step 2: Run the new test to confirm scalar evaluation cannot express the distinction**

Run: `python -m pytest backend/tests/test_character_behavior_evaluation.py::test_evaluation_marks_unprovable_social_effect_unknown_not_neutral -v`

Expected: FAIL because the current evaluator returns a scalar mapping.

- [ ] **Step 3: Implement deterministic dimension derivation**

Derive comprehension from interpretation/authority constraint agreement, goal
progress from the active-goal transition, role consistency from profile and
supervision constraints, execution quality from authority/local evidence,
social consequence from authorized relationship evidence, and recovery quality
from a completed recovery record. Leave a dimension `None` with a typed
unknown reason if its evidence is absent. Preserve `behavior_score` only as a
backward-compatible derived summary, not as the policy gate.

- [ ] **Step 4: Gate policy proposals on evidence completeness**

Require the evaluator to supply confidence and relevant evidence for a
candidate. A rejected/unknown settlement can create a recovery candidate but
cannot become an active policy merely because its scalar score is low.

- [ ] **Step 5: Run evaluator and graph-projection tests**

Run: `python -m pytest backend/tests/test_character_behavior_evaluation.py backend/tests/test_behavior_turn_recorder.py backend/tests/test_behavior_policy_lifecycle.py -v`

Expected: PASS, including a replayed completed turn retaining the same
evaluation and policy candidate identity.

- [ ] **Step 6: Commit evaluation closure**

```bash
git add backend/app/character_agent/models/behavior_evaluation.py backend/app/character_agent/services/character_behavior_evaluation.py backend/app/character_agent/services/behavior_turn_projection.py backend/app/character_agent/runtime/runtime_loop.py backend/tests/test_character_behavior_evaluation.py backend/tests/test_behavior_turn_recorder.py
git commit -m "feat: add evidence-backed character behavior evaluation"
```

### Task 6: Add bounded graph-aware semantic recall for L2 and L3

**Files:**
- Create: `backend/app/character_agent/services/character_semantic_recall.py`
- Modify: `backend/app/character_agent/gateway/memory_recall.py`
- Modify: `backend/app/character_agent/planning/l3_planner.py`
- Modify: `backend/app/character_agent/reasoning/l2_reasoner.py`
- Test: `backend/tests/test_character_semantic_recall.py`
- Test: `backend/tests/test_character_memory_recall_policy.py`

**Interfaces:**
- `CharacterSemanticRecallService.select(actor_id, context, *, turn_context) -> SemanticRecallResult`.
- Result contains `cards`, `selected_refs`, `omitted_refs`, `relation_refs`,
  `causal_refs`, `conflict_refs`, `perspective_refs`, `revision_vector`,
  `context_hash`, `truncated`, `incomplete_reason`, and per-card evidence
  status, plus `cards_by_ref` for deterministic consumers/tests.
- L2/L3 consume the result as a read-only context bundle; neither gets graph
  write authority.

- [ ] **Step 1: Add query-scope and conflict tests**

```python
def test_semantic_recall_expands_visible_cause_but_excludes_private_conflict() -> None:
    result = service.select("char_b", context_for("door:archive"), turn_context=running_turn())
    assert "event:door-opened:1" in result.causal_refs
    assert "memory:char_a:private:1" not in result.selected_refs
    assert result.cards_by_ref["belief:door-state"].evidence_status == "disputed"


def test_semantic_recall_reports_truncation_without_hiding_required_evidence() -> None:
    result = service.select("char_b", oversized_context(), turn_context=running_turn())
    assert result.truncated is True
    assert result.incomplete_reason == "token_budget_exhausted"
    assert required_claim_ref in result.selected_refs
```

- [ ] **Step 2: Run the new tests to confirm the current policy only ranks pool records**

Run: `python -m pytest backend/tests/test_character_semantic_recall.py -v`

Expected: FAIL because the semantic facade does not exist.

- [ ] **Step 3: Implement a facade over existing bounded recall and graph queries**

Start with `CharacterMemoryRecallPolicy.select()` for five-pool candidates.
Call only existing bounded behavior-turn, causal-path, conflict-set,
perspective, and source-impact query APIs. Revalidate actor scope, visibility,
branch, valid time, and revision before converting each graph record into a
recall card. Do not introduce unbounded multi-hop traversal or a new graph
storage format.

- [ ] **Step 4: Carry recall metadata into L2/L3 and the turn stage event**

Store only selected/omitted references and a digest in the stage event; keep
private card contents in the actor-private runtime context. When a required
claim cannot fit the budget, emit a typed missing/incomplete state and block
the affected model call rather than silently planning on partial truth.

- [ ] **Step 5: Run recall and runtime regressions**

Run: `python -m pytest backend/tests/test_character_semantic_recall.py backend/tests/test_character_memory_recall_policy.py backend/tests/test_character_agent_runtime_memory_integration.py -v`

Expected: PASS for causal/perspective recall, scope denial, conflict status,
deterministic budgets, and L2/L3 metadata preservation.

- [ ] **Step 6: Commit semantic recall work**

```bash
git add backend/app/character_agent/services/character_semantic_recall.py backend/app/character_agent/gateway/memory_recall.py backend/app/character_agent/planning/l3_planner.py backend/app/character_agent/reasoning/l2_reasoner.py backend/tests/test_character_semantic_recall.py backend/tests/test_character_memory_recall_policy.py
git commit -m "feat: add bounded character semantic recall"
```

### Task 7: Converge L4 on one production execution contract

**Files:**
- Create: `backend/app/character_agent/models/character_execution.py`
- Modify: `backend/app/character_agent/execution/l4_executor.py`
- Modify: `backend/app/character_agent/execution/l4_adapter.py`
- Modify: `backend/app/character_agent/runtime/runtime_loop.py`
- Modify: `backend/app/models/character_agent_runtime.py`
- Test: `backend/tests/test_character_execution_contract.py`
- Test: `backend/tests/test_character_agent_l4_execution.py`

**Interfaces:**
- `CharacterExecutionContract` has `turn_id`, actor/source/target refs,
  semantic intent/action, allowed realization hints, expected revision vector,
  idempotency key, causation/correlation, privacy/authority scope, and
  expected observation; it rejects body/world-write fields.
- `CharacterAgentL4Executor.build_execution_contract(snapshot, interpretation, decision, turn_context, *, skill_evaluation_result=None, action_settlement_result=None) -> CharacterExecutionContract`.
- `CharacterAgentL4Adapter.from_legacy_command(command, *, turn_context) -> LegacyExecutionTranslation` returns `{contract, legacy_translation=True}` and never dispatches the contract itself.
- `CharacterAgentL4Adapter.from_legacy_command(command, *, turn_context) -> CharacterExecutionContract` is one-way compatibility input.

- [ ] **Step 1: Write contract ownership tests**

```python
def test_execution_contract_requires_turn_and_rejects_body_or_world_writes() -> None:
    contract = CharacterExecutionContract.model_validate(valid_contract(turn_id="turn:char_b:p-1"))
    assert contract.semantic_action_id == "open_close"
    with pytest.raises(ValidationError, match="forbidden execution field"):
        CharacterExecutionContract.model_validate(valid_contract(global_position=[1, 0, 1]))


def test_legacy_command_translates_once_without_creating_second_request() -> None:
    result = adapter.from_legacy_command(legacy_open_command(), turn_context=running_turn())
    assert result.contract.turn_id == "turn:char_b:p-1"
    assert result.legacy_translation is True
```

- [ ] **Step 2: Run it to verify the current L4 bundle has no closed production contract**

Run: `python -m pytest backend/tests/test_character_execution_contract.py -v`

Expected: FAIL because `CharacterExecutionContract` does not exist.

- [ ] **Step 3: Implement the contract and executor output**

Build it from existing L4 execution semantics and skill realization metadata;
copy only presentation-safe local hints. Require the current canonical turn,
stable idempotency key, and expected revision metadata before dispatch. Do not
make a clip ref, role-state hint, or primitive tag a settlement result.

- [ ] **Step 4: Restrict legacy command use to translation**

New runtime paths dispatch the contract. Legacy `CharacterGoalCommand` can be
accepted only by a translator that records its source and returns the same
contract shape. Add a duplicate guard keyed by `turn_id` so dual observation
cannot send two requests.

- [ ] **Step 5: Run L4/runtime regressions**

Run: `python -m pytest backend/tests/test_character_execution_contract.py backend/tests/test_character_agent_l4_execution.py backend/tests/test_character_agent_goal_command_runtime.py -v`

Expected: PASS. New calls use the contract, while existing compatibility tests
continue to observe translated command delivery.

- [ ] **Step 6: Commit execution-contract convergence**

```bash
git add backend/app/character_agent/models/character_execution.py backend/app/character_agent/execution/l4_executor.py backend/app/character_agent/execution/l4_adapter.py backend/app/character_agent/runtime/runtime_loop.py backend/app/models/character_agent_runtime.py backend/tests/test_character_execution_contract.py backend/tests/test_character_agent_l4_execution.py
git commit -m "feat: converge character L4 on execution contracts"
```

### Task 8: Add advisory candidate normalization and the actor-owned episode record

**Files:**
- Create: `backend/app/character_agent/models/embodied_episode.py`
- Create: `backend/app/character_agent/services/embodied_episode_service.py`
- Modify: `backend/app/world_runtime/vla_percept_bridge.py`
- Modify: `backend/app/character_agent/reasoning/actor_scene_knowledge.py`
- Modify: `backend/app/character_agent/runtime/runtime_loop.py`
- Test: `backend/tests/test_embodied_episode_service.py`
- Test: `backend/tests/test_vla_percept_bridge.py`
- Test: `backend/tests/test_vla_runtime_consumption.py`

**Interfaces:**
- `CandidateActionObservation` accepts only a reviewed target/action candidate,
  preconditions, expected observation, confidence, uncertainty, and evidence
  references.
- `EmbodiedEpisodeService.begin(turn, candidate, pre_capture_ref) -> EmbodiedEpisodeRecord` and `complete(episode, authority_result, post_capture_ref, observed_state) -> EmbodiedEpisodeRecord`.
- `EpisodeFailureClass` is closed: `perception`, `localization`, `precondition`, `unreachable`, `contact`, `wrong_target`, `stale_scene`, `timeout`, `authority_rejected`, `observation_mismatch`, `strategy`.
- `VLAProviderResult` remains unchanged as an advisory contract; its bridge may
  derive a candidate but cannot add control/world-write fields.

- [ ] **Step 1: Write provider-boundary and episode-linkage tests**

```python
def test_vla_candidate_becomes_intent_candidate_not_motor_command() -> None:
    candidate = adapter.to_candidate_action(mock_vla_door_result())
    assert candidate.semantic_action_id == "open_close"
    assert candidate.target_ref == "obj_archive_door"
    assert "velocity" not in candidate.model_dump()
    assert "global_position" not in candidate.model_dump()


def test_episode_requires_authority_and_post_capture_for_success() -> None:
    episode = service.begin(running_turn(), door_candidate(), pre_capture_ref="capture:1")
    result = service.complete(episode, authority_result=accepted_door_result(), post_capture_ref="capture:2", observed_state="open")
    assert result.outcome == "confirmed_success"
    assert result.authority_result_ref

    mismatch = service.complete(episode, authority_result=accepted_door_result(), post_capture_ref="capture:2", observed_state="closed")
    assert mismatch.failure_class == "observation_mismatch"
```

- [ ] **Step 2: Run tests to verify there is no joined candidate/action/observation record**

Run: `python -m pytest backend/tests/test_embodied_episode_service.py -v`

Expected: FAIL because the candidate and episode models do not exist.

- [ ] **Step 3: Implement a strict VLA-to-candidate adapter**

Validate target/action references against the reviewed `SceneAffordanceRegistry`
and the VLA request grounding catalog. Map findings only into attention,
uncertainty, candidate interpretation, or `reobserve_required`; reject unknown
targets, unreviewed affordances, provider control fields, and candidates whose
capture/PQF provenance is stale or scope-mismatched.

- [ ] **Step 4: Implement the episode state machine and input conflict record**

Persist an actor-private episode reference on the canonical turn. Use the
fixed fact precedence `committed authority > structured percept > provider
advisory > model inference`. On conflict append `percept_conflict`, retain
both refs, raise uncertainty, and require a fresh observation; never rewrite
the authority fact or promote a provider claim to memory.

- [ ] **Step 5: Connect episode outcome to evaluation and policy, not settlement**

The runtime maps a typed episode failure to a recovery candidate and next
observation request. `EmbodiedEpisodeService` may not call an ESM/Gameplay
writer or invoke Godot. It only consumes existing authority/local/capture
evidence and returns a record for the turn/evaluator.

- [ ] **Step 6: Run VLA boundary and episode tests**

Run: `python -m pytest backend/tests/test_embodied_episode_service.py backend/tests/test_vla_percept_bridge.py backend/tests/test_vla_runtime_consumption.py backend/tests/test_character_behavior_evaluation.py -v`

Expected: PASS, including VLA advisory-only validation, stale capture rejection,
success, observation mismatch, and recovery-candidate evidence.

- [ ] **Step 7: Commit advisory episode work**

```bash
git add backend/app/character_agent/models/embodied_episode.py backend/app/character_agent/services/embodied_episode_service.py backend/app/world_runtime/vla_percept_bridge.py backend/app/character_agent/reasoning/actor_scene_knowledge.py backend/app/character_agent/runtime/runtime_loop.py backend/tests/test_embodied_episode_service.py backend/tests/test_vla_percept_bridge.py backend/tests/test_vla_runtime_consumption.py
git commit -m "feat: add advisory character embodied episodes"
```

### Task 9: Prove one archive-door episode across backend and Godot

**Files:**
- Modify: `backend/app/services/default_scene_archive_door_embodied_service.py`
- Modify: `backend/app/services/embodied_execution_ingress.py`
- Modify: `scripts/interaction/ArchiveDoorEmbodiedActionHost.gd`
- Modify: `scripts/verification/ObjArchiveDoorPhysicalEmbodimentProbe.gd`
- Create: `scripts/verification/verify_character_turn_embodied_episode.py`
- Create: `.harness/profiles/character-turn-embodied-episode.json`
- Test: `backend/tests/test_character_turn_embodied_episode.py`
- Test: `scripts/verification/tests/test_verify_character_turn_embodied_episode.py`

**Interfaces:**
- Existing archive-door request/settlement paths receive `turn_id`, execution
  contract refs, and episode refs as correlation metadata only.
- The probe records pre/post capture refs, local terminal state, authority
  result ref, expected/observed door state, and recovery evidence.
- Harness result requires `overall_passed`, a backend settlement trace, a
  replay trace, and Godot runtime artifact/screenshots for success and one
  typed failure.

- [ ] **Step 1: Write backend test for the canonical door episode**

```python
def test_archive_door_turn_has_one_contract_receipt_and_confirmed_episode(client) -> None:
    response = submit_turn_scoped_door_execution(client, turn_id="turn:char_b:door-1")
    payload = response.json()
    assert payload["authority_result"]["outcome"] == "committed"
    assert payload["episode"]["outcome"] == "confirmed_success"
    assert payload["episode"]["turn_id"] == "turn:char_b:door-1"
    assert payload["episode"]["post_capture_ref"]
```

- [ ] **Step 2: Run it to confirm the current narrow vertical lacks turn/episode evidence**

Run: `python -m pytest backend/tests/test_character_turn_embodied_episode.py -v`

Expected: FAIL because the route/probe does not yet emit the new records.

- [ ] **Step 3: Thread correlation metadata through the existing route only**

Validate `turn_id` and execution contract identity at ingress. Add them to
existing request/settlement trace payloads without making the default-scene
service a new actor or authority owner. Preserve old Phase 0 client requests
through a documented compatibility adapter that creates no invented turn.

- [ ] **Step 4: Extend the Godot probe after authority result delivery**

Capture before the request and after the committed/rejected response. The
probe may render/record local state, but it declares success only when the
expected state, committed authority response, and post-action observation
agree. For the failure scenario, assert zero authority mutation or a typed
recovery result as appropriate.

- [ ] **Step 5: Implement the dedicated Harness verifier**

The verifier must start the real backend, run success plus one distance/stale
or observation-mismatch case, collect backend/replay/Godot artifacts, and
write an `overall_passed` report. It must fail if any case uses a mock
authority result or lacks a visible runtime artifact.

- [ ] **Step 6: Run focused backend, Godot, and Harness verification**

Run: `python -m pytest backend/tests/test_character_turn_embodied_episode.py backend/tests/test_obj_archive_door_embodied_authority.py scripts/verification/tests/test_verify_character_turn_embodied_episode.py -v`

Run: `python scripts/verification/harness.py --profile character-turn-embodied-episode`

Expected: PASS with an authority settlement trace, replay trace, and Godot
runtime capture for success and failure. If the configured backend or Godot
runtime cannot start, record this task as runtime-unverified rather than
complete.

- [ ] **Step 7: Commit the vertical proof**

```bash
git add backend/app/services/default_scene_archive_door_embodied_service.py backend/app/services/embodied_execution_ingress.py scripts/interaction/ArchiveDoorEmbodiedActionHost.gd scripts/verification/ObjArchiveDoorPhysicalEmbodimentProbe.gd scripts/verification/verify_character_turn_embodied_episode.py .harness/profiles/character-turn-embodied-episode.json backend/tests/test_character_turn_embodied_episode.py scripts/verification/tests/test_verify_character_turn_embodied_episode.py
git commit -m "test: prove character turn archive door episode"
```

### Task 10: Close documentation and release the action-foundation dependency gate

**Files:**
- Modify: `docs/character/character-agent-runtime-architecture.md`
- Modify: `docs/character/character-mind-core-status.md`
- Modify: `docs/character/character-action-foundation-current-state.md`
- Modify: `docs/superpowers/plans/2026-09-14-unified-character-action-foundation-and-inf-tag-contract-implementation-plan.md`
- Modify: `scripts/verification/harness.py` only if profile registration requires it
- Test: `backend/tests/test_character_turn_documentation_contract.py`

**Interfaces:**
- Documentation distinguishes completed/current/legacy behavior-turn records
  from the new canonical live turn context.
- The action-foundation plan declares this plan as a prerequisite and maps
  `CharacterExecutionContract`, turn metadata, recovery, and episode evidence
  to its Tasks 9, 10, 13, and 14.
- No document claims VLA controls a body or that an episode is authority truth.

- [ ] **Step 1: Add a documentation consistency test**

```python
def test_action_plan_requires_turn_closure_before_semantic_action_work() -> None:
    plan = ROOT.joinpath("docs/superpowers/plans/2026-09-14-unified-character-action-foundation-and-inf-tag-contract-implementation-plan.md").read_text(encoding="utf-8")
    assert "2026-09-23-character-turn-continuity-and-embodied-episode-implementation-plan.md" in plan
    assert "VLA direct Motor control" not in plan
    assert "CharacterExecutionContract" in plan
```

- [ ] **Step 2: Run it to verify legacy sequencing/documentation is incomplete**

Run: `python -m pytest backend/tests/test_character_turn_documentation_contract.py -v`

Expected: FAIL before the documentation changes are applied.

- [ ] **Step 3: Update the truth documents and action-plan sequencing**

Record the actual migration status, exact verifier commands and artifact
locations, explicit legacy adapter status, and remaining external-asset work.
Do not replace the action plan with this one: update its dependency order and
Task 9/10/13/14 consumer notes only.

- [ ] **Step 4: Run full backend and aggregate verification**

Run: `python -m pytest -v`

Run: `python scripts/verification/harness.py --profile all`

Run: `git diff --check`

Expected: all checks pass. If an external provider credential is absent, retain
the existing non-live VLA evidence and report provider status separately; it
does not invalidate mock/authority/Godot episode evidence.

- [ ] **Step 5: Commit release-gate documentation**

```bash
git add docs/character/character-agent-runtime-architecture.md docs/character/character-mind-core-status.md docs/character/character-action-foundation-current-state.md docs/superpowers/plans/2026-09-14-unified-character-action-foundation-and-inf-tag-contract-implementation-plan.md backend/tests/test_character_turn_documentation_contract.py
git commit -m "docs: gate action foundation on character turn closure"
```

### Task 11: Close Godot interaction-session projection delivery with cursor flow control

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/tests/test_embodied_interaction_session.py`
- Modify: `scripts/verification/EmbodiedInteractionSessionProbe.gd`
- Modify: `scripts/verification/verify_embodied_interaction_session.py`
- Modify: `scripts/verification/tests/test_verify_embodied_interaction_session.py`

**Interfaces:**
- `embodied_interaction_session_probe` returns only its admission acknowledgement.
- `embodied_interaction_session_projection_pull` accepts `session_id: str` and
  `after_global_sequence: int >= 0`, then returns exactly one safe
  `embodied_interaction_session_event` or one
  `embodied_interaction_session_projection_exhausted` envelope.
- The Godot probe sends the next pull only after `InteractionSessionSlotConsumer`
  accepted the preceding event; it never posts an authority acknowledgement or
  world-state write.

- [ ] **Step 1: Add the backend pull/replay regression test**

```python
def test_websocket_session_projection_pull_replays_one_safe_event_after_the_last_cursor() -> None:
    reset_runtime_state()
    with TestClient(app).websocket_connect("/ws") as websocket:
        websocket.send_json(handshake_probe_payload("session:handshake:pull"))
        assert websocket.receive_json()["message_type"] == "ack"
        received = []
        for sequence in range(4):
            websocket.send_json({
                "message_type": "embodied_interaction_session_projection_pull",
                "payload": {"session_id": "session:handshake:pull", "after_global_sequence": sequence},
            })
            received.append(websocket.receive_json())
    assert [row["payload"]["event_type"] for row in received] == [
        "embodied.interaction_session.proposed",
        "embodied.interaction_session.accepted",
        "embodied.interaction_session.authorized",
        "embodied.interaction_session.realizing",
    ]
```

- [ ] **Step 2: Run the new test and observe the missing-route failure**

Run: `python -m pytest backend/tests/test_embodied_interaction_session.py -k projection_pull -v`

Expected: FAIL because the route does not yet recognize the projection pull.

- [ ] **Step 3: Implement one-event public stream projection**

Read the existing Gameplay stream for `session:{session_id}`. Reject absent
or invalid cursors with the existing structured error-ack convention. Reuse
`_embodied_session_event_envelope_from_authority_event`'s allowlist semantics
for the committed stream event payload. Return exactly the first event whose
`global_sequence` is greater than the cursor, or the typed exhaustion
envelope. Do not hold a second stream, duplicate the event store, or mutate a
session from this route.

- [ ] **Step 4: Run the backend regression test and focused session suite**

Run: `python -m pytest backend/tests/test_embodied_interaction_session.py backend/tests/test_embodied_interaction_session_godot_static.py -v`

Expected: PASS, including replay of an already-used cursor, exhausted stream,
privacy filtering, and the existing authority lifecycle tests.

- [ ] **Step 5: Make the live Godot probe consume one projection per pull**

```gdscript
var cursor := 0
while _backend_session_events.size() < 4 and Time.get_ticks_msec() < receive_deadline:
    bridge.send_envelope({
        "message_type": "embodied_interaction_session_projection_pull",
        "payload": {"session_id": SESSION_ID, "after_global_sequence": cursor},
    })
    await get_tree().process_frame
    if live_consumer.last_global_sequence > cursor:
        cursor = live_consumer.last_global_sequence
```

Only advance `cursor` after `consume_authority_event` accepts the event.
Record the received public event types and final cursor in the report.

- [ ] **Step 6: Run the live verifier and its static contract test**

Run: `python -m pytest scripts/verification/tests/test_verify_embodied_interaction_session.py -v`

Run: `python scripts/verification/verify_embodied_interaction_session.py --godot-exe 'D:\godot\Godot_v4.6.3-stable_win64.exe' --python-exe 'C:\Anaconda3\python.exe'`

Expected: PASS. The report must show four accepted public lifecycle events,
strictly increasing sequence, no private terms, and a realizing local slot
consumer state.

- [ ] **Step 7: Run the owning Harness profile and aggregate gate**

Run: `python scripts/verification/harness.py --profile harness-embodied-task --godot-exe 'D:\godot\Godot_v4.6.3-stable_win64.exe' --python-exe 'C:\Anaconda3\python.exe'`

Run: `python scripts/verification/harness.py --profile all --godot-exe 'D:\godot\Godot_v4.6.3-stable_win64.exe' --python-exe 'C:\Anaconda3\python.exe'`

Expected: PASS with new `.harness/verification/` evidence. If an unrelated
profile fails, preserve this task's passed report and record the unrelated
failure by profile name.

### Task 12: Migrate the stale policy-calibration verifier to the canonical candidate contract

**Files:**
- Modify: `scripts/verification/verify_character_policy_calibration.py`
- Modify: `.harness/profiles/character-policy-calibration.json`
- Create: `scripts/verification/tests/test_verify_character_policy_calibration.py`

**Interfaces:**
- The verifier accepts `candidate.status == "candidate"` and
  `candidate.policy_type == "recovery"` when evidence marks the candidate
  `qualified == true`.
- The verifier continues to prove candidate-only behavior: it must not claim
  automatic profile mutation or active-policy installation.

- [x] **Step 1: Add a regression test for the canonical candidate report**

```python
def test_character_policy_calibration_profile_accepts_canonical_candidate_policy() -> None:
    assert verifier.main() == 0
```

- [x] **Step 2: Run it against the stale verifier and observe the failure**

Observed: the old verifier returned `1` because it expected the removed
`candidate_only/context_recall_policy` vocabulary.

- [x] **Step 3: Update only the verifier vocabulary and profile description**

The implementation still evaluates the same rejected authority outcome; only
the acceptance predicate now matches the canonical behavior-evaluation
contract and requires `evidence.qualified`.

- [x] **Step 4: Run the focused test and profile**

Run: `python -m pytest scripts/verification/tests/test_verify_character_policy_calibration.py -v`

Run: `python scripts/verification/verify_character_policy_calibration.py`

Observed: both pass and report `overall_character_policy_calibration_passed=True`.

## Completion Checklist

- [x] A canonical turn is created before L1 and persists through its durable checkpoint.
- [x] Every L1/L2/L3/L4, settlement, evaluation, and policy stage plus every checkpoint/receipt record has the same `turn_id`.
- [x] Restart reconciliation does not resend an uncertain authority request.
- [x] Durable policy lifecycle, consumption, expiry, supersession, and failure-window behavior alter later L3 selection only under evidence gates.
- [x] Evaluation dimensions preserve `unknown` instead of false certainty.
- [x] Recall is bounded, actor-private, branch/time-aware, conflict-aware, and traceable.
- [x] L4 uses `CharacterExecutionContract`; legacy commands are translation-only.
- [x] VLA remains advisory and only yields normal actor intent candidates.
- [ ] One archive-door episode has a current real authority result, post-action observation, typed failure/recovery case, replay trace, and Godot runtime evidence.
- [x] The unified action-foundation plan consumes these contracts before its remaining work begins.

Current release note (2026-09-24): the focused turn, recall, and legacy-route
regressions pass, but the fresh aggregate suite and the fresh archive-door
episode profile are red. Do not treat this checklist as an overall acceptance
claim until the profile success scenario and repository-wide regressions are
closed with fresh evidence.
