from app.models.siming_runtime_state import (
    GroupSimulationBranchSnapshot,
    ObservedSimingEvent,
    StateTreeNode,
    StateTreeSnapshot,
)


class InMemorySimingStateTree:
    def __init__(self) -> None:
        self._latest_snapshot: StateTreeSnapshot | None = None

    def update_from_observed(
        self,
        observed_events: list[ObservedSimingEvent],
        *,
        sim_tick_ts: int,
    ) -> StateTreeSnapshot:
        if not observed_events:
            raise ValueError("at least one observed event is required")

        current_event = observed_events[-1]
        environment_id = self._latest_non_empty_payload_value(
            observed_events, "target_environment_id"
        )
        actor_id = self._latest_non_empty_payload_value(observed_events, "target_actor_id")
        established_fact_id = self._latest_non_empty_payload_value(
            observed_events, "established_fact_id"
        )

        snapshot = StateTreeSnapshot(
            snapshot_id=f"state_tree:{current_event.room_id}:{sim_tick_ts}",
            schema_version=1,
            producer_system="siming.state_tree",
            room_id=current_event.room_id,
            scene_id=current_event.scene_id,
            zone_id=current_event.zone_id,
            world_ts=current_event.producer_ts,
            sim_tick_ts=sim_tick_ts,
            causation_id=current_event.causation_id,
            correlation_id=current_event.correlation_id,
            environment=StateTreeNode(
                node_id=f"environment:{environment_id or 'unknown'}",
                owner_system="L1/ESM",
                authority="mirror",
                status="fresh" if environment_id else "partial",
                summary={
                    "target_environment_id": environment_id,
                    "established_fact_id": established_fact_id,
                },
            ),
            character=StateTreeNode(
                node_id=f"character:{actor_id or 'unknown'}",
                owner_system="character_agent",
                authority="mirror",
                status="fresh" if actor_id else "partial",
                summary={"target_actor_id": actor_id},
            ),
            storyline=StateTreeNode(
                node_id="storyline:main",
                owner_system="siming",
                authority="editable",
                status="fresh",
                summary={"active_phase": "rising"},
            ),
            group_simulation=GroupSimulationBranchSnapshot(status="unavailable", summary={}),
        )
        self._latest_snapshot = snapshot
        return snapshot

    @property
    def latest_snapshot(self) -> StateTreeSnapshot | None:
        return self._latest_snapshot

    def _optional_payload_value(self, event: ObservedSimingEvent, key: str) -> str | None:
        value = event.payload.get(key)
        if value is None:
            return None
        text = str(value)
        return text or None

    def _latest_non_empty_payload_value(
        self,
        observed_events: list[ObservedSimingEvent],
        key: str,
    ) -> str | None:
        latest_value: str | None = None
        for event in observed_events:
            value = self._optional_payload_value(event, key)
            if value is not None:
                latest_value = value
        return latest_value
