from app.models.siming_runtime_state import (
    NarrativeObligation,
    NarrativeObligationLedgerSnapshot,
    StateTreeSnapshot,
    StorylineMarker,
    StorylineStateSnapshot,
)


class InMemoryStorylineState:
    def __init__(self) -> None:
        self._latest_snapshot: StorylineStateSnapshot | None = None

    def update_from_state_tree(self, state_tree: StateTreeSnapshot) -> StorylineStateSnapshot:
        markers: list[StorylineMarker] = []
        if self._has_complete_visibility_surface(state_tree):
            markers.append(
                StorylineMarker(
                    marker_id=f"marker:{state_tree.snapshot_id}:information_visibility",
                    marker_type="information_visibility",
                    status="active",
                    entity_refs=[state_tree.environment.node_id, state_tree.character.node_id],
                    reason="Established environment state has an eligible character visibility surface.",
                )
            )
        storyline = StorylineStateSnapshot(
            snapshot_id=f"storyline:{state_tree.snapshot_id}",
            schema_version=1,
            producer_system="siming.storyline",
            room_id=state_tree.room_id,
            world_ts=state_tree.world_ts,
            sim_tick_ts=state_tree.sim_tick_ts,
            causation_id=state_tree.causation_id,
            correlation_id=state_tree.correlation_id,
            active_phase=str(state_tree.storyline.summary.get("active_phase", "rising")),
            markers=markers,
        )
        self._latest_snapshot = storyline
        return storyline

    @property
    def latest_snapshot(self) -> StorylineStateSnapshot | None:
        return self._latest_snapshot

    def _has_complete_visibility_surface(self, state_tree: StateTreeSnapshot) -> bool:
        established_fact_id = state_tree.environment.summary.get("established_fact_id")
        if established_fact_id is None:
            return False

        normalized_fact_id = str(established_fact_id).strip()
        return (
            state_tree.environment.status == "fresh"
            and state_tree.character.status == "fresh"
            and bool(normalized_fact_id)
        )


class InMemoryNarrativeObligationLedger:
    def __init__(self) -> None:
        self._latest_snapshot: NarrativeObligationLedgerSnapshot | None = None

    def update_from_storyline(
        self,
        storyline: StorylineStateSnapshot,
    ) -> NarrativeObligationLedgerSnapshot:
        obligations = [
            NarrativeObligation(
                obligation_id=f"obligation:{marker.marker_id}",
                source_ref=marker.marker_id,
                obligation_type="unresolved_reveal",
                status="open",
                reason=marker.reason,
            )
            for marker in storyline.markers
            if marker.status in {"active", "stalled"}
        ]
        ledger = NarrativeObligationLedgerSnapshot(
            ledger_id=f"ledger:{storyline.snapshot_id}",
            schema_version=1,
            producer_system="siming.obligation",
            room_id=storyline.room_id,
            world_ts=storyline.world_ts,
            sim_tick_ts=storyline.sim_tick_ts,
            causation_id=storyline.causation_id,
            correlation_id=storyline.correlation_id,
            obligations=obligations,
        )
        self._latest_snapshot = ledger
        return ledger

    @property
    def latest_snapshot(self) -> NarrativeObligationLedgerSnapshot | None:
        return self._latest_snapshot
