"""Bounded, explicit-context semantic read facade for Heavenly Graph."""

from __future__ import annotations

import hashlib
import json
from typing import Protocol

from app.models.siming_heavenly_graph import (
    CausalPathQuery,
    GraphRevisionVector,
    HeavenlyGraphNode,
    HeavenlyGraphQueryResult,
    HeavenlyGraphRelation,
    HeavenlyGraphSemanticQuery,
    HeavenlyNodeQuery,
    HeavenlyRelationQuery,
    NodeLookupQuery,
    RelationLookupQuery,
)


class _LowLevelGraph(Protocol):
    def query_nodes(self, query: HeavenlyNodeQuery) -> list[HeavenlyGraphNode]: ...

    def query_relations(
        self, query: HeavenlyRelationQuery
    ) -> list[HeavenlyGraphRelation]: ...


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
            # Domain traversal is introduced in Task 3; keep this shell bounded.
            return [], [], False
        return [], [], False

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
