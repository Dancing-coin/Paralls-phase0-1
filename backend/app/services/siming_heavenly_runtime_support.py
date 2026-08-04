from __future__ import annotations

from dataclasses import dataclass
from typing import Any

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
    SimingContextRequest,
)
from app.services.siming_actor_memory_gateway import ActorMemoryReadGateway
from app.services.siming_context_compiler import SimingContextCompiler
from app.services.siming_heavenly_memory import SimingHeavenlyMemoryService
from app.services.siming_llm_provider import SimingLlmCandidateProvider
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
        bridges: Any,
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
        self._selected_node_by_correlation: dict[str, str] = {}
        self._dispatch_event_by_correlation: dict[str, str] = {}

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
            return PreparedHeavenlyDecision(
                mode=self.mode,
                event_family=event_family,
                owns_event_family=owns_event_family,
                correlation_id=event.correlation_id,
                context_hash="",
                degraded_reason=f"graph_degraded:{type(error).__name__}",
            )

        audit_ref = self._record(
            scope=scope,
            recorded_at=event.producer_ts,
            correlation_id=event.correlation_id,
            stage="proposal",
            reason="shadow_advisory" if self.mode == "shadow" else "prepared",
        )
        return PreparedHeavenlyDecision(
            mode=self.mode,
            event_family=event_family,
            owns_event_family=owns_event_family,
            correlation_id=event.correlation_id,
            context_hash=context.context_hash,
            eligible_node_refs=[],
            validation_audit_refs=[audit_ref],
        )

    def record_selection(
        self,
        prepared: PreparedHeavenlyDecision,
        selected_node_ref: str,
    ) -> str:
        self._require_active_owned(prepared)
        context = self._prepared_context(prepared.correlation_id)
        prior_selection = self._selected_node_by_correlation.get(
            prepared.correlation_id
        )
        if prior_selection is not None and prior_selection != selected_node_ref:
            raise ValueError(
                "a heavenly decision is already selected for this correlation"
            )
        record_ref = self._record(
            scope=context.scope,
            recorded_at=context.recorded_at,
            correlation_id=prepared.correlation_id,
            stage="selection",
            selected_node_ref=selected_node_ref,
        )
        self._selected_node_by_correlation[prepared.correlation_id] = selected_node_ref
        return record_ref

    def record_dispatch(self, *, correlation_id: str, dispatch_event_id: str) -> str:
        context = self._prepared_context(correlation_id)
        if self.mode != "active" or not context.owns_event_family:
            raise ValueError("only active graph-owned decisions may record dispatch")
        prior_dispatch = self._dispatch_event_by_correlation.get(correlation_id)
        if prior_dispatch is not None and prior_dispatch != dispatch_event_id:
            raise ValueError(
                "a heavenly dispatch is already recorded for this correlation"
            )
        record_ref = self._record(
            scope=context.scope,
            recorded_at=context.recorded_at,
            correlation_id=correlation_id,
            stage="dispatch",
            authority_result_ref=dispatch_event_id,
        )
        self._dispatch_event_by_correlation[correlation_id] = dispatch_event_id
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

    def _require_active_owned(self, prepared: PreparedHeavenlyDecision) -> None:
        if self.mode != "active" or not prepared.owns_event_family:
            raise ValueError("only active graph-owned decisions may be selected")
        if prepared.degraded_reason:
            raise ValueError(prepared.degraded_reason)

    def _record(
        self,
        *,
        scope: HeavenlyGraphScope,
        recorded_at: int,
        correlation_id: str,
        stage: str,
        selected_node_ref: str | None = None,
        authority_result_ref: str | None = None,
        reason: str = "",
    ) -> str:
        entry_id = f"heavenly_{stage}:{correlation_id}:{selected_node_ref or authority_result_ref or 'record'}"
        self._memory.write_entry(
            scope=scope,
            entry=InterventionOutcomeMemoryEntry(
                entry_id=entry_id,
                stage=stage,
                correlation_id=correlation_id,
                selected_node_ref=selected_node_ref,
                authority_result_ref=authority_result_ref,
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
