from app.models.authority_event import AuthorityEvent
from app.models.siming_event import (
    FairnessStateSnapshot,
    InterventionCandidate,
    SimingAuditRecord,
    SimingInput,
    SimingOutput,
    SimingTickResult,
)
from app.services.authority_event_bus import AuthorityRecoveryLedger
from app.models.siming_narrative import NarrativeCoreResult
from app.models.siming_runtime_state import (
    ProjectionRunSnapshot,
    StateTreeSnapshot,
    StorylineStateSnapshot,
)
from app.services.siming_fact_core import SimingFactCore
from app.services.siming_fairness_audit import SimingFairnessAuditEngine
from app.services.siming_feature_registry import SimingFeatureRegistry
from app.services.siming_feasibility import SimingExecutionFeasibility
from app.services.siming_intervention_guardrails import (
    GuardrailResult,
    SimingInterventionGuardrails,
)
from app.services.siming_llm_provider import (
    DisabledSimingLlmCandidateProvider,
    SimingLlmCandidateProvider,
    SimingLlmProviderInvalidOutput,
    SimingLlmProviderTimeout,
)
from app.services.siming_narrative_core import SimingNarrativeCore
from app.services.siming_observe import SimingObservePipeline
from app.services.siming_policy import SimingInterventionPolicy
from app.services.siming_projection import (
    GroupSimulationBridgePort,
    StorylineProjectionPort,
    StubGroupSimulationBridge,
    StubStorylineProjection,
)
from app.services.siming_quality_monitor import (
    QualityMonitorResult,
    SimingQualityMonitor,
)
from app.services.siming_read_model import (
    SimingReadModelBuilder,
    perception_identity_from_bundle,
)
from app.services.siming_state_tree import InMemorySimingStateTree
from app.services.siming_storyline import (
    InMemoryNarrativeObligationLedger,
    InMemoryStorylineState,
)
from app.services.siming_debug_projection import SimingDebugProjection
from app.world_runtime.intelligence_upgrade import CanonicalPerceptBundle
from app.services.siming_heavenly_runtime_support import SimingHeavenlyRuntimeSupport
from app.models.siming_resource_capability import StagingRequest
from app.services.siming_story_projection import SimingStoryProjection
from app.services.behavior_turn_recorder import BehaviorTurnRecorder
from app.models.behavior_turn import BehaviorTurnRecordRequest, BehaviorTurnStageRecord
from app.models.siming_heavenly_graph import GraphProvenance, GraphRevisionVector, HeavenlyGraphScope


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
        narrative_core: SimingNarrativeCore | None = None,
        quality_monitor: SimingQualityMonitor | None = None,
        intervention_guardrails: SimingInterventionGuardrails | None = None,
        storyline_state: InMemoryStorylineState | None = None,
        obligation_ledger: InMemoryNarrativeObligationLedger | None = None,
        storyline_projection: StorylineProjectionPort | None = None,
        group_bridge: GroupSimulationBridgePort | None = None,
        read_model_builder: SimingReadModelBuilder | None = None,
        heavenly_support: SimingHeavenlyRuntimeSupport | None = None,
        behavior_turn_recorder: BehaviorTurnRecorder | None = None,
        behavior_turn_scope_resolver: object | None = None,
    ) -> None:
        self._feature_registry = feature_registry or SimingFeatureRegistry()
        self._llm_provider = llm_provider or DisabledSimingLlmCandidateProvider()
        self._policy = policy or SimingInterventionPolicy(
            feature_registry=self._feature_registry
        )
        self._feasibility = feasibility or SimingExecutionFeasibility()
        self._observe_pipeline = observe_pipeline or SimingObservePipeline()
        self._fact_core = fact_core or SimingFactCore()
        self._state_tree = state_tree or InMemorySimingStateTree()
        self._fairness_audit = fairness_audit or SimingFairnessAuditEngine(
            self._feature_registry
        )
        self._narrative_core = narrative_core or SimingNarrativeCore()
        self._quality_monitor = quality_monitor or SimingQualityMonitor(
            feature_registry=self._feature_registry
        )
        self._intervention_guardrails = (
            intervention_guardrails or SimingInterventionGuardrails()
        )
        self._storyline_state = storyline_state or InMemoryStorylineState()
        self._obligation_ledger = (
            obligation_ledger or InMemoryNarrativeObligationLedger()
        )
        self._storyline_projection = storyline_projection or StubStorylineProjection()
        self._group_bridge = group_bridge or StubGroupSimulationBridge()
        self._read_model_builder = read_model_builder or SimingReadModelBuilder()
        self._heavenly_support = heavenly_support
        self._behavior_turn_recorder = behavior_turn_recorder
        self._behavior_turn_scope_resolver = behavior_turn_scope_resolver
        self._heavenly_story_projection = SimingStoryProjection()
        self._observatory_projection = SimingDebugProjection()
        self._pending_observatory_messages: list[dict[str, object]] = []
        self._active_turn_event: AuthorityEvent | None = None
        self._active_turn_prepared: object | None = None

    @property
    def heavenly_support(self) -> SimingHeavenlyRuntimeSupport | None:
        return self._heavenly_support

    def tick(self, inputs: list[SimingInput]) -> SimingTickResult:
        result = SimingTickResult()
        for siming_input in inputs:
            event = siming_input.source_event
            self._active_turn_event = event
            if siming_input.input_type == "siming_staging_ack":
                self._process_staging_ack(event, result)
                continue
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

            prepared = (
                self._heavenly_support.prepare(siming_input)
                if self._heavenly_support is not None
                else None
            )
            self._active_turn_prepared = prepared
            if (
                prepared is not None
                and prepared.mode == "active"
                and prepared.owns_event_family
            ):
                self._project_graph_owned_context(event, prepared, result)
                outputs, audits = self._process_graph_owned_event(event, prepared)
                result.outputs.extend(outputs)
                result.audit_records.extend(audits)
                self._record_behavior_turn(event, prepared, result)
                continue
            if prepared is not None and prepared.mode == "shadow":
                result.audit_records.append(
                    self._audit(event, status="recorded", reason="shadow_recorded")
                )

            state_tree = self._state_tree.update_from_observed(
                observed,
                sim_tick_ts=event.producer_ts + 1,
            )
            state_tree.group_simulation = self._group_bridge.summarize(
                room_id=event.room_id
            )
            narrative = self._narrative_core.update(observed)
            quality = self._quality_monitor.evaluate(
                state_tree=state_tree, narrative=narrative
            )
            fairness_snapshot = quality.snapshot
            storyline = self._storyline_state.update_from_state_tree(state_tree)
            ledger = self._obligation_ledger.update_from_storyline(storyline)
            projection = self._storyline_projection.project(
                state_tree=state_tree,
                fairness=fairness_snapshot,
                storyline=storyline,
                ledger=ledger,
            )
            guardrail_results = [
                self._intervention_guardrails.evaluate_seed(
                    seed, snapshot=fairness_snapshot
                )
                for seed in narrative.seeds
            ]
            result.checkpoints.append(
                self._read_model_builder.build_checkpoint(
                    state_tree=state_tree,
                    fairness=fairness_snapshot,
                    storyline=storyline,
                    checkpoint_type="pre_decision",
                )
            )
            narrative_summary = self._narrative_summary_for(narrative)
            quality_summary = self._quality_summary_for(quality)
            guardrail_summary = self._guardrail_summary_for(guardrail_results)
            guardrail_rejection_reason = self._guardrail_rejection_reason(
                guardrail_results
            )

            if self._is_light_drop(event):
                if guardrail_rejection_reason is not None:
                    result.outputs.append(
                        self._no_action(event, reason=guardrail_rejection_reason)
                    )
                    result.audit_records.append(
                        self._audit(
                            event, status="no_action", reason=guardrail_rejection_reason
                        )
                    )
                    self._queue_snapshot(
                        source_event=event,
                        fairness_summary=self._fairness_summary_for(event),
                        intervention_candidate="",
                        intervention_decision="no_action",
                        selected_path="no_action",
                        intervention_band="none",
                        target_ref=self._target_ref_for(event),
                        reason_summary=guardrail_rejection_reason,
                        downstream_status="guardrail_rejected",
                        no_action_reason=guardrail_rejection_reason,
                    )
                    self._queue_event(
                        source_event=event,
                        stage="no_action",
                        summary="siming guardrails rejected narrative seed",
                        selected_path="no_action",
                        intervention_band="none",
                        target_ref=self._target_ref_for(event),
                        reason_summary=guardrail_rejection_reason,
                        downstream_status="guardrail_rejected",
                        no_action_reason=guardrail_rejection_reason,
                    )
                    self._finalize_tick_state(
                        result,
                        state_tree=state_tree,
                        fairness_snapshot=fairness_snapshot,
                        storyline=storyline,
                        projection=projection,
                        narrative_summary=narrative_summary,
                        quality_summary=quality_summary,
                        guardrail_summary=guardrail_summary,
                    )
                    continue
                policy_snapshot = self._policy_snapshot_for_event(
                    event, fairness_snapshot
                )
                llm_candidates, llm_audit = self._llm_candidates_for(
                    event, policy_snapshot
                )
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
                        narrative_summary=narrative_summary,
                        quality_summary=quality_summary,
                        guardrail_summary=guardrail_summary,
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
                        narrative_summary=narrative_summary,
                        quality_summary=quality_summary,
                        guardrail_summary=guardrail_summary,
                    )
                    continue
                candidate_summary = self._candidate_summary_for(event)
                decision_summary = self._decision_summary_for(
                    event,
                    selected_path="visual_fact_path",
                    intervention_band="fact_reveal",
                )
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
                    narrative_summary=narrative_summary,
                    quality_summary=quality_summary,
                    guardrail_summary=guardrail_summary,
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
                    intervention_decision=self._decision_summary_for(
                        event,
                        selected_path="character_input_path",
                        intervention_band="fact_reveal",
                    ),
                    selected_path="character_input_path",
                    intervention_band="fact_reveal",
                    target_ref=self._target_ref_for(event),
                    reason_summary="environment state attention requested",
                    downstream_status="published",
                    no_action_reason="",
                )
                self._finalize_tick_state(
                    result,
                    state_tree=state_tree,
                    fairness_snapshot=fairness_snapshot,
                    storyline=storyline,
                    projection=projection,
                    narrative_summary=narrative_summary,
                    quality_summary=quality_summary,
                    guardrail_summary=guardrail_summary,
                )
                continue

            if (
                event.event_type == "conversation_resolution_event"
                and self._has_conversation_candidate(event)
            ):
                result.outputs.append(self._conversation_fact_reveal(event))
                result.audit_records.append(
                    self._audit(
                        event,
                        status="recorded",
                        reason="conversation candidate fact reveal requested",
                    )
                )
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
                    intervention_decision=self._decision_summary_for(
                        event,
                        selected_path="character_input_path",
                        intervention_band="fact_reveal",
                    ),
                    selected_path="character_input_path",
                    intervention_band="fact_reveal",
                    target_ref=self._target_ref_for(event),
                    reason_summary="conversation candidate fact reveal requested",
                    downstream_status="published",
                    no_action_reason="",
                )
                self._finalize_tick_state(
                    result,
                    state_tree=state_tree,
                    fairness_snapshot=fairness_snapshot,
                    storyline=storyline,
                    projection=projection,
                    narrative_summary=narrative_summary,
                    quality_summary=quality_summary,
                    guardrail_summary=guardrail_summary,
                )
                continue

            if event.event_type == "constraint_state_event":
                reason = str(
                    event.payload.get(
                        "constraint_summary", "constraint rejected downstream"
                    )
                )
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
                result.audit_records.append(
                    self._audit(event, status="esm_rejected", reason=reason)
                )
                self._finalize_tick_state(
                    result,
                    state_tree=state_tree,
                    fairness_snapshot=fairness_snapshot,
                    storyline=storyline,
                    projection=projection,
                    narrative_summary=narrative_summary,
                    quality_summary=quality_summary,
                    guardrail_summary=guardrail_summary,
                )
                continue

            result.outputs.append(self._no_action(event))
            result.audit_records.append(
                self._audit(
                    event, status="no_action", reason="no eligible intervention"
                )
            )
            self._finalize_tick_state(
                result,
                state_tree=state_tree,
                fairness_snapshot=fairness_snapshot,
                storyline=storyline,
                projection=projection,
                narrative_summary=narrative_summary,
                quality_summary=quality_summary,
                guardrail_summary=guardrail_summary,
            )
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
        return result

    def record_authority_outcome(self, event: AuthorityEvent) -> None:
        if self._heavenly_support is not None:
            self._heavenly_support.record_authority_outcome(event)

    def reconcile_pending_dispatch(
        self,
        event: AuthorityEvent,
        *,
        authority_ledger: AuthorityRecoveryLedger | None,
    ) -> str:
        if self._heavenly_support is None:
            return "not_pending"
        return self._heavenly_support.reconcile_dispatch(
            event, authority_ledger=authority_ledger
        )

    def ensure_dispatches_unpublished(
        self, event: AuthorityEvent, outputs: list[SimingOutput]
    ) -> None:
        if self._heavenly_support is None:
            return
        for output in outputs:
            if (
                output.output_type == "dispatch_intent"
                and output.payload.get("siming_graph_owned") is True
            ):
                self._heavenly_support.ensure_dispatch_available(event)

    def record_dispatches_unconfirmed(
        self, event: AuthorityEvent, dispatch_events: list[AuthorityEvent]
    ) -> None:
        if self._heavenly_support is None:
            return
        for dispatch_event in dispatch_events:
            self._heavenly_support.record_dispatch_for_event(
                event, dispatch_event.event_id, unconfirmed=True
            )

    def record_published_dispatches(
        self, event: AuthorityEvent, dispatch_events: list[AuthorityEvent]
    ) -> None:
        if self._heavenly_support is None:
            return
        for dispatch_event in dispatch_events:
            if dispatch_event.payload.get("siming_graph_owned") is True:
                self._heavenly_support.record_dispatch_for_event(
                    event, dispatch_event.event_id
                )

    def _project_graph_owned_context(self, event, prepared, result) -> None:
        context = prepared.compiled_context
        if context is None:
            return
        projection = self._heavenly_story_projection.project(context)
        fairness = FairnessStateSnapshot(
            snapshot_id=f"graph-projection:{event.correlation_id}",
            room_id=event.room_id,
            scene_id=event.scene_id,
            zone_id=event.zone_id,
            causation_id=event.event_id,
            correlation_id=event.correlation_id,
            known_fact_ids=[fact.entry_id for fact in context.world_facts],
        )
        result.read_model = projection.read_model
        result.checkpoints.extend(
            self._read_model_builder.build_checkpoint(
                state_tree=projection.state_tree,
                fairness=fairness,
                storyline=projection.storyline,
                checkpoint_type=checkpoint_type,
            )
            for checkpoint_type in ("pre_decision", "post_decision")
        )

    def ingest_canonical_percept_bundle(
        self, bundle: CanonicalPerceptBundle
    ) -> SimingTickResult:
        if bundle.consumer_kind != "siming":
            raise ValueError(
                "SimingRuntime only accepts siming CanonicalPerceptBundle payloads"
            )
        producer_ts = self._producer_ts_from_bundle(bundle)
        output_base = {
            "room_id": str(
                bundle.local_spatial_state.get("room_id", "") or "room_demo"
            ),
            "scene_id": str(
                bundle.local_spatial_state.get("scene_id", "") or "scene_demo"
            ),
            "zone_id": str(
                bundle.local_spatial_state.get("zone_id", "") or "zone_focus"
            ),
            "causation_id": bundle.bundle_id,
            "correlation_id": bundle.query_id,
        }
        perception_identity = perception_identity_from_bundle(bundle)
        result = SimingTickResult()
        result.outputs.append(
            SimingOutput(
                output_type="fairness_snapshot",
                producer_ts=producer_ts + 1,
                payload={
                    "source_bundle_id": bundle.bundle_id,
                    "known_fact_ids": list(bundle.structured_fact_refs),
                    "environment_state": dict(bundle.environment_state),
                    "perception_identity": perception_identity,
                },
                **output_base,
            )
        )
        result.read_model = self._read_model_builder.build_bundle_read_model(
            bundle, producer_ts=producer_ts + 2
        )
        self._pending_observatory_messages.append(
            {
                "message_type": "siming_debug_event",
                "payload": {
                    "stage": "canonical_percept_bundle_consumed",
                    "summary": "Siming consumed L1 global situation bundle",
                    "bundle_id": bundle.bundle_id,
                    "perception_identity": perception_identity,
                    "producer_ts": producer_ts + 2,
                },
            }
        )
        return result

    def _process_graph_owned_event(
        self, event: AuthorityEvent, prepared
    ) -> tuple[list[SimingOutput], list[SimingAuditRecord]]:
        if prepared.degraded_reason or not prepared.eligible_candidates:
            reason = prepared.degraded_reason or "proposal_rejected"
            return [self._no_action(event, reason=reason)], [
                self._audit(event, status="no_action", reason=reason)
            ]
        candidate_contract = prepared.eligible_candidates[0]
        proposal = candidate_contract.proposal
        candidate = InterventionCandidate(
            candidate_id=candidate_contract.node_ref,
            room_id=event.room_id,
            scene_id=event.scene_id,
            zone_id=event.zone_id,
            causation_id=event.event_id,
            correlation_id=event.correlation_id,
            proposed_band="opportunity",
            target_actor_id=proposal.target_actor_id,
            target_object_id=proposal.realization_request.target_object_id,
            target_environment_id=proposal.realization_request.target_environment_id,
            established_fact_ids=list(proposal.supporting_fact_refs),
            explanation=proposal.title,
            confidence=1.0,
            source="llm",
        )
        snapshot = FairnessStateSnapshot(
            snapshot_id=f"graph-policy:{event.correlation_id}",
            room_id=event.room_id,
            scene_id=event.scene_id,
            zone_id=event.zone_id,
            causation_id=event.event_id,
            correlation_id=event.correlation_id,
            known_fact_ids=list(proposal.supporting_fact_refs),
            eligible_actor_ids=[proposal.target_actor_id]
            if proposal.target_actor_id
            else [],
        )
        policy_result = self._policy.evaluate(candidate, snapshot=snapshot)
        if not policy_result.accepted:
            reason = "policy_rejected:" + ",".join(policy_result.reasons)
            return [self._no_action(event, reason=reason)], [
                self._audit(event, status="policy_rejected", reason=reason)
            ]
        feasibility_result = self._feasibility.evaluate(candidate)
        if not feasibility_result.accepted:
            reason = "feasibility_rejected:" + ",".join(feasibility_result.reasons)
            return [self._no_action(event, reason=reason)], [
                self._audit(event, status="feasibility_rejected", reason=reason)
            ]
        request = self._heavenly_support.select_for_staging(
            prepared, candidate_contract.node_ref
        )
        return [
            self._candidate_output(event, candidate),
            self._decision_output(
                event,
                candidate,
                feasibility_result.selected_path,
                policy_result.reasons,
                feasibility_result.reasons,
            ),
            self._staging_request_output(event, candidate, request),
        ], [self._audit(event, status="recorded", reason="graph candidate staged")]

    def _process_staging_ack(
        self, event: AuthorityEvent, result: SimingTickResult
    ) -> None:
        if self._heavenly_support is None:
            return
        if self._heavenly_support.has_dispatch(event):
            result.outputs.append(
                self._no_action(event, reason="dispatch_already_recorded")
            )
            result.audit_records.append(
                self._audit(
                    event,
                    status="duplicate_suppressed",
                    reason="dispatch_already_recorded",
                )
            )
            return
        request = self._heavenly_support.record_staging_ack(event)
        staging_result = self._heavenly_support.complete_staging(event)
        if request is None or staging_result is None:
            result.audit_records.append(
                self._audit(event, status="no_action", reason="staging_pending")
            )
            return
        if staging_result.status != "staged":
            result.outputs.append(self._no_action(event, reason=staging_result.reason))
            result.audit_records.append(
                self._audit(event, status="no_action", reason=staging_result.reason)
            )
            return
        candidate_contract = self._heavenly_support.find_candidate(event)
        if candidate_contract is None:
            result.outputs.append(
                self._no_action(event, reason="staging_candidate_missing")
            )
            result.audit_records.append(
                self._audit(
                    event, status="no_action", reason="staging_candidate_missing"
                )
            )
            return
        proposal = candidate_contract.proposal
        candidate = InterventionCandidate(
            candidate_id=candidate_contract.node_ref,
            room_id=event.room_id,
            scene_id=event.scene_id,
            zone_id=event.zone_id,
            causation_id=event.event_id,
            correlation_id=event.correlation_id,
            proposed_band="opportunity",
            target_actor_id=proposal.target_actor_id,
            target_object_id=proposal.realization_request.target_object_id,
            target_environment_id=proposal.realization_request.target_environment_id,
            established_fact_ids=list(proposal.supporting_fact_refs),
            explanation=proposal.title,
            confidence=1.0,
            source="llm",
        )
        feasibility_result = self._feasibility.evaluate(candidate)
        if not feasibility_result.accepted:
            result.outputs.append(
                self._no_action(
                    event,
                    reason="feasibility_rejected:"
                    + ",".join(feasibility_result.reasons),
                )
            )
            result.audit_records.append(
                self._audit(
                    event, status="feasibility_rejected", reason="staging_dispatch"
                )
            )
            return
        dispatch = self._dispatch_output(
            event, candidate, feasibility_result.selected_path
        )
        dispatch.payload["siming_graph_owned"] = True
        result.outputs.extend(
            [
                self._candidate_output(event, candidate),
                self._decision_output(
                    event,
                    candidate,
                    feasibility_result.selected_path,
                    ["staging_complete"],
                    feasibility_result.reasons,
                ),
                dispatch,
            ]
        )
        result.audit_records.append(
            self._audit(event, status="recorded", reason="graph staging complete")
        )

    def _staging_request_output(
        self,
        event: AuthorityEvent,
        candidate: InterventionCandidate,
        request: StagingRequest,
    ) -> SimingOutput:
        return SimingOutput(
            output_type="staging_request",
            room_id=event.room_id,
            scene_id=event.scene_id,
            zone_id=event.zone_id,
            causation_id=event.event_id,
            correlation_id=event.correlation_id,
            producer_ts=event.producer_ts + 4,
            selected_path="character_input_path",
            intervention_band=candidate.proposed_band,
            payload={
                "node_id": request.node_id,
                "obligation_id": request.obligation_id,
                "realization_signature": request.resource_match.realization_signature,
                "target_actor_id": candidate.target_actor_id,
            },
        )

    def _llm_candidates_for(
        self,
        event: AuthorityEvent,
        snapshot: FairnessStateSnapshot,
    ) -> tuple[list[InterventionCandidate], list[SimingAuditRecord]]:
        try:
            return (
                self._llm_provider.generate_candidates(
                    snapshot=snapshot, recent_events=[event], recent_audit=[]
                ),
                [],
            )
        except SimingLlmProviderTimeout:
            return [], [
                self._audit(
                    event, status="llm_timeout", reason="LLM provider timed out"
                )
            ]
        except (SimingLlmProviderInvalidOutput, ValueError) as exc:
            return [], [
                self._audit(event, status="llm_invalid_output", reason=str(exc))
            ]

    def _producer_ts_from_bundle(self, bundle: CanonicalPerceptBundle) -> int:
        try:
            return int(str(bundle.query_id).split(":")[-1])
        except ValueError:
            return 0

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
                self._dispatch_output(
                    event, candidate, feasibility_result.selected_path
                ),
            ]
            audits.append(
                self._audit(
                    event, status="recorded", reason="LLM-assisted candidate accepted"
                )
            )
            return outputs, audits

        audits.append(
            self._audit(event, status="no_action", reason="no executable llm candidate")
        )
        return [self._no_action(event)], audits

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

    def _candidate_output(
        self, event: AuthorityEvent, candidate: InterventionCandidate
    ) -> SimingOutput:
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
                "target_actor_id": candidate.target_actor_id,
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
        pressure_hint = str(getattr(candidate, "pressure_hint", "") or "").strip()
        if pressure_hint != "":
            payload["pressure_hint"] = pressure_hint
        salience_boost = getattr(candidate, "salience_boost", None)
        if isinstance(salience_boost, int | float):
            payload["salience_boost"] = min(1.0, max(0.0, float(salience_boost)))
        reason_scope = str(getattr(candidate, "reason_scope", "") or "").strip()
        if reason_scope != "":
            payload["reason_scope"] = reason_scope
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

    def _intervention_decision(
        self, event: AuthorityEvent, *, selected_path: str, intervention_band: str
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
            intervention_band=intervention_band,
            payload={"decision_id": f"decision_{event.event_id}"},
        )

    def _visual_fact_dispatch(self, event: AuthorityEvent) -> SimingOutput:
        established_fact_id = str(
            event.payload.get("established_fact_id", event.event_id)
        )
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
        target_label = (
            target_environment_id
            or target_object_id
            or event.payload.get("entity_id")
            or "world state"
        )
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
        target_environment_id = self._first_payload_entry(
            event, "candidate_environment_ids"
        )
        target_label = (
            target_actor_id
            or target_object_id
            or target_environment_id
            or event.source.actor_id
            or "candidate"
        )
        selected_path = (
            "character_input_path" if target_actor_id else "visual_fact_path"
        )
        payload = {
            "presentation_hint": f"watch {target_label}",
            "target_actor_id": target_actor_id,
            "target_object_id": target_object_id,
            "target_environment_id": target_environment_id,
        }
        if selected_path == "visual_fact_path":
            payload["established_fact_id"] = str(
                event.payload.get("candidate_ref")
                or event.payload.get("event_id")
                or event.event_id
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

    def _no_action(
        self, event: AuthorityEvent, *, reason: str = "no eligible intervention"
    ) -> SimingOutput:
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
            payload={"reason": reason},
        )

    def _audit(
        self, event: AuthorityEvent, *, status: str, reason: str
    ) -> SimingAuditRecord:
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
        narrative_summary: dict[str, object] | None = None,
        quality_summary: dict[str, object] | None = None,
        guardrail_summary: dict[str, object] | None = None,
    ) -> None:
        checkpoint_types = ("post_decision", "post_dispatch")
        for checkpoint_type in checkpoint_types:
            result.checkpoints.append(
                self._read_model_builder.build_checkpoint(
                    state_tree=state_tree,
                    fairness=fairness_snapshot,
                    storyline=storyline,
                    checkpoint_type=checkpoint_type,
                )
            )
        checkpoint_summary = {
            "checkpoint_types": [
                checkpoint.checkpoint_type
                for checkpoint in result.checkpoints
                if checkpoint.correlation_id == state_tree.correlation_id
            ]
        }
        result.read_model = self._read_model_builder.build_read_model(
            state_tree=state_tree,
            fairness=fairness_snapshot,
            storyline=storyline,
            projection=projection,
            audit_records=result.audit_records,
            narrative_summary=narrative_summary,
            quality_summary=quality_summary,
            guardrail_summary=guardrail_summary,
            checkpoint_summary=checkpoint_summary,
        )
        if self._active_turn_event is not None:
            self._record_behavior_turn(self._active_turn_event, self._active_turn_prepared, result)

    def _record_behavior_turn(self, event: AuthorityEvent, prepared: object | None, result: SimingTickResult) -> None:
        if self._behavior_turn_recorder is None:
            return
        resolver = self._behavior_turn_scope_resolver
        if callable(resolver):
            scope = resolver(event)
        else:
            scope = HeavenlyGraphScope(
                world_id="world:demo",
                session_id="session:demo",
                story_branch_id="branch:main",
            )
        output_payload = [output.model_dump(mode="json") for output in result.outputs if output.correlation_id == event.correlation_id]
        audit_payload = [audit.model_dump(mode="json") for audit in result.audit_records if audit.correlation_id == event.correlation_id]
        prepared_payload = prepared.model_dump(mode="json") if hasattr(prepared, "model_dump") else {}
        self._behavior_turn_recorder.record(
            BehaviorTurnRecordRequest(
                turn_id=f"siming:{event.correlation_id}",
                scope=scope,
                valid_at=event.producer_ts,
                recorded_at=event.producer_ts,
                policy_revision="policy:siming-runtime:v1",
                source_revision_vector=GraphRevisionVector(source_revision=event.producer_ts),
                scope_digest="scope:siming-authority",
                provenance=GraphProvenance(
                    source_kind="authority_event",
                    source_ref=event.event_id,
                    causation_id=event.causation_id,
                    correlation_id=event.correlation_id,
                    producer_system="siming_runtime",
                ),
                transaction_id=f"siming-behavior-turn:{event.correlation_id}",
                idempotency_key=f"siming-behavior-turn:{event.correlation_id}",
                stages=(
                    BehaviorTurnStageRecord(stage="context", source_refs=(event.event_id,), payload=event.payload),
                    BehaviorTurnStageRecord(stage="interpretation", source_refs=(event.event_id,), payload={"prepared_context": prepared_payload}),
                    BehaviorTurnStageRecord(stage="goal", source_refs=tuple(audit.audit_id for audit in result.audit_records), payload={"event_family": event.event_type}),
                    BehaviorTurnStageRecord(stage="intent", source_refs=tuple(output.output_type for output in result.outputs), payload={"candidate_count": len(output_payload)}),
                    BehaviorTurnStageRecord(stage="execution", source_refs=tuple(output.output_type for output in result.outputs), payload={"outputs": output_payload}),
                    BehaviorTurnStageRecord(stage="settlement", outcome="committed" if event.event_type.endswith("result_event") else "recorded", source_refs=(event.event_id,), payload={"event_type": event.event_type}),
                    BehaviorTurnStageRecord(stage="evaluation", source_refs=tuple(audit.audit_id for audit in result.audit_records), payload={"audits": audit_payload}),
                    BehaviorTurnStageRecord(stage="policy", source_refs=tuple(audit.audit_id for audit in result.audit_records), payload={"policy_revision": "policy:siming-runtime:v1"}),
                ),
            )
        )

    def _narrative_summary_for(
        self, narrative: NarrativeCoreResult
    ) -> dict[str, object]:
        obligations = [
            {
                "obligation_type": obligation.obligation_type,
                "source_event_id": obligation.source_event_id,
                "target_refs": list(obligation.target_refs[:4]),
                "status": obligation.status,
            }
            for obligation in narrative.ledger.obligations[:5]
        ]
        intervention_seeds = [
            {
                "seed_type": seed.seed_type,
                "basis_obligation_refs": list(seed.basis_obligation_refs[:4]),
                "basis_fact_refs": list(seed.basis_fact_refs[:4]),
                "target_refs": list(seed.target_refs[:4]),
                "suggested_band": seed.suggested_band,
            }
            for seed in narrative.seeds[:5]
        ]
        return {
            "active_phase": narrative.state.active_phase,
            "pressure_level": narrative.state.pressure_level,
            "open_obligation_count": len(narrative.ledger.obligations),
            "intervention_seed_count": len(narrative.seeds),
            "seed_types": [seed.seed_type for seed in narrative.seeds],
            "obligations": obligations,
            "intervention_seeds": intervention_seeds,
        }

    def _quality_summary_for(self, quality: QualityMonitorResult) -> dict[str, object]:
        return {
            "quality_signal_count": len(quality.signals),
            "quality_risk_tags": list(quality.risk_tags),
            "quality_dimensions": sorted(quality.snapshot.dimensions.keys()),
        }

    def _guardrail_summary_for(
        self, guardrail_results: list[GuardrailResult]
    ) -> dict[str, object]:
        return {
            "guardrail_statuses": [
                "accepted" if guardrail_result.accepted else "rejected"
                for guardrail_result in guardrail_results
            ],
            "guardrail_reasons": [
                reason
                for guardrail_result in guardrail_results
                for reason in guardrail_result.reasons
            ],
        }

    def _guardrail_rejection_reason(
        self, guardrail_results: list[GuardrailResult]
    ) -> str | None:
        reasons = [
            reason
            for guardrail_result in guardrail_results
            if not guardrail_result.accepted
            for reason in guardrail_result.reasons
        ]
        if not reasons:
            return None
        return "guardrail_rejected:" + ",".join(sorted(set(reasons)))

    def _policy_snapshot_for_event(
        self,
        event: AuthorityEvent,
        snapshot: FairnessStateSnapshot,
    ) -> FairnessStateSnapshot:
        if snapshot.eligible_actor_ids or not self._is_light_drop(event):
            return snapshot
        return snapshot.model_copy(update={"eligible_actor_ids": ["char_b"]})

    def _is_light_drop(self, event: AuthorityEvent) -> bool:
        return (
            event.event_type == "visual_fact_event"
            and event.payload.get("fact_type") == "light_level_drop"
        )

    def _is_environment_attention_event(self, event: AuthorityEvent) -> bool:
        if event.event_type != "esm_result_event":
            return False
        return event.payload.get("result_type") == "environment_state_result" and bool(
            event.payload.get("target_environment_id")
        )

    def _has_conversation_candidate(self, event: AuthorityEvent) -> bool:
        return any(
            self._first_payload_entry(event, field) is not None
            for field in (
                "candidate_actor_ids",
                "candidate_object_ids",
                "candidate_environment_ids",
            )
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
        for key in (
            "target_actor_id",
            "target_object_id",
            "target_environment_id",
            "entity_id",
        ):
            value = str(event.payload.get(key, "") or "")
            if value != "":
                return value
        if event.source.actor_id:
            return event.source.actor_id
        return ""

    def _fairness_summary_for(self, event: AuthorityEvent) -> str:
        if event.event_type == "visual_fact_event":
            return "visibility imbalance detected around %s" % (
                self._target_ref_for(event) or "scene"
            )
        return "scene balance reviewed for %s" % (event.event_type or "event")

    def _candidate_summary_for(self, event: AuthorityEvent) -> str:
        return "candidate for %s" % (self._target_ref_for(event) or event.event_type)

    def _decision_summary_for(
        self, event: AuthorityEvent, *, selected_path: str, intervention_band: str
    ) -> str:
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
