from app.models.authority_event import AuthorityEvent
from app.models.siming_event import SimingAuditRecord, SimingInput, SimingOutput, SimingTickResult


class SimingRuntime:
    def tick(self, inputs: list[SimingInput]) -> SimingTickResult:
        result = SimingTickResult()
        for siming_input in inputs:
            event = siming_input.source_event
            result.outputs.append(self._fairness_snapshot(event))

            if self._is_light_drop(event):
                result.outputs.extend(
                    [
                        self._intervention_candidate(event),
                        self._intervention_decision(event, selected_path="visual_fact_path", intervention_band="fact_reveal"),
                        self._visual_fact_dispatch(event),
                    ]
                )
                result.audit_records.append(self._audit(event, status="recorded", reason="visual fact observability requested"))
                continue

            if event.event_type == "constraint_state_event":
                reason = str(event.payload.get("constraint_summary", "constraint rejected downstream"))
                result.audit_records.append(self._audit(event, status="esm_rejected", reason=reason))
                continue

            result.outputs.append(self._no_action(event))
            result.audit_records.append(self._audit(event, status="no_action", reason="no eligible intervention"))
        return result

    def _fairness_snapshot(self, event: AuthorityEvent) -> SimingOutput:
        return SimingOutput(
            output_type="fairness_snapshot",
            room_id=event.room_id,
            scene_id=event.scene_id,
            zone_id=event.zone_id,
            causation_id=event.event_id,
            correlation_id=event.correlation_id,
            producer_ts=event.producer_ts + 1,
            payload={"source_event_id": event.event_id},
        )

    def _intervention_candidate(self, event: AuthorityEvent) -> SimingOutput:
        return SimingOutput(
            output_type="intervention_candidate",
            room_id=event.room_id,
            scene_id=event.scene_id,
            zone_id=event.zone_id,
            causation_id=event.event_id,
            correlation_id=event.correlation_id,
            producer_ts=event.producer_ts + 2,
            payload={"candidate_id": f"candidate_{event.event_id}"},
        )

    def _intervention_decision(self, event: AuthorityEvent, *, selected_path: str, intervention_band: str) -> SimingOutput:
        return SimingOutput(
            output_type="intervention_decision",
            room_id=event.room_id,
            scene_id=event.scene_id,
            zone_id=event.zone_id,
            causation_id=event.event_id,
            correlation_id=event.correlation_id,
            producer_ts=event.producer_ts + 3,
            selected_path=selected_path,
            intervention_band=intervention_band,
            payload={"decision_id": f"decision_{event.event_id}"},
        )

    def _visual_fact_dispatch(self, event: AuthorityEvent) -> SimingOutput:
        established_fact_id = str(event.payload.get("established_fact_id", event.event_id))
        return SimingOutput(
            output_type="dispatch_intent",
            room_id=event.room_id,
            scene_id=event.scene_id,
            zone_id=event.zone_id,
            causation_id=event.event_id,
            correlation_id=event.correlation_id,
            producer_ts=event.producer_ts + 4,
            selected_path="visual_fact_path",
            intervention_band="fact_reveal",
            payload={
                "established_fact_id": established_fact_id,
                "presentation_hint": "increase observability for established light change",
            },
        )

    def _no_action(self, event: AuthorityEvent) -> SimingOutput:
        return SimingOutput(
            output_type="no_action",
            room_id=event.room_id,
            scene_id=event.scene_id,
            zone_id=event.zone_id,
            causation_id=event.event_id,
            correlation_id=event.correlation_id,
            producer_ts=event.producer_ts + 1,
            selected_path="no_action",
            intervention_band="none",
            payload={"reason": "no eligible intervention"},
        )

    def _audit(self, event: AuthorityEvent, *, status: str, reason: str) -> SimingAuditRecord:
        return SimingAuditRecord(
            audit_id=f"audit_{event.event_id}_{status}",
            room_id=event.room_id,
            correlation_id=event.correlation_id,
            causation_id=event.event_id,
            source_event_id=event.event_id,
            status=status,
            reason=reason,
        )

    def _is_light_drop(self, event: AuthorityEvent) -> bool:
        return event.event_type == "visual_fact_event" and event.payload.get("fact_type") == "light_level_drop"
