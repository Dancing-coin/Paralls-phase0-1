# PlotPilot-style Siming Narrative Core Design

## 1. Goal

This design integrates the narrative-core engineering ideas borrowed from
`shenminglinyi/PlotPilot` into the existing Siming Phase 1 runtime without
embedding PlotPilot as an external service or importing its full novel-writing
workflow.

The goal is to make the current Siming runtime move beyond shape-only objects
and event-specific branches by adding a real stateful narrative core, a real
quality-monitor layer, explicit intervention guardrails, in-memory checkpoints,
and a queryable read facade that existing runtime and pipeline tests can verify.

## 2. Scope

In scope for the first implementation phase:

- `NarrativeCore`: stateful narrative state, obligations, pressure, and short
  intervention seeds.
- `QualityMonitor`: real quality signals that feed `FairnessStateSnapshot`.
- `InterventionGuardrails`: an explicit guardrail boundary implemented through
  existing policy and feasibility services in this phase.
- `SimingRuntime` wiring: keep `SimingRuntime.tick()` as the public entrypoint,
  but make it operate as the synchronous orchestrator step for the new narrative,
  quality, guardrail, checkpoint, and read-facade layers.
- `ReadFacade`: expose a queryable, read-only facade for the latest
  `NarrativeReadModel`.
- Multi-stage in-memory checkpoints for pre-decision, post-decision, and
  post-dispatch audit points.
- Tests for the new units and the runtime/pipeline integration.

Out of scope for the first implementation phase:

- Direct dependency on PlotPilot code.
- Running PlotPilot as an external process or HTTP service.
- Full workbench UI.
- Durable checkpoint persistence and recover.
- Full `EventChainCandidate` or long-horizon event-chain search.
- Background daemon thread, task queue, or async lifecycle management.
- LLM mutation of narrative state.
- Novel chapter generation, writing UI, beat-sheet expansion, prompt packages,
  or text-quality scoring.

## 3. Architecture

The existing runtime entry remains:

```text
SimingEventPipeline -> SimingRuntime.tick()
```

Inside `SimingRuntime.tick()`, the target flow becomes:

```text
AuthorityEvent
-> SimingObservePipeline
-> SimingFactCore
-> NarrativeCore
-> QualityMonitor
-> InterventionGuardrails
-> SimingOutput
-> Checkpoint / Audit / ReadFacade
```

The entrypoint stays conservative so the existing websocket, authority event
bus, character dispatch adapter, and tests keep their current integration
surface. The internal structure becomes explicit enough for later
durable checkpoint/recover, daemon scheduling, and workbench expansion.

## 4. Components

### 4.1 NarrativeCore

Suggested files:

- `backend/app/models/siming_narrative.py`
- `backend/app/services/siming_narrative_core.py`

Responsibilities:

- Consume observed, fact-validated Siming events.
- Maintain per-room narrative state.
- Generate narrative obligations.
- Track dramatic pressure.
- Generate thin intervention seeds for the orchestrator to evaluate later.

It must not:

- Read Godot nodes or websocket payloads directly.
- Decide final dispatch paths.
- Write world truth.
- Bypass ESM, role autonomy, policy, or feasibility checks.
- Call LLM providers.

LLM providers may still exist as optional candidate sources elsewhere in the
runtime, but their output cannot directly mutate `NarrativeStateSnapshot`.
LLM-derived intervention seeds must carry source/audit metadata and pass
intervention guardrails.

Minimal supported signal types:

- `unresolved_reveal`: an established fact exists but key actors have not been
  made aware of it.
- `participation_gap`: a key actor has not meaningfully participated in the
  current situation.
- `constraint_recovery`: ESM or role execution rejected a path and the runtime
  should remember the failed attempt for later compensation.

### 4.2 QualityMonitor

Suggested files:

- `backend/app/services/siming_quality_monitor.py`
- existing `backend/app/services/siming_fairness_audit.py` is strengthened or
  delegated to this service.

Responsibilities:

- Convert narrative state, obligations, observed facts, and actor participation
  hints into quality signals.
- Produce non-placeholder `FairnessStateSnapshot` data.
- Preserve the five Phase 1 fairness dimensions:
  `information_distribution`, `participation_distribution`,
  `conversation_access_fairness`, `suspicion_heat_distribution`, and
  `evidence_visibility_distribution`.
- Mark individual failed auditors as unavailable while allowing the rest of the
  quality monitor to complete.
- Never return fixed placeholder scores for required dimensions.

The first phase must run all five auditors with real, deterministic logic:

- `information_distribution`: whether established facts are only visible to part
  of the relevant cast.
- `participation_distribution`: whether key actors have not been touched within
  the recent runtime window.
- `conversation_access_fairness`: whether a candidate conversation path excludes
  relevant actors.
- `suspicion_heat_distribution`: whether suspicion heat data is present and
  usable; missing data returns `partial` or `unavailable`, not a fake score.
- `evidence_visibility_distribution`: whether evidence or visual facts have
  entered an observable route.

It must not:

- Generate `dispatch_intent`.
- Select the final intervention path.
- Mutate narrative state directly.

### 4.3 InterventionGuardrails

Suggested files:

- existing `backend/app/services/siming_policy.py`
- existing `backend/app/services/siming_feasibility.py`
- optional wrapper `backend/app/services/siming_intervention_guardrails.py`

Responsibilities:

- Provide the explicit PlotPilot-style guardrail boundary.
- Reuse `SimingInterventionPolicy` and `SimingExecutionFeasibility` in the first
  implementation phase.
- Reject candidates or seeds that violate fact locks, role autonomy, ESM routing,
  execution feasibility, or Phase 1 scope.

Minimum rejection cases:

- `locked_truth_rewrite`
- `skip_role_autonomy`
- `skip_esm`
- `phase2_projection_required`
- unknown fact reference
- actor not eligible
- execution path unavailable

It must not:

- Produce quality signals.
- Mutate narrative state.
- Bypass audit recording.

### 4.4 SimingRuntime as Orchestrator

Suggested file:

- existing `backend/app/services/siming_runtime.py`

Responsibilities:

- Keep the public `tick(inputs: list[SimingInput]) -> SimingTickResult` contract.
- Coordinate observe, fact core, narrative core, quality monitor, policy,
  feasibility, checkpoint, dispatch, audit, and read-facade building.
- Preserve existing Phase 1 smoke behavior such as the light-drop dispatch path.
- Stop carrying long-term business logic as event-specific inline branches.

This first phase does not create a separate `SimingOrchestrator` class. The
runtime can later be split once the new narrative, quality, guardrail, checkpoint,
and read-facade units are stable.

This first phase also does not create a background daemon. It implements the
synchronous orchestrator step. A future daemon may only schedule this same step;
it must not introduce a second decision path.

### 4.5 CheckpointAuditService

Suggested files:

- existing `backend/app/services/siming_audit_writer.py`
- existing `backend/app/services/siming_read_model.py`

Responsibilities:

- Record in-memory checkpoints for the main orchestrator step.
- Preserve audit and read-model links for replay/debug inspection.
- Avoid durable persistence and recover in this phase.

Minimum checkpoint types:

- `pre_decision`: fact, narrative, and quality state exist before policy,
  feasibility, and dispatch.
- `post_decision`: candidate/seed, decision, and guardrail result exist.
- `post_dispatch`: dispatch intent was generated or no-action was finalized.

### 4.6 ReadFacade

Suggested file:

- existing `backend/app/services/siming_read_model.py`
- optional route wiring in `backend/app/main.py`

Responsibilities:

- Add externally-readable narrative fields to `NarrativeReadModel`.
- Include obligation summaries, candidate summaries, quality status, and the
  active narrative phase.
- Preserve the rule that read models are not world truth and are not published
  as authority event bus facts.
- Provide a queryable read-only facade for the latest read model by room.

The first implementation may expose the facade as a service method or a thin
debug HTTP endpoint such as `GET /debug/siming/read-model/{room_id}`. Full
workbench UI remains out of scope.

## 5. Data Contracts

The first phase introduces these model shapes in
`backend/app/models/siming_narrative.py`.

```python
class NarrativeStateSnapshot:
    snapshot_id: str
    schema_version: int
    producer_system: str
    room_id: str
    scene_id: str
    zone_id: str
    world_ts: int
    sim_tick_ts: int
    active_phase: str
    pressure_level: str
    open_threads: list[NarrativeThread]
    active_markers: list[NarrativeMarker]
    causation_id: str
    correlation_id: str
```

```python
class NarrativeObligation:
    obligation_id: str
    obligation_type: str
    source_event_id: str
    target_refs: list[str]
    pressure: str
    status: str
    reason: str
```

```python
class NarrativeObligationLedger:
    ledger_id: str
    schema_version: int
    producer_system: str
    room_id: str
    world_ts: int
    sim_tick_ts: int
    obligations: list[NarrativeObligation]
    causation_id: str
    correlation_id: str
```

```python
class InterventionSeed:
    seed_id: str
    seed_type: str
    basis_snapshot_ref: str
    basis_obligation_refs: list[str]
    target_refs: list[str]
    suggested_band: str
    risk_tags: list[str]
    explanation: str
```

`InterventionSeed` is intentionally thinner than `EventChainCandidate`. It does
not perform story-chain search, long-horizon projection, dramatic-priority
optimization, or world-truth mutation. Full `EventChainCandidate` remains a
Phase 2+ projection object.

```python
class QualitySignal:
    signal_id: str
    dimension: str
    severity: str
    target_refs: list[str]
    evidence_refs: list[str]
    suggested_action_band: str
    reason: str
```

If the current `siming_runtime_state.py` already contains overlapping shapes,
implementation should either adapt those names or move only the new narrative
specific objects into `siming_narrative.py`. The final code should avoid two
different model classes for the same concept.

## 6. Error Handling

Narrative-core failure:

- Return no candidates for that event.
- Record `SimingAuditRecord(status="narrative_core_skipped")`.
- Continue the runtime tick if fact core and policy paths can still produce
  safe no-action output.

Quality-monitor failure:

- Mark the failed dimension as `status="unavailable"`.
- Continue running remaining dimensions.
- Add `quality_monitor_partial` to risk or reason metadata.
- Still produce a `FairnessStateSnapshot`.

Candidate rejection:

- Do not generate dispatch.
- Keep candidate, decision, and audit information available to the read model.
- If rejection comes from guardrails, preserve the guardrail reason in audit and
  read facade output.

Read-facade failure:

- Do not block dispatch.
- Record `read_model_failed`.
- Continue emitting minimal observatory/debug events where available.

Checkpoint failure:

- Do not block safe no-action output.
- Record `checkpoint_failed`.
- Do not claim replay coverage for that tick.

Fact-core veto:

- Continue to block narrative-core state updates for locked-fact conflicts.
- Preserve the existing behavior where no checkpoint/read model is finalized for
  vetoed facts unless the implementation explicitly adds a separate rejected
  read surface later.

LLM failure:

- Never blocks deterministic narrative-core updates.
- Produces only candidate-provider audit such as `llm_timeout` or
  `llm_invalid_output`.
- Cannot mutate narrative state.

## 7. Testing Plan

Unit tests for `NarrativeCore`:

- Visual fact input produces an `unresolved_reveal` obligation.
- Constraint rejection input produces a `constraint_recovery` obligation.
- Repeated unresolved obligations increase `pressure_level`.
- Intervention seed generation uses obligation refs and does not assert world
  truth.
- LLM provider output cannot mutate narrative state.

Unit tests for `QualityMonitor`:

- Visibility imbalance produces an `information_distribution` quality signal.
- Participation gap produces a `participation_distribution` quality signal.
- Conversation exclusion produces a `conversation_access_fairness` signal.
- Missing suspicion data produces `partial` or `unavailable`, not a fixed score.
- Evidence route gaps produce an `evidence_visibility_distribution` signal.
- A failed auditor produces a partial snapshot instead of interrupting the tick.
- Existing `SimingFeatureRegistry` dimensions still map to policy rejection
  reasons.

Unit tests for `InterventionGuardrails`:

- Locked-truth rewrite is rejected.
- Skipping role autonomy is rejected.
- Skipping ESM for environment requests is rejected.
- Phase 2 projection requirements are rejected in Phase 1.
- Accepted seeds include auditable guardrail reasons.

Integration tests for `SimingRuntime.tick()`:

- Tick invokes narrative core and places intervention seed summaries in the read
  model.
- The existing light-drop path still emits `intervention_candidate`,
  `intervention_decision`, and `dispatch_intent`.
- Locked fact conflict still vetoes before narrative-core state update.
- No eligible intervention still produces audit/read model data when fact core
  accepted the event.
- Tick records `pre_decision`, `post_decision`, and `post_dispatch` checkpoints
  when the corresponding stages are reached.
- Synchronous `tick()` is the only orchestrator decision path.

Pipeline tests for `SimingEventPipeline`:

- Pipeline records checkpoint and read model after a runtime tick.
- Read model includes obligation, intervention seed, quality, guardrail, and
  checkpoint summaries.
- Latest read model is queryable through the chosen read-facade surface.
- Internal checkpoint/read-model objects are not published onto the authority
  event bus as public events.

## 8. Migration Plan

1. Add narrative, quality, intervention seed, guardrail, and checkpoint model
   fields.
2. Add `SimingNarrativeCore` with in-memory per-room state.
3. Add `SimingQualityMonitor` or strengthen `SimingFairnessAuditEngine` behind
   the same public call path, with deterministic logic for all five auditors.
4. Add an explicit `InterventionGuardrails` wrapper or equivalent service
   boundary around existing policy and feasibility services.
5. Extend checkpoint/read-model builders with obligation, intervention seed,
   quality, guardrail, and checkpoint summaries.
6. Add a queryable read-facade surface for the latest room read model.
7. Wire `SimingRuntime.tick()` to call narrative core and quality monitor after
   fact-core acceptance, then guardrails, checkpoints, dispatch, audit, and read
   facade in order.
8. Keep the existing dispatch behavior passing while replacing placeholder
   fairness/projection values with real computed data.
9. Add focused unit and integration tests.

## 9. Open Decisions

No open product decisions remain for the first implementation phase. The chosen
direction is:

- Borrow PlotPilot-style narrative-core engineering ideas.
- Do not depend on PlotPilot code.
- Implement a stateful narrative core inside the current Siming runtime.
- Use thin `InterventionSeed` objects in Phase 1; keep full
  `EventChainCandidate` for Phase 2+.
- Implement a queryable read-only facade without building a full workbench UI.
- Implement multi-stage in-memory checkpoints without durable persistence or
  recover.
- Implement a synchronous orchestrator step without a background daemon.
- Keep LLM providers outside deterministic narrative-state mutation.
