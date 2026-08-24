from __future__ import annotations

from app.models.siming_heavenly_graph import (
    GraphProvenance,
    GraphReaderContext,
    GraphSemanticMetadata,
    GraphValidity,
    HeavenlyGraphNode,
    HeavenlyGraphScope,
    HeavenlyGraphWriteBatch,
    HeavenlyGraphWriteResult,
    NodeLookupQuery,
    HeavenlyNodeQuery,
)
from app.models.siming_story_graph import (
    NarrativeAttractor,
    NarrativeObligation,
    ObligationTransformResult,
    RuntimeStoryNode,
)
from app.services.siming_heavenly_graph_port import HeavenlyGraphPort
from app.services.siming_heavenly_memory import SimingHeavenlyMemoryService


class StoryObligationError(RuntimeError):
    pass


class SimingStoryObligationRuntime:
    _OBLIGATION_NODE_TYPE = "narrative_obligation"
    _ATTRACTOR_NODE_TYPE = "narrative_attractor"
    _RUNTIME_NODE_TYPE = "runtime_story_node"

    def __init__(
        self,
        graph: HeavenlyGraphPort,
        memory: SimingHeavenlyMemoryService,
    ) -> None:
        self._graph = graph
        self._memory = memory

    def seed(
        self,
        *,
        scope: HeavenlyGraphScope,
        obligation: NarrativeObligation,
        provenance: GraphProvenance,
        recorded_at: int,
    ) -> HeavenlyGraphWriteResult:
        existing = self.read(
            scope=scope,
            obligation_id=obligation.obligation_id,
            valid_at=recorded_at,
        )
        if existing is not None:
            if existing != obligation:
                raise StoryObligationError(
                    f"narrative obligation {obligation.obligation_id!r} already exists"
                )
            return HeavenlyGraphWriteResult(
                transaction_id=f"story_obligation_seed:{obligation.obligation_id}",
                idempotency_key=f"story_obligation_seed:{obligation.obligation_id}",
                applied=False,
                replayed=True,
            )
        return self._graph.write_batch(
            HeavenlyGraphWriteBatch(
                transaction_id=f"story_obligation_seed:{obligation.obligation_id}",
                idempotency_key=f"story_obligation_seed:{obligation.obligation_id}",
                scope=scope,
                nodes=[
                    self._obligation_graph_node(
                        scope=scope,
                        obligation=obligation,
                        prior=None,
                        recorded_at=recorded_at,
                        provenance=provenance,
                    )
                ],
            )
        )

    def read(
        self,
        *,
        scope: HeavenlyGraphScope,
        obligation_id: str,
        valid_at: int,
        recorded_at: int | None = None,
    ) -> NarrativeObligation | None:
        node = self._semantic_node(scope, self._obligation_node_id(obligation_id), valid_at, recorded_at)
        if node is None or node.node_type != self._OBLIGATION_NODE_TYPE:
            return None
        return NarrativeObligation.model_validate(node.attributes)

    def transform(
        self,
        *,
        scope: HeavenlyGraphScope,
        source_obligation_id: str,
        replacement: NarrativeObligation,
        authority_result_ref: str,
        correlation_id: str,
        recorded_at: int,
    ) -> ObligationTransformResult:
        if replacement.status != "open":
            raise StoryObligationError("replacement obligation must begin open")
        source_prior = self._obligation_graph_node_at(
            scope=scope,
            obligation_id=source_obligation_id,
            valid_at=recorded_at,
        )
        source = NarrativeObligation.model_validate(source_prior.attributes)
        replacement_prior = self._graph.get_node(
            node_id=self._obligation_node_id(replacement.obligation_id),
            scope=scope,
            valid_at=recorded_at,
        )
        transformed_refs = sorted(
            set([*source.transformed_to_refs, replacement.obligation_id])
        )
        transformed = source.model_copy(
            update={"status": "transformed", "transformed_to_refs": transformed_refs}
        )
        transaction_id = (
            f"story_obligation_transform:{source_obligation_id}:{replacement.obligation_id}:"
            f"{authority_result_ref}"
        )
        provenance = GraphProvenance(
            source_kind="runtime_outcome",
            source_ref=authority_result_ref,
            causation_id=authority_result_ref,
            correlation_id=correlation_id,
            producer_system="siming_story_obligation_runtime",
        )
        if source.status == "transformed":
            if source.transformed_to_refs == transformed_refs and replacement_prior is not None:
                existing_replacement = NarrativeObligation.model_validate(
                    replacement_prior.attributes
                )
                if existing_replacement == replacement:
                    return ObligationTransformResult(
                        source=source,
                        replacement=existing_replacement,
                        graph_transaction_ref=transaction_id,
                    )
            raise StoryObligationError("obligation was already transformed")
        if replacement_prior is not None:
            raise StoryObligationError(
                f"replacement obligation {replacement.obligation_id!r} already exists"
            )

        self._graph.write_batch(
            HeavenlyGraphWriteBatch(
                transaction_id=transaction_id,
                idempotency_key=transaction_id,
                scope=scope,
                nodes=[
                    self._obligation_graph_node(
                        scope=scope,
                        obligation=transformed,
                        prior=source_prior,
                        recorded_at=recorded_at,
                        provenance=provenance,
                    ),
                    self._obligation_graph_node(
                        scope=scope,
                        obligation=replacement,
                        prior=None,
                        recorded_at=recorded_at,
                        provenance=provenance,
                    ),
                ],
            )
        )
        return ObligationTransformResult(
            source=transformed,
            replacement=replacement,
            graph_transaction_ref=transaction_id,
        )

    def seed_attractor(
        self,
        *,
        scope: HeavenlyGraphScope,
        attractor: NarrativeAttractor,
        provenance: GraphProvenance,
        recorded_at: int,
    ) -> HeavenlyGraphWriteResult:
        existing = self.read_attractor(
            scope=scope,
            attractor_id=attractor.attractor_id,
            valid_at=recorded_at,
        )
        if existing is not None:
            if existing != attractor:
                raise StoryObligationError(
                    f"narrative attractor {attractor.attractor_id!r} already exists"
                )
            return HeavenlyGraphWriteResult(
                transaction_id=f"story_attractor_seed:{attractor.attractor_id}",
                idempotency_key=f"story_attractor_seed:{attractor.attractor_id}",
                applied=False,
                replayed=True,
            )
        return self._graph.write_batch(
            HeavenlyGraphWriteBatch(
                transaction_id=f"story_attractor_seed:{attractor.attractor_id}",
                idempotency_key=f"story_attractor_seed:{attractor.attractor_id}",
                scope=scope,
                nodes=[
                    self._attractor_graph_node(
                        scope=scope,
                        attractor=attractor,
                        prior=None,
                        recorded_at=recorded_at,
                        provenance=provenance,
                    )
                ],
            )
        )

    def read_attractor(
        self,
        *,
        scope: HeavenlyGraphScope,
        attractor_id: str,
        valid_at: int,
        recorded_at: int | None = None,
    ) -> NarrativeAttractor | None:
        node = self._semantic_node(scope, self._attractor_node_id(attractor_id), valid_at, recorded_at)
        if node is None or node.node_type != self._ATTRACTOR_NODE_TYPE:
            return None
        return NarrativeAttractor.model_validate(node.attributes)

    def evaluate_attractor(
        self,
        *,
        scope: HeavenlyGraphScope,
        attractor_id: str,
        valid_at: int,
    ) -> NarrativeAttractor:
        prior = self._attractor_graph_node_at(
            scope=scope,
            attractor_id=attractor_id,
            valid_at=valid_at,
        )
        attractor = NarrativeAttractor.model_validate(prior.attributes)
        reachability = (
            "blocked"
            if self._has_missing_facts(scope=scope, attractor=attractor, valid_at=valid_at)
            or self._has_unreplaced_closed_route(
                scope=scope,
                attractor=attractor,
                valid_at=valid_at,
            )
            else "reachable"
        )
        if attractor.reachability == reachability:
            return attractor
        updated = attractor.model_copy(update={"reachability": reachability})
        self._graph.write_batch(
            HeavenlyGraphWriteBatch(
                transaction_id=f"story_attractor_evaluate:{attractor_id}:{valid_at}",
                idempotency_key=f"story_attractor_evaluate:{attractor_id}:{valid_at}",
                scope=scope,
                nodes=[
                    self._attractor_graph_node(
                        scope=scope,
                        attractor=updated,
                        prior=prior,
                        recorded_at=valid_at,
                        provenance=GraphProvenance(
                            source_kind="runtime_outcome",
                            source_ref=f"story_attractor:{attractor_id}",
                            causation_id=f"story_attractor:{attractor_id}",
                            correlation_id=f"story_attractor:{attractor_id}:{valid_at}",
                            producer_system="siming_story_obligation_runtime",
                        ),
                    )
                ],
            )
        )
        return updated

    def _has_missing_facts(
        self,
        *,
        scope: HeavenlyGraphScope,
        attractor: NarrativeAttractor,
        valid_at: int,
    ) -> bool:
        return any(
            self._graph.get_node(
                node_id=fact_ref,
                scope=scope,
                valid_at=valid_at,
            )
            is None
            for fact_ref in attractor.required_fact_refs
        )

    def _has_unreplaced_closed_route(
        self,
        *,
        scope: HeavenlyGraphScope,
        attractor: NarrativeAttractor,
        valid_at: int,
    ) -> bool:
        runtime_nodes = self._runtime_nodes(scope=scope, valid_at=valid_at)
        by_id = {node.node_id: node for node in runtime_nodes}
        for node_id in attractor.forbidden_terminal_node_refs:
            route = by_id.get(node_id)
            if route is None or not (
                route.terminal or route.reachability != "reachable"
            ):
                continue
            has_alternative = any(
                candidate.node_id != route.node_id
                and candidate.blueprint_id == route.blueprint_id
                and not candidate.terminal
                and candidate.reachability == "reachable"
                and candidate.reopen_policy == "new_causal_basis"
                and bool(candidate.causal_basis_refs)
                for candidate in runtime_nodes
            )
            if not has_alternative:
                return True
        return False

    def _runtime_nodes(
        self,
        *,
        scope: HeavenlyGraphScope,
        valid_at: int,
    ) -> list[RuntimeStoryNode]:
        return [
            RuntimeStoryNode.model_validate(node.attributes)
            for node in self._graph.query_nodes(
                HeavenlyNodeQuery(
                    scope=scope,
                    valid_at=valid_at,
                    node_types=[self._RUNTIME_NODE_TYPE],
                    limit=None,
                )
            )
        ]

    @staticmethod
    def _obligation_node_id(obligation_id: str) -> str:
        return f"story_obligation:{obligation_id}"

    @staticmethod
    def _attractor_node_id(attractor_id: str) -> str:
        return f"story_attractor:{attractor_id}"

    def _obligation_graph_node_at(
        self,
        *,
        scope: HeavenlyGraphScope,
        obligation_id: str,
        valid_at: int,
    ) -> HeavenlyGraphNode:
        node = self._graph.get_node(
            node_id=self._obligation_node_id(obligation_id),
            scope=scope,
            valid_at=valid_at,
        )
        if node is None or node.node_type != self._OBLIGATION_NODE_TYPE:
            raise StoryObligationError(f"unknown obligation {obligation_id!r}")
        return node

    def _attractor_graph_node_at(
        self,
        *,
        scope: HeavenlyGraphScope,
        attractor_id: str,
        valid_at: int,
    ) -> HeavenlyGraphNode:
        node = self._graph.get_node(
            node_id=self._attractor_node_id(attractor_id),
            scope=scope,
            valid_at=valid_at,
        )
        if node is None or node.node_type != self._ATTRACTOR_NODE_TYPE:
            raise StoryObligationError(f"unknown attractor {attractor_id!r}")
        return node

    def _obligation_graph_node(
        self,
        *,
        scope: HeavenlyGraphScope,
        obligation: NarrativeObligation,
        prior: HeavenlyGraphNode | None,
        recorded_at: int,
        provenance: GraphProvenance,
    ) -> HeavenlyGraphNode:
        return HeavenlyGraphNode(
            node_id=self._obligation_node_id(obligation.obligation_id),
            node_type=self._OBLIGATION_NODE_TYPE,
            scope=scope,
            validity=GraphValidity(valid_from=recorded_at),
            recorded_at=recorded_at,
            revision=1 if prior is None else prior.revision + 1,
            supersedes_revision=None if prior is None else prior.revision,
            provenance=provenance,
            attributes=obligation.model_dump(mode="json"),
            semantic_metadata=GraphSemanticMetadata(
                record_kind="projection",
                visibility_scope="siming_internal",
                derivation_kind="projection",
                source_event_refs=(provenance.source_ref,),
                policy_revision="policy:v1",
                scope_digest="scope:siming-heavenly",
            ),
        )

    def _attractor_graph_node(
        self,
        *,
        scope: HeavenlyGraphScope,
        attractor: NarrativeAttractor,
        prior: HeavenlyGraphNode | None,
        recorded_at: int,
        provenance: GraphProvenance,
    ) -> HeavenlyGraphNode:
        return HeavenlyGraphNode(
            node_id=self._attractor_node_id(attractor.attractor_id),
            node_type=self._ATTRACTOR_NODE_TYPE,
            scope=scope,
            validity=GraphValidity(valid_from=recorded_at),
            recorded_at=recorded_at,
            revision=1 if prior is None else prior.revision + 1,
            supersedes_revision=None if prior is None else prior.revision,
            provenance=provenance,
            attributes=attractor.model_dump(mode="json"),
            semantic_metadata=GraphSemanticMetadata(
                record_kind="projection",
                visibility_scope="siming_internal",
                derivation_kind="projection",
                source_event_refs=(provenance.source_ref,),
                policy_revision="policy:v1",
                scope_digest="scope:siming-heavenly",
            ),
        )

    def _semantic_node(self, scope: HeavenlyGraphScope, node_id: str, valid_at: int, recorded_at: int | None) -> HeavenlyGraphNode | None:
        result = self._graph.query_semantic(
            NodeLookupQuery(
                context=GraphReaderContext(
                    reader_principal="reader:siming",
                    allowed_visibility_scopes=("siming_internal", "authority_only", "branch_only"),
                    world_id=scope.world_id,
                    session_id=scope.session_id,
                    story_branch_id=scope.story_branch_id,
                    valid_at=valid_at,
                    recorded_at=recorded_at,
                    policy_revision="policy:v1",
                ),
                scope=scope,
                node_ids=[node_id],
                limit=1,
            )
        )
        if result.nodes:
            return result.nodes[0]
        # Compatibility for pre-semantic story fixtures; newly written nodes
        # always carry policy:v1 metadata and are served by the facade above.
        return self._graph.get_node(
            node_id=node_id,
            scope=scope,
            valid_at=valid_at,
            recorded_at=recorded_at,
        )
