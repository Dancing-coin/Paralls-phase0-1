from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from pydantic import BaseModel, Field

from app.config import SimingHeavenlyMode
from app.models.authority_event import AuthorityEvent
from app.models.siming_event import SimingInput
from app.models.siming_heavenly_graph import (
    GraphProvenance,
    GraphValidity,
    HeavenlyGraphScope,
)
from app.models.siming_heavenly_memory import (
    InterventionOutcomeMemoryEntry,
    SimingCompiledContext,
    SimingContextRequest,
)
from app.models.siming_resource_capability import (
    StagingAck,
    StagingRequest,
    StagingResult,
)
from app.services.siming_actor_memory_gateway import ActorMemoryReadGateway
from app.services.siming_adaptive_bridge import SimingAdaptiveBridge
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
    validation_audit_refs: list[str] = Field(default_factory=list)
    degraded_reason: str = ""


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

    def prepare(self, siming_input: SimingInput) -> PreparedHeavenlyDecision:
        event = siming_input.source_event
        event_family = self._event_family(event)
        scope = self._scope_for(event)
        owns_event_family = (
            self.mode == "active" and event_family in self.GRAPH_OWNED_EVENT_FAMILIES
        )
        self._prepared_by_correlation[event.correlation_id] = _PreparedContext(
            scope=scope,
            recorded_at=event.producer_ts,
            owns_event_family=owns_event_family,
        )
        try:
            context = self._compiler.compile(
                SimingContextRequest(
                    scope=scope,
                    valid_at=event.producer_ts,
                    seed_node_ids=self._seed_node_ids(event),
                    relevant_actor_ids=event.routing.target_ids,
                )
            )
        except Exception as error:
            return self._graph_degraded(event, event_family, error)

        proposal_batch = None
        if owns_event_family:
            try:
                proposal_batch = self._llm_provider.generate_adaptive_bridge_proposals(
                    compiled_context=context.model_dump(mode="json"),
                    correlation_id=event.correlation_id,
                )
            except SimingLlmProviderError as error:
                return self._llm_unavailable(event, event_family, error)
        try:
            eligible_node_refs = []
            validation_audit_refs = []
            if proposal_batch is not None:
                bridge = self._bridges(context)
                validation_results = [
                    (
                        proposal,
                        bridge.validate_and_commit(
                            proposal,
                            provider_audit=proposal_batch.audit,
                        ),
                    )
                    for proposal in proposal_batch.proposals
                ]
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
                        obligation_id=proposal.obligation_refs[0],
                        recorded_at=event.producer_ts,
                        resource_match=resource_match,
                    )
                    eligible_node_refs.append(validation.runtime_node_ref)
                    validation_audit_refs.append(
                        self._record(
                            scope=scope,
                            recorded_at=event.producer_ts,
                            correlation_id=event.correlation_id,
                            stage="proposal",
                            selected_node_ref=validation.runtime_node_ref,
                            staging_request=staging_request,
                            reason="candidate_prepared",
                        )
                    )
                eligible_node_refs.sort()
                validation_audit_refs.extend(
                    f"adaptive_bridge_audit:{proposal.proposal_id}"
                    for proposal in proposal_batch.proposals
                )
            validation_audit_refs.append(
                self._record(
                    scope=scope,
                    recorded_at=event.producer_ts,
                    correlation_id=event.correlation_id,
                    stage="proposal",
                    reason="shadow_advisory" if self.mode == "shadow" else "prepared",
                )
            )
        except Exception as error:
            return self._graph_degraded(event, event_family, error)
        return PreparedHeavenlyDecision(
            mode=self.mode,
            event_family=event_family,
            owns_event_family=owns_event_family,
            correlation_id=event.correlation_id,
            context_hash=context.context_hash,
            eligible_node_refs=eligible_node_refs,
            validation_audit_refs=validation_audit_refs,
        )

    def record_selection(
        self,
        prepared: PreparedHeavenlyDecision,
        selected_node_ref: str,
    ) -> str:
        self._require_active_owned(prepared)
        context = self._prepared_context(prepared.correlation_id)
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
        prior_dispatch = self._durable_stage_record(
            context,
            correlation_id=correlation_id,
            stage="dispatch",
        )
        if (
            prior_dispatch is not None
            and prior_dispatch.authority_result_ref != dispatch_event_id
        ):
            raise ValueError(
                "a heavenly dispatch is already recorded for this correlation"
            )
        if prior_dispatch is not None:
            return self._entry_id("dispatch", correlation_id, dispatch_event_id)
        record_ref = self._record(
            scope=context.scope,
            recorded_at=context.recorded_at,
            correlation_id=correlation_id,
            stage="dispatch",
            authority_result_ref=dispatch_event_id,
        )
        return record_ref

    def record_authority_outcome(self, event: AuthorityEvent) -> str | None:
        if self.mode == "off":
            return None
        context = self._prepared_by_correlation.get(event.correlation_id)
        scope = context.scope if context is not None else self._scope_for(event)
        return self._record(
            scope=scope,
            recorded_at=event.producer_ts,
            correlation_id=event.correlation_id,
            stage="authority_result",
            authority_result_ref=event.event_id,
            reason=event.event_type,
        )

    def select_for_staging(
        self,
        prepared: PreparedHeavenlyDecision,
        selected_node_ref: str,
    ) -> StagingRequest:
        self._require_active_owned(prepared)
        context = self._prepared_context(prepared.correlation_id)
        request = self._staging_request_for(
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
            return request
        node = self._story.read_runtime_node(
            scope=context.scope,
            node_id=selected_node_ref,
            valid_at=context.recorded_at,
        )
        if node is None:
            raise ValueError("selected heavenly candidate is missing its story node")
        if node.lifecycle == "latent":
            node = self._story.transition(
                scope=context.scope,
                node_id=selected_node_ref,
                expected="latent",
                target="eligible",
                reason="heavenly_candidate_validated",
                recorded_at=context.recorded_at,
            )
        if node.lifecycle != "eligible":
            raise ValueError("selected heavenly candidate is not eligible")
        selection_id = self._entry_id(
            "selection", prepared.correlation_id, selected_node_ref
        )
        self._story.transition_with_intervention_outcome(
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
        return request

    def record_staging_ack(self, event: AuthorityEvent) -> StagingRequest | None:
        request = self.find_staging_request(event)
        if request is None:
            return None
        ack = StagingAck.model_validate(event.payload)
        if ack.correlation_id != event.correlation_id:
            raise ValueError("staging acknowledgement correlation mismatch")
        self._record(
            scope=request.scope,
            recorded_at=event.producer_ts,
            correlation_id=event.correlation_id,
            stage="staging_ack",
            selected_node_ref=request.node_id,
            staging_ack=ack,
            entry_value=ack.source,
        )
        return request

    def complete_staging(self, event: AuthorityEvent) -> StagingResult | None:
        request = self.find_staging_request(event)
        if request is None or not self._has_selection(
            scope=request.scope,
            correlation_id=event.correlation_id,
            valid_at=event.producer_ts,
            node_id=request.node_id,
        ):
            return None
        acks = [
            entry.staging_ack
            for entry in self._memory.list_domain(
                request.scope,
                "intervention_outcome",
                valid_at=event.producer_ts,
            )
            if isinstance(entry, InterventionOutcomeMemoryEntry)
            and entry.correlation_id == event.correlation_id
            and entry.stage == "staging_ack"
            and entry.selected_node_ref == request.node_id
            and entry.staging_ack is not None
        ]
        if {ack.source for ack in acks} != self._staging.REQUIRED_ACK_SOURCES:
            return None
        return self._staging.complete(request, acks=acks)

    @staticmethod
    def _event_family(event: AuthorityEvent) -> str:
        payload = event.payload
        if (
            payload.get("target_ref") == "obj_letter"
            and payload.get("current_state") == "removed_from_surface"
        ):
            return "evidence_destruction_consequence"
        return event.event_type

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
        if not isinstance(raw_seed_ids, list) or not all(
            isinstance(node_id, str) and node_id for node_id in raw_seed_ids
        ):
            return []
        return sorted(set(raw_seed_ids))

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
        context = self._prepared_by_correlation.get(event.correlation_id)
        if context is not None:
            self._prepared_by_correlation[event.correlation_id] = _PreparedContext(
                scope=context.scope,
                recorded_at=context.recorded_at,
                owns_event_family=False,
            )
        return PreparedHeavenlyDecision(
            mode=self.mode,
            event_family=event_family,
            owns_event_family=False,
            correlation_id=event.correlation_id,
            context_hash="",
            degraded_reason=f"graph_degraded:{type(error).__name__}",
        )

    def _llm_unavailable(
        self,
        event: AuthorityEvent,
        event_family: str,
        error: SimingLlmProviderError,
    ) -> PreparedHeavenlyDecision:
        context = self._prepared_by_correlation.get(event.correlation_id)
        if context is not None:
            self._prepared_by_correlation[event.correlation_id] = _PreparedContext(
                scope=context.scope,
                recorded_at=context.recorded_at,
                owns_event_family=False,
            )
        return PreparedHeavenlyDecision(
            mode=self.mode,
            event_family=event_family,
            owns_event_family=False,
            correlation_id=event.correlation_id,
            context_hash="",
            degraded_reason=f"llm_unavailable:{type(error).__name__}",
        )

    def find_staging_request(self, event: AuthorityEvent) -> StagingRequest | None:
        scope = self._scope_for(event)
        return self._staging_request_for(
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
            entry.staging_request
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

    def _record(
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
        entry_value: str | None = None,
        reason: str = "",
    ) -> str:
        entry_id = self._entry_id(
            stage,
            correlation_id,
            entry_value or selected_node_ref or authority_result_ref or "record",
        )
        self._memory.write_entry(
            scope=scope,
            entry=InterventionOutcomeMemoryEntry(
                entry_id=entry_id,
                stage=stage,
                correlation_id=correlation_id,
                selected_node_ref=selected_node_ref,
                authority_result_ref=authority_result_ref,
                staging_ack=staging_ack,
                staging_request=staging_request,
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
        return entry_id

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
