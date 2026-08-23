import base64
import copy
import hashlib
import json
from collections.abc import Sequence

from app.models.siming_heavenly_graph import (
    GraphCorrectionRequest,
    GraphRevisionVector,
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

    def write_batch(
        self,
        batch: HeavenlyGraphWriteBatch,
    ) -> HeavenlyGraphWriteResult:
        return self._write_batch(batch)

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

        for node in batch.nodes:
            key = (self._scope_key(node.scope), node.node_id)
            self._nodes.setdefault(key, []).append(node.model_copy(deep=True))
        for relation in batch.relations:
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
        for node in batch.nodes:
            DEFAULT_NODE_TYPE_REGISTRY.validate_node(node, allow_legacy=True)
        for relation in batch.relations:
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
            branch_revision=max((item.branch_revision for item in vectors), default=0),
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

    def _snapshot_mutable_state(self) -> tuple[object, object, object, object, object, object]:
        """Return a deep snapshot used by durable adapters around persistence."""
        return (
            copy.deepcopy(self._nodes),
            copy.deepcopy(self._relations),
            copy.deepcopy(self._idempotency),
            copy.deepcopy(self._checkpoints),
            copy.deepcopy(self._checkpoint_refs),
            copy.deepcopy(self._scope_stream_revisions),
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
