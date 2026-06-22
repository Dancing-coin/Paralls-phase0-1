from app.models.authority_event import AuthorityEvent
from app.models.siming_event import SimingAuditRecord, SimingInput, SimingOutput, SimingTickResult
from app.services.siming_debug_projection import SimingDebugProjection


class SimingRuntime:
    def __init__(self) -> None:
        self._observatory_projection = SimingDebugProjection()
        self._pending_observatory_messages: list[dict[str, object]] = []

    def tick(self, inputs: list[SimingInput]) -> SimingTickResult:
        result = SimingTickResult()
        for siming_input in inputs:
            event = siming_input.source_event
            fairness_output = self._fairness_snapshot(event)
            result.outputs.append(fairness_output)
            self._queue_snapshot(
                source_event=event,
                fairness_summary=self._fairness_summary_for(event),
                intervention_candidate="",
                intervention_decision="reviewing",
                selected_path="no_action",
                intervention_band="none",
                target_ref=self._target_ref_for(event),
                reason_summary="",
                downstream_status="reviewing",
                no_action_reason="",
            )
            self._queue_event(
                source_event=event,
                stage="fairness_snapshot",
                summary=self._fairness_summary_for(event),
                selected_path="no_action",
                intervention_band="none",
                target_ref=self._target_ref_for(event),
                reason_summary="",
                downstream_status="reviewing",
                no_action_reason="",
            )

            if self._is_light_drop(event):
                candidate_summary = self._candidate_summary_for(event)
                decision_summary = self._decision_summary_for(event, selected_path="visual_fact_path", intervention_band="fact_reveal")
                result.outputs.extend(
                    [
                        self._intervention_candidate(event),
                        self._intervention_decision(event, selected_path="visual_fact_path", intervention_band="fact_reveal"),
                        self._visual_fact_dispatch(event),
                    ]
                )
                self._queue_event(
                    source_event=event,
                    stage="intervention_candidate",
                    summary=candidate_summary,
                    selected_path="visual_fact_path",
                    intervention_band="fact_reveal",
                    target_ref=self._target_ref_for(event),
                    reason_summary="visibility imbalance detected",
                    downstream_status="candidate_created",
                    no_action_reason="",
                )
                self._queue_snapshot(
                    source_event=event,
                    fairness_summary=self._fairness_summary_for(event),
                    intervention_candidate=candidate_summary,
                    intervention_decision=decision_summary,
                    selected_path="visual_fact_path",
                    intervention_band="fact_reveal",
                    target_ref=self._target_ref_for(event),
                    reason_summary="make the light drop legible to the cast",
                    downstream_status="published",
                    no_action_reason="",
                )
                self._queue_event(
                    source_event=event,
                    stage="intervention_decision",
                    summary=decision_summary,
                    selected_path="visual_fact_path",
                    intervention_band="fact_reveal",
                    target_ref=self._target_ref_for(event),
                    reason_summary="make the light drop legible to the cast",
                    downstream_status="published",
                    no_action_reason="",
                )
                self._queue_event(
                    source_event=event,
                    stage="dispatch_finalized",
                    summary="visual observability dispatch published",
                    selected_path="visual_fact_path",
                    intervention_band="fact_reveal",
                    target_ref=self._target_ref_for(event),
                    reason_summary="make the light drop legible to the cast",
                    downstream_status="published",
                    no_action_reason="",
                )
                result.audit_records.append(self._audit(event, status="recorded", reason="visual fact observability requested"))
                continue

            if self._is_environment_attention_event(event):
                dispatch = self._environment_attention_dispatch(event)
                result.outputs.append(dispatch)
                self._queue_event(
                    source_event=event,
                    stage="dispatch_finalized",
                    summary="environment attention dispatch published",
                    selected_path="character_input_path",
                    intervention_band="fact_reveal",
                    target_ref=self._target_ref_for(event),
                    reason_summary="environment state attention requested",
                    downstream_status="published",
                    no_action_reason="",
                )
                self._queue_snapshot(
                    source_event=event,
                    fairness_summary=self._fairness_summary_for(event),
                    intervention_candidate=self._candidate_summary_for(event),
                    intervention_decision=self._decision_summary_for(event, selected_path="character_input_path", intervention_band="fact_reveal"),
                    selected_path="character_input_path",
                    intervention_band="fact_reveal",
                    target_ref=self._target_ref_for(event),
                    reason_summary="environment state attention requested",
                    downstream_status="published",
                    no_action_reason="",
                )
                result.audit_records.append(self._audit(event, status="recorded", reason="environment state attention requested"))
                continue

            if event.event_type == "conversation_resolution_event" and self._has_conversation_candidate(event):
                dispatch = self._conversation_fact_reveal(event)
                result.outputs.append(dispatch)
                self._queue_event(
                    source_event=event,
                    stage="dispatch_finalized",
                    summary="conversation fact reveal published",
                    selected_path="character_input_path",
                    intervention_band="fact_reveal",
                    target_ref=self._target_ref_for(event),
                    reason_summary="conversation candidate fact reveal requested",
                    downstream_status="published",
                    no_action_reason="",
                )
                self._queue_snapshot(
                    source_event=event,
                    fairness_summary=self._fairness_summary_for(event),
                    intervention_candidate=self._candidate_summary_for(event),
                    intervention_decision=self._decision_summary_for(event, selected_path="character_input_path", intervention_band="fact_reveal"),
                    selected_path="character_input_path",
                    intervention_band="fact_reveal",
                    target_ref=self._target_ref_for(event),
                    reason_summary="conversation candidate fact reveal requested",
                    downstream_status="published",
                    no_action_reason="",
                )
                result.audit_records.append(self._audit(event, status="recorded", reason="conversation candidate fact reveal requested"))
                continue

            if event.event_type == "constraint_state_event":
                reason = str(event.payload.get("constraint_summary", "constraint rejected downstream"))
                self._queue_snapshot(
                    source_event=event,
                    fairness_summary=self._fairness_summary_for(event),
                    intervention_candidate="",
                    intervention_decision="no_action",
                    selected_path="no_action",
                    intervention_band="none",
                    target_ref=self._target_ref_for(event),
                    reason_summary=reason,
                    downstream_status="esm_rejected",
                    no_action_reason=reason,
                )
                self._queue_event(
                    source_event=event,
                    stage="no_action",
                    summary="siming declined after downstream rejection",
                    selected_path="no_action",
                    intervention_band="none",
                    target_ref=self._target_ref_for(event),
                    reason_summary=reason,
                    downstream_status="esm_rejected",
                    no_action_reason=reason,
                )
                result.audit_records.append(self._audit(event, status="esm_rejected", reason=reason))
                continue

            result.outputs.append(self._no_action(event))
            self._queue_snapshot(
                source_event=event,
                fairness_summary=self._fairness_summary_for(event),
                intervention_candidate="",
                intervention_decision="no_action",
                selected_path="no_action",
                intervention_band="none",
                target_ref=self._target_ref_for(event),
                reason_summary="",
                downstream_status="audit_only",
                no_action_reason="no eligible intervention",
            )
            self._queue_event(
                source_event=event,
                stage="no_action",
                summary="siming declined to intervene",
                selected_path="no_action",
                intervention_band="none",
                target_ref=self._target_ref_for(event),
                reason_summary="",
                downstream_status="audit_only",
                no_action_reason="no eligible intervention",
            )
            result.audit_records.append(self._audit(event, status="no_action", reason="no eligible intervention"))
        return result

    def drain_observatory_messages(self) -> list[dict[str, object]]:
        messages = self._pending_observatory_messages
        self._pending_observatory_messages = []
        return messages

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
                "target_actor_id": "char_b",
                "target_environment_id": event.payload.get("target_environment_id"),
            },
        )

    def _environment_attention_dispatch(self, event: AuthorityEvent) -> SimingOutput:
        target_environment_id = event.payload.get("target_environment_id")
        target_object_id = event.payload.get("target_object_id")
        target_label = target_environment_id or target_object_id or event.payload.get("entity_id") or "world state"
        return SimingOutput(
            output_type="dispatch_intent",
            room_id=event.room_id,
            scene_id=event.scene_id,
            zone_id=event.zone_id,
            causation_id=event.event_id,
            correlation_id=event.correlation_id,
            producer_ts=event.producer_ts + 1,
            selected_path="character_input_path",
            intervention_band="fact_reveal",
            payload={
                "presentation_hint": f"notice change around {target_label}",
                "target_actor_id": "char_b",
                "target_environment_id": target_environment_id,
                "target_object_id": target_object_id,
            },
        )

    def _conversation_fact_reveal(self, event: AuthorityEvent) -> SimingOutput:
        target_actor_id = self._first_payload_entry(event, "candidate_actor_ids")
        target_object_id = self._first_payload_entry(event, "candidate_object_ids")
        target_environment_id = self._first_payload_entry(event, "candidate_environment_ids")
        target_label = target_actor_id or target_object_id or target_environment_id or event.source.actor_id or "candidate"
        return SimingOutput(
            output_type="dispatch_intent",
            room_id=event.room_id,
            scene_id=event.scene_id,
            zone_id=event.zone_id,
            causation_id=event.event_id,
            correlation_id=event.correlation_id,
            producer_ts=event.producer_ts + 1,
            selected_path="character_input_path",
            intervention_band="fact_reveal",
            payload={
                "presentation_hint": f"watch {target_label}",
                "target_actor_id": target_actor_id,
                "target_object_id": target_object_id,
                "target_environment_id": target_environment_id,
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

    def _is_environment_attention_event(self, event: AuthorityEvent) -> bool:
        if event.event_type != "esm_result_event":
            return False
        return event.payload.get("result_type") == "environment_state_result" and bool(event.payload.get("target_environment_id"))

    def _has_conversation_candidate(self, event: AuthorityEvent) -> bool:
        return any(
            self._first_payload_entry(event, field) is not None
            for field in ("candidate_actor_ids", "candidate_object_ids", "candidate_environment_ids")
        )

    def _first_payload_entry(self, event: AuthorityEvent, field: str) -> str | None:
        value = event.payload.get(field)
        if not isinstance(value, list) or not value:
            return None
        first = value[0]
        if first is None:
            return None
        text = str(first)
        return text or None

    def _target_ref_for(self, event: AuthorityEvent) -> str:
        for key in ("target_actor_id", "target_object_id", "target_environment_id", "entity_id"):
            value = str(event.payload.get(key, "") or "")
            if value != "":
                return value
        if event.source.actor_id:
            return event.source.actor_id
        return ""

    def _fairness_summary_for(self, event: AuthorityEvent) -> str:
        if event.event_type == "visual_fact_event":
            return "visibility imbalance detected around %s" % (self._target_ref_for(event) or "scene")
        return "scene balance reviewed for %s" % (event.event_type or "event")

    def _candidate_summary_for(self, event: AuthorityEvent) -> str:
        return "candidate for %s" % (self._target_ref_for(event) or event.event_type)

    def _decision_summary_for(self, event: AuthorityEvent, *, selected_path: str, intervention_band: str) -> str:
        return "%s via %s" % (intervention_band or "none", selected_path or "no_action")

    def _queue_snapshot(
        self,
        *,
        source_event: AuthorityEvent,
        fairness_summary: str,
        intervention_candidate: str,
        intervention_decision: str,
        selected_path: str,
        intervention_band: str,
        target_ref: str,
        reason_summary: str,
        downstream_status: str,
        no_action_reason: str,
    ) -> None:
        snapshot = self._observatory_projection.project_snapshot(
            source_event=source_event,
            fairness_summary=fairness_summary,
            intervention_candidate=intervention_candidate,
            intervention_decision=intervention_decision,
            selected_path=selected_path,
            intervention_band=intervention_band,
            target_ref=target_ref,
            reason_summary=reason_summary,
            downstream_status=downstream_status,
            no_action_reason=no_action_reason,
        )
        self._pending_observatory_messages.append(
            {
                "message_type": "siming_debug_snapshot",
                "payload": snapshot.model_dump(exclude_none=True),
            }
        )

    def _queue_event(
        self,
        *,
        source_event: AuthorityEvent,
        stage: str,
        summary: str,
        selected_path: str,
        intervention_band: str,
        target_ref: str,
        reason_summary: str,
        downstream_status: str,
        no_action_reason: str,
    ) -> None:
        event = self._observatory_projection.project_event(
            source_event=source_event,
            stage=stage,
            summary=summary,
            selected_path=selected_path,
            intervention_band=intervention_band,
            target_ref=target_ref,
            reason_summary=reason_summary,
            downstream_status=downstream_status,
            no_action_reason=no_action_reason,
        )
        self._pending_observatory_messages.append(
            {
                "message_type": "siming_debug_event",
                "payload": event.model_dump(exclude_none=True),
            }
        )
