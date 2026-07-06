# PlotPilot-style Siming Narrative Core Design

## 1. Goal

This design integrates the narrative-core engineering ideas borrowed from
`shenminglinyi/PlotPilot` into the existing Siming Phase 1 runtime without
embedding PlotPilot as an external service or importing its full novel-writing
workflow.

The goal is to make the current Siming runtime move beyond shape-only objects
and event-specific branches by adding a real stateful narrative core, a real
quality-monitor layer, and minimal read-facade fields that existing runtime and
pipeline tests can verify.

## 2. Scope

In scope for the first implementation phase:

- `NarrativeCore`: stateful narrative state, obligations, pressure, and short
  event-chain candidates.
- `QualityMonitor`: real quality signals that feed `FairnessStateSnapshot`.
- `SimingRuntime` wiring: keep `SimingRuntime.tick()` as the public entrypoint,
  but make it orchestrate the new narrative and quality layers.
- Minimal `ReadFacade` fields: expose obligation and candidate summaries in the
  existing `NarrativeReadModel`.
- Tests for the new units and the runtime/pipeline integration.

Out of scope for the first implementation phase:

- Direct dependency on PlotPilot code.
- Running PlotPilot as an external process or HTTP service.
- HTTP read-model/checkpoint query endpoints.
- Persistent checkpoint/recover.
- Long-horizon event-chain search.
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
-> Policy / Feasibility
-> SimingOutput
-> Audit / ReadModel
```

The entrypoint stays conservative so the existing websocket, authority event
bus, character dispatch adapter, and tests keep their current integration
surface. The internal structure becomes explicit enough for later
checkpoint/recover and read-facade expansion.

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
- Generate short event-chain candidates for the orchestrator to evaluate later.

It must not:

- Read Godot nodes or websocket payloads directly.
- Decide final dispatch paths.
- Write world truth.
- Bypass ESM, role autonomy, policy, or feasibility checks.

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

It must not:

- Generate `dispatch_intent`.
- Select the final intervention path.
- Mutate narrative state directly.

### 4.3 SimingRuntime as Orchestrator

Suggested file:

- existing `backend/app/services/siming_runtime.py`

Responsibilities:

- Keep the public `tick(inputs: list[SimingInput]) -> SimingTickResult` contract.
- Coordinate observe, fact core, narrative core, quality monitor, policy,
  feasibility, dispatch, audit, and read-model building.
- Preserve existing Phase 1 smoke behavior such as the light-drop dispatch path.
- Stop carrying long-term business logic as event-specific inline branches.

This first phase does not create a separate `SimingOrchestrator` class. The
runtime can later be split once the new narrative and quality units are stable.

### 4.4 ReadFacade

Suggested file:

- existing `backend/app/services/siming_read_model.py`

Responsibilities:

- Add minimal externally-readable narrative fields to `NarrativeReadModel`.
- Include obligation summaries, candidate summaries, quality status, and the
  active narrative phase.
- Preserve the rule that read models are not world truth and are not published
  as authority event bus facts.

This phase does not add HTTP endpoints. Existing pipeline storage through
`SimingAuditWriter.record_read_model()` remains the integration point.

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
class EventChainCandidate:
    candidate_id: str
    chain_type: str
    basis_snapshot_ref: str
    basis_obligation_refs: list[str]
    target_refs: list[str]
    suggested_band: str
    risk_tags: list[str]
    priority_score: float
    explanation: str
```

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

Read-facade failure:

- Do not block dispatch.
- Record `read_model_failed`.
- Continue emitting minimal observatory/debug events where available.

Fact-core veto:

- Continue to block narrative-core state updates for locked-fact conflicts.
- Preserve the existing behavior where no checkpoint/read model is finalized for
  vetoed facts unless the implementation explicitly adds a separate rejected
  read surface later.

## 7. Testing Plan

Unit tests for `NarrativeCore`:

- Visual fact input produces an `unresolved_reveal` obligation.
- Constraint rejection input produces a `constraint_recovery` obligation.
- Repeated unresolved obligations increase `pressure_level`.
- Candidate generation uses obligation refs and does not assert world truth.

Unit tests for `QualityMonitor`:

- Visibility imbalance produces an `information_distribution` quality signal.
- Participation gap produces a `participation_distribution` quality signal.
- A failed auditor produces a partial snapshot instead of interrupting the tick.
- Existing `SimingFeatureRegistry` dimensions still map to policy rejection
  reasons.

Integration tests for `SimingRuntime.tick()`:

- Tick invokes narrative core and places candidate summaries in the read model.
- The existing light-drop path still emits `intervention_candidate`,
  `intervention_decision`, and `dispatch_intent`.
- Locked fact conflict still vetoes before narrative-core state update.
- No eligible intervention still produces audit/read model data when fact core
  accepted the event.

Pipeline tests for `SimingEventPipeline`:

- Pipeline records checkpoint and read model after a runtime tick.
- Read model includes obligation and candidate summaries.
- Internal checkpoint/read-model objects are not published onto the authority
  event bus as public events.

## 8. Migration Plan

1. Add narrative and quality model classes.
2. Add `SimingNarrativeCore` with in-memory per-room state.
3. Add `SimingQualityMonitor` or strengthen `SimingFairnessAuditEngine` behind
   the same public call path.
4. Extend `SimingReadModelBuilder` with obligation/candidate/quality fields.
5. Wire `SimingRuntime.tick()` to call narrative core and quality monitor after
   fact-core acceptance.
6. Keep the existing dispatch behavior passing while replacing placeholder
   fairness/projection values with real computed data.
7. Add focused unit and integration tests.

## 9. Open Decisions

No open product decisions remain for the first implementation phase. The chosen
direction is:

- Borrow PlotPilot-style narrative-core engineering ideas.
- Do not depend on PlotPilot code.
- Implement a stateful narrative core inside the current Siming runtime.
- Keep external service, persistence, recover, and HTTP read facade out of this
  phase.
