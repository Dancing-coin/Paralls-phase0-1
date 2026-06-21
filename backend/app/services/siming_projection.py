from typing import Protocol

from app.models.siming_event import FairnessStateSnapshot
from app.models.siming_runtime_state import (
    GroupSimulationBranchSnapshot,
    NarrativeObligationLedgerSnapshot,
    ProjectionRunSnapshot,
    StateTreeSnapshot,
    StorylineStateSnapshot,
)


class GroupSimulationBridgePort(Protocol):
    def summarize(self, *, room_id: str) -> GroupSimulationBranchSnapshot: ...


class StorylineProjectionPort(Protocol):
    def project(
        self,
        *,
        state_tree: StateTreeSnapshot,
        fairness: FairnessStateSnapshot,
        storyline: StorylineStateSnapshot,
        ledger: NarrativeObligationLedgerSnapshot,
    ) -> ProjectionRunSnapshot: ...


class StubGroupSimulationBridge:
    def summarize(self, *, room_id: str) -> GroupSimulationBranchSnapshot:
        return GroupSimulationBranchSnapshot(
            status="unavailable",
            summary={
                "mode": "shape_only",
                "room_id": room_id,
                "access": "read_only",
            },
        )


class StubStorylineProjection:
    def project(
        self,
        *,
        state_tree: StateTreeSnapshot,
        fairness: FairnessStateSnapshot,
        storyline: StorylineStateSnapshot,
        ledger: NarrativeObligationLedgerSnapshot,
    ) -> ProjectionRunSnapshot:
        return ProjectionRunSnapshot(
            projection_id=f"projection:{state_tree.room_id}:{state_tree.sim_tick_ts}",
            schema_version=1,
            producer_system="siming.projection",
            room_id=state_tree.room_id,
            world_ts=state_tree.world_ts,
            sim_tick_ts=state_tree.sim_tick_ts,
            causation_id=state_tree.causation_id,
            correlation_id=state_tree.correlation_id,
            status="fresh",
            basis_state_tree_ref=state_tree.snapshot_id,
            basis_fairness_snapshot_ref=fairness.snapshot_id,
            candidate_hints=[
                {
                    "obligation_id": obligation.obligation_id,
                    "reason": obligation.reason,
                    "suggested_band": self._suggested_band(obligation.obligation_type),
                }
                for obligation in ledger.obligations
                if obligation.status == "open"
            ],
            summary={
                "mode": "candidate_hints_only",
                "storyline_snapshot_ref": storyline.snapshot_id,
                "ledger_ref": ledger.ledger_id,
            },
        )

    def _suggested_band(self, obligation_type: str) -> str:
        if obligation_type == "unresolved_reveal":
            return "fact_reveal"
        return "opportunity"
