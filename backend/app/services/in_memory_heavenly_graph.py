import base64
import copy
import hashlib
import json
from collections.abc import Sequence

from app.models.siming_heavenly_graph import (
    GraphBranchDiffQuery,
    GraphBranchDiffResult,
    GraphBranchForkRequest,
    GraphBranchLifecycleMarker,
    GraphBranchLifecycleRequest,
    GraphCorrectionRequest,
    GraphProvenance,
    GraphRevisionVector,
    GraphSemanticMetadata,
    GraphValidity,
    HeavenlyGraphQueryResult,
    HeavenlyGraphSemanticQuery,
    HeavenlyGraphCheckpointRef,
    HeavenlyGraphNode,
    HeavenlyGraphRelation,
    HeavenlyGraphScope,
    HeavenlyGraphSnapshot,
    HeavenlySubgraphDirection,
    HeavenlySubgraphResult,
    HeavenlyGraphWriteBatch,
    HeavenlyGraphWriteResult,
    HeavenlyNodeQuery,
    HeavenlyRelationQuery,
)
from app.services.siming_heavenly_graph_port import (
    HeavenlyGraphCheckpointConflict,
    HeavenlyGraphCheckpointNotFound,
    HeavenlyGraphIdempotencyConflict,
    HeavenlyGraphReferentialIntegrityError,
    HeavenlyGraphRevisionConflict,
)
from app.services.heavenly_graph_semantics import (
    DEFAULT_NODE_TYPE_REGISTRY,
    DEFAULT_RELATION_TYPE_REGISTRY,
    validate_correction_request,
)


ScopeKey = tuple[str, str, str, str | None, str | None, str, str | None]
CheckpointKey = tuple[ScopeKey, str]


class InMemoryHeavenlyGraphAdapter:
    def __init__(self) -> None:
        self._nodes: dict[
            tuple[ScopeKey, str],
            list[HeavenlyGraphNode],
        ] = {}
        self._relations: dict[
            tuple[ScopeKey, str],
            list[HeavenlyGraphRelation],
        ] = {}
        self._idempotency: dict[
            tuple[ScopeKey, str],
            tuple[str, HeavenlyGraphWriteResult],
        ] = {}
        self._checkpoints: dict[CheckpointKey, HeavenlyGraphSnapshot] = {}
        self._checkpoint_refs: dict[str, CheckpointKey] = {}
        # Entity revisions identify a record's local history. These counters
        # identify every committed write in a scope, which is what a reader's
        # stale-read set must pin.
        self._scope_stream_revisions: dict[ScopeKey, tuple[int, int]] = {}
        self._branch_markers: dict[ScopeKey, list[GraphBranchLifecycleMarker]] = {}
        self._branch_status: dict[ScopeKey, str] = {}
        self._branch_revisions: dict[ScopeKey, int] = {}

    def write_batch(
        self,
        batch: HeavenlyGraphWriteBatch,
    ) -> HeavenlyGraphWriteResult:
        return self._write_batch(batch)

    def fork_branch(self, request: GraphBranchForkRequest) -> HeavenlyGraphWriteResult:
        source = request.source_scope
        source_status = self._branch_status.get(self._scope_key(source))
        if source_status in {"discarded", "admitted"}:
            raise ValueError(
                f"branch {source.story_branch_id!r} is terminal: {source_status}"
            )
        source_vector = self._scope_revision_vector(source)
        if not self._revision_vector_matches(request.source_revision_vector, source_vector):
            raise HeavenlyGraphRevisionConflict(
                "branch fork source revision vector is stale",
                expected_revision_vector=request.source_revision_vector,
                current_revision_vector=source_vector,
                affected_refs=[source.story_branch_id],
            )
        target = source.model_copy(update={"story_branch_id": request.target_branch_id})
        target_key = self._scope_key(target)
        if target_key in self._branch_status or self._has_scope_records(target):
            raise ValueError(f"branch {request.target_branch_id!r} already exists")
        source_nodes, source_relations = self._branch_snapshot_at(
            source,
            valid_at=request.fork_valid_at,
            recorded_at=request.fork_recorded_at,
        )
        self._branch_status[target_key] = "forked"
        self._branch_markers[target_key] = [
            self._copy_branch_marker(marker, target)
            for marker in self._branch_markers.get(self._scope_key(source), [])
            if marker.recorded_at <= request.fork_recorded_at
        ]
        self._scope_stream_revisions[target_key] = (len(source_nodes), len(source_relations))
        self._branch_revision(target_key, advance=True)
        for node in source_nodes:
            self._nodes.setdefault((target_key, node.node_id), []).append(
                node.model_copy(update={"scope": target}, deep=True)
            )
        for relation in source_relations:
            self._relations.setdefault((target_key, relation.relation_id), []).append(
                relation.model_copy(update={"scope": target}, deep=True)
            )
        marker = self._append_branch_marker(
            target,
            "fork",
            source_scope=source,
            source_revision_vector=request.source_revision_vector,
            recorded_at=request.fork_recorded_at,
            target_branch_id=request.target_branch_id,
        )
        result = HeavenlyGraphWriteResult(
            transaction_id=f"graph:branch:fork:{request.target_branch_id}",
            idempotency_key=f"graph:branch:fork:{source.story_branch_id}:{request.target_branch_id}",
            applied=True,
            node_refs=[self._entity_ref("node", target, node.node_id, node.revision) for node in source_nodes],
            relation_refs=[self._entity_ref("relation", target, relation.relation_id, relation.revision) for relation in source_relations],
        )
        return result

    def diff_branches(self, query: GraphBranchDiffQuery) -> GraphBranchDiffResult:
        left_nodes = {
            node.node_id: node
            for node in self.query_nodes(HeavenlyNodeQuery(scope=query.left_scope, valid_at=query.reader_context.valid_at, recorded_at=query.reader_context.recorded_at, limit=None))
            if self._branch_entity_visible(node, query)
        }
        right_nodes = {
            node.node_id: node
            for node in self.query_nodes(HeavenlyNodeQuery(scope=query.right_scope, valid_at=query.reader_context.valid_at, recorded_at=query.reader_context.recorded_at, limit=None))
            if self._branch_entity_visible(node, query)
        }
        left_relations = {
            relation.relation_id: relation
            for relation in self.query_relations(HeavenlyRelationQuery(scope=query.left_scope, valid_at=query.reader_context.valid_at, recorded_at=query.reader_context.recorded_at, limit=None))
            if self._branch_entity_visible(relation, query)
        }
        right_relations = {
            relation.relation_id: relation
            for relation in self.query_relations(HeavenlyRelationQuery(scope=query.right_scope, valid_at=query.reader_context.valid_at, recorded_at=query.reader_context.recorded_at, limit=None))
            if self._branch_entity_visible(relation, query)
        }
        node_ids = sorted(set(left_nodes) | set(right_nodes))
        relation_ids = sorted(set(left_relations) | set(right_relations))
        markers = sorted(
            [
                *self._branch_markers.get(self._scope_key(query.left_scope), []),
                *self._branch_markers.get(self._scope_key(query.right_scope), []),
            ],
            key=lambda marker: marker.marker_id,
        )
        markers = [
            marker
            for marker in markers
            if "authority_only" in query.reader_context.allowed_visibility_scopes
            and (
                query.reader_context.recorded_at is None
                or marker.recorded_at <= query.reader_context.recorded_at
            )
            and marker.policy_revision == query.reader_context.policy_revision
        ]
        truncated = len(node_ids) > query.limits.node_limit or len(relation_ids) > query.limits.relation_limit or len(markers) > query.limits.marker_limit
        added_nodes = [right_nodes[node_id] for node_id in node_ids if node_id not in left_nodes][: query.limits.node_limit]
        removed_nodes = [left_nodes[node_id] for node_id in node_ids if node_id not in right_nodes][: query.limits.node_limit]
        changed_nodes = [
            right_nodes[node_id]
            for node_id in node_ids
            if node_id in left_nodes
            and node_id in right_nodes
            and self._branch_independent_payload(right_nodes[node_id])
            != self._branch_independent_payload(left_nodes[node_id])
        ][: query.limits.node_limit]
        added_relations = [right_relations[item] for item in relation_ids if item not in left_relations][: query.limits.relation_limit]
        removed_relations = [left_relations[item] for item in relation_ids if item not in right_relations][: query.limits.relation_limit]
        changed_relations = [
            right_relations[item]
            for item in relation_ids
            if item in left_relations
            and item in right_relations
            and self._branch_independent_payload(right_relations[item])
            != self._branch_independent_payload(left_relations[item])
        ][: query.limits.relation_limit]
        return GraphBranchDiffResult(
            added_nodes=added_nodes,
            removed_nodes=removed_nodes,
            changed_nodes=changed_nodes,
            added_relations=added_relations,
            removed_relations=removed_relations,
            changed_relations=changed_relations,
            lifecycle_markers=markers[: query.limits.marker_limit],
            left_revision_vector=self._scope_revision_vector(query.left_scope),
            right_revision_vector=self._scope_revision_vector(query.right_scope),
            truncated=truncated,
        )

    @staticmethod
    def _branch_entity_visible(entity: object, query: GraphBranchDiffQuery) -> bool:
        metadata = entity.semantic_metadata
        if metadata.visibility_scope not in query.reader_context.allowed_visibility_scopes:
            return False
        owner_actor_id = entity.scope.owner_actor_id
        if metadata.visibility_scope == "actor_private" and owner_actor_id is not None:
            principal = query.reader_context.reader_principal
            if principal not in {owner_actor_id, f"actor:{owner_actor_id}", f"reader:{owner_actor_id}"}:
                return False
        return metadata.policy_revision == query.reader_context.policy_revision

    def lifecycle_branch(self, request: GraphBranchLifecycleRequest) -> HeavenlyGraphWriteResult:
        branch = request.branch_scope
        key = self._scope_key(branch)
        status = self._branch_status.get(key)
        if status is None:
            raise ValueError("branch lifecycle requires a forked branch")
        current = self._scope_revision_vector(branch)
        if not self._revision_vector_matches(request.expected_revision_vector, current):
            raise HeavenlyGraphRevisionConflict(
                "branch lifecycle expected revision vector is stale",
                expected_revision_vector=request.expected_revision_vector,
                current_revision_vector=current,
                affected_refs=[branch.story_branch_id],
            )
        if status in {"discarded", "admitted"}:
            raise ValueError(f"branch {branch.story_branch_id!r} is terminal: {status}")
        if request.operation == "close_node":
            assert request.node_id is not None
            if self._is_node_closed(branch, request.node_id):
                raise ValueError(f"node {request.node_id!r} is permanently closed")
            target = self._latest_entity(branch, request.node_id, self._nodes)
            if target is None:
                raise ValueError(f"node {request.node_id!r} is missing")
            lifecycle_recorded_at = current.branch_revision + 1
            marker_node = self._branch_marker_node(
                branch,
                request.node_id,
                current,
                valid_from=target.validity.valid_from,
                recorded_at=lifecycle_recorded_at,
            )
            marker_relation = self._branch_close_relation(
                branch,
                marker_node,
                request.node_id,
                current,
                valid_from=target.validity.valid_from,
                recorded_at=lifecycle_recorded_at,
            )
            self._nodes.setdefault((key, marker_node.node_id), []).append(marker_node)
            self._relations.setdefault((key, marker_relation.relation_id), []).append(marker_relation)
            self._append_branch_marker(
                branch,
                "close_node",
                recorded_at=marker_node.recorded_at,
                node_id=request.node_id,
            )
        elif request.operation == "discard":
            self._append_branch_marker(branch, "discard", recorded_at=current.branch_revision + 1)
            self._branch_status[key] = "discarded"
        elif request.operation == "admit":
            assert request.target_branch_id is not None
            fork_marker = next(
                (marker for marker in self._branch_markers.get(key, []) if marker.operation == "fork"),
                None,
            )
            if fork_marker is None or fork_marker.source_scope is None or fork_marker.source_revision_vector is None:
                raise ValueError("branch admission requires a fork source marker")
            source_current = self._scope_revision_vector(fork_marker.source_scope)
            if not self._revision_vector_matches(fork_marker.source_revision_vector, source_current):
                raise HeavenlyGraphRevisionConflict(
                    "branch admission fork source revision vector is stale",
                    expected_revision_vector=fork_marker.source_revision_vector,
                    current_revision_vector=source_current,
                    affected_refs=[fork_marker.source_scope.story_branch_id],
                )
            target = branch.model_copy(update={"story_branch_id": request.target_branch_id})
            target_key = self._scope_key(target)
            if target_key in self._branch_status or self._has_scope_records(target):
                raise ValueError(f"admit target branch {request.target_branch_id!r} already exists")
            nodes, relations = self._active_branch_snapshot(branch)
            self._branch_status[target_key] = "admitted"
            self._branch_markers[target_key] = [
                self._copy_branch_marker(marker, target)
                for marker in self._branch_markers.get(key, [])
            ]
            self._branch_revisions[target_key] = self._branch_revisions.get(key, 0)
            for node in nodes:
                self._nodes.setdefault((target_key, node.node_id), []).append(node.model_copy(update={"scope": target}, deep=True))
            for relation in relations:
                self._relations.setdefault((target_key, relation.relation_id), []).append(relation.model_copy(update={"scope": target}, deep=True))
            # The admitted target starts with the copied entity streams. Set
            # these counters before constructing its audit marker so the
            # marker's revision vector describes the actual admitted snapshot.
            self._scope_stream_revisions[target_key] = (len(nodes), len(relations))
            admission_recorded_at = current.branch_revision + 1
            self._append_branch_marker(
                branch,
                "admit",
                recorded_at=admission_recorded_at,
                target_branch_id=request.target_branch_id,
                source_scope=fork_marker.source_scope,
                source_revision_vector=fork_marker.source_revision_vector,
            )
            self._append_branch_marker(
                target,
                "admit",
                recorded_at=admission_recorded_at,
                target_branch_id=request.target_branch_id,
                source_scope=branch,
                source_revision_vector=current,
            )
            self._branch_status[key] = "admitted"
            self._branch_revision(target_key, advance=True)
        else:  # fork is represented by fork_branch and cannot be repeated here.
            raise ValueError("fork must be requested through fork_branch")
        self._branch_revision(key, advance=True)
        marker = self._branch_markers[key][-1] if self._branch_markers.get(key) else None
        return HeavenlyGraphWriteResult(
            transaction_id=f"graph:branch:{request.operation}:{branch.story_branch_id}",
            idempotency_key=f"graph:branch:{request.operation}:{branch.story_branch_id}:{current.branch_revision + 1}",
            applied=True,
            node_refs=[] if marker is None else [marker.marker_id],
        )

    def _write_batch(
        self,
        batch: HeavenlyGraphWriteBatch,
        *,
        idempotency_payload_hash: str | None = None,
    ) -> HeavenlyGraphWriteResult:
        self._validate_batch_semantics(batch)
        payload_hash = idempotency_payload_hash or self._batch_hash(batch)
        scoped_idempotency_key = (
            self._scope_key(batch.scope),
            batch.idempotency_key,
        )
        prior = self._idempotency.get(scoped_idempotency_key)
        if prior is not None:
            prior_hash, prior_result = prior
            if prior_hash != payload_hash:
                raise HeavenlyGraphIdempotencyConflict(
                    f"idempotency key {batch.idempotency_key!r} "
                    "was reused with different payload"
                )
            return prior_result.model_copy(
                update={"applied": False, "replayed": True},
                deep=True,
            )

        self._validate_batch_scopes(batch)
        self._validate_batch_revisions(batch)
        self._validate_relation_endpoints(batch)

        branch_status = self._branch_status.get(self._scope_key(batch.scope))
        if (
            self._is_explicit_branch_scope(batch.scope)
            and branch_status is None
            and not self._is_legacy_compat_batch(batch)
        ):
            raise ValueError(
                f"branch {batch.scope.story_branch_id!r} requires an explicit fork"
            )
        if branch_status in {"discarded", "admitted"}:
            raise ValueError(
                f"branch {batch.scope.story_branch_id!r} is terminal: {branch_status}"
            )
        for node in batch.nodes:
            if node.node_type == "branch_marker":
                raise ValueError("branch_marker nodes are lifecycle-internal")
            key = (self._scope_key(node.scope), node.node_id)
            self._nodes.setdefault(key, []).append(node.model_copy(deep=True))
        for relation in batch.relations:
            if relation.relation_type == "closes_branch_node":
                raise ValueError("closes_branch_node relations are lifecycle-internal")
            key = (self._scope_key(relation.scope), relation.relation_id)
            self._relations.setdefault(key, []).append(
                relation.model_copy(deep=True)
            )
        self._advance_scope_stream_revisions(batch)

        result = HeavenlyGraphWriteResult(
            transaction_id=batch.transaction_id,
            idempotency_key=batch.idempotency_key,
            applied=True,
            replayed=False,
            node_refs=[
                self._entity_ref("node", node.scope, node.node_id, node.revision)
                for node in batch.nodes
            ],
            relation_refs=[
                self._entity_ref(
                    "relation",
                    relation.scope,
                    relation.relation_id,
                    relation.revision,
                )
                for relation in batch.relations
            ],
        )
        self._idempotency[scoped_idempotency_key] = (
            payload_hash,
            result.model_copy(deep=True),
        )
        return result

    def correct(
        self,
        request: GraphCorrectionRequest,
    ) -> HeavenlyGraphWriteResult:
        """Append one correction revision without mutating prior history."""
        scope, versions = self._resolve_correction_target(request)
        idempotency_key = self._correction_idempotency_key(request, scope)
        payload_hash = self._correction_hash(request, scope)
        prior = self._idempotency.get((self._scope_key(scope), idempotency_key))
        if prior is not None:
            if prior[0] != payload_hash:
                raise HeavenlyGraphIdempotencyConflict(
                    f"idempotency key {idempotency_key!r} was reused with different payload"
                )
            return prior[1].model_copy(update={"applied": False, "replayed": True}, deep=True)

        current_vector = self._scope_revision_vector(scope)
        expected_vector = request.expected_revision_vector
        if expected_vector is not None and not self._revision_vector_matches(
            expected_vector, current_vector
        ):
            raise HeavenlyGraphRevisionConflict(
                "correction expected revision vector is stale",
                expected_revision_vector=expected_vector,
                current_revision_vector=current_vector,
                affected_refs=[
                    request.target_id,
                    self._entity_ref(
                        request.target_kind,
                        scope,
                        request.target_id,
                        request.target_revision,
                    ),
                ],
            )

        target = next(
            (item for item in versions if item.revision == request.target_revision),
            None,
        )
        if target is None:
            raise HeavenlyGraphRevisionConflict(
                f"{request.target_kind} {request.target_id!r} target revision is missing",
                expected_revision_vector=expected_vector,
                current_revision_vector=current_vector,
                affected_refs=[request.target_id],
            )
        latest = max(versions, key=lambda item: item.revision)
        if target.revision != latest.revision:
            raise HeavenlyGraphRevisionConflict(
                f"{request.target_kind} {request.target_id!r} target revision is not current",
                expected_revision_vector=expected_vector,
                current_revision_vector=current_vector,
                affected_refs=[request.target_id],
            )
        validate_correction_request(request, target)

        derivation_kind = {
            "corrected": "correction",
            "retracted": "retraction",
            "redacted": "redaction",
        }[request.correction_kind]
        next_metadata = request.semantic_metadata.model_copy(
            update={
                "record_kind": target.semantic_metadata.record_kind,
                "visibility_scope": target.semantic_metadata.visibility_scope,
                "derivation_kind": derivation_kind,
                "source_event_refs": tuple(
                    dict.fromkeys(
                        [
                            *target.semantic_metadata.source_event_refs,
                            *request.source_refs,
                        ]
                    )
                ),
            },
            deep=True,
        )
        next_provenance = target.provenance.model_copy(
            update={
                "causation_id": f"correction:{request.target_kind}:{request.target_id}:{request.target_revision}",
                "correlation_id": target.provenance.correlation_id,
                "evidence_refs": list(
                    dict.fromkeys(
                        [*target.provenance.evidence_refs, *request.source_refs]
                    )
                ),
                "source_ref_lineage": list(
                    dict.fromkeys(
                        [
                            target.provenance.source_ref,
                            *target.provenance.source_ref_lineage,
                            *request.source_refs,
                        ]
                    )
                ),
            },
            deep=True,
        )
        attrs = {
            **target.attributes,
            "correction_target_id": request.target_id,
            "correction_target_revision": request.target_revision,
            "correction_target_source_ref": target.provenance.source_ref,
            "correction_kind": request.correction_kind,
            "correction_source_refs": list(request.source_refs),
        }
        next_recorded_at = max(target.recorded_at + 1, target.validity.valid_from)
        if request.target_kind == "node":
            corrected = target.model_copy(
                update={
                    "recorded_at": next_recorded_at,
                    "revision": target.revision + 1,
                    "supersedes_revision": target.revision,
                    "attributes": attrs,
                    "provenance": next_provenance,
                    "semantic_metadata": next_metadata,
                },
                deep=True,
            )
            batch = HeavenlyGraphWriteBatch(
                transaction_id=f"graph:correction:{request.target_kind}:{request.target_id}:{target.revision + 1}",
                idempotency_key=idempotency_key,
                scope=scope,
                nodes=[corrected],
            )
        else:
            corrected = target.model_copy(
                update={
                    "recorded_at": next_recorded_at,
                    "revision": target.revision + 1,
                    "supersedes_revision": target.revision,
                    "attributes": attrs,
                    "provenance": next_provenance,
                    "semantic_metadata": next_metadata,
                },
                deep=True,
            )
            batch = HeavenlyGraphWriteBatch(
                transaction_id=f"graph:correction:{request.target_kind}:{request.target_id}:{target.revision + 1}",
                idempotency_key=idempotency_key,
                scope=scope,
                relations=[corrected],
            )
        return self._write_batch(
            batch,
            idempotency_payload_hash=payload_hash,
        )

    def query_semantic(
        self, query: HeavenlyGraphSemanticQuery
    ) -> HeavenlyGraphQueryResult:
        from app.services.heavenly_graph_queries import HeavenlyGraphSemanticQueryFacade

        return HeavenlyGraphSemanticQueryFacade(self).query(query)

    def _validate_batch_semantics(self, batch: HeavenlyGraphWriteBatch) -> None:
        """Reject semantically invalid records before idempotency or mutation."""
        scope_key = self._scope_key(batch.scope)
        branch_status = self._branch_status.get(scope_key)
        if (
            self._is_explicit_branch_scope(batch.scope)
            and branch_status is None
            and not self._is_legacy_compat_batch(batch)
        ):
            raise ValueError(
                f"branch {batch.scope.story_branch_id!r} requires an existing fork"
            )
        if branch_status in {"discarded", "admitted"}:
            raise ValueError(
                f"branch {batch.scope.story_branch_id!r} is terminal: {branch_status}"
            )
        for node in batch.nodes:
            if (
                node.semantic_metadata.visibility_scope == "branch_only"
                and self._scope_key(node.scope) not in self._branch_status
            ):
                raise ValueError("branch_only node requires an existing forked branch")
            if self._is_node_closed(node.scope, node.node_id):
                raise HeavenlyGraphRevisionConflict(
                    f"node {node.node_id!r} is permanently closed"
                )
            DEFAULT_NODE_TYPE_REGISTRY.validate_node(node, allow_legacy=True)
        for relation in batch.relations:
            if (
                relation.semantic_metadata.visibility_scope == "branch_only"
                and self._scope_key(relation.scope) not in self._branch_status
            ):
                raise ValueError("branch_only relation requires an existing forked branch")
            closed_endpoint = next(
                (
                    endpoint
                    for endpoint in (relation.source_node_id, relation.target_node_id)
                    if self._is_node_closed(relation.scope, endpoint)
                ),
                None,
            )
            if closed_endpoint is not None:
                raise HeavenlyGraphReferentialIntegrityError(
                    f"relation endpoint {closed_endpoint!r} is permanently closed"
                )
            DEFAULT_RELATION_TYPE_REGISTRY.validate_relation(relation, allow_legacy=True)

    def has_idempotency_key(
        self,
        *,
        scope: HeavenlyGraphScope,
        idempotency_key: str,
    ) -> bool:
        return (self._scope_key(scope), idempotency_key) in self._idempotency

    def get_node(
        self,
        *,
        node_id: str,
        scope: HeavenlyGraphScope,
        valid_at: int,
        recorded_at: int | None = None,
    ) -> HeavenlyGraphNode | None:
        nodes = self.query_nodes(
            HeavenlyNodeQuery(
                scope=scope,
                valid_at=valid_at,
                recorded_at=recorded_at,
                node_ids=[node_id],
                limit=1,
            )
        )
        return nodes[0] if nodes else None

    def get_relation(
        self,
        *,
        relation_id: str,
        scope: HeavenlyGraphScope,
        valid_at: int,
        recorded_at: int | None = None,
    ) -> HeavenlyGraphRelation | None:
        relations = self.query_relations(
            HeavenlyRelationQuery(
                scope=scope,
                valid_at=valid_at,
                recorded_at=recorded_at,
                relation_ids=[relation_id],
                limit=1,
            )
        )
        return relations[0] if relations else None

    def query_nodes(
        self,
        query: HeavenlyNodeQuery,
    ) -> list[HeavenlyGraphNode]:
        scope_key = self._scope_key(query.scope)
        node_id_filter = set(query.node_ids)
        node_type_filter = set(query.node_types)
        selected: list[HeavenlyGraphNode] = []
        if self._is_branch_discarded(query.scope, query.recorded_at):
            return []
        for (stored_scope, node_id), versions in self._nodes.items():
            if stored_scope != scope_key:
                continue
            if node_id_filter and node_id not in node_id_filter:
                continue
            node = self._effective_entity(
                versions,
                valid_at=query.valid_at,
                recorded_at=query.recorded_at,
            )
            if node is None:
                continue
            if node.node_type == "branch_marker":
                continue
            if self._is_node_closed(
                query.scope, node.node_id, recorded_at=query.recorded_at
            ):
                continue
            if node_type_filter and node.node_type not in node_type_filter:
                continue
            selected.append(node.model_copy(deep=True))
        ordered = sorted(selected, key=lambda node: node.node_id)
        return ordered if query.limit is None else ordered[: query.limit]

    def query_relations(
        self,
        query: HeavenlyRelationQuery,
    ) -> list[HeavenlyGraphRelation]:
        scope_key = self._scope_key(query.scope)
        relation_id_filter = set(query.relation_ids)
        relation_type_filter = set(query.relation_types)
        source_filter = set(query.source_node_ids)
        target_filter = set(query.target_node_ids)
        selected: list[HeavenlyGraphRelation] = []
        if self._is_branch_discarded(query.scope, query.recorded_at):
            return []
        for (stored_scope, relation_id), versions in self._relations.items():
            if stored_scope != scope_key:
                continue
            if relation_id_filter and relation_id not in relation_id_filter:
                continue
            relation = self._effective_entity(
                versions,
                valid_at=query.valid_at,
                recorded_at=query.recorded_at,
            )
            if relation is None:
                continue
            if (
                relation_type_filter
                and relation.relation_type not in relation_type_filter
            ):
                continue
            if source_filter and relation.source_node_id not in source_filter:
                continue
            if target_filter and relation.target_node_id not in target_filter:
                continue
            selected.append(relation.model_copy(deep=True))
        ordered = sorted(
            selected,
            key=lambda relation: relation.relation_id,
        )
        return ordered if query.limit is None else ordered[: query.limit]

    def query_subgraph(
        self,
        *,
        scope: HeavenlyGraphScope,
        seed_node_ids: list[str],
        relation_types: list[str],
        direction: HeavenlySubgraphDirection,
        max_depth: int,
        valid_at: int,
        recorded_at: int | None,
        node_limit: int,
        relation_limit: int,
    ) -> HeavenlySubgraphResult:
        if direction not in {"outgoing", "incoming", "both"}:
            raise ValueError(f"unsupported subgraph direction {direction!r}")
        if not 0 <= max_depth <= 8:
            raise ValueError("max_depth must be within 0..8")
        if not 1 <= node_limit <= 1000:
            raise ValueError("node_limit must be within 1..1000")
        if not 1 <= relation_limit <= 2000:
            raise ValueError("relation_limit must be within 1..2000")

        nodes = self.query_nodes(
            HeavenlyNodeQuery(
                scope=scope,
                valid_at=valid_at,
                recorded_at=recorded_at,
                limit=None,
            )
        )
        node_by_id = {node.node_id: node for node in nodes}
        relations = self.query_relations(
            HeavenlyRelationQuery(
                scope=scope,
                valid_at=valid_at,
                recorded_at=recorded_at,
                relation_types=relation_types,
                limit=None,
            )
        )
        selected_node_ids: list[str] = []
        seen_node_ids: set[str] = set()
        truncated = False
        for node_id in sorted(set(seed_node_ids)):
            if node_id not in node_by_id:
                continue
            if len(selected_node_ids) == node_limit:
                truncated = True
                break
            selected_node_ids.append(node_id)
            seen_node_ids.add(node_id)

        selected_relations: list[HeavenlyGraphRelation] = []
        seen_relation_ids: set[str] = set()
        frontier = selected_node_ids
        for depth in range(max_depth + 1):
            next_frontier: list[str] = []
            for node_id in sorted(frontier):
                for relation in relations:
                    if relation.relation_id in seen_relation_ids:
                        continue
                    neighbor_id = self._traversal_neighbor(
                        relation,
                        node_id=node_id,
                        direction=direction,
                    )
                    if neighbor_id is None or neighbor_id not in node_by_id:
                        continue
                    if neighbor_id not in seen_node_ids and depth == max_depth:
                        truncated = True
                        continue
                    if (
                        neighbor_id not in seen_node_ids
                        and len(selected_node_ids) == node_limit
                    ):
                        truncated = True
                        continue
                    if len(selected_relations) == relation_limit:
                        truncated = True
                        continue
                    selected_relations.append(relation)
                    seen_relation_ids.add(relation.relation_id)
                    if neighbor_id not in seen_node_ids:
                        seen_node_ids.add(neighbor_id)
                        selected_node_ids.append(neighbor_id)
                        next_frontier.append(neighbor_id)
            frontier = next_frontier

        return HeavenlySubgraphResult(
            scope=scope,
            seed_node_ids=seed_node_ids,
            valid_at=valid_at,
            recorded_at=recorded_at,
            nodes=[node_by_id[node_id] for node_id in selected_node_ids],
            relations=sorted(
                selected_relations, key=lambda relation: relation.relation_id
            ),
            truncated=truncated,
        )

    def create_checkpoint(
        self,
        *,
        checkpoint_id: str,
        scope: HeavenlyGraphScope,
        valid_at: int,
        recorded_at: int,
    ) -> HeavenlyGraphCheckpointRef:
        checkpoint_key = (self._scope_key(scope), checkpoint_id)
        checkpoint_ref = self._checkpoint_ref(checkpoint_id, scope)
        checkpoint = HeavenlyGraphCheckpointRef(
            checkpoint_ref=checkpoint_ref,
            checkpoint_id=checkpoint_id,
            scope=scope,
            valid_at=valid_at,
            recorded_at=recorded_at,
        )
        existing = self._checkpoints.get(checkpoint_key)
        if existing is not None:
            if existing.checkpoint != checkpoint:
                raise HeavenlyGraphCheckpointConflict(
                    f"checkpoint {checkpoint_id!r} was reused "
                    "with different coordinates"
                )
            return existing.checkpoint.model_copy(deep=True)

        snapshot = HeavenlyGraphSnapshot(
            checkpoint=checkpoint,
            nodes=self.query_nodes(
                HeavenlyNodeQuery(
                    scope=scope,
                    valid_at=valid_at,
                    recorded_at=recorded_at,
                    limit=None,
                )
            ),
            relations=self.query_relations(
                HeavenlyRelationQuery(
                    scope=scope,
                    valid_at=valid_at,
                    recorded_at=recorded_at,
                    limit=None,
                )
            ),
        )
        self._checkpoints[checkpoint_key] = snapshot.model_copy(deep=True)
        self._checkpoint_refs[checkpoint_ref] = checkpoint_key
        return checkpoint.model_copy(deep=True)

    def read_checkpoint(
        self,
        checkpoint_ref: str,
    ) -> HeavenlyGraphSnapshot:
        checkpoint_key = self._checkpoint_refs.get(checkpoint_ref)
        snapshot = (
            None
            if checkpoint_key is None
            else self._checkpoints.get(checkpoint_key)
        )
        if snapshot is None:
            raise HeavenlyGraphCheckpointNotFound(
                f"checkpoint ref {checkpoint_ref!r} was not found"
            )
        return snapshot.model_copy(deep=True)

    def _validate_batch_scopes(
        self,
        batch: HeavenlyGraphWriteBatch,
    ) -> None:
        for entity in [*batch.nodes, *batch.relations]:
            if entity.scope != batch.scope:
                raise HeavenlyGraphReferentialIntegrityError(
                    "every entity must match the batch scope"
                )

    def _traversal_neighbor(
        self,
        relation: HeavenlyGraphRelation,
        *,
        node_id: str,
        direction: HeavenlySubgraphDirection,
    ) -> str | None:
        if direction in {"outgoing", "both"} and relation.source_node_id == node_id:
            return relation.target_node_id
        if direction in {"incoming", "both"} and relation.target_node_id == node_id:
            return relation.source_node_id
        return None

    def _batch_hash(self, batch: HeavenlyGraphWriteBatch) -> str:
        canonical = json.dumps(
            batch.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def _validate_batch_revisions(
        self,
        batch: HeavenlyGraphWriteBatch,
    ) -> None:
        for node in batch.nodes:
            versions = self._nodes.get(
                (self._scope_key(node.scope), node.node_id),
                [],
            )
            self._validate_revision(
                entity_kind="node",
                entity_id=node.node_id,
                revision=node.revision,
                supersedes_revision=node.supersedes_revision,
                existing_revisions=[item.revision for item in versions],
                recorded_at=node.recorded_at,
                predecessor_recorded_at=(
                    max(versions, key=lambda item: item.revision).recorded_at
                    if versions
                    else None
                ),
            )
        for relation in batch.relations:
            versions = self._relations.get(
                (self._scope_key(relation.scope), relation.relation_id),
                [],
            )
            self._validate_revision(
                entity_kind="relation",
                entity_id=relation.relation_id,
                revision=relation.revision,
                supersedes_revision=relation.supersedes_revision,
                existing_revisions=[item.revision for item in versions],
                recorded_at=relation.recorded_at,
                predecessor_recorded_at=(
                    max(versions, key=lambda item: item.revision).recorded_at
                    if versions
                    else None
                ),
            )

    def _validate_relation_endpoints(
        self,
        batch: HeavenlyGraphWriteBatch,
    ) -> None:
        batch_nodes = {node.node_id: node for node in batch.nodes}
        scope_key = self._scope_key(batch.scope)
        for relation in batch.relations:
            for endpoint in [
                relation.source_node_id,
                relation.target_node_id,
            ]:
                versions = list(
                    self._nodes.get((scope_key, endpoint), [])
                )
                batch_node = batch_nodes.get(endpoint)
                if batch_node is not None:
                    versions.append(batch_node)
                exists = (
                    self._effective_entity(
                        versions,
                        valid_at=relation.validity.valid_from,
                        recorded_at=relation.recorded_at,
                    )
                    is not None
                )
                if not exists:
                    raise HeavenlyGraphReferentialIntegrityError(
                        f"relation endpoint {endpoint!r} is missing in batch scope "
                        "at the relation valid/recorded time"
                    )

    def _validate_revision(
        self,
        *,
        entity_kind: str,
        entity_id: str,
        revision: int,
        supersedes_revision: int | None,
        existing_revisions: list[int],
        recorded_at: int,
        predecessor_recorded_at: int | None,
    ) -> None:
        expected = max(existing_revisions, default=0) + 1
        expected_supersedes = expected - 1 if expected > 1 else None
        if (
            revision != expected
            or supersedes_revision != expected_supersedes
        ):
            raise HeavenlyGraphRevisionConflict(
                f"{entity_kind} {entity_id!r} expected revision {expected} "
                f"superseding {expected_supersedes!r}"
            )
        if (
            predecessor_recorded_at is not None
            and recorded_at < predecessor_recorded_at
        ):
            raise HeavenlyGraphRevisionConflict(
                f"{entity_kind} {entity_id!r} recorded_at {recorded_at} is "
                f"lower than predecessor {predecessor_recorded_at}"
            )

    def _effective_entity(
        self,
        versions: Sequence[HeavenlyGraphNode]
        | Sequence[HeavenlyGraphRelation],
        *,
        valid_at: int,
        recorded_at: int | None,
    ) -> HeavenlyGraphNode | HeavenlyGraphRelation | None:
        candidates = [
            item
            for item in versions
            if item.validity.contains(valid_at)
            and (recorded_at is None or item.recorded_at <= recorded_at)
        ]
        if not candidates:
            return None
        selected = max(
            candidates,
            key=lambda item: (item.recorded_at, item.revision),
        )
        if selected.semantic_metadata.derivation_kind in {"retraction", "redaction"}:
            return None
        return selected

    def _resolve_correction_target(
        self,
        request: GraphCorrectionRequest,
    ) -> tuple[HeavenlyGraphScope, list[HeavenlyGraphNode] | list[HeavenlyGraphRelation]]:
        store = self._nodes if request.target_kind == "node" else self._relations
        candidates = [
            (scope_key, entity_id, versions)
            for (scope_key, entity_id), versions in store.items()
            if entity_id == request.target_id
            and scope_key == self._scope_key(request.scope)
        ]
        if not candidates:
            raise ValueError(
                f"correction target {request.target_kind}:{request.target_id} was not found in scope"
            )
        if len(candidates) > 1:
            raise ValueError("correction target scope is ambiguous")
        scope_key, _, versions = candidates[0]
        return self._scope_from_key(scope_key), versions

    def _scope_from_key(self, key: ScopeKey) -> HeavenlyGraphScope:
        return HeavenlyGraphScope(
            world_id=key[0],
            session_id=key[1],
            story_branch_id=key[2],
            room_id=key[3],
            scene_id=key[4],
            graph_namespace=key[5],
            owner_actor_id=key[6],
        )

    def _scope_revision_vector(self, scope: HeavenlyGraphScope) -> GraphRevisionVector:
        scope_key = self._scope_key(scope)
        nodes = [item for (key, _), values in self._nodes.items() if key == scope_key for item in values]
        relations = [item for (key, _), values in self._relations.items() if key == scope_key for item in values]
        entities = [*nodes, *relations]
        vectors = [item.semantic_metadata.source_revision_vector for item in entities]
        node_revision, relation_revision = self._scope_stream_revisions.get(
            scope_key, (0, 0)
        )
        return GraphRevisionVector(
            node_revision=node_revision,
            relation_revision=relation_revision,
            source_revision=max((item.source_revision for item in vectors), default=0),
            policy_revision=max((item.policy_revision for item in vectors), default=0),
            branch_revision=max(
                self._branch_revisions.get(scope_key, 0),
                max((item.branch_revision for item in vectors), default=0),
            ),
        )

    def scope_revision_vector(self, scope: HeavenlyGraphScope) -> GraphRevisionVector:
        """Expose committed scope streams to semantic readers and stale writes."""
        return self._scope_revision_vector(scope)

    def _advance_scope_stream_revisions(self, batch: HeavenlyGraphWriteBatch) -> None:
        key = self._scope_key(batch.scope)
        node_revision, relation_revision = self._scope_stream_revisions.get(key, (0, 0))
        self._scope_stream_revisions[key] = (
            node_revision + len(batch.nodes),
            relation_revision + len(batch.relations),
        )

    def _has_scope_records(self, scope: HeavenlyGraphScope) -> bool:
        key = self._scope_key(scope)
        return any(stored_scope == key for stored_scope, _ in self._nodes) or any(
            stored_scope == key for stored_scope, _ in self._relations
        )

    @staticmethod
    def _is_explicit_branch_scope(scope: HeavenlyGraphScope) -> bool:
        """Return whether a scope uses the explicit branch lifecycle namespace."""

        return (
            scope.story_branch_id.startswith("branch:")
            and scope.story_branch_id != "branch:main"
        )

    @staticmethod
    def _is_legacy_compat_batch(batch: HeavenlyGraphWriteBatch) -> bool:
        """Keep pre-semantic contract records readable during migration.

        The branch lifecycle admission rule applies to semantic records. The
        old contract fixtures use ``policy:legacy`` and predate explicit fork
        registration; retaining that narrow compatibility path avoids
        changing the historical storage contract while all new records still
        require a registered fork.
        """

        entities = [*batch.nodes, *batch.relations]
        return bool(entities) and all(
            entity.semantic_metadata.policy_revision == "policy:legacy"
            for entity in entities
        )

    def _branch_revision(self, key: ScopeKey, *, advance: bool = False) -> int:
        current = self._branch_revisions.get(key, 0)
        if advance:
            current += 1
            self._branch_revisions[key] = current
        return current

    def _append_branch_marker(
        self,
        scope: HeavenlyGraphScope,
        operation: str,
        *,
        recorded_at: int,
        source_scope: HeavenlyGraphScope | None = None,
        source_revision_vector: GraphRevisionVector | None = None,
        node_id: str | None = None,
        target_branch_id: str | None = None,
    ) -> GraphBranchLifecycleMarker:
        key = self._scope_key(scope)
        marker = GraphBranchLifecycleMarker(
            marker_id=f"branch-marker:{scope.story_branch_id}:{len(self._branch_markers.get(key, [])) + 1}",
            branch_scope=scope,
            operation=operation,  # type: ignore[arg-type]
            recorded_at=recorded_at,
            revision_vector=self._scope_revision_vector(scope),
            policy_revision="policy:v1",
            source_scope=source_scope,
            source_revision_vector=source_revision_vector,
            node_id=node_id,
            target_branch_id=target_branch_id,
        )
        self._branch_markers.setdefault(key, []).append(marker)
        return marker

    def _is_node_closed(
        self,
        scope: HeavenlyGraphScope,
        node_id: str,
        *,
        recorded_at: int | None = None,
    ) -> bool:
        return any(
            marker.operation == "close_node" and marker.node_id == node_id
            and (recorded_at is None or marker.recorded_at <= recorded_at)
            for marker in self._branch_markers.get(self._scope_key(scope), [])
        )

    def _is_branch_discarded(
        self, scope: HeavenlyGraphScope, recorded_at: int | None = None
    ) -> bool:
        if self._branch_status.get(self._scope_key(scope)) != "discarded":
            return False
        return any(
            marker.operation == "discard"
            and (recorded_at is None or marker.recorded_at <= recorded_at)
            for marker in self._branch_markers.get(self._scope_key(scope), [])
        )

    def _latest_entity(
        self,
        scope: HeavenlyGraphScope,
        entity_id: str,
        store: dict[tuple[ScopeKey, str], list[object]],
    ) -> object | None:
        versions = store.get((self._scope_key(scope), entity_id), [])
        if not versions:
            return None
        return max(versions, key=lambda item: (item.recorded_at, item.revision))

    def _active_branch_snapshot(
        self, scope: HeavenlyGraphScope
    ) -> tuple[list[HeavenlyGraphNode], list[HeavenlyGraphRelation]]:
        return self._branch_snapshot_at(scope, valid_at=10**18, recorded_at=None)

    def _branch_snapshot_at(
        self,
        scope: HeavenlyGraphScope,
        *,
        valid_at: int,
        recorded_at: int | None,
    ) -> tuple[list[HeavenlyGraphNode], list[HeavenlyGraphRelation]]:
        key = self._scope_key(scope)
        nodes: list[HeavenlyGraphNode] = []
        if self._is_branch_discarded(scope, recorded_at):
            return [], []
        for (stored_scope, node_id), versions in self._nodes.items():
            if stored_scope != key or node_id.startswith("branch:closed:"):
                continue
            effective = self._effective_entity(
                versions, valid_at=valid_at, recorded_at=recorded_at
            )
            if not isinstance(effective, HeavenlyGraphNode):
                continue
            if effective.node_type == "branch_marker" or self._is_node_closed(
                scope, node_id, recorded_at=recorded_at
            ):
                continue
            nodes.append(effective.model_copy(deep=True))
        node_ids = {node.node_id for node in nodes}
        relations: list[HeavenlyGraphRelation] = []
        for (stored_scope, relation_id), versions in self._relations.items():
            if stored_scope != key:
                continue
            effective = self._effective_entity(
                versions, valid_at=valid_at, recorded_at=recorded_at
            )
            if not isinstance(effective, HeavenlyGraphRelation):
                continue
            if effective.relation_type == "closes_branch_node":
                continue
            if (
                effective.source_node_id not in node_ids
                or effective.target_node_id not in node_ids
            ):
                continue
            relations.append(effective.model_copy(deep=True))
        return sorted(nodes, key=lambda item: item.node_id), sorted(
            relations, key=lambda item: item.relation_id
        )

    def _copy_branch_marker(
        self, marker: GraphBranchLifecycleMarker, target: HeavenlyGraphScope
    ) -> GraphBranchLifecycleMarker:
        return marker.model_copy(
            update={
                "marker_id": f"{marker.marker_id}:admitted:{target.story_branch_id}",
                "branch_scope": target,
            },
            deep=True,
        )

    @staticmethod
    def _branch_independent_payload(entity: object) -> dict[str, object]:
        payload = entity.model_dump(mode="json")
        scope = payload.get("scope")
        if isinstance(scope, dict):
            scope["story_branch_id"] = "__branch__"
        return payload

    def _branch_marker_node(
        self,
        scope: HeavenlyGraphScope,
        node_id: str,
        vector: GraphRevisionVector,
        *,
        valid_from: int,
        recorded_at: int,
    ) -> HeavenlyGraphNode:
        marker_id = f"branch:closed:{node_id}"
        return HeavenlyGraphNode(
            node_id=marker_id,
            node_type="branch_marker",
            scope=scope,
            validity=GraphValidity(valid_from=valid_from),
            recorded_at=recorded_at,
            revision=1,
            attributes={"operation": "close_node", "node_id": node_id},
            provenance=GraphProvenance(
                source_kind="authority_event",
                source_ref=f"branch:{scope.story_branch_id}:close:{node_id}",
                causation_id=f"branch:close:{node_id}",
                correlation_id=f"branch:{scope.story_branch_id}",
                producer_system="heavenly_graph",
            ),
            semantic_metadata=GraphSemanticMetadata(
                visibility_scope="authority_only", policy_revision="policy:v1"
            ),
        )

    def _branch_close_relation(
        self,
        scope: HeavenlyGraphScope,
        marker_node: HeavenlyGraphNode,
        node_id: str,
        vector: GraphRevisionVector,
        *,
        valid_from: int,
        recorded_at: int,
    ) -> HeavenlyGraphRelation:
        return HeavenlyGraphRelation(
            relation_id=f"branch:close:{node_id}",
            relation_type="closes_branch_node",
            source_node_id=marker_node.node_id,
            target_node_id=node_id,
            scope=scope,
            validity=GraphValidity(valid_from=valid_from),
            recorded_at=recorded_at,
            revision=1,
            provenance=GraphProvenance(
                source_kind="authority_event",
                source_ref=f"branch:{scope.story_branch_id}:close:{node_id}",
                causation_id=f"branch:close:{node_id}",
                correlation_id=f"branch:{scope.story_branch_id}",
                producer_system="heavenly_graph",
            ),
            semantic_metadata=GraphSemanticMetadata(
                visibility_scope="authority_only", policy_revision="policy:v1"
            ),
        )

    def _snapshot_mutable_state(self) -> tuple[object, ...]:
        """Return a deep snapshot used by durable adapters around persistence."""
        return (
            copy.deepcopy(self._nodes),
            copy.deepcopy(self._relations),
            copy.deepcopy(self._idempotency),
            copy.deepcopy(self._checkpoints),
            copy.deepcopy(self._checkpoint_refs),
            copy.deepcopy(self._scope_stream_revisions),
            copy.deepcopy(self._branch_markers),
            copy.deepcopy(self._branch_status),
            copy.deepcopy(self._branch_revisions),
        )

    def _restore_mutable_state(
        self, snapshot: tuple[object, object, object, object, object, object]
    ) -> None:
        (
            self._nodes,
            self._relations,
            self._idempotency,
            self._checkpoints,
            self._checkpoint_refs,
            self._scope_stream_revisions,
            self._branch_markers,
            self._branch_status,
            self._branch_revisions,
        ) = snapshot

    @staticmethod
    def _revision_vector_matches(
        expected: GraphRevisionVector,
        current: GraphRevisionVector,
    ) -> bool:
        """Treat explicitly supplied vector dimensions as the read set.

        Pydantic preserves ``model_fields_set`` on the frozen vector, allowing
        callers to pin only the streams they actually read while still making
        an explicit zero revision a stale-read check.
        """
        fields = expected.model_fields_set or set(GraphRevisionVector.model_fields)
        return all(
            getattr(expected, field) == getattr(current, field)
            for field in fields
        )

    @staticmethod
    def _correction_idempotency_key(
        request: GraphCorrectionRequest, scope: HeavenlyGraphScope
    ) -> str:
        return (
            f"graph:correction:{request.target_kind}:{request.target_id}:"
            f"{request.target_revision}:{request.correction_kind}"
        )

    def _correction_hash(
        self, request: GraphCorrectionRequest, scope: HeavenlyGraphScope
    ) -> str:
        canonical = json.dumps(
            {
                "scope": scope.model_dump(mode="json"),
                "request": request.model_dump(mode="json"),
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


    def _scope_key(self, scope: HeavenlyGraphScope) -> ScopeKey:
        return (
            scope.world_id,
            scope.session_id,
            scope.story_branch_id,
            scope.room_id,
            scope.scene_id,
            scope.graph_namespace,
            scope.owner_actor_id,
        )

    def _entity_ref(
        self,
        entity_kind: str,
        scope: HeavenlyGraphScope,
        entity_id: str,
        revision: int,
    ) -> str:
        canonical_payload = json.dumps(
            {
                "entity_kind": entity_kind,
                "scope": scope.model_dump(mode="json"),
                "entity_id": entity_id,
                "revision": revision,
            },
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        encoded_payload = base64.urlsafe_b64encode(canonical_payload).decode(
            "ascii"
        )
        return (
            f"heavenly_graph_{entity_kind}:"
            f"{encoded_payload.rstrip('=')}"
        )

    def _checkpoint_ref(
        self,
        checkpoint_id: str,
        scope: HeavenlyGraphScope,
    ) -> str:
        canonical_payload = json.dumps(
            {
                "checkpoint_id": checkpoint_id,
                "scope": scope.model_dump(mode="json"),
            },
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        encoded_payload = base64.urlsafe_b64encode(canonical_payload).decode(
            "ascii"
        )
        return f"heavenly_graph_checkpoint:{encoded_payload.rstrip('=')}"
