from __future__ import annotations

import hashlib
from collections.abc import Callable

from app.models.siming_actor_memory_read import ActorMemoryReadRequest
from app.models.siming_adaptive_bridge import (
    AdaptiveBridgeNodeProposal,
    AdaptiveBridgeValidationResult,
    SimingLlmProposalAudit,
)
from app.models.siming_heavenly_graph import (
    GraphProvenance,
    GraphValidity,
    HeavenlyGraphNode,
    HeavenlyGraphWriteBatch,
)
from app.models.siming_heavenly_memory import SimingCompiledContext
from app.models.siming_story_graph import StoryNodeBlueprint
from app.services.siming_actor_memory_gateway import ActorMemoryReadGateway
from app.services.siming_heavenly_graph_port import HeavenlyGraphPort
from app.services.siming_resource_capability_registry import ResourceCapabilityRegistry
from app.services.siming_story_graph_runtime import SimingStoryGraphRuntime
from app.services.siming_story_obligation_runtime import SimingStoryObligationRuntime


class SimingAdaptiveBridgeError(RuntimeError):
    pass


def canonical_obligation_id(reference: str) -> str:
    return reference.removeprefix("obligation:")


class SimingAdaptiveBridge:
    _AUDIT_NODE_TYPE = "adaptive_bridge_audit"
    _PATTERN_TITLES = {
        "private_confrontation": "Adaptive private confrontation",
        "consequence_reveal": "Adaptive consequence reveal",
        "relationship_shift": "Adaptive relationship shift",
        "alternative_opportunity": "Adaptive alternative opportunity",
        "delayed_payoff": "Adaptive delayed payoff",
        "aftermath": "Adaptive aftermath",
    }

    def __init__(
        self,
        *,
        graph: HeavenlyGraphPort,
        compiled_context: SimingCompiledContext,
        story_runtime: SimingStoryGraphRuntime,
        obligations: SimingStoryObligationRuntime,
        resources: ResourceCapabilityRegistry,
        actor_memory_gateway: ActorMemoryReadGateway,
        actor_autonomy: Callable[[AdaptiveBridgeNodeProposal], bool],
    ) -> None:
        self._graph = graph
        self._context = compiled_context
        self._scope = compiled_context.request.scope
        self._valid_at = compiled_context.request.valid_at
        self._recorded_at = (
            compiled_context.request.recorded_at
            if compiled_context.request.recorded_at is not None
            else self._valid_at
        )
        self._story_runtime = story_runtime
        self._obligations = obligations
        self._resources = resources
        self._actor_memory_gateway = actor_memory_gateway
        self._actor_autonomy = actor_autonomy

    @property
    def story_runtime(self) -> SimingStoryGraphRuntime:
        return self._story_runtime

    def validate_and_commit(
        self,
        proposal: AdaptiveBridgeNodeProposal,
        *,
        provider_audit: SimingLlmProposalAudit,
    ) -> AdaptiveBridgeValidationResult:
        prior = self._read_audit(proposal)
        if prior is not None:
            return prior

        checks = (
            self._validate_schema_and_pattern,
            self._validate_existing_facts,
            self._validate_no_terminal_resurrection,
            self._validate_actor_memory,
            self._validate_open_obligations,
            self._validate_autonomy,
            self._validate_resource_match,
        )
        reasons = [
            reason
            for check in checks
            for reason in check(proposal, provider_audit)
        ]
        if reasons:
            result = AdaptiveBridgeValidationResult(
                accepted=False,
                proposal_id=proposal.proposal_id,
                reason_codes=reasons,
            )
            self._write_audit(proposal, provider_audit, result)
            return result

        result = self._commit_new_runtime_node(proposal)
        self._write_audit(proposal, provider_audit, result)
        return result

    def _validate_schema_and_pattern(
        self,
        proposal: AdaptiveBridgeNodeProposal,
        provider_audit: SimingLlmProposalAudit,
    ) -> list[str]:
        if proposal.pattern not in self._PATTERN_TITLES:
            return ["bridge_pattern_invalid"]
        if proposal.correlation_id != provider_audit.correlation_id:
            return ["correlation_mismatch"]
        return []

    def _validate_existing_facts(
        self,
        proposal: AdaptiveBridgeNodeProposal,
        provider_audit: SimingLlmProposalAudit,
    ) -> list[str]:
        del provider_audit
        known_fact_refs = {entry.entry_id for entry in self._context.world_facts}
        return (
            []
            if set(proposal.supporting_fact_refs).issubset(known_fact_refs)
            else ["supporting_fact_missing"]
        )

    def _validate_no_terminal_resurrection(
        self,
        proposal: AdaptiveBridgeNodeProposal,
        provider_audit: SimingLlmProposalAudit,
    ) -> list[str]:
        del provider_audit
        node_refs = [
            self._runtime_node_id(proposal),
            proposal.causal_gap_ref,
            *proposal.supporting_fact_refs,
            *proposal.obligation_refs,
            *proposal.attractor_refs,
        ]
        for node_ref in node_refs:
            node = self._story_runtime.read_runtime_node(
                scope=self._scope,
                node_id=node_ref,
                valid_at=self._valid_at,
            )
            if node is not None and node.terminal:
                return ["terminal_node_resurrection"]
        return []

    def _validate_actor_memory(
        self,
        proposal: AdaptiveBridgeNodeProposal,
        provider_audit: SimingLlmProposalAudit,
    ) -> list[str]:
        del provider_audit
        if proposal.pattern != "private_confrontation":
            return []
        memory = self._actor_memory_gateway.read(
            ActorMemoryReadRequest(
                actor_id="char_b",
                story_branch_id=self._scope.story_branch_id,
                valid_at=self._valid_at,
            )
        )
        if memory.completeness != "complete":
            return ["memory_surface_incomplete"]
        destruction_refs = {
            entry.authority_result_ref
            for entry in self._context.world_facts
            if entry.entry_id in proposal.supporting_fact_refs
        }
        event_refs = {
            ref
            for record in memory.bundle.event_memories
            for ref in (record.source_event_id, *record.refs)
            if ref
        }
        observation_refs = {
            ref
            for record in memory.bundle.observation_memories
            for ref in (record.source_event_id, *record.refs)
            if ref
        }
        if not destruction_refs.intersection(event_refs).intersection(observation_refs):
            return ["actor_did_not_observe"]
        return []

    def _validate_open_obligations(
        self,
        proposal: AdaptiveBridgeNodeProposal,
        provider_audit: SimingLlmProposalAudit,
    ) -> list[str]:
        del provider_audit
        for obligation_id in proposal.obligation_refs:
            obligation = self._obligations.read(
                scope=self._scope,
                obligation_id=canonical_obligation_id(obligation_id),
                valid_at=self._valid_at,
            )
            if obligation is None or obligation.status != "open":
                return ["obligation_not_open"]
        return []

    def _validate_autonomy(
        self,
        proposal: AdaptiveBridgeNodeProposal,
        provider_audit: SimingLlmProposalAudit,
    ) -> list[str]:
        del provider_audit
        return [] if self._actor_autonomy(proposal) else ["actor_autonomy_rejected"]

    def _validate_resource_match(
        self,
        proposal: AdaptiveBridgeNodeProposal,
        provider_audit: SimingLlmProposalAudit,
    ) -> list[str]:
        del provider_audit
        match = self._resources.match(
            proposal.realization_request,
            world_ts=self._valid_at,
        )
        return [] if match.accepted else ["resource_unavailable"]

    def _commit_new_runtime_node(
        self,
        proposal: AdaptiveBridgeNodeProposal,
    ) -> AdaptiveBridgeValidationResult:
        node_id = self._runtime_node_id(proposal)
        blueprint = StoryNodeBlueprint(
            blueprint_id=self._bridge_blueprint_id(proposal),
            title=self._PATTERN_TITLES[proposal.pattern],
        )
        self._story_runtime.seed_blueprint(
            scope=self._scope,
            blueprint=blueprint,
            provenance=self._provenance(proposal),
            recorded_at=self._recorded_at,
        )
        existing = self._story_runtime.read_runtime_node(
            scope=self._scope,
            node_id=node_id,
            valid_at=self._valid_at,
        )
        causal_basis_refs = sorted(
            {proposal.causal_gap_ref, *proposal.supporting_fact_refs, *proposal.obligation_refs}
        )
        if existing is not None:
            if (
                existing.blueprint_id != blueprint.blueprint_id
                or existing.causal_basis_refs != causal_basis_refs
            ):
                raise SimingAdaptiveBridgeError("proposal ID was reused with different bridge inputs")
        else:
            self._story_runtime.instantiate(
                scope=self._scope,
                blueprint_id=blueprint.blueprint_id,
                node_id=node_id,
                causal_basis_refs=causal_basis_refs,
                recorded_at=self._recorded_at,
            )
        return AdaptiveBridgeValidationResult(
            accepted=True,
            proposal_id=proposal.proposal_id,
            graph_transaction_ref=f"story_instantiate:{node_id}",
            runtime_node_ref=node_id,
        )

    def _read_audit(
        self,
        proposal: AdaptiveBridgeNodeProposal,
    ) -> AdaptiveBridgeValidationResult | None:
        node = self._graph.get_node(
            node_id=self._audit_node_id(proposal),
            scope=self._scope,
            valid_at=self._valid_at,
        )
        if node is None:
            return None
        if node.node_type != self._AUDIT_NODE_TYPE:
            raise SimingAdaptiveBridgeError("adaptive bridge audit has an invalid node type")
        if node.attributes.get("proposal_fingerprint") != self._proposal_fingerprint(proposal):
            raise SimingAdaptiveBridgeError("proposal ID was reused with different bridge inputs")
        return AdaptiveBridgeValidationResult.model_validate(node.attributes["validation"])

    def _write_audit(
        self,
        proposal: AdaptiveBridgeNodeProposal,
        provider_audit: SimingLlmProposalAudit,
        result: AdaptiveBridgeValidationResult,
    ) -> None:
        audit_id = self._audit_node_id(proposal)
        self._graph.write_batch(
            HeavenlyGraphWriteBatch(
                transaction_id=audit_id,
                idempotency_key=audit_id,
                scope=self._scope,
                nodes=[
                    HeavenlyGraphNode(
                        node_id=audit_id,
                        node_type=self._AUDIT_NODE_TYPE,
                        scope=self._scope,
                        validity=GraphValidity(valid_from=self._valid_at),
                        recorded_at=self._recorded_at,
                        revision=1,
                        provenance=self._provenance(proposal),
                        attributes={
                            "proposal_id": proposal.proposal_id,
                            "proposal": proposal.model_dump(mode="json"),
                            "proposal_fingerprint": self._proposal_fingerprint(proposal),
                            "provider_audit": provider_audit.model_dump(mode="json"),
                            "validation": result.model_dump(mode="json"),
                        },
                    )
                ],
            )
        )

    @staticmethod
    def _runtime_node_id(proposal: AdaptiveBridgeNodeProposal) -> str:
        return f"runtime:bridge:{proposal.proposal_id}"

    @staticmethod
    def _bridge_blueprint_id(proposal: AdaptiveBridgeNodeProposal) -> str:
        return f"adaptive_bridge:{proposal.pattern}"

    @staticmethod
    def _audit_node_id(proposal: AdaptiveBridgeNodeProposal) -> str:
        return f"adaptive_bridge_audit:{proposal.proposal_id}"

    @staticmethod
    def _proposal_fingerprint(proposal: AdaptiveBridgeNodeProposal) -> str:
        return hashlib.sha256(proposal.model_dump_json().encode("utf-8")).hexdigest()

    @staticmethod
    def _provenance(proposal: AdaptiveBridgeNodeProposal) -> GraphProvenance:
        return GraphProvenance(
            source_kind="siming_projection",
            source_ref=proposal.proposal_id,
            causation_id=proposal.causal_gap_ref,
            correlation_id=proposal.correlation_id,
            producer_system="siming_adaptive_bridge",
        )
