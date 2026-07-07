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
            seed_type=suggested_band,
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
