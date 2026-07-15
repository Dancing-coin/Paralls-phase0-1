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
        self._revision_by_room: dict[str, int] = {}

    def update(self, observed_events: list[ObservedSimingEvent]) -> NarrativeCoreResult:
        if not observed_events:
            raise ValueError("observed_events must contain at least one event")

        event = observed_events[-1]
        room_id = event.room_id
        revision = self._revision_by_room.get(room_id, 0) + 1
        self._revision_by_room[room_id] = revision
        obligations = self._obligations_for_batch(observed_events, revision)
        open_count = self._open_counts_by_room.get(room_id, 0) + len(obligations)
        self._open_counts_by_room[room_id] = open_count
        pressure = self._pressure_for(open_count)
        markers = [
            NarrativeMarker(
                marker_id=f"marker:{room_id}:r{revision}:{index}",
                marker_type=item.obligation_type,
                source_event_id=item.source_event_id,
                target_refs=item.target_refs,
                reason=item.reason,
            )
            for index, item in enumerate(obligations, start=1)
        ]
        state = NarrativeStateSnapshot(
            snapshot_id=f"narrative:{room_id}:ts{event.producer_ts}:r{revision}",
            room_id=room_id,
            scene_id=event.scene_id,
            zone_id=event.zone_id,
            world_ts=event.producer_ts,
            sim_tick_ts=event.producer_ts + revision,
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
        for obligation in obligations:
            obligation.pressure = pressure
        ledger = NarrativeObligationLedger(
            ledger_id=f"ledger:{room_id}:ts{event.producer_ts}:r{revision}",
            room_id=room_id,
            world_ts=event.producer_ts,
            sim_tick_ts=event.producer_ts + revision,
            obligations=obligations,
            causation_id=event.causation_id,
            correlation_id=event.correlation_id,
        )
        return NarrativeCoreResult(
            state=state,
            ledger=ledger,
            seeds=[self._seed_for(state, item) for item in obligations],
        )

    def _obligations_for_batch(
        self,
        observed_events: list[ObservedSimingEvent],
        revision: int,
    ) -> list[NarrativeObligation]:
        obligations: list[NarrativeObligation] = []
        for event in observed_events:
            obligations.extend(self._obligations_for_event(event, revision, len(obligations)))
        return obligations

    def _obligations_for_event(
        self,
        event: ObservedSimingEvent,
        revision: int,
        existing_count: int,
    ) -> list[NarrativeObligation]:
        if event.event_type == "visual_fact_event" and event.payload.get("established_fact_id"):
            refs = self._target_refs(event, "target_actor_id", "target_environment_id", "target_object_id")
            return [
                NarrativeObligation(
                    obligation_id=self._obligation_id(
                        event=event,
                        obligation_type="unresolved_reveal",
                        revision=revision,
                        event_index=existing_count + 1,
                    ),
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
                    obligation_id=self._obligation_id(
                        event=event,
                        obligation_type="constraint_recovery",
                        revision=revision,
                        event_index=existing_count + 1,
                    ),
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
        fact_refs = [obligation.source_event_id] if obligation.obligation_type == "unresolved_reveal" else []
        return InterventionSeed(
            seed_id=f"seed:{obligation.obligation_id}",
            seed_type=suggested_band,
            basis_snapshot_ref=state.snapshot_id,
            basis_obligation_refs=[obligation.obligation_id],
            basis_fact_refs=fact_refs,
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

    def _obligation_id(
        self,
        *,
        event: ObservedSimingEvent,
        obligation_type: str,
        revision: int,
        event_index: int,
    ) -> str:
        return f"obligation:{event.room_id}:r{revision}:e{event_index}:{event.source_event_id}:{obligation_type}"
