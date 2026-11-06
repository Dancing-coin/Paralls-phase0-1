"""The Siming orchestration entry point.

The runtime already judges one input correctly; what it lacked was an owner for
*cadence*: a single ingest queue, the three degradation modes, per-auditor
bookkeeping, and a fixed cycle order.  This module supplies exactly that and
delegates the judging, so there is one implementation of fairness and policy
rather than two drifting ones.

Priority handling follows the frozen contract: P0/P1 (the main judge chain) are
never shed, ``survival`` keeps only those, and an auditor that is not scheduled
reports a ``degraded`` dimension instead of a missing one.
"""

from __future__ import annotations

from typing import Iterable

from pydantic import BaseModel, ConfigDict, Field

from app.models.siming_event import (
    FairnessStateSnapshot,
    SimingAuditRecord,
    SimingInput,
    SimingOutput,
)
from app.services.siming_orchestration import (
    AUDITORS,
    AUDITOR_FOR_DIMENSION,
    DEFAULT_BUDGETS,
    PRESSURE_DOWNSAMPLED_AUDITORS,
    RUNTIME_PRIORITIES,
    SimingBudgetProfile,
    is_priority_scheduled,
    retained_priorities,
    select_runtime_mode,
)
from app.services.siming_runtime import SimingRuntime


class AuditorResult(BaseModel):
    """Per-auditor outcome, including the shed case.

    A shed auditor still reports a dimension object: representing "not computed"
    as a missing field would make an unmeasured dimension look healthy.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    auditor: str
    dimension_id: str
    status: str = Field(pattern="^(fresh|degraded|stale|unavailable)$")
    reason: str = ""


class OrchestratorTick(BaseModel):
    """One orchestrated cycle, reported in contract order."""

    model_config = ConfigDict(extra="forbid")

    mode: str
    consumed_events: int = Field(ge=0)
    snapshot: FairnessStateSnapshot | None = None
    candidate_outputs: tuple[SimingOutput, ...] = ()
    decision_outputs: tuple[SimingOutput, ...] = ()
    dispatch_outputs: tuple[SimingOutput, ...] = ()
    audits: tuple[SimingAuditRecord, ...] = ()
    read_model: dict[str, object] | None = None
    auditor_results: tuple[AuditorResult, ...] = ()
    shed_priorities: tuple[str, ...] = ()
    budget_overruns: tuple[str, ...] = ()


class SimingOrchestrator:
    """Single entry point that decides what runs when.

    ``runtime`` performs the judging; this class owns cadence, degradation and
    the audit of both.
    """

    def __init__(
        self,
        *,
        runtime: SimingRuntime | None = None,
        budgets: SimingBudgetProfile | None = None,
        pressure_threshold: int = 8,
        survival_threshold: int = 32,
    ) -> None:
        if survival_threshold < pressure_threshold:
            raise ValueError("survival_threshold_below_pressure_threshold")
        self._runtime = runtime or SimingRuntime()
        self._budgets = budgets or SimingBudgetProfile.default()
        self._pressure_threshold = pressure_threshold
        self._survival_threshold = survival_threshold
        self._queue: list[SimingInput] = []
        self._last_snapshot: FairnessStateSnapshot | None = None
        self._recent_audits: list[SimingAuditRecord] = []

    @property
    def budgets(self) -> SimingBudgetProfile:
        return self._budgets

    @property
    def runtime(self) -> SimingRuntime:
        return self._runtime

    # -- ingestion ---------------------------------------------------------

    def ingest_event(self, event: SimingInput) -> None:
        """Queue one event.  Ingest records intent; it never judges."""
        self._queue.append(event)

    def pending_events(self) -> int:
        return len(self._queue)

    def consume_queued_events(self) -> list[SimingInput]:
        consumed, self._queue = self._queue, []
        return consumed

    # -- mode --------------------------------------------------------------

    def current_mode(self) -> str:
        return select_runtime_mode(
            queued_events=len(self._queue),
            pressure_threshold=self._pressure_threshold,
            survival_threshold=self._survival_threshold,
        )

    def scheduled_auditors(self, mode: str) -> tuple[str, ...]:
        """Auditors that run in ``mode``.

        Only suspicion is sheddable, and only outside ``standard``; the other four
        stay because they are what keep the judge inputs complete.
        """
        if retained_priorities(mode) == retained_priorities("standard"):
            return AUDITORS
        return tuple(a for a in AUDITORS if a not in PRESSURE_DOWNSAMPLED_AUDITORS)

    def shed_priorities(self, mode: str) -> tuple[str, ...]:
        return tuple(p for p in RUNTIME_PRIORITIES if not is_priority_scheduled(p, mode))

    def auditor_results(self, mode: str) -> tuple[AuditorResult, ...]:
        scheduled = set(self.scheduled_auditors(mode))
        results: list[AuditorResult] = []
        for dimension_id, auditor in AUDITOR_FOR_DIMENSION.items():
            if auditor in scheduled:
                results.append(
                    AuditorResult(
                        auditor=auditor, dimension_id=dimension_id, status="fresh", reason=""
                    )
                )
            else:
                results.append(
                    AuditorResult(
                        auditor=auditor,
                        dimension_id=dimension_id,
                        status="degraded",
                        reason="runtime_pressure",
                    )
                )
        return tuple(results)

    # -- cycle stages ------------------------------------------------------

    def build_fairness_snapshot(self, *, mode: str | None = None) -> FairnessStateSnapshot | None:
        """Build the snapshot from the last installed state tree.

        ``mode`` must be the mode the running cycle decided on.  Recomputing it
        here would read the queue *after* it was drained and silently report a
        calmer mode than the one that actually served this cycle.

        Returns ``None`` before any event has been observed: an empty snapshot
        would read as "measured and balanced", which is a different claim.
        """
        state_tree = self._runtime._state_tree.latest_snapshot
        if state_tree is None:
            return None
        effective_mode = mode if mode is not None else self.current_mode()
        snapshot = self._runtime._fairness_audit.build_snapshot(state_tree)
        # Unscheduleable auditors must still yield a dimension object.
        for result in self.auditor_results(effective_mode):
            if result.status == "fresh":
                continue
            existing = snapshot.dimensions.get(result.dimension_id)
            if existing is None:
                continue
            snapshot.dimensions[result.dimension_id] = existing.model_copy(
                update={"status": "unavailable", "reason": result.reason}
            )
        self._last_snapshot = snapshot
        return snapshot

    def refresh_read_model(
        self,
        snapshot: FairnessStateSnapshot | None,
        recent_audit: Iterable[SimingAuditRecord],
    ) -> dict[str, object] | None:
        if snapshot is None:
            return None
        audits = list(recent_audit)
        return {
            "snapshot_id": snapshot.snapshot_id,
            "audit_count": len(audits),
            "global_imbalance_score": snapshot.global_imbalance_score,
            "dominant_imbalance_type": snapshot.dominant_imbalance_type,
        }

    def audit_cycle(
        self,
        *,
        mode: str,
        consumed_events: int,
        auditor_results: tuple[AuditorResult, ...],
        candidate_outputs: tuple[SimingOutput, ...],
        decision_outputs: tuple[SimingOutput, ...],
    ) -> SimingAuditRecord:
        """Record the cycle, including what was shed and what ran.

        Shedding is written into the audit because a degraded cycle that looks
        identical to a full one cannot be diagnosed afterwards.
        """
        snapshot = self._last_snapshot
        degraded = sorted(r.auditor for r in auditor_results if r.status != "fresh")
        status = "recorded" if decision_outputs else "no_action"
        room_id = snapshot.room_id if snapshot else ""
        correlation_id = snapshot.correlation_id if snapshot else ""
        causation_id = snapshot.causation_id if snapshot else ""
        return SimingAuditRecord(
            audit_id=f"orchestrator-audit:{room_id}:{len(self._recent_audits) + 1}",
            room_id=room_id,
            correlation_id=correlation_id,
            causation_id=causation_id,
            source_event_id=snapshot.snapshot_id if snapshot else "",
            status=status,
            reason=(
                f"orchestrator mode={mode}"
                f" events={consumed_events}"
                f" candidates={len(candidate_outputs)}"
                f" decisions={len(decision_outputs)}"
                f" degraded_auditors={len(degraded)}"
                f" shed={'none' if not self.shed_priorities(mode) else ','.join(self.shed_priorities(mode))}"
            ),
        )

    def generate_intervention_candidates(
        self, outputs: Iterable[SimingOutput]
    ) -> tuple[SimingOutput, ...]:
        """Extract the candidate stage from a runtime result.

        The candidates are *generated* by the runtime (narrative core + LLM
        provider).  Re-deriving them here would create a second generator whose
        output could disagree with the one actually judged, so this stage selects
        from the result instead of recomputing.
        """
        return tuple(o for o in outputs if o.output_type == "intervention_candidate")

    def evaluate_candidates(self, outputs: Iterable[SimingOutput]) -> tuple[SimingOutput, ...]:
        """Extract policy/feasibility rejections recorded by the runtime."""
        evaluated: list[SimingOutput] = []
        for output in outputs:
            if output.output_type in {"intervention_candidate", "intervention_decision"}:
                evaluated.append(output)
        return tuple(evaluated)

    def select_intervention(self, outputs: Iterable[SimingOutput]) -> tuple[SimingOutput, ...]:
        """Extract the single selected decision, if the runtime produced one."""
        return tuple(o for o in outputs if o.output_type == "intervention_decision")

    def dispatch_intervention(self, outputs: Iterable[SimingOutput]) -> tuple[SimingOutput, ...]:
        """Extract dispatch intents the runtime emitted for the selected decision."""
        return tuple(o for o in outputs if o.output_type == "dispatch_intent")

    # -- tick --------------------------------------------------------------

    def tick(self, sim_tick_ts: float, world_ts: float) -> OrchestratorTick:
        """Run one cycle in the contract's fixed order.

        The order matters: the audit is written even when nothing is dispatched,
        and the read model is refreshed last so it never describes a partial cycle.
        """
        mode = self.current_mode()
        consumed = self.consume_queued_events()
        auditor_results = self.auditor_results(mode)

        runtime_result = self._runtime.tick(consumed) if consumed else None
        outputs = tuple(runtime_result.outputs) if runtime_result else ()
        candidates = self.generate_intervention_candidates(outputs)
        decisions = self.select_intervention(outputs)
        dispatches = self.dispatch_intervention(outputs)

        snapshot = self.build_fairness_snapshot(mode=mode) if consumed else self._last_snapshot
        audits = tuple(runtime_result.audit_records) if runtime_result else ()
        cycle_audit = self.audit_cycle(
            mode=mode,
            consumed_events=len(consumed),
            auditor_results=auditor_results,
            candidate_outputs=candidates,
            decision_outputs=decisions,
        )
        self._recent_audits.append(cycle_audit)
        all_audits = audits + (cycle_audit,)
        read_model = self.refresh_read_model(snapshot, all_audits)

        return OrchestratorTick(
            mode=mode,
            consumed_events=len(consumed),
            snapshot=snapshot,
            candidate_outputs=candidates,
            decision_outputs=decisions,
            dispatch_outputs=dispatches,
            audits=all_audits,
            read_model=read_model,
            auditor_results=auditor_results,
            shed_priorities=self.shed_priorities(mode),
            budget_overruns=(),
        )
