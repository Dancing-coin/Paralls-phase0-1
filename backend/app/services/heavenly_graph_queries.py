"""Bounded, explicit-context semantic read facade for Heavenly Graph."""

from __future__ import annotations

import hashlib
import json
from typing import Protocol

from app.models.siming_heavenly_graph import (
    BehaviorTurnQuery,
    CausalPathQuery,
    ConflictSetQuery,
    GraphRevisionVector,
    HeavenlyGraphNode,
    HeavenlyGraphQueryResult,
    HeavenlyGraphRelation,
    HeavenlyGraphSemanticQuery,
    HeavenlyNodeQuery,
    HeavenlyRelationQuery,
    NodeLookupQuery,
    PerspectiveQuery,
    RelationLookupQuery,
    SourceImpactQuery,
)


_CAUSAL_RELATION_TYPES = frozenset({"caused_by", "enabled_by", "prevented_by"})
_SEMANTIC_CANDIDATE_LIMIT = 1000


class _LowLevelGraph(Protocol):
    def query_nodes(self, query: HeavenlyNodeQuery) -> list[HeavenlyGraphNode]: ...

    def query_relations(
        self, query: HeavenlyRelationQuery
    ) -> list[HeavenlyGraphRelation]: ...

    def query_subgraph(self, **kwargs: object): ...


class HeavenlyGraphSemanticQueryFacade:
    """Applies reader context and semantic admission to bounded adapter reads."""

    def __init__(self, graph: _LowLevelGraph) -> None:
        self._graph = graph

    def query(self, query: HeavenlyGraphSemanticQuery) -> HeavenlyGraphQueryResult:
        try:
            nodes, relations, truncated = self._read_bounded(query)
        except Exception:
            return self._empty(query, incomplete_reason="graph_unavailable")

        visible_nodes, node_denied, node_stale = self._filter_entities(
            nodes, query
        )
        visible_relations, relation_denied, relation_stale = self._filter_entities(
            relations, query
        )
        nodes = sorted(visible_nodes, key=lambda node: node.node_id)
        relations = sorted(visible_relations, key=lambda relation: relation.relation_id)
        if node_stale or relation_stale:
            incomplete_reason = "stale_read_set"
        elif node_denied or relation_denied:
            incomplete_reason = "visibility_denied"
        else:
            incomplete_reason = None
        return HeavenlyGraphQueryResult(
            nodes=nodes,
            relations=relations,
            selected_node_refs=[node.node_id for node in nodes],
            selected_relation_refs=[relation.relation_id for relation in relations],
            revision_vector=self._revision_vector(nodes, relations),
            policy_revision=query.context.policy_revision,
            scope_digest=self._scope_digest(query),
            truncated=truncated,
            incomplete_reason=incomplete_reason,
        )

    def _read_bounded(
        self, query: HeavenlyGraphSemanticQuery
    ) -> tuple[list[HeavenlyGraphNode], list[HeavenlyGraphRelation], bool]:
        scope = query.resolved_scope()
        node_query = HeavenlyNodeQuery(
            scope=scope,
            valid_at=query.context.valid_at,
            recorded_at=query.context.recorded_at,
            limit=query.limit,
        )
        relation_query = HeavenlyRelationQuery(
            scope=scope,
            valid_at=query.context.valid_at,
            recorded_at=query.context.recorded_at,
            limit=query.limit,
        )
        if isinstance(query, NodeLookupQuery):
            candidate_limit = query.limit
            has_post_query_filter = bool(query.source_refs or query.record_kinds)
            if has_post_query_filter:
                # Fetch a larger but still adapter-bounded candidate window so
                # post-query semantic filters cannot hide an eligible match.
                candidate_limit = 1000
            node_query = node_query.model_copy(
                update={
                    "node_ids": query.node_ids,
                    "node_types": query.node_types,
                    "limit": candidate_limit,
                }
            )
            candidates = self._graph.query_nodes(node_query)
            candidate_window_truncated = len(candidates) >= candidate_limit
            if query.source_refs:
                refs = set(query.source_refs)
                candidates = [
                    node for node in candidates
                    if node.provenance.source_ref in refs
                    or refs.intersection(node.semantic_metadata.source_event_refs)
                ]
            if query.record_kinds:
                candidates = [
                    node
                    for node in candidates
                    if node.semantic_metadata.record_kind in query.record_kinds
                ]
            filtered_count = len(candidates)
            truncated = candidate_window_truncated or filtered_count > query.limit
            return candidates[: query.limit], [], truncated
        if isinstance(query, RelationLookupQuery):
            relation_query = relation_query.model_copy(
                update={
                    "relation_ids": query.relation_ids,
                    "relation_types": query.relation_types,
                    "source_node_ids": query.source_node_ids,
                    "target_node_ids": query.target_node_ids,
                }
            )
            relations = self._graph.query_relations(relation_query)
            return [], relations, len(relations) >= query.limit
        if isinstance(query, CausalPathQuery):
            relation_types = query.relation_types or sorted(_CAUSAL_RELATION_TYPES)
            relation_types = [
                relation_type
                for relation_type in relation_types
                if relation_type in _CAUSAL_RELATION_TYPES
            ]
            subgraph = self._graph.query_subgraph(
                scope=scope,
                seed_node_ids=query.seed_node_ids,
                relation_types=relation_types,
                direction="outgoing",
                max_depth=query.max_depth,
                valid_at=query.context.valid_at,
                recorded_at=query.context.recorded_at,
                node_limit=query.node_limit,
                relation_limit=query.relation_limit,
            )
            # Result v1 returns a deterministic path union rather than exposing
            # path rows. More independent route edges than max_paths is still
            # disclosed as incomplete instead of silently implying a full read.
            path_bound_reached = len(subgraph.relations) >= query.max_paths
            return subgraph.nodes, subgraph.relations, (
                subgraph.truncated or path_bound_reached
            )
        if isinstance(query, PerspectiveQuery):
            perspective_scope = scope
            if query.actor_ref and query.scope is None:
                perspective_scope = HeavenlyGraphScope(
                    world_id=query.context.world_id,
                    session_id=query.context.session_id,
                    story_branch_id=query.context.story_branch_id,
                    graph_namespace="actor_private",
                    owner_actor_id=query.actor_ref,
                )
            candidates = self._graph.query_nodes(
                HeavenlyNodeQuery(
                    scope=perspective_scope,
                    valid_at=query.context.valid_at,
                    recorded_at=query.context.recorded_at,
                    node_types=["actor_view", "actor_memory_ref"],
                    limit=self._candidate_limit(query.limit),
                )
            )
            scopes = set(query.visibility_scopes)
            if scopes:
                candidates = [
                    node for node in candidates
                    if node.semantic_metadata.visibility_scope in scopes
                ]
            if query.actor_ref:
                candidates = [
                    node for node in candidates
                    if node.scope.owner_actor_id == query.actor_ref
                    or node.provenance.actor_id == query.actor_ref
                    or node.attributes.get("actor_ref") == query.actor_ref
                ]
            return candidates[: query.limit], [], self._bounded(candidates, query.limit)
        if isinstance(query, ConflictSetQuery):
            candidates = self._graph.query_nodes(
                HeavenlyNodeQuery(
                    scope=scope,
                    valid_at=query.context.valid_at,
                    recorded_at=query.context.recorded_at,
                    limit=self._candidate_limit(query.limit),
                )
            )
            candidates = [
                node for node in candidates
                if (
                    query.subject_ref is None
                    or node.attributes.get("subject_ref") == query.subject_ref
                    or node.attributes.get("subject_id") == query.subject_ref
                )
                and (
                    query.property_key is None
                    or node.attributes.get("property_key") == query.property_key
                    or node.attributes.get("property") == query.property_key
                )
            ]
            selected_ids = {node.node_id for node in candidates}
            relations = self._graph.query_relations(
                HeavenlyRelationQuery(
                    scope=scope,
                    valid_at=query.context.valid_at,
                    recorded_at=query.context.recorded_at,
                    relation_types=["contradicts"],
                    limit=self._candidate_limit(query.limit),
                )
            )
            relations = [
                relation for relation in relations
                if relation.source_node_id in selected_ids
                or relation.target_node_id in selected_ids
            ]
            return (
                candidates[: query.limit],
                relations[: query.limit],
                self._bounded(candidates, query.limit)
                or self._bounded(relations, query.limit),
            )
        if isinstance(query, BehaviorTurnQuery):
            candidates = self._graph.query_nodes(
                HeavenlyNodeQuery(
                    scope=scope,
                    valid_at=query.context.valid_at,
                    recorded_at=query.context.recorded_at,
                    limit=self._candidate_limit(query.limit),
                )
            )
            matching_nodes = [
                node for node in candidates if self._matches_turn(node, query)
            ]
            selected_ids = {node.node_id for node in matching_nodes}
            relations = self._graph.query_relations(
                HeavenlyRelationQuery(
                    scope=scope,
                    valid_at=query.context.valid_at,
                    recorded_at=query.context.recorded_at,
                    limit=self._candidate_limit(query.limit),
                )
            )
            relations = [
                relation for relation in relations
                if relation.source_node_id in selected_ids
                or relation.target_node_id in selected_ids
                or self._matches_turn(relation, query)
            ]
            related_ids = {
                node_id
                for relation in relations
                for node_id in (relation.source_node_id, relation.target_node_id)
            }
            nodes = [
                node for node in candidates
                if node.node_id in selected_ids or node.node_id in related_ids
            ]
            return (
                nodes[: query.limit],
                relations[: query.limit],
                self._bounded(nodes, query.limit)
                or self._bounded(relations, query.limit),
            )
        if isinstance(query, SourceImpactQuery):
            candidates = self._graph.query_nodes(
                HeavenlyNodeQuery(
                    scope=scope,
                    valid_at=query.context.valid_at,
                    recorded_at=query.context.recorded_at,
                    limit=self._candidate_limit(query.limit),
                )
            )
            candidates = [
                node for node in candidates
                if self._references_source(node, query.source_ref, query.source_revision)
            ]
            relations = self._graph.query_relations(
                HeavenlyRelationQuery(
                    scope=scope,
                    valid_at=query.context.valid_at,
                    recorded_at=query.context.recorded_at,
                    limit=self._candidate_limit(query.limit),
                )
            )
            relations = [
                relation for relation in relations
                if self._references_source(relation, query.source_ref, query.source_revision)
            ]
            return (
                candidates[: query.limit],
                relations[: query.limit],
                self._bounded(candidates, query.limit)
                or self._bounded(relations, query.limit),
            )
        return [], [], False

    @staticmethod
    def _candidate_limit(limit: int) -> int:
        # Semantic predicates run after the adapter read. Use the fixed
        # candidate window so an early non-match cannot hide a later match.
        return _SEMANTIC_CANDIDATE_LIMIT

    @staticmethod
    def _bounded(entities: list[object], limit: int) -> bool:
        return len(entities) >= limit

    @staticmethod
    def _matches_turn(entity: object, query: BehaviorTurnQuery) -> bool:
        attrs = entity.attributes
        provenance = entity.provenance
        if query.turn_id is not None and attrs.get("turn_id") != query.turn_id:
            return False
        if query.correlation_id is not None and provenance.correlation_id != query.correlation_id and attrs.get("correlation_id") != query.correlation_id:
            return False
        if query.actor_id is not None and provenance.actor_id != query.actor_id and attrs.get("actor_id") != query.actor_id:
            return False
        if query.stage is not None and attrs.get("stage") != query.stage:
            return False
        return True

    @staticmethod
    def _references_source(entity: object, source_ref: str, source_revision: int | None) -> bool:
        metadata = entity.semantic_metadata
        source_match = (
            source_ref in metadata.source_event_refs
            or source_ref in entity.provenance.evidence_refs
            or entity.attributes.get("source_ref") == source_ref
            or entity.attributes.get("source_node_id") == source_ref
            or getattr(entity, "source_node_id", None) == source_ref
            or getattr(entity, "target_node_id", None) == source_ref
            or (
                entity.provenance.source_ref == source_ref
                and metadata.derivation_kind != "authority"
            )
        )
        if not source_match:
            return False
        return source_revision is None or metadata.source_revision_vector.source_revision == source_revision

    def _filter_entities(self, entities: list[object], query: HeavenlyGraphSemanticQuery):
        visible: list[object] = []
        denied = False
        stale = False
        for entity in entities:
            metadata = entity.semantic_metadata
            if metadata.visibility_scope not in query.context.allowed_visibility_scopes:
                denied = True
                continue
            owner_actor_id = entity.scope.owner_actor_id
            if (
                metadata.visibility_scope == "actor_private"
                and owner_actor_id is not None
                and not self._principal_matches_owner(
                    query.context.reader_principal, owner_actor_id
                )
            ):
                denied = True
                continue
            if metadata.record_kind == "proposal" and not query.include_proposals:
                continue
            if metadata.policy_revision != query.context.policy_revision:
                stale = True
                continue
            visible.append(entity)
        return visible, denied, stale

    @staticmethod
    def _principal_matches_owner(principal: str, owner_actor_id: str) -> bool:
        if principal == owner_actor_id:
            return True
        namespace, separator, actor_id = principal.partition(":")
        return separator == ":" and namespace in {"actor", "reader"} and actor_id == owner_actor_id

    @staticmethod
    def _revision_vector(
        nodes: list[HeavenlyGraphNode], relations: list[HeavenlyGraphRelation]
    ) -> GraphRevisionVector:
        vectors = [
            entity.semantic_metadata.source_revision_vector
            for entity in [*nodes, *relations]
        ]
        return GraphRevisionVector(
            node_revision=max((node.revision for node in nodes), default=0),
            relation_revision=max((relation.revision for relation in relations), default=0),
            source_revision=max((vector.source_revision for vector in vectors), default=0),
            policy_revision=max((vector.policy_revision for vector in vectors), default=0),
            branch_revision=max((vector.branch_revision for vector in vectors), default=0),
        )

    @staticmethod
    def _scope_digest(query: HeavenlyGraphSemanticQuery) -> str:
        payload = {
            "context": query.context.model_dump(mode="json"),
            "scope": query.resolved_scope().model_dump(mode="json"),
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return "scope:" + hashlib.sha256(encoded).hexdigest()

    def _empty(
        self, query: HeavenlyGraphSemanticQuery, *, incomplete_reason: str
    ) -> HeavenlyGraphQueryResult:
        return HeavenlyGraphQueryResult(
            policy_revision=query.context.policy_revision,
            scope_digest=self._scope_digest(query),
            incomplete_reason=incomplete_reason,
        )


# Short aliases keep the facade discoverable without introducing a second implementation.
HeavenlyGraphQueryFacade = HeavenlyGraphSemanticQueryFacade


def query_semantic(graph: _LowLevelGraph, query: HeavenlyGraphSemanticQuery) -> HeavenlyGraphQueryResult:
    return HeavenlyGraphSemanticQueryFacade(graph).query(query)
