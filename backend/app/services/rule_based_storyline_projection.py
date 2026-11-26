from __future__ import annotations

from app.models.siming_event import FairnessStateSnapshot
from app.models.siming_runtime_state import (
    GroupSimulationBranchSnapshot, NarrativeObligation, NarrativeObligationLedgerSnapshot,
    ProjectionRunSnapshot, StateTreeSnapshot, StorylineStateSnapshot,
)


class RuleBasedStorylineProjection:
    def __init__(self, *, max_hints: int = 5) -> None:
        if max_hints < 1:
            raise ValueError("storyline_projection_max_hints_invalid")
        self._max_hints = max_hints

    def project(self, *, state_tree: StateTreeSnapshot, fairness: FairnessStateSnapshot,
                storyline: StorylineStateSnapshot, ledger: NarrativeObligationLedgerSnapshot) -> ProjectionRunSnapshot:
        open_obligations = [item for item in ledger.obligations if item.status == "open"]
        hints = []
        for obligation in open_obligations:
            phase_match = self._phase_match(obligation.obligation_type, storyline.active_phase)
            hints.append({
                "obligation_id": obligation.obligation_id,
                "reason": obligation.reason,
                "suggested_band": self._suggested_band(obligation.obligation_type, storyline.active_phase),
                "weight": self._compute_weight(obligation, fairness, state_tree.group_simulation, phase_match),
                "phase_match": phase_match,
                "preconditions_met": True,
            })
        hints.sort(key=lambda item: (-item["weight"], item["obligation_id"]))
        hints = hints[: self._max_hints]
        return ProjectionRunSnapshot(
            projection_id=f"projection:{state_tree.room_id}:{state_tree.sim_tick_ts}",
            schema_version=1,
            producer_system="siming.projection.rule_based",
            room_id=state_tree.room_id,
            world_ts=state_tree.world_ts,
            sim_tick_ts=state_tree.sim_tick_ts,
            causation_id=state_tree.causation_id,
            correlation_id=state_tree.correlation_id,
            status="fresh",
            basis_state_tree_ref=state_tree.snapshot_id,
            basis_fairness_snapshot_ref=fairness.snapshot_id,
            candidate_hints=hints,
            summary={
                "mode": "rule_based", "open_obligation_count": len(open_obligations),
                "output_hint_count": len(hints), "active_phase": storyline.active_phase,
                "group_simulation_status": state_tree.group_simulation.status,
            },
        )

    @staticmethod
    def _phase_match(obligation_type: str, active_phase: str) -> bool:
        if active_phase in {"setup", "pressure"}:
            return True
        if active_phase == "rising":
            return obligation_type in {"open_opportunity", "unresolved_reveal", "rising_conflict"}
        if active_phase == "resolution":
            return obligation_type in {"unresolved_reveal", "resolution_required"}
        return True

    @staticmethod
    def _compute_weight(obligation: NarrativeObligation, fairness: FairnessStateSnapshot,
                        group_simulation: GroupSimulationBranchSnapshot, phase_match: bool) -> float:
        weight = 0.5 + (0.2 if phase_match else 0.0)
        if obligation.obligation_type == "unresolved_reveal":
            weight += 0.1
        elif obligation.obligation_type in {"open_opportunity", "rising_conflict"}:
            weight += 0.15
        if group_simulation.status == "fresh":
            weight += float(group_simulation.summary.get("avg_need_pressure", 0.0)) * 0.2
        imbalance = fairness.global_imbalance_score
        if imbalance is None:
            imbalance = max(0.0, 1.0 - fairness.overall_fairness_score)
        weight += float(imbalance) * 0.1
        return round(min(1.0, weight), 3)

    @staticmethod
    def _suggested_band(obligation_type: str, active_phase: str) -> str:
        if obligation_type == "unresolved_reveal":
            return "fact_reveal"
        if obligation_type in {"open_opportunity", "rising_conflict"}:
            return "opportunity"
        return "impulse" if active_phase == "pressure" else "opportunity"


__all__ = ["RuleBasedStorylineProjection"]
