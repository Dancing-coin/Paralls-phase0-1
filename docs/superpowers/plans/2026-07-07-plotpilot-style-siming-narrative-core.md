# PlotPilot-style Siming Narrative Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the approved PlotPilot-style Siming narrative core inside the existing Phase 1 runtime.

**Architecture:** Keep `SimingEventPipeline -> SimingRuntime.tick()` as the entrypoint. Add deterministic narrative state, quality monitoring, intervention guardrails, in-memory checkpoints, and a queryable read facade behind the existing Siming runtime surface.

**Tech Stack:** Python 3, Pydantic models, pytest, FastAPI debug route, existing in-memory Siming services.

## Global Constraints

- Do not import or run PlotPilot code directly.
- Do not add an external PlotPilot service or process.
- Do not build a full workbench UI.
- Do not add durable checkpoint persistence or recover.
- Do not implement full `EventChainCandidate` or long-horizon event-chain search.
- Do not add a background daemon, task queue, or async lifecycle manager.
- Do not let LLM output mutate deterministic narrative state.
- Keep `SimingRuntime.tick(inputs: list[SimingInput]) -> SimingTickResult` as the public runtime entrypoint.
- Internal checkpoint/read-model objects must not be published as public authority event bus facts.
- Fact-core veto must block narrative-core state updates for locked-fact conflicts.

---

## File Structure

- Create `backend/app/models/siming_narrative.py`: deterministic narrative state, obligation, intervention seed, quality signal, and result models.
- Create `backend/app/services/siming_narrative_core.py`: in-memory per-room narrative state and intervention seed generation.
- Create `backend/app/services/siming_quality_monitor.py`: deterministic five-auditor quality monitor producing quality signals and `FairnessStateSnapshot`.
- Create `backend/app/services/siming_intervention_guardrails.py`: explicit guardrail wrapper around current policy and feasibility services.
- Modify `backend/app/models/siming_runtime_state.py`: extend checkpoint type and read-model surfaces.
- Modify `backend/app/services/siming_read_model.py`: include narrative, quality, guardrail, and checkpoint summaries.
- Modify `backend/app/services/siming_audit_writer.py`: expose latest read model lookup by room.
- Modify `backend/app/services/siming_runtime.py`: wire narrative core, quality monitor, guardrails, checkpoints, dispatch, audit, and read facade in order.
- Modify `backend/app/services/siming_event_pipeline.py`: keep storage flow, no bus publication of internal read/checkpoint objects.
- Modify `backend/app/main.py`: add a thin read-only debug route for latest Siming read model.
- Create `backend/tests/test_siming_narrative_core.py`.
- Create `backend/tests/test_siming_quality_monitor.py`.
- Create `backend/tests/test_siming_intervention_guardrails.py`.
- Modify `backend/tests/test_siming_agent_loop_runtime.py`.
- Modify `backend/tests/test_siming_event_pipeline.py`.
- Create `backend/tests/test_siming_read_facade.py`.

---

### Task 1: Narrative Models and Core

**Files:**
- Create: `backend/app/models/siming_narrative.py`
- Create: `backend/app/services/siming_narrative_core.py`
- Test: `backend/tests/test_siming_narrative_core.py`

**Interfaces:**
- Consumes: `ObservedSimingEvent` from `app.models.siming_runtime_state`.
- Produces: `SimingNarrativeCore.update(observed_events: list[ObservedSimingEvent]) -> NarrativeCoreResult`.
- Produces: `NarrativeCoreResult.state`, `NarrativeCoreResult.ledger`, `NarrativeCoreResult.seeds`.

- [ ] **Step 1: Write failing tests for unresolved reveal, constraint recovery, pressure, and LLM isolation**

Create `backend/tests/test_siming_narrative_core.py`:

```python
from app.models.authority_event import AuthorityEvent
from app.models.siming_runtime_state import ObservedSimingEvent
from app.services.siming_narrative_core import SimingNarrativeCore


def make_event(event_type: str, payload: dict[str, object]) -> AuthorityEvent:
    return AuthorityEvent.model_validate(
        {
            "event_id": f"{event_type}:300",
            "event_type": event_type,
            "producer_ts": 300,
            "room_id": "room_demo",
            "scene_id": "scene_demo",
            "zone_id": "zone_focus",
            "source": {"layer": "L1", "system": "visual_fact", "actor_id": "char_c"},
            "routing": {"audience_mode": "room", "routing_mode": "event_type", "target_ids": ["siming"]},
            "priority": "p2",
            "ttl": 5000,
            "durability": "replayable",
            "causation_id": f"{event_type}:300",
            "correlation_id": "corr_demo",
            "payload": payload,
        }
    )


def observed(event: AuthorityEvent) -> ObservedSimingEvent:
    return ObservedSimingEvent.from_authority_event(event)


def test_visual_fact_creates_unresolved_reveal_obligation_and_seed() -> None:
    core = SimingNarrativeCore()
    event = make_event(
        "visual_fact_event",
        {
            "fact_type": "light_level_drop",
            "established_fact_id": "visual_fact:300:light",
            "target_environment_id": "env_lamp",
            "target_actor_id": "char_b",
        },
    )

    result = core.update([observed(event)])

    assert result.state.active_phase == "rising"
    assert result.state.pressure_level == "normal"
    assert [item.obligation_type for item in result.ledger.obligations] == ["unresolved_reveal"]
    assert result.seeds[0].seed_type == "fact_reveal"
    assert result.seeds[0].basis_obligation_refs == [result.ledger.obligations[0].obligation_id]
    assert result.seeds[0].target_refs == ["char_b", "env_lamp"]


def test_constraint_rejection_creates_recovery_obligation() -> None:
    core = SimingNarrativeCore()
    event = make_event(
        "constraint_state_event",
        {
            "constraint_summary": "locked cabinet rejected",
            "target_object_id": "obj_cabinet",
        },
    )

    result = core.update([observed(event)])

    assert [item.obligation_type for item in result.ledger.obligations] == ["constraint_recovery"]
    assert result.seeds[0].suggested_band == "opportunity"
    assert "phase2_projection_required" not in result.seeds[0].risk_tags


def test_repeated_unresolved_obligations_raise_pressure_without_llm() -> None:
    core = SimingNarrativeCore()
    event = make_event(
        "visual_fact_event",
        {
            "fact_type": "light_level_drop",
            "established_fact_id": "visual_fact:300:light",
            "target_actor_id": "char_b",
        },
    )

    first = core.update([observed(event)])
    second = core.update([observed(event)])

    assert first.state.pressure_level == "normal"
    assert second.state.pressure_level == "elevated"
    assert all(seed.source == "narrative_core" for seed in second.seeds)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest backend/tests/test_siming_narrative_core.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.siming_narrative_core'`.

- [ ] **Step 3: Add narrative models**

Create `backend/app/models/siming_narrative.py`:

```python
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


NarrativePhase = Literal["setup", "rising", "pressure", "resolution"]
PressureLevel = Literal["low", "normal", "elevated", "critical"]
ObligationStatus = Literal["open", "closed"]
QualitySeverity = Literal["ok", "low", "medium", "high", "unavailable", "partial"]


class NarrativeMarker(BaseModel):
    model_config = ConfigDict(extra="forbid")

    marker_id: str
    marker_type: str
    source_event_id: str
    target_refs: list[str] = Field(default_factory=list)
    reason: str


class NarrativeThread(BaseModel):
    model_config = ConfigDict(extra="forbid")

    thread_id: str
    thread_type: str
    status: str
    target_refs: list[str] = Field(default_factory=list)


class NarrativeStateSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot_id: str
    schema_version: int = 1
    producer_system: str = "siming.narrative_core"
    room_id: str
    scene_id: str
    zone_id: str
    world_ts: int
    sim_tick_ts: int
    active_phase: NarrativePhase
    pressure_level: PressureLevel
    open_threads: list[NarrativeThread] = Field(default_factory=list)
    active_markers: list[NarrativeMarker] = Field(default_factory=list)
    causation_id: str
    correlation_id: str


class NarrativeObligation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    obligation_id: str
    obligation_type: str
    source_event_id: str
    target_refs: list[str] = Field(default_factory=list)
    pressure: PressureLevel
    status: ObligationStatus = "open"
    reason: str


class NarrativeObligationLedger(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ledger_id: str
    schema_version: int = 1
    producer_system: str = "siming.narrative_core"
    room_id: str
    world_ts: int
    sim_tick_ts: int
    obligations: list[NarrativeObligation] = Field(default_factory=list)
    causation_id: str
    correlation_id: str


class InterventionSeed(BaseModel):
    model_config = ConfigDict(extra="forbid")

    seed_id: str
    seed_type: str
    basis_snapshot_ref: str
    basis_obligation_refs: list[str] = Field(default_factory=list)
    target_refs: list[str] = Field(default_factory=list)
    suggested_band: str
    risk_tags: list[str] = Field(default_factory=list)
    explanation: str
    source: str = "narrative_core"


class QualitySignal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    signal_id: str
    dimension: str
    severity: QualitySeverity
    target_refs: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    suggested_action_band: str
    reason: str


class NarrativeCoreResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: NarrativeStateSnapshot
    ledger: NarrativeObligationLedger
    seeds: list[InterventionSeed] = Field(default_factory=list)
```

- [ ] **Step 4: Add deterministic narrative core**

Create `backend/app/services/siming_narrative_core.py`:

```python
from app.models.siming_narrative import (
    InterventionSeed,
    NarrativeCoreResult,
    NarrativeMarker,
    NarrativeObligation,
    NarrativeObligationLedger,
    NarrativeStateSnapshot,
    NarrativeThread,
    PressureLevel,
)
from app.models.siming_runtime_state import ObservedSimingEvent


class SimingNarrativeCore:
    def __init__(self) -> None:
        self._open_counts_by_room: dict[str, int] = {}

    def update(self, observed_events: list[ObservedSimingEvent]) -> NarrativeCoreResult:
        if not observed_events:
            raise ValueError("observed_events must contain at least one event")

        event = observed_events[-1]
        obligations = self._obligations_for(event)
        open_count = self._open_counts_by_room.get(event.room_id, 0) + len(obligations)
        self._open_counts_by_room[event.room_id] = open_count
        pressure = self._pressure_for(open_count)
        markers = [
            NarrativeMarker(
                marker_id=f"marker:{event.source_event_id}:{item.obligation_type}",
                marker_type=item.obligation_type,
                source_event_id=event.source_event_id,
                target_refs=item.target_refs,
                reason=item.reason,
            )
            for item in obligations
        ]
        state = NarrativeStateSnapshot(
            snapshot_id=f"narrative:{event.room_id}:{event.producer_ts + 1}",
            room_id=event.room_id,
            scene_id=event.scene_id,
            zone_id=event.zone_id,
            world_ts=event.producer_ts,
            sim_tick_ts=event.producer_ts + 1,
            active_phase="rising" if obligations else "setup",
            pressure_level=pressure,
            open_threads=[
                NarrativeThread(
                    thread_id=f"thread:{item.obligation_id}",
                    thread_type=item.obligation_type,
                    status=item.status,
                    target_refs=item.target_refs,
                )
                for item in obligations
            ],
            active_markers=markers,
            causation_id=event.causation_id,
            correlation_id=event.correlation_id,
        )
        ledger = NarrativeObligationLedger(
            ledger_id=f"ledger:{state.snapshot_id}",
            room_id=event.room_id,
            world_ts=event.producer_ts,
            sim_tick_ts=event.producer_ts + 1,
            obligations=obligations,
            causation_id=event.causation_id,
            correlation_id=event.correlation_id,
        )
        return NarrativeCoreResult(
            state=state,
            ledger=ledger,
            seeds=[self._seed_for(state, item) for item in obligations],
        )

    def _obligations_for(self, event: ObservedSimingEvent) -> list[NarrativeObligation]:
        if event.event_type == "visual_fact_event" and event.payload.get("established_fact_id"):
            refs = self._target_refs(event, "target_actor_id", "target_environment_id", "target_object_id")
            return [
                NarrativeObligation(
                    obligation_id=f"obligation:{event.source_event_id}:unresolved_reveal",
                    obligation_type="unresolved_reveal",
                    source_event_id=event.source_event_id,
                    target_refs=refs,
                    pressure="normal",
                    reason="established fact needs a visible runtime surface",
                )
            ]
        if event.event_type == "constraint_state_event":
            refs = self._target_refs(event, "target_actor_id", "target_object_id", "target_environment_id")
            return [
                NarrativeObligation(
                    obligation_id=f"obligation:{event.source_event_id}:constraint_recovery",
                    obligation_type="constraint_recovery",
                    source_event_id=event.source_event_id,
                    target_refs=refs,
                    pressure="normal",
                    reason=str(event.payload.get("constraint_summary", "constraint rejected")),
                )
            ]
        return []

    def _seed_for(self, state: NarrativeStateSnapshot, obligation: NarrativeObligation) -> InterventionSeed:
        suggested_band = "fact_reveal" if obligation.obligation_type == "unresolved_reveal" else "opportunity"
        return InterventionSeed(
            seed_id=f"seed:{obligation.obligation_id}",
            seed_type=obligation.obligation_type,
            basis_snapshot_ref=state.snapshot_id,
            basis_obligation_refs=[obligation.obligation_id],
            target_refs=obligation.target_refs,
            suggested_band=suggested_band,
            explanation=obligation.reason,
        )

    def _pressure_for(self, open_count: int) -> PressureLevel:
        if open_count >= 6:
            return "critical"
        if open_count >= 2:
            return "elevated"
        return "normal"

    def _target_refs(self, event: ObservedSimingEvent, *keys: str) -> list[str]:
        refs: list[str] = []
        for key in keys:
            value = str(event.payload.get(key, "") or "").strip()
            if value and value not in refs:
                refs.append(value)
        return refs
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest backend/tests/test_siming_narrative_core.py -v`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/models/siming_narrative.py backend/app/services/siming_narrative_core.py backend/tests/test_siming_narrative_core.py
git commit -m "Add deterministic Siming narrative core"
```

---

### Task 2: Quality Monitor

**Files:**
- Create: `backend/app/services/siming_quality_monitor.py`
- Modify: `backend/app/services/siming_fairness_audit.py`
- Test: `backend/tests/test_siming_quality_monitor.py`

**Interfaces:**
- Consumes: `StateTreeSnapshot`, `NarrativeCoreResult`.
- Produces: `SimingQualityMonitor.evaluate(state_tree: StateTreeSnapshot, narrative: NarrativeCoreResult) -> QualityMonitorResult`.
- Produces: `QualityMonitorResult.snapshot: FairnessStateSnapshot`.
- Produces: `QualityMonitorResult.signals: list[QualitySignal]`.

- [ ] **Step 1: Write failing quality-monitor tests**

Create `backend/tests/test_siming_quality_monitor.py`:

```python
from app.models.siming_narrative import (
    InterventionSeed,
    NarrativeCoreResult,
    NarrativeObligationLedger,
    NarrativeStateSnapshot,
    QualitySignal,
)
from app.models.siming_runtime_state import (
    GroupSimulationBranchSnapshot,
    StateTreeNode,
    StateTreeSnapshot,
)
from app.services.siming_quality_monitor import SimingQualityMonitor


def make_state_tree() -> StateTreeSnapshot:
    return StateTreeSnapshot(
        snapshot_id="state_tree:room_demo:301",
        schema_version=1,
        producer_system="siming.state_tree",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        world_ts=300,
        sim_tick_ts=301,
        causation_id="visual_fact:300",
        correlation_id="corr_demo",
        environment=StateTreeNode(
            node_id="env_lamp",
            owner_system="esm",
            authority="mirror",
            status="fresh",
            summary={"established_fact_id": "visual_fact:300:light", "visible_actor_ids": ["char_c"]},
        ),
        character=StateTreeNode(
            node_id="char_b",
            owner_system="character_agent",
            authority="mirror",
            status="fresh",
            summary={"target_actor_id": "char_b", "recent_participation_count": 0},
        ),
        storyline=StateTreeNode(
            node_id="storyline:room_demo",
            owner_system="siming",
            authority="editable",
            status="fresh",
            summary={"conversation_candidate_actor_ids": ["char_c"]},
        ),
        group_simulation=GroupSimulationBranchSnapshot(status="unavailable", summary={}),
    )


def make_narrative() -> NarrativeCoreResult:
    state = NarrativeStateSnapshot(
        snapshot_id="narrative:room_demo:301",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        world_ts=300,
        sim_tick_ts=301,
        active_phase="rising",
        pressure_level="normal",
        causation_id="visual_fact:300",
        correlation_id="corr_demo",
    )
    return NarrativeCoreResult(
        state=state,
        ledger=NarrativeObligationLedger(
            ledger_id="ledger:narrative:room_demo:301",
            room_id="room_demo",
            world_ts=300,
            sim_tick_ts=301,
            causation_id="visual_fact:300",
            correlation_id="corr_demo",
        ),
        seeds=[
            InterventionSeed(
                seed_id="seed:1",
                seed_type="unresolved_reveal",
                basis_snapshot_ref=state.snapshot_id,
                target_refs=["char_b", "env_lamp"],
                suggested_band="fact_reveal",
                explanation="surface established fact",
            )
        ],
    )


def test_quality_monitor_runs_all_required_dimensions_without_placeholder_scores() -> None:
    result = SimingQualityMonitor().evaluate(state_tree=make_state_tree(), narrative=make_narrative())

    assert set(result.snapshot.dimensions) == {
        "information_distribution",
        "participation_distribution",
        "conversation_access_fairness",
        "suspicion_heat_distribution",
        "evidence_visibility_distribution",
    }
    assert result.snapshot.dimensions["information_distribution"].score > 0.5
    assert result.snapshot.dimensions["participation_distribution"].score > 0.5
    assert result.snapshot.dimensions["suspicion_heat_distribution"].status in {"partial", "unavailable"}
    assert any(signal.dimension == "evidence_visibility_distribution" for signal in result.signals)


def test_quality_monitor_marks_failed_auditor_partial_without_interrupting_tick() -> None:
    monitor = SimingQualityMonitor(force_failed_dimensions={"conversation_access_fairness"})

    result = monitor.evaluate(state_tree=make_state_tree(), narrative=make_narrative())

    assert result.snapshot.dimensions["conversation_access_fairness"].status == "unavailable"
    assert result.snapshot.dimensions["conversation_access_fairness"].score == 0.0
    assert "quality_monitor_partial" in result.risk_tags
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest backend/tests/test_siming_quality_monitor.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.siming_quality_monitor'`.

- [ ] **Step 3: Implement quality monitor result and service**

Create `backend/app/services/siming_quality_monitor.py`:

```python
from pydantic import BaseModel, ConfigDict, Field

from app.models.siming_event import FairnessStateSnapshot
from app.models.siming_narrative import NarrativeCoreResult, QualitySignal
from app.models.siming_runtime_state import FairnessDimensionSnapshot, StateTreeSnapshot


REQUIRED_DIMENSIONS = (
    "information_distribution",
    "participation_distribution",
    "conversation_access_fairness",
    "suspicion_heat_distribution",
    "evidence_visibility_distribution",
)


class QualityMonitorResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot: FairnessStateSnapshot
    signals: list[QualitySignal] = Field(default_factory=list)
    risk_tags: list[str] = Field(default_factory=list)


class SimingQualityMonitor:
    def __init__(self, *, force_failed_dimensions: set[str] | None = None) -> None:
        self._force_failed_dimensions = force_failed_dimensions or set()

    def evaluate(self, *, state_tree: StateTreeSnapshot, narrative: NarrativeCoreResult) -> QualityMonitorResult:
        signals = self._signals_for(state_tree=state_tree, narrative=narrative)
        dimensions: dict[str, FairnessDimensionSnapshot] = {}
        risk_tags: list[str] = []
        for dimension_id in REQUIRED_DIMENSIONS:
            if dimension_id in self._force_failed_dimensions:
                dimensions[dimension_id] = FairnessDimensionSnapshot(
                    dimension_id=dimension_id,
                    status="unavailable",
                    score=0.0,
                    reason="auditor unavailable",
                    mapped_to_policy=True,
                )
                risk_tags.append("quality_monitor_partial")
                continue
            dimension_signals = [signal for signal in signals if signal.dimension == dimension_id]
            dimensions[dimension_id] = self._dimension_from_signals(dimension_id, dimension_signals)

        established_fact_id = state_tree.environment.summary.get("established_fact_id")
        target_actor_id = state_tree.character.summary.get("target_actor_id")
        return QualityMonitorResult(
            snapshot=FairnessStateSnapshot(
                snapshot_id=f"fairness:{state_tree.snapshot_id}",
                room_id=state_tree.room_id,
                scene_id=state_tree.scene_id,
                zone_id=state_tree.zone_id,
                causation_id=state_tree.causation_id,
                correlation_id=state_tree.correlation_id,
                known_fact_ids=[str(established_fact_id)] if established_fact_id else [],
                eligible_actor_ids=[str(target_actor_id)] if target_actor_id else [],
                blocked_actor_ids=[],
                recent_intervention_ids=[],
                dimensions=dimensions,
            ),
            signals=signals,
            risk_tags=sorted(set(risk_tags)),
        )

    def _signals_for(self, *, state_tree: StateTreeSnapshot, narrative: NarrativeCoreResult) -> list[QualitySignal]:
        signals: list[QualitySignal] = []
        visible_actor_ids = state_tree.environment.summary.get("visible_actor_ids", [])
        target_actor_id = str(state_tree.character.summary.get("target_actor_id", "") or "")
        if target_actor_id and isinstance(visible_actor_ids, list) and target_actor_id not in visible_actor_ids:
            signals.append(
                QualitySignal(
                    signal_id=f"quality:{state_tree.snapshot_id}:information_distribution",
                    dimension="information_distribution",
                    severity="high",
                    target_refs=[target_actor_id],
                    evidence_refs=[str(state_tree.environment.summary.get("established_fact_id", ""))],
                    suggested_action_band="fact_reveal",
                    reason="established fact is not visible to target actor",
                )
            )
        if int(state_tree.character.summary.get("recent_participation_count", 0) or 0) == 0:
            signals.append(
                QualitySignal(
                    signal_id=f"quality:{state_tree.snapshot_id}:participation_distribution",
                    dimension="participation_distribution",
                    severity="medium",
                    target_refs=[target_actor_id] if target_actor_id else [],
                    suggested_action_band="opportunity",
                    reason="target actor has no recent participation",
                )
            )
        candidate_actor_ids = state_tree.storyline.summary.get("conversation_candidate_actor_ids", [])
        if target_actor_id and isinstance(candidate_actor_ids, list) and target_actor_id not in candidate_actor_ids:
            signals.append(
                QualitySignal(
                    signal_id=f"quality:{state_tree.snapshot_id}:conversation_access_fairness",
                    dimension="conversation_access_fairness",
                    severity="medium",
                    target_refs=[target_actor_id],
                    suggested_action_band="opportunity",
                    reason="target actor is excluded from candidate conversation access",
                )
            )
        signals.append(
            QualitySignal(
                signal_id=f"quality:{state_tree.snapshot_id}:suspicion_heat_distribution",
                dimension="suspicion_heat_distribution",
                severity="partial",
                suggested_action_band="none",
                reason="suspicion heat data is not available in this runtime slice",
            )
        )
        if narrative.seeds:
            signals.append(
                QualitySignal(
                    signal_id=f"quality:{state_tree.snapshot_id}:evidence_visibility_distribution",
                    dimension="evidence_visibility_distribution",
                    severity="medium",
                    target_refs=narrative.seeds[0].target_refs,
                    evidence_refs=narrative.seeds[0].basis_obligation_refs,
                    suggested_action_band=narrative.seeds[0].suggested_band,
                    reason="narrative seed requires evidence visibility surface",
                )
            )
        return signals

    def _dimension_from_signals(self, dimension_id: str, signals: list[QualitySignal]) -> FairnessDimensionSnapshot:
        if not signals and dimension_id == "suspicion_heat_distribution":
            return FairnessDimensionSnapshot(
                dimension_id=dimension_id,
                status="partial",
                score=0.0,
                reason="suspicion heat data unavailable",
                mapped_to_policy=True,
            )
        if not signals:
            return FairnessDimensionSnapshot(
                dimension_id=dimension_id,
                status="fresh",
                score=0.0,
                reason="no imbalance detected",
                mapped_to_policy=True,
            )
        severity_score = {"ok": 0.0, "low": 0.25, "medium": 0.6, "high": 0.9, "partial": 0.0, "unavailable": 0.0}
        score = max(severity_score[signal.severity] for signal in signals)
        status = "partial" if any(signal.severity == "partial" for signal in signals) else "fresh"
        return FairnessDimensionSnapshot(
            dimension_id=dimension_id,
            status=status,
            score=score,
            reason="; ".join(signal.reason for signal in signals),
            mapped_to_policy=True,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest backend/tests/test_siming_quality_monitor.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/siming_quality_monitor.py backend/tests/test_siming_quality_monitor.py
git commit -m "Add deterministic Siming quality monitor"
```

---

### Task 3: Intervention Guardrails

**Files:**
- Create: `backend/app/services/siming_intervention_guardrails.py`
- Test: `backend/tests/test_siming_intervention_guardrails.py`

**Interfaces:**
- Consumes: `InterventionSeed`, `FairnessStateSnapshot`.
- Produces: `SimingInterventionGuardrails.evaluate_seed(seed: InterventionSeed, snapshot: FairnessStateSnapshot) -> GuardrailResult`.
- Produces: `GuardrailResult.accepted`, `GuardrailResult.reasons`, `GuardrailResult.to_candidate(...)`.

- [ ] **Step 1: Write failing guardrail tests**

Create `backend/tests/test_siming_intervention_guardrails.py`:

```python
from app.models.siming_event import FairnessStateSnapshot
from app.models.siming_narrative import InterventionSeed
from app.services.siming_intervention_guardrails import SimingInterventionGuardrails


def make_snapshot() -> FairnessStateSnapshot:
    return FairnessStateSnapshot(
        snapshot_id="fairness:1",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        causation_id="cause",
        correlation_id="corr",
        known_fact_ids=["fact:1"],
        eligible_actor_ids=["char_b"],
        blocked_actor_ids=[],
        recent_intervention_ids=[],
        dimensions={},
    )


def make_seed(**overrides: object) -> InterventionSeed:
    payload = {
        "seed_id": "seed:1",
        "seed_type": "unresolved_reveal",
        "basis_snapshot_ref": "narrative:1",
        "basis_obligation_refs": ["fact:1"],
        "target_refs": ["char_b"],
        "suggested_band": "fact_reveal",
        "risk_tags": [],
        "explanation": "surface fact",
    }
    payload.update(overrides)
    return InterventionSeed.model_validate(payload)


def test_guardrails_reject_phase2_projection_seed() -> None:
    result = SimingInterventionGuardrails().evaluate_seed(
        make_seed(risk_tags=["phase2_projection_required"]),
        snapshot=make_snapshot(),
    )

    assert result.accepted is False
    assert "phase2_projection_required" in result.reasons


def test_guardrails_reject_unknown_fact_reference() -> None:
    result = SimingInterventionGuardrails().evaluate_seed(
        make_seed(basis_obligation_refs=["unknown_fact"]),
        snapshot=make_snapshot(),
    )

    assert result.accepted is False
    assert "unknown_fact_reference" in result.reasons


def test_guardrails_accept_seed_and_convert_to_candidate() -> None:
    result = SimingInterventionGuardrails().evaluate_seed(make_seed(), snapshot=make_snapshot())

    candidate = result.to_candidate(room_id="room_demo", scene_id="scene_demo", zone_id="zone_focus", causation_id="cause", correlation_id="corr")

    assert result.accepted is True
    assert candidate.proposed_band == "fact_reveal"
    assert candidate.target_actor_id == "char_b"
    assert candidate.established_fact_ids == ["fact:1"]
    assert "guardrail_checked" in candidate.reason_tags
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest backend/tests/test_siming_intervention_guardrails.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.siming_intervention_guardrails'`.

- [ ] **Step 3: Implement guardrail wrapper**

Create `backend/app/services/siming_intervention_guardrails.py`:

```python
from pydantic import BaseModel, ConfigDict, Field

from app.models.siming_event import FairnessStateSnapshot, InterventionCandidate
from app.models.siming_narrative import InterventionSeed


BLOCKED_RISK_TAGS = {
    "locked_truth_rewrite",
    "skip_role_autonomy",
    "skip_esm",
    "phase2_projection_required",
}


class GuardrailResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    seed: InterventionSeed
    accepted: bool
    reasons: list[str] = Field(default_factory=list)

    def to_candidate(
        self,
        *,
        room_id: str,
        scene_id: str,
        zone_id: str,
        causation_id: str,
        correlation_id: str,
    ) -> InterventionCandidate:
        if not self.accepted:
            raise ValueError("rejected seed cannot be converted to candidate")
        target_actor_id = next((ref for ref in self.seed.target_refs if ref.startswith("char_")), None)
        target_environment_id = next((ref for ref in self.seed.target_refs if ref.startswith("env_")), None)
        target_object_id = next((ref for ref in self.seed.target_refs if ref.startswith("obj_")), None)
        return InterventionCandidate(
            candidate_id=f"candidate:{self.seed.seed_id}",
            room_id=room_id,
            scene_id=scene_id,
            zone_id=zone_id,
            causation_id=causation_id,
            correlation_id=correlation_id,
            proposed_band=self.seed.suggested_band,
            target_actor_id=target_actor_id,
            target_object_id=target_object_id,
            target_environment_id=target_environment_id,
            established_fact_ids=list(self.seed.basis_obligation_refs),
            explanation=self.seed.explanation,
            confidence=0.75,
            reason_tags=["guardrail_checked", *self.reasons],
            source=self.seed.source,
        )


class SimingInterventionGuardrails:
    def evaluate_seed(self, seed: InterventionSeed, *, snapshot: FairnessStateSnapshot) -> GuardrailResult:
        reasons: list[str] = []
        for tag in seed.risk_tags:
            if tag in BLOCKED_RISK_TAGS:
                reasons.append(tag)
        unknown_refs = [ref for ref in seed.basis_obligation_refs if ref not in snapshot.known_fact_ids]
        if unknown_refs:
            reasons.append("unknown_fact_reference")
        target_actor_refs = [ref for ref in seed.target_refs if ref.startswith("char_")]
        for actor_ref in target_actor_refs:
            if actor_ref not in snapshot.eligible_actor_ids:
                reasons.append("actor_not_eligible")
        if seed.suggested_band == "environment_request" and "esm_validated_request" not in seed.risk_tags:
            reasons.append("environment_request_requires_esm_path")
        return GuardrailResult(seed=seed, accepted=not reasons, reasons=sorted(set(reasons)))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest backend/tests/test_siming_intervention_guardrails.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/siming_intervention_guardrails.py backend/tests/test_siming_intervention_guardrails.py
git commit -m "Add Siming intervention guardrails"
```

---

### Task 4: Checkpoint and Read Facade

**Files:**
- Modify: `backend/app/models/siming_runtime_state.py`
- Modify: `backend/app/services/siming_read_model.py`
- Modify: `backend/app/services/siming_audit_writer.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_siming_read_facade.py`

**Interfaces:**
- Consumes: `NarrativeCoreResult`, `QualityMonitorResult`, `GuardrailResult`, `SimingCheckpoint`.
- Produces: `SimingReadModelBuilder.build_checkpoint(..., checkpoint_type: CheckpointType) -> SimingCheckpoint`.
- Produces: `SimingAuditWriter.latest_read_model(room_id: str) -> NarrativeReadModel | None`.
- Produces: `GET /debug/siming/read-model/{room_id}`.

- [ ] **Step 1: Write failing read-facade tests**

Create `backend/tests/test_siming_read_facade.py`:

```python
from fastapi.testclient import TestClient

from app.main import app, reset_runtime_state, siming_audit_writer
from app.models.siming_runtime_state import NarrativeReadModel


def test_audit_writer_returns_latest_read_model_by_room() -> None:
    reset_runtime_state()
    first = NarrativeReadModel(
        read_model_id="read:room_demo:1",
        schema_version=1,
        producer_system="siming.read_model",
        room_id="room_demo",
        scene_scope="scene/zone",
        world_ts=1,
        sim_tick_ts=2,
    )
    second = first.model_copy(update={"read_model_id": "read:room_demo:2", "world_ts": 2, "sim_tick_ts": 3})

    siming_audit_writer.record_read_model(first)
    siming_audit_writer.record_read_model(second)

    latest = siming_audit_writer.latest_read_model(room_id="room_demo")
    assert latest is not None
    assert latest.read_model_id == "read:room_demo:2"


def test_debug_read_model_endpoint_returns_latest_model() -> None:
    reset_runtime_state()
    siming_audit_writer.record_read_model(
        NarrativeReadModel(
            read_model_id="read:room_demo:1",
            schema_version=1,
            producer_system="siming.read_model",
            room_id="room_demo",
            scene_scope="scene/zone",
            world_ts=1,
            sim_tick_ts=2,
            narrative_surface={"active_phase": "rising"},
        )
    )

    response = TestClient(app).get("/debug/siming/read-model/room_demo")

    assert response.status_code == 200
    assert response.json()["read_model_id"] == "read:room_demo:1"
    assert response.json()["narrative_surface"]["active_phase"] == "rising"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest backend/tests/test_siming_read_facade.py -v`

Expected: FAIL because `latest_read_model` and the debug route do not exist.

- [ ] **Step 3: Extend runtime state models**

Modify `backend/app/models/siming_runtime_state.py`:

```python
CheckpointType = Literal["fairness_before", "fairness_after", "pre_decision", "post_decision", "post_dispatch"]
```

Keep `NarrativeReadModel` fields, and rely on existing `current_state`, `intervention_surface`, and `narrative_surface` dictionaries for summaries in this phase.

- [ ] **Step 4: Extend read model builder**

Modify `backend/app/services/siming_read_model.py` so `build_checkpoint` accepts `checkpoint_type`:

```python
    def build_checkpoint(
        self,
        *,
        state_tree: StateTreeSnapshot,
        fairness: FairnessStateSnapshot,
        storyline: StorylineStateSnapshot,
        checkpoint_type: str = "fairness_after",
    ) -> SimingCheckpoint:
        return SimingCheckpoint(
            checkpoint_id=(
                f"checkpoint:{checkpoint_type}:{state_tree.room_id}:{state_tree.sim_tick_ts}:{fairness.snapshot_id}"
            ),
            schema_version=1,
            room_id=state_tree.room_id,
            world_ts=state_tree.world_ts,
            sim_tick_ts=state_tree.sim_tick_ts,
            checkpoint_type=checkpoint_type,
            fairness_snapshot_ref=fairness.snapshot_id,
            state_tree_snapshot_ref=state_tree.snapshot_id,
            storyline_snapshot_ref=storyline.snapshot_id,
            causation_id=state_tree.causation_id,
            correlation_id=state_tree.correlation_id,
        )
```

Modify `build_read_model` to accept optional summary dictionaries:

```python
        narrative_summary: dict[str, object] | None = None,
        quality_summary: dict[str, object] | None = None,
        guardrail_summary: dict[str, object] | None = None,
        checkpoint_summary: dict[str, object] | None = None,
```

Merge those into `current_state`, `intervention_surface`, and `narrative_surface` without removing existing fields.

- [ ] **Step 5: Add latest read model lookup and debug route**

Modify `backend/app/services/siming_audit_writer.py`:

```python
    def latest_read_model(self, *, room_id: str) -> NarrativeReadModel | None:
        models = self.list_read_models(room_id=room_id)
        if not models:
            return None
        return max(models, key=lambda model: (model.sim_tick_ts, model.world_ts, model.read_model_id))
```

Modify `backend/app/main.py`:

```python
@app.get("/debug/siming/read-model/{room_id}")
def debug_siming_read_model(room_id: str) -> dict[str, object]:
    read_model = siming_audit_writer.latest_read_model(room_id=room_id)
    if read_model is None:
        return {"room_id": room_id, "status": "missing"}
    return read_model.model_dump(exclude_none=True)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `python -m pytest backend/tests/test_siming_read_facade.py -v`

Expected: PASS.

- [ ] **Step 7: Commit read facade pieces**

```bash
git add backend/app/models/siming_runtime_state.py backend/app/services/siming_read_model.py backend/app/services/siming_audit_writer.py backend/app/main.py backend/tests/test_siming_read_facade.py
git commit -m "Add Siming read facade and checkpoint surfaces"
```

---

### Task 5: Runtime Orchestrator Wiring

**Files:**
- Modify: `backend/app/services/siming_runtime.py`
- Modify: `backend/tests/test_siming_agent_loop_runtime.py`
- Modify: `backend/tests/test_siming_event_pipeline.py`

**Interfaces:**
- Consumes: `SimingNarrativeCore`, `SimingQualityMonitor`, `SimingInterventionGuardrails`.
- Produces: `SimingTickResult` with outputs, audit records, multi-stage checkpoints, and enriched read model.

- [ ] **Step 1: Add failing runtime integration tests**

Add to `backend/tests/test_siming_agent_loop_runtime.py`:

```python
def test_tick_places_narrative_seed_quality_and_guardrail_summaries_in_read_model() -> None:
    runtime = SimingRuntime()

    result = runtime.tick(
        [SimingInput(input_type="visual_fact_event", source_event=make_visual_fact_event())]
    )

    assert result.read_model is not None
    assert result.read_model.narrative_surface["active_phase"] == "rising"
    assert result.read_model.narrative_surface["intervention_seed_count"] >= 1
    assert "quality_signal_count" in result.read_model.intervention_surface
    assert "guardrail_statuses" in result.read_model.intervention_surface


def test_tick_records_multi_stage_checkpoints() -> None:
    runtime = SimingRuntime()

    result = runtime.tick(
        [SimingInput(input_type="visual_fact_event", source_event=make_visual_fact_event())]
    )

    checkpoint_types = {checkpoint.checkpoint_type for checkpoint in result.checkpoints}
    assert {"pre_decision", "post_decision", "post_dispatch"}.issubset(checkpoint_types)


def test_locked_fact_conflict_still_does_not_update_narrative_core() -> None:
    runtime = SimingRuntime()
    event = make_visual_fact_event(payload_overrides={"locked_fact_conflict": True})

    result = runtime.tick([SimingInput(input_type="visual_fact_event", source_event=event)])

    assert any(audit.reason == "fact_veto:locked_fact_conflict" for audit in result.audit_records)
    assert result.checkpoints == []
    assert result.read_model is None
```

Add to `backend/tests/test_siming_event_pipeline.py`:

```python
def test_pipeline_records_multi_stage_checkpoints_for_runtime_tick() -> None:
    bus = InMemoryAuthorityEventBus()
    audit_writer = SimingAuditWriter()
    pipeline = make_pipeline(bus, audit_writer)
    bus.subscribe("visual_fact_event", pipeline.handle_event)

    bus.publish(make_visual_fact_event())

    checkpoint_types = {checkpoint.checkpoint_type for checkpoint in audit_writer.list_checkpoints(room_id="room_demo")}
    assert {"pre_decision", "post_decision", "post_dispatch"}.issubset(checkpoint_types)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest backend/tests/test_siming_agent_loop_runtime.py::test_tick_places_narrative_seed_quality_and_guardrail_summaries_in_read_model backend/tests/test_siming_agent_loop_runtime.py::test_tick_records_multi_stage_checkpoints backend/tests/test_siming_agent_loop_runtime.py::test_locked_fact_conflict_still_does_not_update_narrative_core -v`

Expected: FAIL because runtime does not instantiate or use the new services.

- [ ] **Step 3: Inject new services into SimingRuntime**

Modify `backend/app/services/siming_runtime.py` imports:

```python
from app.services.siming_intervention_guardrails import SimingInterventionGuardrails
from app.services.siming_narrative_core import SimingNarrativeCore
from app.services.siming_quality_monitor import SimingQualityMonitor
```

Modify `SimingRuntime.__init__`:

```python
        narrative_core: SimingNarrativeCore | None = None,
        quality_monitor: SimingQualityMonitor | None = None,
        intervention_guardrails: SimingInterventionGuardrails | None = None,
```

Assign:

```python
        self._narrative_core = narrative_core or SimingNarrativeCore()
        self._quality_monitor = quality_monitor or SimingQualityMonitor()
        self._intervention_guardrails = intervention_guardrails or SimingInterventionGuardrails()
```

- [ ] **Step 4: Wire narrative, quality, guardrails, and checkpoints after fact acceptance**

Inside `tick()`, after `state_tree` and before branch-specific dispatch logic, add:

```python
            narrative = self._narrative_core.update(observed)
            quality = self._quality_monitor.evaluate(state_tree=state_tree, narrative=narrative)
            fairness_snapshot = quality.snapshot
            result.checkpoints.append(
                self._read_model_builder.build_checkpoint(
                    state_tree=state_tree,
                    fairness=fairness_snapshot,
                    storyline=storyline,
                    checkpoint_type="pre_decision",
                )
            )
            guardrail_results = [
                self._intervention_guardrails.evaluate_seed(seed, snapshot=fairness_snapshot)
                for seed in narrative.seeds
            ]
```

Replace the old immediate `fairness_snapshot = self._fairness_audit.build_snapshot(state_tree)` assignment in that block. Keep `self._fairness_audit` initialized in `__init__` for compatibility during this task; do not call it on the new fact-accepted path after `quality.snapshot` is available.

- [ ] **Step 5: Update finalize helper to accept summaries and emit post checkpoints**

Modify `_finalize_tick_state` signature:

```python
        narrative_summary: dict[str, object] | None = None,
        quality_summary: dict[str, object] | None = None,
        guardrail_summary: dict[str, object] | None = None,
```

Inside `_finalize_tick_state`, append `post_decision` and `post_dispatch` checkpoints before building the read model:

```python
        for checkpoint_type in ("post_decision", "post_dispatch"):
            result.checkpoints.append(
                self._read_model_builder.build_checkpoint(
                    state_tree=state_tree,
                    fairness=fairness_snapshot,
                    storyline=storyline,
                    checkpoint_type=checkpoint_type,
                )
            )
```

Pass the summaries to `build_read_model`.

- [ ] **Step 6: Build summary dictionaries in tick branches**

Use these helpers inside `SimingRuntime`:

```python
    def _narrative_summary_for(self, narrative) -> dict[str, object]:
        return {
            "active_phase": narrative.state.active_phase,
            "pressure_level": narrative.state.pressure_level,
            "open_obligation_count": len(narrative.ledger.obligations),
            "intervention_seed_count": len(narrative.seeds),
            "seed_types": [seed.seed_type for seed in narrative.seeds],
        }

    def _quality_summary_for(self, quality) -> dict[str, object]:
        return {
            "quality_signal_count": len(quality.signals),
            "quality_risk_tags": list(quality.risk_tags),
            "quality_dimensions": sorted(quality.snapshot.dimensions.keys()),
        }

    def _guardrail_summary_for(self, guardrail_results) -> dict[str, object]:
        return {
            "guardrail_statuses": [
                "accepted" if result.accepted else "rejected"
                for result in guardrail_results
            ],
            "guardrail_reasons": [
                reason
                for result in guardrail_results
                for reason in result.reasons
            ],
        }
```

- [ ] **Step 7: Run focused runtime tests**

Run: `python -m pytest backend/tests/test_siming_agent_loop_runtime.py -v`

Expected: PASS.

Run: `python -m pytest backend/tests/test_siming_event_pipeline.py::test_pipeline_records_multi_stage_checkpoints_for_runtime_tick -v`

Expected: PASS.

- [ ] **Step 8: Commit runtime wiring**

```bash
git add backend/app/services/siming_runtime.py backend/tests/test_siming_agent_loop_runtime.py backend/tests/test_siming_event_pipeline.py
git commit -m "Wire Siming narrative core into runtime tick"
```

---

### Task 6: Regression Sweep and Boundary Tests

**Files:**
- Modify: `backend/tests/test_siming_llm_boundary_static.py`
- Modify: `backend/tests/test_siming_event_pipeline.py`

**Interfaces:**
- Consumes: all new services and existing websocket/runtime behavior.
- Produces: regression evidence that LLM boundaries, bus boundaries, and old dispatch paths still hold.

- [ ] **Step 1: Add static LLM boundary assertion**

Modify `backend/tests/test_siming_llm_boundary_static.py`:

```python
def test_narrative_core_does_not_import_or_call_llm_provider() -> None:
    text = read("app/services/siming_narrative_core.py")

    assert "siming_llm_provider" not in text
    assert "generate_candidates(" not in text
    assert "SimingLlm" not in text
```

- [ ] **Step 2: Add bus boundary assertion**

Modify `backend/tests/test_siming_event_pipeline.py`:

```python
def test_pipeline_does_not_publish_internal_narrative_or_read_facade_events() -> None:
    bus = InMemoryAuthorityEventBus()
    audit_writer = SimingAuditWriter()
    pipeline = make_pipeline(bus, audit_writer)
    bus.subscribe("visual_fact_event", pipeline.handle_event)

    bus.publish(make_visual_fact_event())

    event_types = {event.event_type for event in bus.list_events(room_id="room_demo")}
    assert "siming.read_model" not in event_types
    assert "siming.checkpoint" not in event_types
    assert "siming.narrative_state" not in event_types
    assert "siming.intervention_seed" not in event_types
```

- [ ] **Step 3: Run focused regression tests**

Run:

```bash
python -m pytest \
  backend/tests/test_siming_narrative_core.py \
  backend/tests/test_siming_quality_monitor.py \
  backend/tests/test_siming_intervention_guardrails.py \
  backend/tests/test_siming_read_facade.py \
  backend/tests/test_siming_agent_loop_runtime.py \
  backend/tests/test_siming_event_pipeline.py \
  backend/tests/test_siming_llm_boundary_static.py \
  -v
```

Expected: PASS.

- [ ] **Step 4: Run broader Siming and websocket regression slice**

Run:

```bash
python -m pytest \
  backend/tests/test_siming_llm_runtime.py \
  backend/tests/test_visual_fact_pipeline.py \
  backend/tests/test_ws_protocol.py \
  backend/tests/test_verification_audit.py \
  -k "siming or visual_fact or observatory or read_model or checkpoint" \
  -v
```

Expected: PASS.

- [ ] **Step 5: Run full backend test suite if the focused slices pass**

Run: `python -m pytest -v`

Expected: PASS.

- [ ] **Step 6: Commit boundary/regression tests**

```bash
git add backend/tests/test_siming_llm_boundary_static.py backend/tests/test_siming_event_pipeline.py backend/tests/test_ws_protocol.py
git commit -m "Verify Siming narrative core boundaries"
```

---

## Self-Review

Spec coverage:

- Stateful narrative core is covered by Tasks 1 and 5.
- Thin `InterventionSeed` replacement for full `EventChainCandidate` is covered by Tasks 1, 3, and 5.
- Five real quality auditors are covered by Task 2.
- Explicit guardrails are covered by Task 3.
- Multi-stage in-memory checkpoints are covered by Tasks 4 and 5.
- Queryable read facade is covered by Task 4.
- Synchronous orchestrator step is covered by Task 5.
- LLM boundary is covered by Tasks 1 and 6.
- Public bus boundary is covered by Tasks 4 and 6.

Placeholder scan:

- No unresolved placeholders or unspecified test steps remain.

Type consistency:

- `InterventionSeed`, `QualitySignal`, and `NarrativeCoreResult` are defined in Task 1 and used by later tasks.
- `QualityMonitorResult` is defined in Task 2 and consumed by Task 5.
- `GuardrailResult` is defined in Task 3 and consumed by Task 5.
- `latest_read_model(room_id: str)` is defined in Task 4 and used by the debug route.
