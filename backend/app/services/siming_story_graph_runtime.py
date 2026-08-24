from __future__ import annotations

from app.models.siming_heavenly_graph import (
    GraphProvenance,
    GraphReaderContext,
    GraphSemanticMetadata,
    GraphSemanticMetadata,
    GraphValidity,
    HeavenlyGraphNode,
    HeavenlyGraphScope,
    HeavenlyGraphWriteBatch,
    HeavenlyGraphWriteResult,
    NodeLookupQuery,
    HeavenlyNodeQuery,
)
from app.models.siming_heavenly_memory import (
    InterventionOutcomeMemoryEntry,
    StorylineObligationMemoryEntry,
)
from app.models.siming_story_graph import (
    AuthorityStoryOutcome,
    RuntimeStoryNode,
    StoryNodeBlueprint,
    StoryNodeTransitionCommand,
    StoryOutcomeApplication,
    StoryOutcomeEffect,
    StoryOutcomePort,
)
from app.services.siming_heavenly_graph_port import HeavenlyGraphPort
from app.services.siming_heavenly_memory import SimingHeavenlyMemoryService


class StoryGraphError(RuntimeError):
    pass


class StoryNodeTransitionError(StoryGraphError):
    pass


class SimingStoryGraphRuntime:
    _BLUEPRINT_NODE_TYPE = "authored_story_blueprint"
    _RUNTIME_NODE_TYPE = "runtime_story_node"
    _OUTCOME_NODE_TYPE = "story_authority_outcome"

    def __init__(
        self,
        graph: HeavenlyGraphPort,
        memory: SimingHeavenlyMemoryService,
    ) -> None:
        self._graph = graph
        self._memory = memory

    def seed_blueprint(
        self,
        *,
        scope: HeavenlyGraphScope,
        blueprint: StoryNodeBlueprint,
        provenance: GraphProvenance,
        recorded_at: int,
    ) -> HeavenlyGraphWriteResult:
        existing = self.read_blueprint(
            scope=scope,
            blueprint_id=blueprint.blueprint_id,
            valid_at=recorded_at,
        )
        if existing is not None:
            if existing != blueprint:
                raise StoryGraphError(
                    f"authored blueprint {blueprint.blueprint_id!r} is immutable"
                )
            return HeavenlyGraphWriteResult(
                transaction_id=f"story_seed:{blueprint.blueprint_id}",
                idempotency_key=f"story_seed:{blueprint.blueprint_id}",
                applied=False,
                replayed=True,
            )

        node = HeavenlyGraphNode(
            node_id=self._blueprint_node_id(blueprint.blueprint_id),
            node_type=self._BLUEPRINT_NODE_TYPE,
            scope=scope,
            validity=GraphValidity(valid_from=recorded_at),
            recorded_at=recorded_at,
            revision=1,
            provenance=provenance,
            attributes=blueprint.model_dump(mode="json"),
            semantic_metadata=GraphSemanticMetadata(
                record_kind="projection",
                visibility_scope="siming_internal",
                derivation_kind="projection",
                source_event_refs=(provenance.source_ref,),
                policy_revision="policy:v1",
                scope_digest="scope:siming-heavenly",
            ),
        )
        return self._graph.write_batch(
            HeavenlyGraphWriteBatch(
                transaction_id=f"story_seed:{blueprint.blueprint_id}",
                idempotency_key=f"story_seed:{blueprint.blueprint_id}",
                scope=scope,
                nodes=[node],
            )
        )

    def read_blueprint(
        self,
        *,
        scope: HeavenlyGraphScope,
        blueprint_id: str,
        valid_at: int,
        recorded_at: int | None = None,
    ) -> StoryNodeBlueprint | None:
        node = self._semantic_node(scope, self._blueprint_node_id(blueprint_id), valid_at, recorded_at)
        if node is None or node.node_type != self._BLUEPRINT_NODE_TYPE:
            return None
        return StoryNodeBlueprint.model_validate(node.attributes)

    def instantiate(
        self,
        *,
        scope: HeavenlyGraphScope,
        blueprint_id: str,
        node_id: str,
        causal_basis_refs: list[str],
        recorded_at: int,
    ) -> RuntimeStoryNode:
        if self.read_blueprint(
            scope=scope,
            blueprint_id=blueprint_id,
            valid_at=recorded_at,
        ) is None:
            raise StoryGraphError(f"unknown authored blueprint {blueprint_id!r}")
        existing = self.read_runtime_node(
            scope=scope,
            node_id=node_id,
            valid_at=recorded_at,
        )
        if existing is not None:
            raise StoryGraphError(f"runtime story node {node_id!r} already exists")

        runtime_node = RuntimeStoryNode(
            node_id=node_id,
            blueprint_id=blueprint_id,
            lifecycle="latent",
            reopen_policy=(
                "new_causal_basis" if causal_basis_refs else "same_instance"
            ),
            causal_basis_refs=causal_basis_refs,
        )
        self._graph.write_batch(
            HeavenlyGraphWriteBatch(
                transaction_id=f"story_instantiate:{node_id}",
                idempotency_key=f"story_instantiate:{node_id}",
                scope=scope,
                nodes=[
                    self._runtime_graph_node(
                        scope=scope,
                        runtime_node=runtime_node,
                        prior=None,
                        recorded_at=recorded_at,
                        provenance=GraphProvenance(
                            source_kind="runtime_outcome",
                            source_ref=(
                                causal_basis_refs[0]
                                if causal_basis_refs
                                else f"story_blueprint:{blueprint_id}"
                            ),
                            causation_id=(
                                causal_basis_refs[0]
                                if causal_basis_refs
                                else f"story_blueprint:{blueprint_id}"
                            ),
                            correlation_id=f"story_instance:{node_id}",
                            producer_system="siming_story_graph_runtime",
                        ),
                    )
                ],
            )
        )
        return runtime_node

    def read_runtime_node(
        self,
        *,
        scope: HeavenlyGraphScope,
        node_id: str,
        valid_at: int,
        recorded_at: int | None = None,
    ) -> RuntimeStoryNode | None:
        node = self._semantic_node(scope, node_id, valid_at, recorded_at)
        if node is None or node.node_type != self._RUNTIME_NODE_TYPE:
            return None
        return RuntimeStoryNode.model_validate(node.attributes)

    def transition(
        self,
        *,
        scope: HeavenlyGraphScope,
        node_id: str,
        expected: str,
        target: str,
        reason: str,
        recorded_at: int,
    ) -> RuntimeStoryNode:
        return self._transition(
            scope=scope,
            node_id=node_id,
            expected=expected,
            target=target,
            reason=reason,
            recorded_at=recorded_at,
            transaction_id=f"story_transition:{node_id}",
            idempotency_key=(
                f"story_transition:{node_id}:{expected}:{target}:{reason}:{recorded_at}"
            ),
        )

    def transition_with_intervention_outcome(
        self,
        *,
        scope: HeavenlyGraphScope,
        node_id: str,
        expected: str,
        target: str,
        reason: str,
        recorded_at: int,
        outcome: InterventionOutcomeMemoryEntry,
        provenance: GraphProvenance,
    ) -> RuntimeStoryNode:
        outcome_node = HeavenlyGraphNode(
            node_id=outcome.entry_id,
            node_type=f"memory:{outcome.domain}",
            scope=scope,
            validity=GraphValidity(valid_from=recorded_at),
            recorded_at=recorded_at,
            revision=1,
            provenance=provenance,
            attributes=outcome.model_dump(mode="json"),
            semantic_metadata=GraphSemanticMetadata(
                record_kind="projection",
                visibility_scope="siming_internal",
                derivation_kind="projection",
                source_event_refs=(provenance.source_ref,),
                policy_revision="policy:v1",
                scope_digest="scope:siming-heavenly",
            ),
        )
        return self._transition(
            scope=scope,
            node_id=node_id,
            expected=expected,
            target=target,
            reason=reason,
            recorded_at=recorded_at,
            transaction_id=outcome.entry_id,
            idempotency_key=outcome.entry_id,
            provenance=provenance,
            extra_nodes=[outcome_node],
        )

    def _transition(
        self,
        *,
        scope: HeavenlyGraphScope,
        node_id: str,
        expected: str,
        target: str,
        reason: str,
        recorded_at: int,
        transaction_id: str,
        idempotency_key: str,
        provenance: GraphProvenance | None = None,
        extra_nodes: list[HeavenlyGraphNode] | None = None,
    ) -> RuntimeStoryNode:
        prior = self._runtime_graph_node_at(
            scope=scope,
            node_id=node_id,
            valid_at=recorded_at,
        )
        current = RuntimeStoryNode.model_validate(prior.attributes)
        if current.terminal:
            raise StoryNodeTransitionError(
                f"terminal story node {node_id!r} cannot be reactivated"
            )
        if current.lifecycle != expected:
            raise StoryNodeTransitionError(
                f"runtime node {node_id!r} expected lifecycle {expected!r}, "
                f"found {current.lifecycle!r}"
            )
        try:
            StoryNodeTransitionCommand(
                node_id=node_id,
                expected=expected,
                target=target,
                reason=reason,
                recorded_at=recorded_at,
            )
        except ValueError as error:
            raise StoryNodeTransitionError(str(error)) from error

        updated = current.model_copy(update={"lifecycle": target})
        provenance = provenance or GraphProvenance(
            source_kind="runtime_outcome",
            source_ref=f"story_transition:{node_id}",
            causation_id=f"story_transition:{node_id}",
            correlation_id=f"story_transition:{node_id}:{prior.revision + 1}",
            producer_system="siming_story_graph_runtime",
        )
        self._graph.write_batch(
            HeavenlyGraphWriteBatch(
                transaction_id=f"{transaction_id}:{prior.revision + 1}",
                idempotency_key=idempotency_key,
                scope=scope,
                nodes=[
                    self._runtime_graph_node(
                        scope=scope,
                        runtime_node=updated,
                        prior=prior,
                        recorded_at=recorded_at,
                        provenance=provenance,
                    )
                ]
                + (extra_nodes or []),
            )
        )
        return updated

    def apply_authority_outcome(
        self,
        *,
        scope: HeavenlyGraphScope,
        outcome: AuthorityStoryOutcome,
    ) -> StoryOutcomeApplication:
        prior_application = self._read_applied_outcome(scope=scope, outcome=outcome)
        if prior_application is not None:
            return prior_application

        matches = self._matching_ports(scope=scope, outcome=outcome)
        if not matches:
            return StoryOutcomeApplication(
                authority_result_ref=outcome.authority_result_ref,
                nodes={},
                graph_transaction_ref=f"story_outcome:{outcome.authority_result_ref}",
            )

        current_by_id = {
            node.node_id: node
            for node in self._runtime_graph_nodes(scope=scope, valid_at=outcome.recorded_at)
        }
        updated_by_id: dict[str, RuntimeStoryNode] = {}
        affected_ids: list[str] = []
        for source, port in matches:
            updated_by_id[source.node_id] = source.model_copy(
                update={
                    "lifecycle": "resolved",
                    "outcome_port": port.port_id,
                    "outcome_semantic": port.outcome_semantic,
                }
            )
            affected_ids.append(source.node_id)
            for effect in port.effects:
                for target in self._effect_targets(
                    current_by_id=current_by_id,
                    effect=effect,
                ):
                    updated_by_id[target.node_id] = self._apply_effect(target, effect)
                    affected_ids.append(target.node_id)

        transaction_id = f"story_outcome:{outcome.authority_result_ref}"
        provenance = GraphProvenance(
            source_kind="runtime_outcome",
            source_ref=outcome.authority_result_ref,
            causation_id=outcome.authority_result_ref,
            correlation_id=outcome.correlation_id,
            producer_system="siming_story_graph_runtime",
        )
        graph_nodes = [
            self._runtime_graph_node(
                scope=scope,
                runtime_node=updated,
                prior=self._runtime_graph_node_at(
                    scope=scope,
                    node_id=node_id,
                    valid_at=outcome.recorded_at,
                ),
                recorded_at=outcome.recorded_at,
                provenance=provenance,
            )
            for node_id, updated in sorted(updated_by_id.items())
        ]
        memory_entry = StorylineObligationMemoryEntry(
            entry_id=f"story_outcome:{outcome.authority_result_ref}",
            record_type="outcome_port",
            lifecycle=matches[0][1].outcome_semantic,
            supporting_fact_refs=[outcome.authority_result_ref],
        )
        graph_nodes.extend(
            [
                HeavenlyGraphNode(
                    node_id=memory_entry.entry_id,
                    node_type="memory:storyline_obligation",
                    scope=scope,
                    validity=GraphValidity(valid_from=outcome.recorded_at),
                    recorded_at=outcome.recorded_at,
                    revision=1,
                    provenance=provenance,
                    attributes=memory_entry.model_dump(mode="json"),
                    semantic_metadata=GraphSemanticMetadata(
                        record_kind="fact",
                        visibility_scope="siming_internal",
                        derivation_kind="authority",
                        source_event_refs=(outcome.authority_result_ref,),
                        policy_revision="policy:v1",
                        scope_digest="scope:siming-heavenly",
                    ),
                ),
                HeavenlyGraphNode(
                    node_id=self._outcome_node_id(outcome.authority_result_ref),
                    node_type=self._OUTCOME_NODE_TYPE,
                    scope=scope,
                    validity=GraphValidity(valid_from=outcome.recorded_at),
                    recorded_at=outcome.recorded_at,
                    revision=1,
                    provenance=provenance,
                    attributes={
                        "outcome": outcome.model_dump(mode="json"),
                        "affected_node_ids": sorted(set(affected_ids)),
                        "transaction_id": transaction_id,
                    },
                    semantic_metadata=GraphSemanticMetadata(
                        record_kind="projection",
                        visibility_scope="siming_internal",
                        derivation_kind="projection",
                        source_event_refs=(outcome.authority_result_ref,),
                        policy_revision="policy:v1",
                        scope_digest="scope:siming-heavenly",
                    ),
                ),
            ]
        )
        self._graph.write_batch(
            HeavenlyGraphWriteBatch(
                transaction_id=transaction_id,
                idempotency_key=transaction_id,
                scope=scope,
                nodes=graph_nodes,
            )
        )
        return StoryOutcomeApplication(
            authority_result_ref=outcome.authority_result_ref,
            nodes={
                node.blueprint_id: node
                for node in sorted(updated_by_id.values(), key=lambda item: item.node_id)
            },
            graph_transaction_ref=transaction_id,
        )

    def _read_applied_outcome(
        self,
        *,
        scope: HeavenlyGraphScope,
        outcome: AuthorityStoryOutcome,
    ) -> StoryOutcomeApplication | None:
        marker = self._graph.get_node(
            node_id=self._outcome_node_id(outcome.authority_result_ref),
            scope=scope,
            valid_at=outcome.recorded_at,
        )
        if marker is None:
            return None
        if marker.node_type != self._OUTCOME_NODE_TYPE:
            raise StoryGraphError("authority outcome marker has an invalid node type")
        if AuthorityStoryOutcome.model_validate(marker.attributes["outcome"]) != outcome:
            raise StoryGraphError("authority result reference was reused with different outcome")
        memory_entry = self._memory.get_entry(
            scope=scope,
            entry_id=f"story_outcome:{outcome.authority_result_ref}",
            valid_at=outcome.recorded_at,
        )
        if not isinstance(memory_entry, StorylineObligationMemoryEntry):
            raise StoryGraphError("applied authority outcome is missing its storyline memory record")
        affected_node_ids = marker.attributes.get("affected_node_ids")
        transaction_id = marker.attributes.get("transaction_id")
        if (
            not isinstance(affected_node_ids, list)
            or not all(isinstance(node_id, str) for node_id in affected_node_ids)
            or not isinstance(transaction_id, str)
        ):
            raise StoryGraphError("authority outcome marker has invalid payload")
        nodes = {
            node.blueprint_id: node
            for node_id in affected_node_ids
            if (
                node := self.read_runtime_node(
                    scope=scope,
                    node_id=node_id,
                    valid_at=outcome.recorded_at,
                )
            )
            is not None
        }
        return StoryOutcomeApplication(
            authority_result_ref=outcome.authority_result_ref,
            nodes=nodes,
            graph_transaction_ref=transaction_id,
        )

    def _matching_ports(
        self,
        *,
        scope: HeavenlyGraphScope,
        outcome: AuthorityStoryOutcome,
    ) -> list[tuple[RuntimeStoryNode, StoryOutcomePort]]:
        matches: list[tuple[RuntimeStoryNode, StoryOutcomePort]] = []
        for runtime_node in self._runtime_graph_nodes(
            scope=scope,
            valid_at=outcome.recorded_at,
        ):
            blueprint = self.read_blueprint(
                scope=scope,
                blueprint_id=runtime_node.blueprint_id,
                valid_at=outcome.recorded_at,
            )
            if blueprint is None:
                raise StoryGraphError(
                    f"runtime story node {runtime_node.node_id!r} has no authored blueprint"
                )
            for port in blueprint.outcome_ports:
                if (
                    port.required_result_type == outcome.result_type
                    and port.target_ref == outcome.target_ref
                    and port.required_state == outcome.current_state
                ):
                    matches.append((runtime_node, port))
        return matches

    def _runtime_graph_nodes(
        self,
        *,
        scope: HeavenlyGraphScope,
        valid_at: int,
    ) -> list[RuntimeStoryNode]:
        result = self._graph.query_semantic(
            NodeLookupQuery(
                context=GraphReaderContext(
                    reader_principal="reader:siming",
                    allowed_visibility_scopes=("siming_internal", "authority_only", "branch_only"),
                    world_id=scope.world_id,
                    session_id=scope.session_id,
                    story_branch_id=scope.story_branch_id,
                    valid_at=valid_at,
                    recorded_at=None,
                    policy_revision="policy:v1",
                ),
                scope=scope,
                node_types=[self._RUNTIME_NODE_TYPE],
                limit=1000,
            )
        )
        return [RuntimeStoryNode.model_validate(node.attributes) for node in result.nodes]

    @staticmethod
    def _effect_targets(
        *,
        current_by_id: dict[str, RuntimeStoryNode],
        effect: StoryOutcomeEffect,
    ) -> list[RuntimeStoryNode]:
        return [
            node
            for node in current_by_id.values()
            if node.blueprint_id == effect.target_blueprint_id
        ]

    @staticmethod
    def _apply_effect(
        node: RuntimeStoryNode,
        effect: StoryOutcomeEffect,
    ) -> RuntimeStoryNode:
        if effect.effect == "close_permanently":
            return node.model_copy(
                update={
                    "lifecycle": "aborted",
                    "reachability": "unreachable",
                    "closure_reason": "closed_by_player_choice",
                    "terminal": True,
                    "reopen_policy": "never",
                }
            )
        if effect.effect == "mark_unreachable":
            return node.model_copy(update={"reachability": "unreachable_by_ledger"})
        if node.terminal:
            raise StoryGraphError("terminal story node cannot be made eligible")
        return node.model_copy(update={"lifecycle": "eligible"})

    @staticmethod
    def _blueprint_node_id(blueprint_id: str) -> str:
        return f"authored_story:{blueprint_id}"

    @staticmethod
    def _outcome_node_id(authority_result_ref: str) -> str:
        return f"story_authority_outcome:{authority_result_ref}"

    def _runtime_graph_node_at(
        self,
        *,
        scope: HeavenlyGraphScope,
        node_id: str,
        valid_at: int,
    ) -> HeavenlyGraphNode:
        node = self._semantic_node(scope, node_id, valid_at, None)
        if node is None or node.node_type != self._RUNTIME_NODE_TYPE:
            raise StoryGraphError(f"unknown runtime story node {node_id!r}")
        return node

    @staticmethod
    def _runtime_graph_node(
        *,
        scope: HeavenlyGraphScope,
        runtime_node: RuntimeStoryNode,
        prior: HeavenlyGraphNode | None,
        recorded_at: int,
        provenance: GraphProvenance,
    ) -> HeavenlyGraphNode:
        revision = 1 if prior is None else prior.revision + 1
        return HeavenlyGraphNode(
            node_id=runtime_node.node_id,
            node_type=SimingStoryGraphRuntime._RUNTIME_NODE_TYPE,
            scope=scope,
            validity=GraphValidity(valid_from=recorded_at),
            recorded_at=recorded_at,
            revision=revision,
            supersedes_revision=None if prior is None else prior.revision,
            provenance=provenance,
            attributes=runtime_node.model_dump(mode="json"),
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
        # Legacy story fixtures predate semantic policy metadata; preserve their
        # read compatibility while new records use the bounded semantic path.
        return self._graph.get_node(
            node_id=node_id,
            scope=scope,
            valid_at=valid_at,
            recorded_at=recorded_at,
        )
