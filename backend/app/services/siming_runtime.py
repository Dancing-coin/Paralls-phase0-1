from app.models.authority_event import AuthorityEvent
from app.models.siming_event import (
    FairnessStateSnapshot,
    InterventionCandidate,
    SelectedPath,
    SimingAuditRecord,
    SimingInput,
    SimingOutput,
    SimingTickResult,
)
from app.services.siming_feasibility import SimingExecutionFeasibility
from app.services.siming_llm_provider import (
    DisabledSimingLlmCandidateProvider,
    SimingLlmCandidateProvider,
    SimingLlmProviderInvalidOutput,
    SimingLlmProviderTimeout,
)
from app.services.siming_policy import SimingInterventionPolicy


class SimingRuntime:
    def __init__(
        self,
        *,
        llm_provider: SimingLlmCandidateProvider | None = None,
        policy: SimingInterventionPolicy | None = None,
        feasibility: SimingExecutionFeasibility | None = None,
    ) -> None:
        self._llm_provider = llm_provider or DisabledSimingLlmCandidateProvider()
        self._policy = policy or SimingInterventionPolicy()
        self._feasibility = feasibility or SimingExecutionFeasibility()

    def tick(self, inputs: list[SimingInput]) -> SimingTickResult:
        result = SimingTickResult()
        for siming_input in inputs:
            event = siming_input.source_event
            result.outputs.append(self._fairness_snapshot(event))

            if self._is_light_drop(event):
                snapshot = self._fairness_state_snapshot(event)
                llm_candidates, llm_audit = self._llm_candidates_for(event, snapshot)
                if llm_candidates:
                    outputs, audits = self._outputs_for_candidates(event, llm_candidates)
                    result.outputs.extend(outputs)
                    result.audit_records.extend(audits)
                    continue
                if llm_audit:
                    result.outputs.append(self._no_action(event))
                    result.audit_records.extend(llm_audit)
                    continue
                result.outputs.extend(
                    [
                        self._intervention_candidate(event),
                        self._intervention_decision(event, selected_path="visual_fact_path", intervention_band="fact_reveal"),
                        self._visual_fact_dispatch(event),
                    ]
                )
                result.audit_records.append(self._audit(event, status="recorded", reason="visual fact observability requested"))
                continue

            if self._is_environment_attention_event(event):
                result.outputs.append(self._environment_attention_dispatch(event))
                result.audit_records.append(self._audit(event, status="recorded", reason="environment state attention requested"))
                continue

            if event.event_type == "conversation_resolution_event" and self._has_conversation_candidate(event):
                result.outputs.append(self._conversation_fact_reveal(event))
                result.audit_records.append(self._audit(event, status="recorded", reason="conversation candidate fact reveal requested"))
                continue

            if event.event_type == "constraint_state_event":
                reason = str(event.payload.get("constraint_summary", "constraint rejected downstream"))
                result.audit_records.append(self._audit(event, status="esm_rejected", reason=reason))
                continue

            result.outputs.append(self._no_action(event))
            result.audit_records.append(self._audit(event, status="no_action", reason="no eligible intervention"))
        return result

    def _fairness_state_snapshot(self, event: AuthorityEvent) -> FairnessStateSnapshot:
        known_fact_id = str(event.payload.get("established_fact_id", event.event_id))
        target_actor_id = str(event.payload.get("target_actor_id", "char_b") or "char_b")
        return FairnessStateSnapshot(
            snapshot_id=f"fairness:{event.event_id}",
            room_id=event.room_id,
            scene_id=event.scene_id,
            zone_id=event.zone_id,
            causation_id=event.event_id,
            correlation_id=event.correlation_id,
            known_fact_ids=[known_fact_id],
            eligible_actor_ids=[target_actor_id],
            blocked_actor_ids=[],
            recent_intervention_ids=[],
        )

    def _llm_candidates_for(
        self,
        event: AuthorityEvent,
        snapshot: FairnessStateSnapshot,
    ) -> tuple[list[InterventionCandidate], list[SimingAuditRecord]]:
        try:
            return (
                self._llm_provider.generate_candidates(snapshot=snapshot, recent_events=[event], recent_audit=[]),
                [],
            )
        except SimingLlmProviderTimeout:
            return [], [self._audit(event, status="llm_timeout", reason="LLM provider timed out")]
        except (SimingLlmProviderInvalidOutput, ValueError) as exc:
            return [], [self._audit(event, status="llm_invalid_output", reason=str(exc))]

    def _outputs_for_candidates(
        self,
        event: AuthorityEvent,
        candidates: list[InterventionCandidate],
    ) -> tuple[list[SimingOutput], list[SimingAuditRecord]]:
        snapshot = self._fairness_state_snapshot(event)
        audits: list[SimingAuditRecord] = []

        for candidate in candidates:
            policy_result = self._policy.evaluate(candidate, snapshot=snapshot)
            if not policy_result.accepted:
                audits.append(
                    self._audit(
                        event,
                        status="policy_rejected",
                        reason=";".join(policy_result.reasons),
                    )
                )
                continue

            feasibility_result = self._feasibility.evaluate(candidate)
            if not feasibility_result.accepted:
                audits.append(
                    self._audit(
                        event,
                        status="feasibility_rejected",
                        reason=";".join(feasibility_result.reasons),
                    )
                )
                continue

            outputs = [
                self._candidate_output(event, candidate),
                self._decision_output(
                    event,
                    candidate,
                    feasibility_result.selected_path,
                    policy_result.reasons,
                    feasibility_result.reasons,
                ),
                self._dispatch_output(event, candidate, feasibility_result.selected_path),
            ]
            audits.append(self._audit(event, status="recorded", reason="LLM-assisted candidate accepted"))
            return outputs, audits

        audits.append(self._audit(event, status="no_action", reason="no executable llm candidate"))
        return [self._no_action(event)], audits

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

    def _candidate_output(self, event: AuthorityEvent, candidate: InterventionCandidate) -> SimingOutput:
        return SimingOutput(
            output_type="intervention_candidate",
            room_id=event.room_id,
            scene_id=event.scene_id,
            zone_id=event.zone_id,
            causation_id=event.event_id,
            correlation_id=event.correlation_id,
            producer_ts=event.producer_ts + 2,
            payload={
                "candidate_id": candidate.candidate_id,
                "proposed_band": candidate.proposed_band,
                "target_actor_id": candidate.target_actor_id,
                "target_object_id": candidate.target_object_id,
                "target_environment_id": candidate.target_environment_id,
                "established_fact_ids": list(candidate.established_fact_ids),
                "explanation": candidate.explanation,
                "confidence": candidate.confidence,
                "reason_tags": list(candidate.reason_tags),
                "source": candidate.source,
            },
        )

    def _decision_output(
        self,
        event: AuthorityEvent,
        candidate: InterventionCandidate,
        selected_path: SelectedPath,
        policy_reasons: list[str],
        feasibility_reasons: list[str],
    ) -> SimingOutput:
        return SimingOutput(
            output_type="intervention_decision",
            room_id=event.room_id,
            scene_id=event.scene_id,
            zone_id=event.zone_id,
            causation_id=event.event_id,
            correlation_id=event.correlation_id,
            producer_ts=event.producer_ts + 3,
            selected_path=selected_path,
            intervention_band=candidate.proposed_band,
            payload={
                "decision_id": f"decision_{candidate.candidate_id}",
                "candidate_id": candidate.candidate_id,
                "accepted": True,
                "policy_reasons": list(policy_reasons),
                "feasibility_reasons": list(feasibility_reasons),
            },
        )

    def _dispatch_output(
        self,
        event: AuthorityEvent,
        candidate: InterventionCandidate,
        selected_path: SelectedPath,
    ) -> SimingOutput:
        payload = {
            "presentation_hint": candidate.explanation or "surface established fact",
            "target_actor_id": candidate.target_actor_id,
            "target_object_id": candidate.target_object_id,
            "target_environment_id": candidate.target_environment_id,
        }
        if selected_path == "visual_fact_path":
            payload["established_fact_id"] = (
                candidate.established_fact_ids[0]
                if candidate.established_fact_ids
                else str(event.payload.get("established_fact_id", event.event_id))
            )
        return SimingOutput(
            output_type="dispatch_intent",
            room_id=event.room_id,
            scene_id=event.scene_id,
            zone_id=event.zone_id,
            causation_id=event.event_id,
            correlation_id=event.correlation_id,
            producer_ts=event.producer_ts + 4,
            selected_path=selected_path,
            intervention_band=candidate.proposed_band,
            payload=payload,
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
