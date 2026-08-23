"""Read-only consistency checks for the Heavenly Graph storage surface.

The audit deliberately consumes the adapter's admitted historical collections
instead of using effective queries.  This makes broken predecessor chains and
retracted/corrected records observable without changing the graph or leaking
private payloads to a reader that cannot see them.
"""

from __future__ import annotations

from typing import Any, Iterable

from pydantic import BaseModel, ConfigDict, Field

from app.models.siming_heavenly_graph import (
    GraphReaderContext,
    HeavenlyGraphNode,
    HeavenlyGraphRelation,
    HeavenlyGraphScope,
)
from app.services.heavenly_graph_semantics import (
    DEFAULT_NODE_TYPE_REGISTRY,
    DEFAULT_RELATION_TYPE_REGISTRY,
)


class HeavenlyGraphConsistencyError(BaseModel):
    """One deterministic invariant failure from a consistency audit."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    error_id: str = Field(min_length=1)
    category: str = Field(min_length=1)
    entity_kind: str = Field(min_length=1)
    entity_ref: str | None = None
    payload: dict[str, object] = Field(default_factory=dict)
    redacted: bool = False


class HeavenlyGraphConsistencyReport(BaseModel):
    """Stable, bounded audit output.  It contains no mutable adapter state."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    scope: HeavenlyGraphScope
    policy_revision: str
    checked_node_revisions: int = Field(ge=0)
    checked_relation_revisions: int = Field(ge=0)
    errors: list[HeavenlyGraphConsistencyError] = Field(default_factory=list)

    @property
    def valid(self) -> bool:
        return not self.errors


class HeavenlyGraphConsistencyAudit:
    """Audit one graph adapter without mutating it.

    The constructor accepts the adapter because both production adapters share
    this exact audit.  ``audit(scope, reader_context)`` pins the coordinates of
    the report and the reader's visibility policy.
    """

    def __init__(
        self,
        graph: object,
        scope: HeavenlyGraphScope | None = None,
        reader_context: GraphReaderContext | None = None,
    ) -> None:
        self._graph = graph
        self._scope = scope
        self._reader_context = reader_context

    def audit(
        self,
        scope: HeavenlyGraphScope | None = None,
        reader_context: GraphReaderContext | None = None,
    ) -> HeavenlyGraphConsistencyReport:
        scope = scope or self._scope
        reader_context = reader_context or self._reader_context
        if scope is None or reader_context is None:
            raise ValueError("consistency audit requires scope and reader_context")
        if (
            scope.world_id != reader_context.world_id
            or scope.session_id != reader_context.session_id
            or scope.story_branch_id != reader_context.story_branch_id
        ):
            raise ValueError("audit scope must match reader context world/session/branch")

        nodes = self._historical(self._collection("_nodes"), scope)
        relations = self._historical(self._collection("_relations"), scope)
        node_by_id: dict[str, list[HeavenlyGraphNode]] = {}
        relation_by_id: dict[str, list[HeavenlyGraphRelation]] = {}
        for node in nodes:
            node_by_id.setdefault(node.node_id, []).append(node)
        for relation in relations:
            relation_by_id.setdefault(relation.relation_id, []).append(relation)

        errors: list[HeavenlyGraphConsistencyError] = []
        for node in nodes:
            self._audit_entity_scope(node, scope, reader_context, errors)
            self._audit_node_semantics(node, reader_context, errors)
            self._audit_provenance(node, reader_context, errors)
        for relation in relations:
            self._audit_entity_scope(relation, scope, reader_context, errors)
            self._audit_relation_semantics(relation, reader_context, errors)
            self._audit_provenance(relation, reader_context, errors)
            self._audit_relation_endpoints(relation, node_by_id, reader_context, errors)

        for entity_id, versions in node_by_id.items():
            self._audit_revision_chain("node", entity_id, versions, reader_context, errors)
        for entity_id, versions in relation_by_id.items():
            self._audit_revision_chain("relation", entity_id, versions, reader_context, errors)
        for node in nodes:
            self._audit_correction_link(node, node_by_id, reader_context, errors)
        for relation in relations:
            self._audit_correction_link(relation, relation_by_id, reader_context, errors)

        errors.sort(key=lambda item: (item.error_id, item.entity_kind, item.entity_ref or "", item.category))
        return HeavenlyGraphConsistencyReport(
            scope=scope,
            policy_revision=reader_context.policy_revision,
            checked_node_revisions=len(nodes),
            checked_relation_revisions=len(relations),
            errors=errors,
        )

    # ``run`` is a small compatibility alias for callers that use audit as a
    # service object rather than a verb.
    run = audit

    def _collection(self, name: str) -> dict[object, list[object]]:
        value = getattr(self._graph, name, None)
        if not isinstance(value, dict):
            raise TypeError(f"graph adapter does not expose historical {name}")
        return value

    def _historical(
        self,
        collection: dict[object, list[object]],
        scope: HeavenlyGraphScope,
    ) -> list[HeavenlyGraphNode | HeavenlyGraphRelation]:
        scope_key = self._scope_key(scope)
        result: list[HeavenlyGraphNode | HeavenlyGraphRelation] = []
        for key, versions in collection.items():
            stored_scope_key = key[0] if isinstance(key, tuple) and key else key
            if stored_scope_key != scope_key:
                continue
            result.extend(item.model_copy(deep=True) for item in versions)
        return sorted(result, key=lambda item: (self._entity_id(item), item.revision))

    def _scope_key(self, scope: HeavenlyGraphScope) -> object:
        helper = getattr(self._graph, "_scope_key", None)
        return helper(scope) if callable(helper) else (
            scope.world_id,
            scope.session_id,
            scope.story_branch_id,
            scope.room_id,
            scope.scene_id,
            scope.graph_namespace,
            scope.owner_actor_id,
        )

    @staticmethod
    def _entity_id(entity: HeavenlyGraphNode | HeavenlyGraphRelation) -> str:
        return entity.node_id if isinstance(entity, HeavenlyGraphNode) else entity.relation_id

    @staticmethod
    def _entity_kind(entity: HeavenlyGraphNode | HeavenlyGraphRelation) -> str:
        return "node" if isinstance(entity, HeavenlyGraphNode) else "relation"

    def _visible(self, entity: HeavenlyGraphNode | HeavenlyGraphRelation, context: GraphReaderContext) -> bool:
        metadata = entity.semantic_metadata
        if metadata.visibility_scope not in context.allowed_visibility_scopes:
            return False
        owner = entity.scope.owner_actor_id
        if metadata.visibility_scope == "actor_private" and owner is not None:
            return context.reader_principal in {owner, f"actor:{owner}", f"reader:{owner}"}
        return True

    def _error(
        self,
        error_id: str,
        category: str,
        entity: HeavenlyGraphNode | HeavenlyGraphRelation,
        context: GraphReaderContext,
        *,
        payload: dict[str, object] | None = None,
    ) -> HeavenlyGraphConsistencyError:
        visible = self._visible(entity, context)
        if not visible:
            return HeavenlyGraphConsistencyError(
                error_id=error_id,
                category=category,
                entity_kind=self._entity_kind(entity),
                entity_ref=None,
                payload={"redacted": True},
                redacted=True,
            )
        ref = self._entity_ref(entity)
        return HeavenlyGraphConsistencyError(
            error_id=error_id,
            category=category,
            entity_kind=self._entity_kind(entity),
            entity_ref=ref,
            payload=payload or {"entity_id": self._entity_id(entity), "revision": entity.revision},
            redacted=False,
        )

    def _entity_ref(self, entity: HeavenlyGraphNode | HeavenlyGraphRelation) -> str:
        helper = getattr(self._graph, "_entity_ref", None)
        if callable(helper):
            return helper(self._entity_kind(entity), entity.scope, self._entity_id(entity), entity.revision)
        return f"{self._entity_kind(entity)}:{self._entity_id(entity)}:{entity.revision}"

    def _append(
        self,
        errors: list[HeavenlyGraphConsistencyError],
        error_id: str,
        category: str,
        entity: HeavenlyGraphNode | HeavenlyGraphRelation,
        context: GraphReaderContext,
        *,
        payload: dict[str, object] | None = None,
    ) -> None:
        errors.append(self._error(error_id, category, entity, context, payload=payload))

    def _audit_entity_scope(self, entity: Any, scope: HeavenlyGraphScope, context: GraphReaderContext, errors: list[HeavenlyGraphConsistencyError]) -> None:
        if entity.scope != scope:
            self._append(errors, "HG-AUDIT-SCOPE", "scope_violation", entity, context)
        if entity.scope.graph_namespace == "actor_private" and entity.scope.owner_actor_id is None:
            self._append(errors, "HG-AUDIT-SCOPE", "scope_violation", entity, context)
        if entity.scope.graph_namespace != "actor_private" and entity.scope.owner_actor_id is not None:
            self._append(errors, "HG-AUDIT-SCOPE", "scope_violation", entity, context)

    def _audit_node_semantics(self, node: HeavenlyGraphNode, context: GraphReaderContext, errors: list[HeavenlyGraphConsistencyError]) -> None:
        try:
            DEFAULT_NODE_TYPE_REGISTRY.validate_node(node, allow_legacy=True)
        except (ValueError, TypeError):
            self._append(errors, "HG-AUDIT-SEMANTIC-TYPE", "unsupported_semantic_type", node, context)

    def _audit_relation_semantics(self, relation: HeavenlyGraphRelation, context: GraphReaderContext, errors: list[HeavenlyGraphConsistencyError]) -> None:
        try:
            DEFAULT_RELATION_TYPE_REGISTRY.validate_relation(relation, allow_legacy=True)
        except (ValueError, TypeError):
            self._append(errors, "HG-AUDIT-SEMANTIC-TYPE", "unsupported_semantic_type", relation, context)

    def _audit_provenance(self, entity: Any, context: GraphReaderContext, errors: list[HeavenlyGraphConsistencyError]) -> None:
        provenance = getattr(entity, "provenance", None)
        fields = ("source_ref", "causation_id", "correlation_id", "producer_system")
        if provenance is None or any(not isinstance(getattr(provenance, field, None), str) or not getattr(provenance, field, "") for field in fields):
            self._append(errors, "HG-AUDIT-PROVENANCE", "invalid_provenance", entity, context)

    def _audit_relation_endpoints(self, relation: HeavenlyGraphRelation, nodes: dict[str, list[HeavenlyGraphNode]], context: GraphReaderContext, errors: list[HeavenlyGraphConsistencyError]) -> None:
        if relation.source_node_id not in nodes or relation.target_node_id not in nodes:
            self._append(errors, "HG-AUDIT-ORPHAN-RELATION", "orphan_relation", relation, context)

    def _audit_revision_chain(self, kind: str, entity_id: str, versions: Iterable[Any], context: GraphReaderContext, errors: list[HeavenlyGraphConsistencyError]) -> None:
        ordered = sorted(versions, key=lambda item: item.revision)
        for expected, item in enumerate(ordered, start=1):
            if item.revision != expected or item.supersedes_revision != (expected - 1 if expected > 1 else None):
                self._append(errors, "HG-AUDIT-REVISION-CHAIN", "invalid_revision_chain", item, context)
                break

    def _audit_correction_link(self, entity: Any, histories: dict[str, list[Any]], context: GraphReaderContext, errors: list[HeavenlyGraphConsistencyError]) -> None:
        metadata = entity.semantic_metadata
        if metadata.derivation_kind not in {"correction", "retraction", "redaction"}:
            return
        attrs = entity.attributes
        target_id = attrs.get("correction_target_id")
        target_revision = attrs.get("correction_target_revision")
        source_refs = attrs.get("correction_source_refs")
        predecessors = histories.get(entity.node_id if isinstance(entity, HeavenlyGraphNode) else entity.relation_id, [])
        expected_revision = entity.supersedes_revision
        if (
            not isinstance(target_id, str)
            or not isinstance(target_revision, int)
            or target_id != (entity.node_id if isinstance(entity, HeavenlyGraphNode) else entity.relation_id)
            or target_revision != expected_revision
            or not isinstance(source_refs, list)
            or not source_refs
            or not any(item.revision == target_revision for item in predecessors)
        ):
            self._append(errors, "HG-AUDIT-CORRECTION-LINK", "broken_correction_link", entity, context)


def audit_heavenly_graph(
    graph: object,
    scope: HeavenlyGraphScope,
    reader_context: GraphReaderContext,
) -> HeavenlyGraphConsistencyReport:
    """Functional entry point for adapters and verification scripts."""

    return HeavenlyGraphConsistencyAudit(graph).audit(scope, reader_context)


__all__ = [
    "HeavenlyGraphConsistencyAudit",
    "HeavenlyGraphConsistencyError",
    "HeavenlyGraphConsistencyReport",
    "audit_heavenly_graph",
]
