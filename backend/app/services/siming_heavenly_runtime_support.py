from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from pydantic import BaseModel, Field

from app.config import SimingHeavenlyMode
from app.models.authority_event import AuthorityEvent
from app.services.siming_continuation import SimingProviderRequest, SimingProviderCompletion, run_siming_provider, digest
from app.services.siming_llm_provider import SimingLlmProviderTimeout, SimingLlmProviderInvalidOutput
from app.models.siming_adaptive_bridge import AdaptiveBridgeNodeProposal
from app.models.siming_event import SimingInput
from app.models.siming_heavenly_graph import (
    GraphProvenance,
    GraphValidity,
    HeavenlyGraphNode,
    HeavenlyGraphScope,
    HeavenlyGraphWriteBatch,
)
from app.models.siming_heavenly_memory import (
    WorldFactMemoryEntry,
    InterventionOutcomeMemoryEntry,
    SimingCompiledContext,
    SimingContextRequest,
    StorylineObligationMemoryEntry,
)
from app.models.siming_story_graph import (
    AuthorityStoryOutcome,
    RuntimeStoryNode,
    NarrativeObligation,
    StoryNodeBlueprint,
    StoryOutcomeEffect,
    StoryOutcomePort,
)
from app.models.siming_resource_capability import (
    StagingAck,
    StagingRequest,
    StagingResult,
)
from app.services.siming_actor_memory_gateway import ActorMemoryReadGateway
from app.services.authority_event_bus import AuthorityRecoveryLedger
from app.services.siming_adaptive_bridge import (
    SimingAdaptiveBridge,
    canonical_obligation_id,
)
from app.services.siming_context_compiler import SimingContextCompiler
from app.services.siming_heavenly_memory import SimingHeavenlyMemoryService
from app.services.siming_llm_provider import (
    SimingLlmCandidateProvider,
    SimingLlmProviderError,
)
from app.services.siming_resource_capability_registry import ResourceCapabilityRegistry
from app.services.siming_story_graph_runtime import SimingStoryGraphRuntime
from app.services.siming_story_node_staging import SimingStoryNodeStaging
from app.services.siming_story_obligation_runtime import SimingStoryObligationRuntime


class PreparedHeavenlyDecision(BaseModel):
    mode: SimingHeavenlyMode
    event_family: str
    owns_event_family: bool
    correlation_id: str
    context_hash: str
    eligible_node_refs: list[str] = Field(default_factory=list)
    eligible_candidates: list["PreparedHeavenlyCandidate"] = Field(default_factory=list)
    validation_audit_refs: list[str] = Field(default_factory=list)
    degraded_reason: str = ""
    compiled_context: SimingCompiledContext | None = None
    scope: HeavenlyGraphScope | None = None
    recorded_at: int = 0


class PreparedHeavenlyCandidate(BaseModel):
    node_ref: str
    proposal: AdaptiveBridgeNodeProposal
    staging_request: StagingRequest


class SimingHeavenlyPreparationPlan(BaseModel):
    prepared: PreparedHeavenlyDecision
    batches: list[HeavenlyGraphWriteBatch] = Field(default_factory=list)


class SimingStagingSelectionPlan(BaseModel):
    request: StagingRequest
    batches: list[HeavenlyGraphWriteBatch] = Field(default_factory=list)


class SimingAuthorityPrefixPlan(BaseModel):
    entry_ref: str | None = None
    batches: list[HeavenlyGraphWriteBatch] = Field(default_factory=list)


class SimingDuplicateDispatchError(ValueError):
    """A graph-owned correlation already has a durable dispatch."""


@dataclass(frozen=True)
class _PreparedContext:
    scope: HeavenlyGraphScope
    recorded_at: int
    owns_event_family: bool


class SimingHeavenlyRuntimeSupport:
    GRAPH_OWNED_EVENT_FAMILIES = frozenset({"evidence_destruction_consequence"})

    def __init__(
        self,
        *,
        mode: SimingHeavenlyMode,
        memory: SimingHeavenlyMemoryService,
        compiler: SimingContextCompiler,
        actor_memory: ActorMemoryReadGateway,
        story: SimingStoryGraphRuntime,
        obligations: SimingStoryObligationRuntime,
        resources: ResourceCapabilityRegistry,
        staging: SimingStoryNodeStaging,
        bridges: Callable[[SimingCompiledContext], SimingAdaptiveBridge],
        llm_provider: SimingLlmCandidateProvider,
    ) -> None:
        self.mode = mode
        self._memory = memory
        self._compiler = compiler
        self._actor_memory = actor_memory
        self._story = story
        self._obligations = obligations
        self._resources = resources
        self._staging = staging
        self._bridges = bridges
        self._llm_provider = llm_provider
        self._prepared_by_correlation: dict[str, _PreparedContext] = {}
        self._authority_seeded_correlations: set[str] = set()

    def prepare(self, siming_input: SimingInput) -> PreparedHeavenlyDecision:
        prepared, frame, request = self.prepare_request(siming_input)
        if request is not None:
            completion = SimingProviderCompletion.model_validate_json(run_siming_provider(self._llm_provider, request.model_dump_json().encode("utf-8")))
            prepared = self.finish_prepare(frame, completion)
        # 仅旧 correlation-only 工具 API 使用；分阶段决策不读取此缓存。
        self._prepared_by_correlation[prepared.correlation_id] = _PreparedContext(
            scope=prepared.scope, recorded_at=prepared.recorded_at, owns_event_family=prepared.owns_event_family)
        return prepared

    def prepare_request(self, siming_input: SimingInput, *, planned_batches: list[HeavenlyGraphWriteBatch] | None = None):
        event = siming_input.source_event
        event_family = self._event_family(event)
        scope = self._scope_for(event)
        owns_event_family = (
            self.mode == "active" and event_family in self.GRAPH_OWNED_EVENT_FAMILIES
            # Authority destruction seeds the durable fact/obligation surface.
            # The adaptive proposal must wait for the subsequent actor-scoped
            # observation event, otherwise async perception can race validation.
            and not self._is_authority_destruction(event)
        )
        try:
            context = self._compiler.compile(
                SimingContextRequest(
                    scope=scope,
                    valid_at=event.producer_ts,
                    seed_node_ids=self._seed_node_ids(event),
                    relevant_actor_ids=event.routing.target_ids,
                ),
                **({"planned_nodes": [node for batch in planned_batches for node in batch.nodes]} if planned_batches else {}),
            )
        except Exception as error:
            if planned_batches:
                raise
            return self._graph_degraded(event, event_family, error), None, None

        frame = {"event": event.model_dump(mode="json"), "event_family": event_family,
                 "scope": scope.model_dump(mode="json"), "owns_event_family": owns_event_family,
                 "context": context.model_dump(mode="json")}
        if owns_event_family:
            proposal_context = context.model_dump(mode="json")
            if event_family == "evidence_destruction_consequence":
                proposal_context = {
                    "world_facts": proposal_context.get("world_facts", []),
                    "storyline_obligations": [
                        obligation
                        for obligation in proposal_context.get("storyline_obligations", [])
                        if str(obligation.get("entry_id", "")) in {"obligation:O2", "obligation:O6"}
                    ],
                    "causal_timeline": [],
                    "actor_cognition": [],
                    "intervention_outcomes": [],
                    "convergence_strategies": [],
                }
                proposal_context["resource_capabilities"] = [
                    {
                        "capability_id": package.capability_id,
                        "asset_bundle": package.asset_bundle,
                        "actor_ids": list(package.actor_ids),
                        "object_ids": list(package.object_ids),
                        "environment_ids": list(package.environment_ids),
                        "realization_keys": list(package.realization_keys),
                        "semantic_purposes": list(package.semantic_purposes),
                        "loaded": package.loaded,
                    }
                    for package in self._resources._packages.values()
                ]
                proposal_context["actor_views"] = [
                    {"actor_id": "char_b", "visibility": "actor_private_endpoint_scoped"},
                    {"actor_id": "char_c", "visibility": "actor_private_endpoint_scoped"},
                ]
            return None, frame, SimingProviderRequest(stage="adaptive", event=event, compiled_context=proposal_context)
        completion = SimingProviderCompletion(request_digest="")
        if planned_batches is None:
            prepared = self.finish_prepare(frame, completion)
        else:
            plan = self.plan_finish_prepare(frame, completion)
            planned_batches.extend(plan.batches)
            prepared = plan.prepared
        return prepared, frame, None

    def finish_prepare(self, frame: dict, completion: SimingProviderCompletion) -> PreparedHeavenlyDecision:
        plan = self.plan_finish_prepare(frame, completion)
        try:
            for batch in plan.batches:
                self._memory._graph.write_batch(batch)
        except Exception as error:
            return self._graph_degraded(AuthorityEvent.model_validate(frame["event"]), frame["event_family"], error)
        return plan.prepared

    def plan_finish_prepare(self, frame: dict, completion: SimingProviderCompletion) -> SimingHeavenlyPreparationPlan:
        batches = []
        prepared = self._plan_prepare(frame, completion, batches)
        return SimingHeavenlyPreparationPlan(prepared=prepared, batches=batches)

    def _plan_prepare(self, frame: dict, completion: SimingProviderCompletion, batches) -> PreparedHeavenlyDecision:
        def record(**kwargs):
            batch = self._plan_record(**kwargs)
            batches.append(batch)
            return batch.nodes[0].node_id
        event = AuthorityEvent.model_validate(frame["event"])
        event_family, owns_event_family = frame["event_family"], frame["owns_event_family"]
        scope = HeavenlyGraphScope.model_validate(frame["scope"])
        context = SimingCompiledContext.model_validate(frame["context"])
        if completion.error:
            error_type = {"SimingLlmProviderTimeout": SimingLlmProviderTimeout,
                          "SimingLlmProviderInvalidOutput": SimingLlmProviderInvalidOutput,
                          "SimingLlmProviderError": SimingLlmProviderError}[completion.error]
            return self._llm_unavailable(event, event_family, error_type(completion.message))
        proposal_batch = completion.proposal_batch
        try:
            eligible_node_refs = []
            eligible_candidates = []
            validation_audit_refs = []
            if proposal_batch is not None:
                bridge = self._bridges(context)
                validation_results = []
                for proposal in proposal_batch.proposals:
                    plan = bridge.plan_commit(proposal, provider_audit=proposal_batch.audit)
                    for batch in plan.batches:
                        previous = next((item for item in batches if item.idempotency_key == batch.idempotency_key), None)
                        if previous is not None:
                            if batch.idempotency_key.startswith("story_seed:") and previous.nodes[0].attributes == batch.nodes[0].attributes:
                                continue
                            if previous != batch:
                                raise ValueError("siming_planned_batch_conflict")
                            continue
                        batches.append(batch)
                    validation_results.append((proposal, plan.result))
                eligible_node_refs = []
                for proposal, validation in validation_results:
                    if not validation.accepted or validation.runtime_node_ref is None:
                        continue
                    if not proposal.obligation_refs:
                        continue
                    resource_match = self._resources.match(
                        proposal.realization_request,
                        world_ts=event.producer_ts,
                    )
                    if not resource_match.accepted:
                        continue
                    staging_request = StagingRequest(
                        scope=scope,
                        node_id=validation.runtime_node_ref,
                        correlation_id=event.correlation_id,
                        obligation_id=canonical_obligation_id(
                            proposal.obligation_refs[0]
                        ),
                        recorded_at=event.producer_ts,
                        resource_match=resource_match,
                    )
                    eligible_node_refs.append(validation.runtime_node_ref)
                    eligible_candidates.append(
                        PreparedHeavenlyCandidate(
                            node_ref=validation.runtime_node_ref,
                            proposal=proposal,
                            staging_request=staging_request,
                        )
                    )
                    validation_audit_refs.append(
                        record(
                            scope=scope,
                            recorded_at=event.producer_ts,
                            correlation_id=event.correlation_id,
                            stage="proposal",
                            selected_node_ref=validation.runtime_node_ref,
                            staging_request=staging_request,
                            proposal=proposal,
                            reason="candidate_prepared",
                        )
                    )
                eligible_node_refs.sort()
                validation_audit_refs.extend(
                    f"adaptive_bridge_audit:{proposal.proposal_id}"
                    for proposal in proposal_batch.proposals
                )
            validation_audit_refs.append(
                record(
                    scope=scope,
                    recorded_at=event.producer_ts,
                    correlation_id=event.correlation_id,
                    stage="proposal",
                    entry_value=event.event_id,
                    reason="shadow_advisory" if self.mode == "shadow" else "prepared",
                )
            )
            eligible_candidates.sort(key=lambda candidate: candidate.node_ref)
        except Exception as error:
            return self._graph_degraded(event, event_family, error)
        return PreparedHeavenlyDecision(
            mode=self.mode,
            event_family=event_family,
            owns_event_family=owns_event_family,
            correlation_id=event.correlation_id,
            context_hash=context.context_hash,
            eligible_node_refs=eligible_node_refs,
            eligible_candidates=eligible_candidates,
            validation_audit_refs=validation_audit_refs,
            compiled_context=context,
            scope=scope, recorded_at=event.producer_ts,
        )

    def record_selection(
        self,
        prepared: PreparedHeavenlyDecision,
        selected_node_ref: str,
    ) -> str:
        self._require_active_owned(prepared)
        context = _PreparedContext(scope=prepared.scope, recorded_at=prepared.recorded_at, owns_event_family=prepared.owns_event_family)
        prior_selection = self._durable_stage_record(
            context,
            correlation_id=prepared.correlation_id,
            stage="selection",
        )
        if (
            prior_selection is not None
            and prior_selection.selected_node_ref != selected_node_ref
        ):
            raise ValueError(
                "a heavenly decision is already selected for this correlation"
            )
        if prior_selection is not None:
            return self._entry_id(
                "selection", prepared.correlation_id, selected_node_ref
            )
        record_ref = self._record(
            scope=context.scope,
            recorded_at=context.recorded_at,
            correlation_id=prepared.correlation_id,
            stage="selection",
            selected_node_ref=selected_node_ref,
        )
        return record_ref

    def record_dispatch(self, *, correlation_id: str, dispatch_event_id: str) -> str:
        context = self._prepared_context(correlation_id)
        if self.mode != "active" or not context.owns_event_family:
            raise ValueError("only active graph-owned decisions may record dispatch")
        return self._record_dispatch_state(
            scope=context.scope,
            recorded_at=context.recorded_at,
            correlation_id=correlation_id,
            dispatch_event_id=dispatch_event_id,
            state="authority_confirmed",
        )

    def has_dispatch(self, event: AuthorityEvent) -> bool:
        record = self._dispatch_record_for(
            scope=self._scope_for(event),
            correlation_id=event.correlation_id,
            valid_at=event.producer_ts,
        )
        return record is not None and self._dispatch_state(record) == "authority_confirmed"

    def ensure_dispatch_available(self, event: AuthorityEvent) -> bool:
        if not self._is_selected_candidate(event):
            return False
        if self.has_dispatch(event):
            raise SimingDuplicateDispatchError(
                "a heavenly dispatch is already recorded for this correlation"
            )
        return True

    def record_dispatch_for_event(
        self, event: AuthorityEvent, dispatch_event_id: str, *, unconfirmed: bool = False
    ) -> str | None:
        if not self._is_selected_candidate(event):
            return None
        return self._record_dispatch_state(
            scope=self._scope_for(event),
            recorded_at=event.producer_ts,
            correlation_id=event.correlation_id,
            dispatch_event_id=dispatch_event_id,
            state="sent_unconfirmed" if unconfirmed else "authority_confirmed",
        )

    def reconcile_dispatch(
        self,
        event: AuthorityEvent,
        *,
        authority_ledger: AuthorityRecoveryLedger | None,
    ) -> str:
        record = self._dispatch_record_for(
            scope=self._scope_for(event),
            correlation_id=event.correlation_id,
            valid_at=event.producer_ts,
        )
        if record is None or self._dispatch_state(record) == "authority_confirmed":
            return "not_pending"
        dispatch_event_id = self._dispatch_event_id(record)
        if authority_ledger is None:
            dispatch_state = "authority_unknown"
            recovery_state = "authority_unknown"
        elif dispatch_event_id in authority_ledger.event_ids:
            dispatch_state = "authority_confirmed"
            recovery_state = "authority_confirmed"
        elif authority_ledger.is_complete_across_restart:
            dispatch_state = "sent_unconfirmed"
            recovery_state = "authority_absent"
        else:
            dispatch_state = "authority_unknown"
            recovery_state = "authority_unknown"
        self._record_dispatch_state(
            scope=self._scope_for(event),
            recorded_at=event.producer_ts,
            correlation_id=event.correlation_id,
            dispatch_event_id=dispatch_event_id,
            state=dispatch_state,
        )
        return recovery_state

    def record_authority_outcome(self, event: AuthorityEvent) -> str | None:
        plan = self.plan_authority_outcome(event)
        for batch in plan.batches:
            self._memory._graph.write_batch(batch)
        if plan.entry_ref is not None:
            self._authority_seeded_correlations.add(event.correlation_id)
        return plan.entry_ref

    def plan_authority_outcome(self, event: AuthorityEvent) -> SimingAuthorityPrefixPlan:
        if self.mode == "off" or not self._is_authority_destruction(event):
            return SimingAuthorityPrefixPlan()
        batches = self._plan_seed_demo_graph(event)
        final = self._plan_record(scope=self._scope_for(event), recorded_at=event.producer_ts,
            correlation_id=event.correlation_id, stage="authority_result",
            authority_result_ref=event.event_id, reason=event.event_type)
        batches.append(final)
        return SimingAuthorityPrefixPlan(entry_ref=final.nodes[0].node_id, batches=batches)

    def select_for_staging(
        self, prepared: PreparedHeavenlyDecision, selected_node_ref: str
    ) -> StagingRequest:
        plan = self.plan_select_for_staging(prepared, selected_node_ref)
        for batch in plan.batches:
            self._memory._graph.write_batch(batch)
        return plan.request

    def plan_select_for_staging(
        self,
        prepared: PreparedHeavenlyDecision,
        selected_node_ref: str,
        *, prior_node: HeavenlyGraphNode | None = None,
    ) -> SimingStagingSelectionPlan:
        self._require_active_owned(prepared)
        context = _PreparedContext(scope=prepared.scope, recorded_at=prepared.recorded_at, owns_event_family=prepared.owns_event_family)
        candidate = next((item for item in prepared.eligible_candidates if item.node_ref == selected_node_ref), None)
        request = candidate.staging_request if candidate is not None else self._staging_request_for(
            scope=context.scope,
            correlation_id=prepared.correlation_id,
            valid_at=context.recorded_at,
            node_id=selected_node_ref,
        )
        if request is None:
            raise ValueError("selected heavenly candidate has no staging contract")
        prior = self._durable_stage_record(
            context,
            correlation_id=prepared.correlation_id,
            stage="selection",
        )
        if prior is not None:
            if prior.selected_node_ref != selected_node_ref:
                raise ValueError(
                    "a heavenly decision is already selected for this correlation"
                )
            return SimingStagingSelectionPlan(request=request)
        if prior_node is None:
            prior_node = self._story._semantic_node(context.scope, selected_node_ref, context.recorded_at, None)
        node = None if prior_node is None else RuntimeStoryNode.model_validate(prior_node.attributes)
        batches = []
        if node is None:
            raise ValueError("selected heavenly candidate is missing its story node")
        if node.lifecycle == "latent":
            eligible = self._story.plan_transition(
                prior=prior_node,
                transaction_id=f"story_transition:{selected_node_ref}",
                idempotency_key=f"story_transition:{selected_node_ref}:latent:eligible:heavenly_candidate_validated:{context.recorded_at}",
                scope=context.scope,
                node_id=selected_node_ref,
                expected="latent",
                target="eligible",
                reason="heavenly_candidate_validated",
                recorded_at=context.recorded_at,
            )
            batches.append(eligible)
            prior_node = eligible.nodes[0]
            node = RuntimeStoryNode.model_validate(prior_node.attributes)
        if node.lifecycle != "eligible":
            raise ValueError("selected heavenly candidate is not eligible")
        selection_id = self._entry_id(
            "selection", prepared.correlation_id, selected_node_ref
        )
        selected = self._story.plan_transition_with_intervention_outcome(
            prior=prior_node,
            scope=context.scope,
            node_id=selected_node_ref,
            expected="eligible",
            target="selected",
            reason="heavenly_candidate_selected",
            recorded_at=context.recorded_at,
            outcome=InterventionOutcomeMemoryEntry(
                entry_id=selection_id,
                stage="selection",
                correlation_id=prepared.correlation_id,
                selected_node_ref=selected_node_ref,
            ),
            provenance=self._provenance(selection_id, prepared.correlation_id),
        )
        batches.append(selected)
        return SimingStagingSelectionPlan(request=request, batches=batches)

    def record_staging_ack(self, event: AuthorityEvent, *, planned_batches=None) -> StagingRequest | None:
        request = self.find_staging_request(event)
        if request is None:
            return None
        ack = StagingAck.model_validate(event.payload)
        if ack.correlation_id != event.correlation_id:
            raise ValueError("staging acknowledgement correlation mismatch")
        batch = self._plan_record(
            scope=request.scope,
            recorded_at=event.producer_ts,
            correlation_id=event.correlation_id,
            stage="staging_ack",
            selected_node_ref=request.node_id,
            staging_ack=ack,
            entry_value=ack.source,
        )
        if planned_batches is None:
            self._memory._graph.write_batch(batch)
        else:
            planned_batches.append(batch)
        return request

    def complete_staging(self, event: AuthorityEvent, *, planned_batches=None) -> StagingResult | None:
        request = self.find_staging_request(event)
        if request is None or not self._has_selection(
            scope=request.scope,
            correlation_id=event.correlation_id,
            valid_at=event.producer_ts,
            node_id=request.node_id,
        ):
            return None
        entries = self._memory.list_domain(request.scope, "intervention_outcome", valid_at=event.producer_ts)
        if planned_batches is not None:
            pending = [InterventionOutcomeMemoryEntry.model_validate(node.attributes) for batch in planned_batches
                for node in batch.nodes if node.node_type == "memory:intervention_outcome"
                and node.scope == request.scope and node.validity.valid_from <= event.producer_ts
                and (node.validity.valid_to is None or event.producer_ts < node.validity.valid_to)]
            merged = {entry.entry_id: entry for entry in [*entries, *pending]}
            # 与原 list_domain 的 node_id 排序和 1000 项查询上限一致。
            entries = [merged[key] for key in sorted(merged)[:1000]]
        acks = [
            entry.staging_ack
            for entry in entries
            if isinstance(entry, InterventionOutcomeMemoryEntry)
            and entry.correlation_id == event.correlation_id
            and entry.stage == "staging_ack"
            and entry.selected_node_ref == request.node_id
            and entry.staging_ack is not None
        ]
        if {ack.source for ack in acks} != self._staging.REQUIRED_ACK_SOURCES:
            return None
        return self._staging.complete(request, acks=acks, **({"planned_batches": planned_batches} if planned_batches is not None else {}))

    @staticmethod
    def _event_family(event: AuthorityEvent) -> str:
        payload = event.payload
        target_ref = (
            payload.get("target_ref")
            or payload.get("target_object_id")
            or payload.get("entity_id")
        )
        lineage = payload.get("source_ref_lineage", [])
        observes_removed_letter = (
            isinstance(lineage, list)
            and any("object_result:obj_letter:" in str(ref) for ref in lineage)
        )
        if (
            event.event_type == "visual_fact_event"
            and target_ref == "obj_letter"
            and (
                payload.get("relation_type") == "actor_observes_object_removal"
                or observes_removed_letter
            )
        ) or (
            target_ref == "obj_letter"
            and payload.get("current_state") == "removed_from_surface"
        ):
            return "evidence_destruction_consequence"
        return event.event_type

    @staticmethod
    def _is_authority_destruction(event: AuthorityEvent) -> bool:
        payload = event.payload
        target_ref = (
            payload.get("target_ref")
            or payload.get("target_object_id")
            or payload.get("entity_id")
        )
        return (
            event.event_type == "esm_result_event"
            and event.source.layer == "L1"
            and event.source.system in {"esm", "world_authority"}
            and isinstance(payload.get("result_id"), str)
            and bool(payload.get("result_id"))
            and payload.get("result_type") == "object_state_result"
            and target_ref == "obj_letter"
            and payload.get("current_state") == "removed_from_surface"
            and payload.get("settlement_status") == "applied"
        )

    def _plan_seed_demo_graph(self, event: AuthorityEvent) -> list[HeavenlyGraphWriteBatch]:
        batches = []
        latest_nodes = {}

        def remember(batch):
            if batch is not None:
                batches.append(batch)
                latest_nodes.update({node.node_id: node for node in batch.nodes})

        def obligation_node(obligation_id):
            node_id = self._obligations._obligation_node_id(obligation_id)
            return latest_nodes.get(node_id) or self._obligations._semantic_node(
                scope, node_id, recorded_at, None)
        scope = self._scope_for(event)
        recorded_at = event.producer_ts
        result_ref = str(event.payload.get("result_id") or event.event_id)
        provenance = GraphProvenance(
            source_kind="authority_event",
            source_ref=result_ref,
            causation_id=event.causation_id,
            correlation_id=event.correlation_id,
            producer_system="system_l6",
        )
        fact = WorldFactMemoryEntry(
            entry_id="fact:letter:removed",
            world_anchor_id="obj_letter",
            state_key="surface_state",
            state_value="removed_from_surface",
            authority_result_ref=result_ref,
            evidence_refs=[result_ref],
        )
        if self._memory.get_entry(scope=scope, entry_id=fact.entry_id, valid_at=recorded_at) is None:
            remember(self._memory.plan_write_entry(
                scope=scope,
                entry=fact,
                validity=GraphValidity(valid_from=recorded_at),
                recorded_at=recorded_at,
                revision=1,
                supersedes_revision=None,
                provenance=provenance,
                transaction_id=f"siming_seed:{fact.entry_id}",
                idempotency_key=f"siming_seed:{fact.entry_id}",
            ))

        blueprints = (
            StoryNodeBlueprint(
                blueprint_id="N3",
                title="Repair record opportunity",
                outcome_ports=[
                    StoryOutcomePort(
                        port_id="player_destroyed_evidence",
                        required_result_type="object_state_result",
                        target_ref="obj_letter",
                        required_state="removed_from_surface",
                        outcome_semantic="resolved_with_divergence",
                        effects=[
                            StoryOutcomeEffect(
                                target_blueprint_id="N4",
                                effect="close_permanently",
                                reason="player destroyed the original evidence",
                            ),
                            StoryOutcomeEffect(
                                target_blueprint_id="N5",
                                effect="mark_unreachable",
                                reason="the evidence route is closed by ledger",
                            ),
                        ],
                    )
                ],
            ),
            StoryNodeBlueprint(blueprint_id="N4", title="Original evidence confrontation"),
            StoryNodeBlueprint(blueprint_id="N5", title="Public time contradiction"),
        )
        for blueprint in blueprints:
            remember(self._story.plan_seed_blueprint(
                scope=scope,
                blueprint=blueprint,
                provenance=provenance,
                recorded_at=recorded_at,
            ))
            node_id = f"runtime:{blueprint.blueprint_id}:main"
            if self._story.read_runtime_node(
                scope=scope, node_id=node_id, valid_at=recorded_at
            ) is None:
                remember(self._story.plan_runtime_node(
                    scope=scope,
                    blueprint_id=blueprint.blueprint_id,
                    node_id=node_id,
                    causal_basis_refs=[],
                    recorded_at=recorded_at,
                ))

        outcome = AuthorityStoryOutcome(
            result_type=str(event.payload.get("result_type") or "object_state_result"),
            target_ref="obj_letter",
            current_state="removed_from_surface",
            authority_result_ref=result_ref,
            correlation_id=event.correlation_id,
            recorded_at=recorded_at,
        )
        outcome_plan = self._story.plan_authority_outcome(scope=scope, outcome=outcome,
            planned_nodes=[node for node in latest_nodes.values() if node.node_type == "runtime_story_node"],
            planned_blueprints=list(blueprints))
        remember(outcome_plan.batch)

        o2 = obligation_node("O2")
        if o2 is None:
            remember(self._obligations.plan_seed(
                scope=scope,
                obligation=NarrativeObligation(
                    obligation_id="O2",
                    description="The time contradiction must have consequences.",
                    status="open",
                    pressure=0.8,
                    source_fact_refs=[fact.entry_id],
                ),
                provenance=provenance,
                recorded_at=recorded_at,
            ))
        o6 = obligation_node("O6")
        if o6 is None:
            transform = self._obligations.plan_transform(
                source_prior=obligation_node("O2"), replacement_prior=None,
                scope=scope,
                source_obligation_id="O2",
                replacement=NarrativeObligation(
                    obligation_id="O6",
                    description="The player cover-up must have consequences.",
                    status="open",
                    pressure=0.7,
                    source_fact_refs=[fact.entry_id],
                ),
                authority_result_ref=result_ref,
                correlation_id=event.correlation_id,
                recorded_at=recorded_at,
            )
            remember(transform.batch)

        for obligation_id in ("O2", "O6"):
            memory_id = f"obligation:{obligation_id}"
            if self._memory.get_entry(
                scope=scope, entry_id=memory_id, valid_at=recorded_at
            ) is not None:
                continue
            node = obligation_node(obligation_id)
            if node is None:
                continue
            obligation = NarrativeObligation.model_validate(node.attributes)
            remember(self._memory.plan_write_entry(
                scope=scope,
                entry=StorylineObligationMemoryEntry(
                    entry_id=memory_id,
                    record_type="obligation",
                    lifecycle=obligation.status,
                    supporting_fact_refs=[fact.entry_id],
                ),
                validity=GraphValidity(valid_from=recorded_at),
                recorded_at=recorded_at,
                revision=1,
                supersedes_revision=None,
                provenance=provenance,
                transaction_id=f"siming_seed:{memory_id}",
                idempotency_key=f"siming_seed:{memory_id}",
            ))
        return batches

    @staticmethod
    def _scope_for(event: AuthorityEvent) -> HeavenlyGraphScope:
        return HeavenlyGraphScope(
            world_id="world:demo",
            session_id="session:demo",
            story_branch_id="branch:main",
            room_id=event.room_id,
            scene_id=event.scene_id,
        )

    @staticmethod
    def _seed_node_ids(event: AuthorityEvent) -> list[str]:
        raw_seed_ids = event.payload.get("graph_seed_node_ids", [])
        seed_ids = (
            set(raw_seed_ids)
            if isinstance(raw_seed_ids, list)
            and all(isinstance(node_id, str) and node_id for node_id in raw_seed_ids)
            else set()
        )
        target_ref = (
            event.payload.get("target_ref")
            or event.payload.get("target_object_id")
            or event.payload.get("entity_id")
        )
        if target_ref == "obj_letter" and (
            event.payload.get("current_state") == "removed_from_surface"
            or event.payload.get("relation_type") == "actor_observes_object_removal"
        ):
            seed_ids.update(
                {
                    "fact:letter:removed",
                    "obligation:O2",
                    "obligation:O6",
                    "runtime:N3:main",
                    "runtime:N4:main",
                    "runtime:N5:main",
                }
            )
        return sorted(seed_ids)

    def _prepared_context(self, correlation_id: str) -> _PreparedContext:
        try:
            return self._prepared_by_correlation[correlation_id]
        except KeyError as error:
            raise ValueError("unknown heavenly decision correlation") from error

    def _durable_stage_record(
        self,
        context: _PreparedContext,
        *,
        correlation_id: str,
        stage: str,
    ) -> InterventionOutcomeMemoryEntry | None:
        records = [
            entry
            for entry in self._memory.list_domain(
                context.scope,
                "intervention_outcome",
                valid_at=context.recorded_at,
            )
            if isinstance(entry, InterventionOutcomeMemoryEntry)
            and entry.correlation_id == correlation_id
            and entry.stage == stage
        ]
        if len(records) > 1:
            raise ValueError(
                "multiple durable heavenly records exist for one correlation stage"
            )
        return records[0] if records else None

    def _dispatch_record_for(
        self,
        *,
        scope: HeavenlyGraphScope,
        correlation_id: str,
        valid_at: int,
    ) -> InterventionOutcomeMemoryEntry | None:
        records = [
            entry
            for entry in self._memory.list_domain(
                scope, "intervention_outcome", valid_at=valid_at
            )
            if isinstance(entry, InterventionOutcomeMemoryEntry)
            and entry.correlation_id == correlation_id
            and entry.stage == "dispatch"
        ]
        if len(records) > 1:
            raise SimingDuplicateDispatchError(
                "multiple durable heavenly dispatches exist for one correlation"
            )
        return records[0] if records else None

    def _record_dispatch_state(self, **kwargs) -> str:
        entry_id, batch = self._plan_dispatch_state(**kwargs)
        if batch is not None:
            self._memory._graph.write_batch(batch)
        return entry_id

    def _plan_dispatch_state(
        self,
        *,
        scope: HeavenlyGraphScope,
        recorded_at: int,
        correlation_id: str,
        dispatch_event_id: str,
        state: str,
        prior_batch: HeavenlyGraphWriteBatch | None = None,
    ) -> tuple[str, HeavenlyGraphWriteBatch | None]:
        if not dispatch_event_id:
            raise ValueError("dispatch event identity is required")
        prior = self._dispatch_record_for(
            scope=scope,
            correlation_id=correlation_id,
            valid_at=recorded_at,
        )
        prior_revision = None
        if prior_batch is not None:
            if (prior_batch.scope != scope or len(prior_batch.nodes) != 1 or prior_batch.relations
                    or prior_batch.nodes[0].node_type != "memory:intervention_outcome"):
                raise ValueError("dispatch_prior_batch_invalid")
            node = prior_batch.nodes[0]
            _, expected = self._plan_dispatch_state(scope=scope, recorded_at=recorded_at,
                correlation_id=correlation_id, dispatch_event_id=dispatch_event_id, state="sent_unconfirmed")
            if expected is not None:
                if prior_batch != expected:
                    raise ValueError("dispatch_prior_batch_invalid")
            else:
                original_key = f"{node.node_id}:{node.revision}:sent_unconfirmed"
                original = HeavenlyGraphWriteBatch(scope=scope, transaction_id=original_key,
                    idempotency_key=original_key, nodes=[node])
                if (prior_batch != original or not self._memory._graph.has_idempotency_key(scope=scope, idempotency_key=original_key)
                        or self._memory._graph.get_node(scope=scope, node_id=node.node_id, valid_at=recorded_at) != node):
                    raise ValueError("dispatch_prior_batch_invalid")
            frozen = InterventionOutcomeMemoryEntry.model_validate(node.attributes)
            if (frozen.stage != "dispatch" or frozen.correlation_id != correlation_id
                    or self._dispatch_event_id(frozen) != dispatch_event_id
                    or self._dispatch_state(frozen) != "sent_unconfirmed"
                    or state != "authority_confirmed" or node.recorded_at != recorded_at):
                raise ValueError("dispatch_prior_batch_invalid")
            if prior is not None and self._dispatch_event_id(prior) != dispatch_event_id:
                raise SimingDuplicateDispatchError("a heavenly dispatch is already recorded for this correlation")
            prior, prior_revision = frozen, node.revision
        if prior is not None:
            if self._dispatch_event_id(prior) != dispatch_event_id:
                raise SimingDuplicateDispatchError(
                    "a heavenly dispatch is already recorded for this correlation"
                )
            if self._dispatch_state(prior) == "authority_confirmed":
                return prior.entry_id, None
            if self._dispatch_state(prior) == state:
                return prior.entry_id, None
        entry_id = self._entry_id("dispatch", correlation_id, dispatch_event_id)
        revision = prior_revision if prior_batch is not None else self._memory.entry_revision(
            scope=scope, entry_id=entry_id, valid_at=recorded_at
        )
        next_revision = (revision or 0) + 1
        batch = self._memory.plan_write_entry(
            scope=scope,
            entry=InterventionOutcomeMemoryEntry(
                entry_id=entry_id,
                stage="dispatch",
                correlation_id=correlation_id,
                authority_result_ref=dispatch_event_id,
                dispatch_event_id=dispatch_event_id,
                dispatch_state=state,  # type: ignore[arg-type]
                reason=state,
            ),
            validity=GraphValidity(valid_from=recorded_at),
            recorded_at=recorded_at,
            revision=next_revision,
            supersedes_revision=revision,
            provenance=GraphProvenance(
                source_kind="siming_projection",
                source_ref=entry_id,
                causation_id=correlation_id,
                correlation_id=correlation_id,
                producer_system="siming_heavenly_runtime_support",
            ),
            transaction_id=f"{entry_id}:{next_revision}:{state}",
            idempotency_key=f"{entry_id}:{next_revision}:{state}",
        )
        return entry_id, batch

    @staticmethod
    def _dispatch_event_id(record: InterventionOutcomeMemoryEntry) -> str:
        return record.dispatch_event_id or record.authority_result_ref or ""

    @staticmethod
    def _dispatch_state(record: InterventionOutcomeMemoryEntry) -> str | None:
        if record.dispatch_state is not None:
            return record.dispatch_state
        if record.authority_result_ref:
            # Dispatch records written before the explicit state field existed
            # were persisted only after publisher success.
            return "authority_confirmed"
        return None

    def _is_selected_candidate(self, event: AuthorityEvent) -> bool:
        candidate = self.find_candidate(event)
        return candidate is not None and self._has_selection(
            scope=self._scope_for(event),
            correlation_id=event.correlation_id,
            valid_at=event.producer_ts,
            node_id=candidate.node_ref,
        )

    def _require_active_owned(self, prepared: PreparedHeavenlyDecision) -> None:
        if self.mode != "active" or not prepared.owns_event_family:
            raise ValueError("only active graph-owned decisions may be selected")
        if prepared.degraded_reason:
            raise ValueError(prepared.degraded_reason)

    def _graph_degraded(
        self,
        event: AuthorityEvent,
        event_family: str,
        error: Exception,
    ) -> PreparedHeavenlyDecision:
        return PreparedHeavenlyDecision(
            mode=self.mode,
            event_family=event_family,
            owns_event_family=False,
            correlation_id=event.correlation_id,
            context_hash="",
            scope=self._scope_for(event), recorded_at=event.producer_ts,
            degraded_reason=f"graph_degraded:{type(error).__name__}",
        )

    def _llm_unavailable(
        self,
        event: AuthorityEvent,
        event_family: str,
        error: SimingLlmProviderError,
    ) -> PreparedHeavenlyDecision:
        return PreparedHeavenlyDecision(
            mode=self.mode,
            event_family=event_family,
            owns_event_family=False,
            correlation_id=event.correlation_id,
            context_hash="",
            scope=self._scope_for(event), recorded_at=event.producer_ts,
            degraded_reason=f"llm_unavailable:{type(error).__name__}",
        )

    def find_staging_request(self, event: AuthorityEvent) -> StagingRequest | None:
        candidate = self.find_candidate(event)
        return candidate.staging_request if candidate is not None else None

    def find_candidate(self, event: AuthorityEvent) -> PreparedHeavenlyCandidate | None:
        scope = self._scope_for(event)
        return self._candidate_for(
            scope=scope,
            correlation_id=event.correlation_id,
            valid_at=event.producer_ts,
        )

    def _staging_request_for(
        self,
        *,
        scope: HeavenlyGraphScope,
        correlation_id: str,
        valid_at: int,
        node_id: str | None = None,
    ) -> StagingRequest | None:
        candidate = self._candidate_for(
            scope=scope,
            correlation_id=correlation_id,
            valid_at=valid_at,
            node_id=node_id,
        )
        return candidate.staging_request if candidate is not None else None

    def _candidate_for(
        self,
        *,
        scope: HeavenlyGraphScope,
        correlation_id: str,
        valid_at: int,
        node_id: str | None = None,
    ) -> PreparedHeavenlyCandidate | None:
        candidates = [
            entry
            for entry in self._memory.list_domain(
                scope,
                "intervention_outcome",
                valid_at=valid_at,
            )
            if isinstance(entry, InterventionOutcomeMemoryEntry)
            and entry.correlation_id == correlation_id
            and entry.stage == "proposal"
            and entry.staging_request is not None
            and entry.proposal is not None
        ]
        selections = [
            entry.selected_node_ref
            for entry in self._memory.list_domain(
                scope,
                "intervention_outcome",
                valid_at=valid_at,
            )
            if isinstance(entry, InterventionOutcomeMemoryEntry)
            and entry.correlation_id == correlation_id
            and entry.stage == "selection"
        ]
        selected_node_ref = node_id or (selections[0] if selections else None)
        matches = [
            PreparedHeavenlyCandidate(
                node_ref=entry.selected_node_ref or entry.staging_request.node_id,
                proposal=entry.proposal,
                staging_request=entry.staging_request,
            )
            for entry in candidates
            if selected_node_ref is None or entry.selected_node_ref == selected_node_ref
        ]
        if len(matches) > 1:
            raise ValueError(
                "multiple durable staging requests exist for one correlation"
            )
        return matches[0] if matches else None

    def _has_selection(
        self,
        *,
        scope: HeavenlyGraphScope,
        correlation_id: str,
        valid_at: int,
        node_id: str,
    ) -> bool:
        return any(
            isinstance(entry, InterventionOutcomeMemoryEntry)
            and entry.correlation_id == correlation_id
            and entry.stage == "selection"
            and entry.selected_node_ref == node_id
            for entry in self._memory.list_domain(
                scope,
                "intervention_outcome",
                valid_at=valid_at,
            )
        )

    def _record(self, **kwargs) -> str:
        batch = self._plan_record(**kwargs)
        self._memory._graph.write_batch(batch)
        return batch.nodes[0].node_id

    def _plan_record(
        self,
        *,
        scope: HeavenlyGraphScope,
        recorded_at: int,
        correlation_id: str,
        stage: str,
        selected_node_ref: str | None = None,
        authority_result_ref: str | None = None,
        staging_ack: StagingAck | None = None,
        staging_request: StagingRequest | None = None,
        proposal: AdaptiveBridgeNodeProposal | None = None,
        entry_value: str | None = None,
        reason: str = "",
    ) -> HeavenlyGraphWriteBatch:
        entry_id = self._entry_id(
            stage,
            correlation_id,
            entry_value or selected_node_ref or authority_result_ref or "record",
        )
        return self._memory.plan_write_entry(
            scope=scope,
            entry=InterventionOutcomeMemoryEntry(
                entry_id=entry_id,
                stage=stage,
                correlation_id=correlation_id,
                selected_node_ref=selected_node_ref,
                authority_result_ref=authority_result_ref,
                staging_ack=staging_ack,
                staging_request=staging_request,
                proposal=proposal,
                reason=reason,
            ),
            validity=GraphValidity(valid_from=recorded_at),
            recorded_at=recorded_at,
            revision=1,
            supersedes_revision=None,
            provenance=GraphProvenance(
                source_kind="siming_projection",
                source_ref=entry_id,
                causation_id=correlation_id,
                correlation_id=correlation_id,
                producer_system="siming_heavenly_runtime_support",
            ),
            transaction_id=entry_id,
            idempotency_key=entry_id,
        )

    @staticmethod
    def _provenance(entry_id: str, correlation_id: str) -> GraphProvenance:
        return GraphProvenance(
            source_kind="siming_projection",
            source_ref=entry_id,
            causation_id=correlation_id,
            correlation_id=correlation_id,
            producer_system="siming_heavenly_runtime_support",
        )

    @staticmethod
    def _entry_id(stage: str, correlation_id: str, value: str) -> str:
        return f"heavenly_{stage}:{correlation_id}:{value}"
    def prepared_actor_ids(self, frame: dict) -> list[str]:
        context = SimingCompiledContext.model_validate(frame["context"])
        return sorted((set(context.request.relevant_actor_ids) - {"siming"}) | {"char_b", "char_c"} |
                      {actor for package in self._resources._packages.values() for actor in package.actor_ids})

    def capture_prepared_pin(self, frame: dict) -> dict:
        from app.models.siming_actor_memory_read import ActorMemoryReadRequest
        request = SimingCompiledContext.model_validate(frame["context"]).request
        seed_ids = set(request.seed_node_ids)
        seed_ids.update(f"story_obligation:{ref.removeprefix('obligation:')}" for ref in request.seed_node_ids if ref.startswith("obligation:"))
        graph = self._compiler._graph.query_subgraph(
            scope=request.scope, seed_node_ids=sorted(seed_ids),
            relation_types=request.relation_types, direction="both", max_depth=4,
            valid_at=request.valid_at, recorded_at=request.recorded_at,
            node_limit=request.node_limit, relation_limit=request.relation_limit,
        )
        from app.models.siming_heavenly_graph import GraphReaderContext, NodeLookupQuery
        semantic_query = NodeLookupQuery(
            context=GraphReaderContext(reader_principal="reader:siming",
                allowed_visibility_scopes=("siming_internal", "authority_only", "branch_only"),
                world_id=request.scope.world_id, session_id=request.scope.session_id,
                story_branch_id=request.scope.story_branch_id, valid_at=request.valid_at,
                recorded_at=request.recorded_at, policy_revision="policy:v1"),
            scope=request.scope, node_ids=sorted(seed_ids | {node.node_id for node in graph.nodes}), limit=1000,
        )
        if semantic_query.node_ids:
            semantic = self._compiler._graph.query_semantic(semantic_query)
        else:
            from app.services.heavenly_graph_queries import HeavenlyGraphSemanticQueryFacade
            semantic = HeavenlyGraphSemanticQueryFacade(self._compiler._graph).empty_selection(semantic_query)
        graph.nodes.sort(key=lambda node: node.node_id)
        graph.relations.sort(key=lambda relation: relation.relation_id)
        # 完整节点/关系及集合成员，不依赖只包含 ID 的 compiled context hash。
        return {
            "graph": graph.model_dump(mode="json"),
            "semantic": {"nodes": [node.model_dump(mode="json") for node in sorted(semantic.nodes, key=lambda node: node.node_id)],
                         "policy": semantic.policy_revision, "scope": semantic.scope_digest,
                         "branch_revision": semantic.revision_vector.branch_revision,
                         "policy_revision": semantic.revision_vector.policy_revision,
                         "incomplete": semantic.incomplete_reason, "truncated": semantic.truncated},
            "resources": [package.model_dump(mode="json") for _, package in sorted(self._resources._packages.items())],
            "fatigue": list(self._resources._recent_signatures),
            # 核对完整读结果的内容摘要，避免每次入站转移重复持久化全部角色记忆。
            "actors": {actor: digest(self._actor_memory.read(ActorMemoryReadRequest(
                actor_id=actor, story_branch_id=request.scope.story_branch_id, valid_at=request.valid_at,
            )).model_dump(mode="json")) for actor in self.prepared_actor_ids(frame)},
            "mode": self.mode,
            "staging": [entry.model_dump(mode="json") for entry in self._memory.list_domain(
                request.scope, "intervention_outcome", valid_at=request.valid_at)
                if entry.correlation_id == frame["event"]["correlation_id"]],
        }

    def completion_within_prepared(self, frame: dict, completion: SimingProviderCompletion, frozen_pin: dict) -> bool:
        context = SimingCompiledContext.model_validate(frame["context"])
        allowed_refs = {node["node_id"] for node in frozen_pin["graph"]["nodes"]}
        allowed_refs.update(ref.removeprefix("story_obligation:") for ref in list(allowed_refs) if ref.startswith("story_obligation:"))
        allowed_refs.update(canonical_obligation_id(ref) for ref in context.selected_node_refs if ref.startswith("obligation:"))
        allowed_actors = set(self.prepared_actor_ids(frame))
        if completion.proposal_batch is None:
            return False
        for proposal in completion.proposal_batch.proposals:
            refs = {proposal.causal_gap_ref, *proposal.supporting_fact_refs, *proposal.obligation_refs, *proposal.attractor_refs}
            actors = {proposal.target_actor_id, *proposal.realization_request.actor_bindings.values()} - {None}
            if not refs.issubset(allowed_refs) or not actors.issubset(allowed_actors):
                return False
            # 输出 ID 尚未知时不扩大冻结依赖；已存在的节点仅允许它本来就在读集。
            node_id = f"runtime:bridge:{proposal.proposal_id}"
            if node_id not in allowed_refs and self._story.read_runtime_node(
                scope=context.request.scope, node_id=node_id, valid_at=context.request.valid_at) is not None:
                return False
        return True
