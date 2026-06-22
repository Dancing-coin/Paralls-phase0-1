from app.models.authority_event import AuthorityEvent
from app.models.siming_event import (
    FairnessStateSnapshot,
    InterventionCandidate,
    SimingAuditRecord,
    SimingInput,
    SimingOutput,
    SimingTickResult,
)
from app.models.siming_runtime_state import ProjectionRunSnapshot, StateTreeSnapshot, StorylineStateSnapshot
from app.services.siming_fact_core import SimingFactCore
from app.services.siming_fairness_audit import SimingFairnessAuditEngine
from app.services.siming_feature_registry import SimingFeatureRegistry
from app.services.siming_feasibility import SimingExecutionFeasibility
from app.services.siming_llm_provider import (
    DisabledSimingLlmCandidateProvider,
    SimingLlmCandidateProvider,
    SimingLlmProviderInvalidOutput,
    SimingLlmProviderTimeout,
)
from app.services.siming_observe import SimingObservePipeline
from app.services.siming_policy import SimingInterventionPolicy
from app.services.siming_projection import (
    GroupSimulationBridgePort,
    StorylineProjectionPort,
    StubGroupSimulationBridge,
    StubStorylineProjection,
)
from app.services.siming_read_model import SimingReadModelBuilder
from app.services.siming_state_tree import InMemorySimingStateTree
from app.services.siming_storyline import InMemoryNarrativeObligationLedger, InMemoryStorylineState


class SimingRuntime:
    def __init__(
        self,
        *,
        feature_registry: SimingFeatureRegistry | None = None,
        llm_provider: SimingLlmCandidateProvider | None = None,
        policy: SimingInterventionPolicy | None = None,
        feasibility: SimingExecutionFeasibility | None = None,
        observe_pipeline: SimingObservePipeline | None = None,
        fact_core: SimingFactCore | None = None,
        state_tree: InMemorySimingStateTree | None = None,
        fairness_audit: SimingFairnessAuditEngine | None = None,
        storyline_state: InMemoryStorylineState | None = None,
        obligation_ledger: InMemoryNarrativeObligationLedger | None = None,
        storyline_projection: StorylineProjectionPort | None = None,
        group_bridge: GroupSimulationBridgePort | None = None,
        read_model_builder: SimingReadModelBuilder | None = None,
    ) -> None:
        self._feature_registry = feature_registry or SimingFeatureRegistry()
        self._llm_provider = llm_provider or DisabledSimingLlmCandidateProvider()
        self._policy = policy or SimingInterventionPolicy(feature_registry=self._feature_registry)
        self._feasibility = feasibility or SimingExecutionFeasibility()
        self._observe_pipeline = observe_pipeline or SimingObservePipeline()
        self._fact_core = fact_core or SimingFactCore()
        self._state_tree = state_tree or InMemorySimingStateTree()
        self._fairness_audit = fairness_audit or SimingFairnessAuditEngine(self._feature_registry)
        self._storyline_state = storyline_state or InMemoryStorylineState()
        self._obligation_ledger = obligation_ledger or InMemoryNarrativeObligationLedger()
        self._storyline_projection = storyline_projection or StubStorylineProjection()
        self._group_bridge = group_bridge or StubGroupSimulationBridge()
        self._read_model_builder = read_model_builder or SimingReadModelBuilder()

    def tick(self, inputs: list[SimingInput]) -> SimingTickResult:
        result = SimingTickResult()
        for siming_input in inputs:
            event = siming_input.source_event
            observed = self._observe_pipeline.observe([event])
            if not observed:
                continue

            fact_result = self._fact_core.evaluate(observed)
            if not fact_result.accepted:
                result.outputs.append(self._no_action(event))
                result.audit_records.append(
                    self._audit(
                        event,
                        status="no_action",
                        reason=f"fact_veto:{fact_result.veto_reason}",
                    )
                )
                continue

            state_tree = self._state_tree.update_from_observed(
                observed,
                sim_tick_ts=event.producer_ts + 1,
            )
            state_tree.group_simulation = self._group_bridge.summarize(room_id=event.room_id)
            fairness_snapshot = self._fairness_audit.build_snapshot(state_tree)
            storyline = self._storyline_state.update_from_state_tree(state_tree)
            ledger = self._obligation_ledger.update_from_storyline(storyline)
            projection = self._storyline_projection.project(
                state_tree=state_tree,
                fairness=fairness_snapshot,
                storyline=storyline,
                ledger=ledger,
            )

            result.outputs.append(self._fairness_snapshot(event))

            if self._is_light_drop(event):
                policy_snapshot = self._policy_snapshot_for_event(event, fairness_snapshot)
                llm_candidates, llm_audit = self._llm_candidates_for(event, policy_snapshot)
                if llm_candidates:
                    outputs, audits = self._outputs_for_candidates(
                        event,
                        llm_candidates,
                        snapshot=policy_snapshot,
                    )
                    result.outputs.extend(outputs)
                    result.audit_records.extend(audits)
                    self._finalize_tick_state(
                        result,
                        state_tree=state_tree,
                        fairness_snapshot=fairness_snapshot,
                        storyline=storyline,
                        projection=projection,
                    )
                    continue
                if llm_audit:
                    result.outputs.append(self._no_action(event))
                    result.audit_records.extend(llm_audit)
                    self._finalize_tick_state(
                        result,
                        state_tree=state_tree,
                        fairness_snapshot=fairness_snapshot,
                        storyline=storyline,
                        projection=projection,
                    )
                    continue
                result.outputs.extend(
                    [
                        self._intervention_candidate(event),
                        self._intervention_decision(
                            event,
                            selected_path="visual_fact_path",
                            intervention_band="fact_reveal",
                        ),
                        self._visual_fact_dispatch(event),
                    ]
                )
                result.audit_records.append(
                    self._audit(
                        event,
                        status="recorded",
                        reason="visual fact observability requested",
                    )
                )
                self._finalize_tick_state(
                    result,
                    state_tree=state_tree,
                    fairness_snapshot=fairness_snapshot,
                    storyline=storyline,
                    projection=projection,
                )
                continue

            if self._is_environment_attention_event(event):
                result.outputs.append(self._environment_attention_dispatch(event))
                result.audit_records.append(
                    self._audit(
                        event,
                        status="recorded",
                        reason="environment state attention requested",
                    )
                )
                self._finalize_tick_state(
                    result,
                    state_tree=state_tree,
                    fairness_snapshot=fairness_snapshot,
                    storyline=storyline,
                    projection=projection,
                )
                continue

            if event.event_type == "conversation_resolution_event" and self._has_conversation_candidate(event):
                result.outputs.append(self._conversation_fact_reveal(event))
                result.audit_records.append(
                    self._audit(
                        event,
                        status="recorded",
                        reason="conversation candidate fact reveal requested",
                    )
                )
                self._finalize_tick_state(
                    result,
                    state_tree=state_tree,
                    fairness_snapshot=fairness_snapshot,
                    storyline=storyline,
                    projection=projection,
                )
                continue

            if event.event_type == "constraint_state_event":
                reason = str(event.payload.get("constraint_summary", "constraint rejected downstream"))
                result.audit_records.append(self._audit(event, status="esm_rejected", reason=reason))
                self._finalize_tick_state(
                    result,
                    state_tree=state_tree,
                    fairness_snapshot=fairness_snapshot,
                    storyline=storyline,
                    projection=projection,
                )
                continue

            result.outputs.append(self._no_action(event))
            result.audit_records.append(
                self._audit(event, status="no_action", reason="no eligible intervention")
            )
            self._finalize_tick_state(
                result,
                state_tree=state_tree,
                fairness_snapshot=fairness_snapshot,
                storyline=storyline,
                projection=projection,
            )
        return result

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
        *,
        snapshot: FairnessStateSnapshot,
    ) -> tuple[list[SimingOutput], list[SimingAuditRecord]]:
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
        selected_path: str,
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
        selected_path: str,
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
        selected_path = "character_input_path" if target_actor_id else "visual_fact_path"
        payload = {
            "presentation_hint": f"watch {target_label}",
            "target_actor_id": target_actor_id,
            "target_object_id": target_object_id,
            "target_environment_id": target_environment_id,
        }
        if selected_path == "visual_fact_path":
            payload["established_fact_id"] = str(
                event.payload.get("candidate_ref") or event.payload.get("event_id") or event.event_id
            )
        return SimingOutput(
            output_type="dispatch_intent",
            room_id=event.room_id,
            scene_id=event.scene_id,
            zone_id=event.zone_id,
            causation_id=event.event_id,
            correlation_id=event.correlation_id,
            producer_ts=event.producer_ts + 1,
            selected_path=selected_path,
            intervention_band="fact_reveal",
            payload=payload,
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

    def _finalize_tick_state(
        self,
        result: SimingTickResult,
        *,
        state_tree: StateTreeSnapshot,
        fairness_snapshot: FairnessStateSnapshot,
        storyline: StorylineStateSnapshot,
        projection: ProjectionRunSnapshot,
    ) -> None:
        result.checkpoints.append(
            self._read_model_builder.build_checkpoint(
                state_tree=state_tree,
                fairness=fairness_snapshot,
                storyline=storyline,
            )
        )
        result.read_model = self._read_model_builder.build_read_model(
            state_tree=state_tree,
            fairness=fairness_snapshot,
            storyline=storyline,
            projection=projection,
            audit_records=result.audit_records,
        )

    def _policy_snapshot_for_event(
        self,
        event: AuthorityEvent,
        snapshot: FairnessStateSnapshot,
    ) -> FairnessStateSnapshot:
        if snapshot.eligible_actor_ids or not self._is_light_drop(event):
            return snapshot
        return snapshot.model_copy(update={"eligible_actor_ids": ["char_b"]})

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
