"""Typed semantic vocabulary and admission rules for Heavenly Graph records."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.models.siming_heavenly_graph import (
    GraphCorrectionRequest,
    GraphNamespace,
    GraphRecordKind,
    GraphVisibilityScope,
    HeavenlyGraphNode,
    HeavenlyGraphRelation,
)


@dataclass(frozen=True)
class _NodeRule:
    allowed_namespaces: tuple[GraphNamespace, ...]
    allowed_record_kinds: tuple[GraphRecordKind, ...]
    allowed_visibility_scopes: tuple[GraphVisibilityScope, ...]


@dataclass(frozen=True)
class _RelationRule:
    allowed_namespace_pairs: tuple[tuple[GraphNamespace, GraphNamespace], ...]
    allowed_record_kinds: tuple[GraphRecordKind, ...]
    allowed_visibility_scopes: tuple[GraphVisibilityScope, ...]


_SIMING: GraphNamespace = "siming_heavenly"
_ACTOR: GraphNamespace = "actor_private"
_RESOURCE: GraphNamespace = "resource_capability"

_PUBLIC: GraphVisibilityScope = "public"
_PRIVATE: GraphVisibilityScope = "actor_private"
_INTERNAL: GraphVisibilityScope = "siming_internal"
_AUTHORITY: GraphVisibilityScope = "authority_only"
_BRANCH: GraphVisibilityScope = "branch_only"


class HeavenlyNodeTypeRegistry:
    """Deterministic registry for the first-version Heavenly Graph node types."""

    DEFAULT_RULES: dict[str, _NodeRule] = {
        "world_fact": _NodeRule((_SIMING, _RESOURCE), ("fact",), (_PUBLIC, _AUTHORITY, _BRANCH)),
        "causal_event": _NodeRule((_SIMING,), ("fact", "projection"), (_PUBLIC, _INTERNAL, _AUTHORITY, _BRANCH)),
        "actor_view": _NodeRule((_ACTOR,), ("projection",), (_PRIVATE,)),
        "actor_memory_ref": _NodeRule((_ACTOR,), ("fact", "projection"), (_PRIVATE,)),
        "behavior_turn": _NodeRule((_SIMING, _ACTOR), ("projection", "proposal"), (_INTERNAL, _PRIVATE, _AUTHORITY, _BRANCH)),
        "storyline_thread": _NodeRule((_SIMING,), ("fact", "projection", "proposal"), (_PUBLIC, _INTERNAL, _BRANCH)),
        "story_node_blueprint": _NodeRule((_SIMING,), ("fact", "projection", "proposal"), (_INTERNAL, _BRANCH)),
        "story_node_instance": _NodeRule((_SIMING,), ("fact", "projection"), (_PUBLIC, _INTERNAL, _BRANCH)),
        "narrative_obligation": _NodeRule((_SIMING,), ("fact", "projection", "proposal"), (_INTERNAL, _BRANCH)),
        "narrative_attractor": _NodeRule((_SIMING,), ("fact", "projection", "proposal"), (_INTERNAL, _BRANCH)),
        "resource_capability": _NodeRule((_RESOURCE,), ("fact", "projection"), (_PUBLIC, _AUTHORITY, _BRANCH)),
        "intervention_outcome": _NodeRule((_SIMING,), ("fact", "projection", "proposal"), (_INTERNAL, _AUTHORITY, _BRANCH)),
        "branch_marker": _NodeRule((_SIMING,), ("fact", "projection"), (_AUTHORITY, _BRANCH)),
        "policy_candidate": _NodeRule((_SIMING,), ("proposal",), (_INTERNAL, _AUTHORITY, _BRANCH)),
    }

    _LEGACY_EXACT_RULES: dict[str, _NodeRule] = {
        "authored_story_blueprint": _NodeRule((_SIMING,), ("fact",), (_PUBLIC,)),
        "runtime_story_node": _NodeRule((_SIMING,), ("fact",), (_PUBLIC,)),
        "story_authority_outcome": _NodeRule((_SIMING,), ("fact",), (_PUBLIC,)),
        "narrative_obligation": _NodeRule((_SIMING,), ("fact",), (_PUBLIC,)),
        "narrative_attractor": _NodeRule((_SIMING,), ("fact",), (_PUBLIC,)),
        "adaptive_bridge_audit": _NodeRule((_SIMING,), ("fact",), (_PUBLIC,)),
    }

    def __init__(self, rules: dict[str, _NodeRule] | None = None) -> None:
        self.rules = dict(rules or self.DEFAULT_RULES)

    @property
    def node_types(self) -> tuple[str, ...]:
        return tuple(sorted(self.rules))

    def require(self, node_type: str) -> _NodeRule:
        if node_type.startswith(("actor_memory:", "actor_memory_anchor:")):
            return _NodeRule((_ACTOR,), ("fact", "projection"), (_PRIVATE,))
        if node_type.startswith("memory:"):
            return _NodeRule((_SIMING,), ("fact", "projection", "proposal"), (_INTERNAL, _AUTHORITY, _BRANCH))
        if node_type in {"authored_story_blueprint", "runtime_story_node", "story_authority_outcome"}:
            return _NodeRule((_SIMING,), ("fact", "projection", "proposal"), (_INTERNAL, _AUTHORITY, _BRANCH, _PUBLIC))
        try:
            return self.rules[node_type]
        except KeyError as exc:
            raise ValueError(f"node type is unregistered: {node_type}") from exc

    def validate(
        self,
        *,
        node_type: str,
        namespace: str,
        record_kind: str,
        visibility_scope: str,
        owner_actor_id: str | None = None,
    ) -> _NodeRule:
        rule = self.require(node_type)
        if namespace not in rule.allowed_namespaces:
            raise ValueError(f"node type namespace is not allowed: {node_type}:{namespace}")
        if record_kind not in rule.allowed_record_kinds:
            raise ValueError(f"node type record_kind is not allowed: {node_type}:{record_kind}")
        if visibility_scope not in rule.allowed_visibility_scopes:
            raise ValueError(f"node type visibility scope is not allowed: {node_type}:{visibility_scope}")
        if namespace == _ACTOR and not owner_actor_id:
            raise ValueError("actor_private namespace requires owner_actor_id")
        if namespace != _ACTOR and owner_actor_id is not None:
            raise ValueError("owner_actor_id is only valid for actor_private namespace")
        return rule

    def validate_node(self, node: HeavenlyGraphNode, *, allow_legacy: bool = False) -> HeavenlyGraphNode:
        if allow_legacy and node.semantic_metadata.policy_revision == "policy:legacy":
            legacy_rule = self._legacy_rule(node.node_type)
            if legacy_rule is not None:
                self._validate_legacy_node(node, legacy_rule)
                return node
        try:
            self.validate(
                node_type=node.node_type,
                namespace=node.scope.graph_namespace,
                record_kind=node.semantic_metadata.record_kind,
                visibility_scope=node.semantic_metadata.visibility_scope,
                owner_actor_id=node.scope.owner_actor_id,
            )
        except ValueError:
            if not allow_legacy or node.semantic_metadata.policy_revision != "policy:legacy":
                raise
            legacy_rule = self._legacy_rule(node.node_type)
            if legacy_rule is None:
                raise
            self._validate_legacy_node(node, legacy_rule)
        self._validate_provenance(node, allow_legacy=allow_legacy)
        return node

    @staticmethod
    def _validate_provenance(
        node: HeavenlyGraphNode, *, allow_legacy: bool
    ) -> None:
        if allow_legacy and node.semantic_metadata.policy_revision == "policy:legacy":
            return
        metadata = node.semantic_metadata
        if node.provenance is None:
            return
        source_kind = node.provenance.source_kind
        if (
            node.node_type == "world_fact"
            and metadata.record_kind == "fact"
            and metadata.derivation_kind == "authority"
            and source_kind not in {"authority_event", "world_result", "esm_result"}
        ):
            raise ValueError(
                "world_fact authority requires canonical owner provenance"
            )
        if metadata.derivation_kind == "authority" and source_kind == "siming_projection":
            raise ValueError("authority records require canonical owner provenance")
        if (
            metadata.derivation_kind == "authority"
            and source_kind == "character_memory"
            and node.scope.graph_namespace != _ACTOR
        ):
            raise ValueError("character memory authority is limited to its canonical owner namespace")

    @classmethod
    def _legacy_rule(cls, node_type: str) -> _NodeRule | None:
        if node_type == "world_fact":
            return _NodeRule((_SIMING, _ACTOR), ("fact",), (_PUBLIC,))
        if node_type in cls._LEGACY_EXACT_RULES:
            return cls._LEGACY_EXACT_RULES[node_type]
        if node_type.startswith(("memory:", "projection:")):
            return _NodeRule((_SIMING,), ("fact",), (_PUBLIC,))
        if node_type.startswith(("actor_memory:", "actor_memory_anchor:")):
            return _NodeRule((_ACTOR,), ("fact",), (_PUBLIC,))
        return None

    @staticmethod
    def _validate_legacy_node(node: HeavenlyGraphNode, rule: _NodeRule) -> None:
        if node.scope.graph_namespace not in rule.allowed_namespaces:
            raise ValueError(f"legacy node namespace is not allowed: {node.node_type}:{node.scope.graph_namespace}")
        if node.semantic_metadata.record_kind not in rule.allowed_record_kinds:
            raise ValueError(f"legacy node record_kind is not allowed: {node.node_type}:{node.semantic_metadata.record_kind}")
        if node.semantic_metadata.visibility_scope not in rule.allowed_visibility_scopes:
            raise ValueError(f"legacy node visibility scope is not allowed: {node.node_type}:{node.semantic_metadata.visibility_scope}")
        if node.scope.graph_namespace == _ACTOR and not node.scope.owner_actor_id:
            raise ValueError("actor_private namespace requires owner_actor_id")


class HeavenlyRelationTypeRegistry:
    """Deterministic registry for relation vocabulary and namespace boundaries."""

    CROSS_NAMESPACE_DECLARED = frozenset(
        {
            "observed_as",
            "believed_as",
            "knows_about",
            "derived_from",
            "part_of_turn",
            "requires_capability",
        }
    )

    _SAME_SIMING = ((_SIMING, _SIMING),)
    _SAME_ANY = ((_SIMING, _SIMING), (_ACTOR, _ACTOR), (_RESOURCE, _RESOURCE))
    _CROSS_ACTOR_SIMING = ((_ACTOR, _SIMING), (_SIMING, _ACTOR), (_SIMING, _SIMING))
    _CROSS_SIMING_RESOURCE = ((_SIMING, _RESOURCE), (_RESOURCE, _SIMING), (_SIMING, _SIMING))
    DEFAULT_RULES: dict[str, _RelationRule] = {
        "caused_by": _RelationRule(_SAME_SIMING, ("fact", "projection"), (_PUBLIC, _INTERNAL, _AUTHORITY, _BRANCH)),
        "enabled_by": _RelationRule(_SAME_SIMING, ("fact", "projection"), (_PUBLIC, _INTERNAL, _AUTHORITY, _BRANCH)),
        "prevented_by": _RelationRule(_SAME_SIMING, ("fact", "projection"), (_PUBLIC, _INTERNAL, _AUTHORITY, _BRANCH)),
        "observed_as": _RelationRule(_CROSS_ACTOR_SIMING, ("fact", "projection"), (_PRIVATE, _INTERNAL, _AUTHORITY)),
        "believed_as": _RelationRule(_CROSS_ACTOR_SIMING, ("projection", "proposal"), (_PRIVATE, _INTERNAL)),
        "knows_about": _RelationRule(_CROSS_ACTOR_SIMING, ("projection",), (_PRIVATE, _INTERNAL)),
        "contradicts": _RelationRule(_SAME_ANY, ("fact", "projection", "proposal"), (_PUBLIC, _PRIVATE, _INTERNAL, _AUTHORITY, _BRANCH)),
        "supersedes": _RelationRule(_SAME_ANY, ("fact", "projection"), (_PUBLIC, _PRIVATE, _INTERNAL, _AUTHORITY, _BRANCH)),
        "retracts": _RelationRule(_SAME_ANY, ("fact", "projection"), (_PUBLIC, _PRIVATE, _INTERNAL, _AUTHORITY, _BRANCH)),
        "derived_from": _RelationRule(_SAME_ANY + _CROSS_ACTOR_SIMING + _CROSS_SIMING_RESOURCE, ("projection", "proposal"), (_PRIVATE, _INTERNAL, _AUTHORITY, _BRANCH)),
        "part_of_turn": _RelationRule(_CROSS_ACTOR_SIMING, ("projection", "proposal"), (_PRIVATE, _INTERNAL, _BRANCH)),
        "opens_obligation": _RelationRule(_SAME_SIMING, ("fact", "projection", "proposal"), (_INTERNAL, _BRANCH)),
        "transforms_obligation": _RelationRule(_SAME_SIMING, ("fact", "projection", "proposal"), (_INTERNAL, _BRANCH)),
        "targets_attractor": _RelationRule(_SAME_SIMING, ("projection", "proposal"), (_INTERNAL, _BRANCH)),
        "requires_capability": _RelationRule(_CROSS_SIMING_RESOURCE, ("fact", "projection", "proposal"), (_PUBLIC, _INTERNAL, _AUTHORITY, _BRANCH)),
        "realized_by": _RelationRule(_SAME_SIMING, ("fact", "projection"), (_INTERNAL, _AUTHORITY, _BRANCH)),
        "closes_branch_node": _RelationRule(_SAME_SIMING, ("fact", "projection"), (_AUTHORITY, _BRANCH)),
        "forked_from": _RelationRule(_SAME_SIMING, ("fact", "projection"), (_AUTHORITY, _BRANCH)),
    }

    _LEGACY_RULE = _RelationRule(
        ((_SIMING, _SIMING), (_ACTOR, _ACTOR)),
        ("fact",),
        (_PUBLIC,),
    )

    def __init__(self, rules: dict[str, _RelationRule] | None = None) -> None:
        self.rules = dict(rules or self.DEFAULT_RULES)

    @property
    def relation_types(self) -> tuple[str, ...]:
        return tuple(sorted(self.rules))

    def require(self, relation_type: str) -> _RelationRule:
        if relation_type.startswith("actor_memory:references_"):
            return _RelationRule(((_ACTOR, _ACTOR),), ("fact", "projection"), (_PRIVATE,))
        try:
            return self.rules[relation_type]
        except KeyError as exc:
            raise ValueError(f"relation type is unregistered: {relation_type}") from exc

    def validate(
        self,
        *,
        relation_type: str,
        source_namespace: str,
        target_namespace: str,
        record_kind: str,
        visibility_scope: str,
        source_owner_actor_id: str | None = None,
        target_owner_actor_id: str | None = None,
    ) -> _RelationRule:
        rule = self.require(relation_type)
        if (source_namespace, target_namespace) not in rule.allowed_namespace_pairs:
            raise ValueError(f"relation namespace pair is not allowed: {relation_type}")
        if record_kind not in rule.allowed_record_kinds:
            raise ValueError(f"relation record_kind is not allowed: {relation_type}:{record_kind}")
        if visibility_scope not in rule.allowed_visibility_scopes:
            raise ValueError(f"relation visibility scope is not allowed: {relation_type}:{visibility_scope}")
        if source_namespace == _ACTOR and not source_owner_actor_id:
            raise ValueError("actor_private source requires owner_actor_id")
        if target_namespace == _ACTOR and not target_owner_actor_id:
            raise ValueError("actor_private target requires owner_actor_id")
        if source_namespace != _ACTOR and source_owner_actor_id is not None:
            raise ValueError("source owner_actor_id is only valid for actor_private")
        if target_namespace != _ACTOR and target_owner_actor_id is not None:
            raise ValueError("target owner_actor_id is only valid for actor_private")
        return rule

    def validate_relation(self, relation: HeavenlyGraphRelation, *, source_scope: Any | None = None, target_scope: Any | None = None, allow_legacy: bool = False) -> HeavenlyGraphRelation:
        source = source_scope or relation.scope
        target = target_scope or relation.scope
        try:
            self.validate(
                relation_type=relation.relation_type,
                source_namespace=source.graph_namespace,
                target_namespace=target.graph_namespace,
                record_kind=relation.semantic_metadata.record_kind,
                visibility_scope=relation.semantic_metadata.visibility_scope,
                source_owner_actor_id=source.owner_actor_id,
                target_owner_actor_id=target.owner_actor_id,
            )
        except ValueError:
            if not allow_legacy or relation.semantic_metadata.policy_revision != "policy:legacy":
                raise
            legacy_rule = self._legacy_rule(relation.relation_type)
            if legacy_rule is None:
                raise
            self._validate_legacy_relation(relation, source, target, legacy_rule)
        self._validate_provenance(relation, allow_legacy=allow_legacy)
        return relation

    @staticmethod
    def _validate_provenance(
        relation: HeavenlyGraphRelation, *, allow_legacy: bool
    ) -> None:
        if allow_legacy and relation.semantic_metadata.policy_revision == "policy:legacy":
            return
        metadata = relation.semantic_metadata
        if relation.provenance is None:
            return
        source_kind = relation.provenance.source_kind
        if metadata.derivation_kind == "authority" and source_kind == "siming_projection":
            raise ValueError("authority records require canonical owner provenance")
        if (
            metadata.derivation_kind == "authority"
            and source_kind == "character_memory"
            and relation.scope.graph_namespace != _ACTOR
        ):
            raise ValueError("character memory authority is limited to its canonical owner namespace")

    @classmethod
    def _legacy_rule(cls, relation_type: str) -> _RelationRule | None:
        if relation_type.upper() in {"CAUSED_BY", "ENABLED_BY", "PREVENTED_BY"}:
            return cls._LEGACY_RULE
        if relation_type.startswith("actor_memory:references_"):
            return _RelationRule(((_ACTOR, _ACTOR),), ("fact", "projection"), (_PRIVATE,))
        return None

    @staticmethod
    def _validate_legacy_relation(relation: HeavenlyGraphRelation, source: Any, target: Any, rule: _RelationRule) -> None:
        pair = (source.graph_namespace, target.graph_namespace)
        if pair not in rule.allowed_namespace_pairs:
            raise ValueError(f"legacy relation namespace pair is not allowed: {relation.relation_type}")
        if relation.semantic_metadata.record_kind not in rule.allowed_record_kinds:
            raise ValueError(f"legacy relation record_kind is not allowed: {relation.relation_type}")
        if relation.semantic_metadata.visibility_scope not in rule.allowed_visibility_scopes:
            raise ValueError(f"legacy relation visibility scope is not allowed: {relation.relation_type}")
        if source.graph_namespace == _ACTOR and not source.owner_actor_id:
            raise ValueError("actor_private source requires owner_actor_id")
        if target.graph_namespace == _ACTOR and not target.owner_actor_id:
            raise ValueError("actor_private target requires owner_actor_id")


DEFAULT_NODE_TYPE_REGISTRY = HeavenlyNodeTypeRegistry()
DEFAULT_RELATION_TYPE_REGISTRY = HeavenlyRelationTypeRegistry()


def validate_correction_request(
    request: GraphCorrectionRequest,
    target: HeavenlyGraphNode | HeavenlyGraphRelation,
) -> None:
    """Validate the semantic invariants shared by both correction adapters."""
    if not request.source_refs:
        raise ValueError("correction requires source linkage")
    if request.scope != target.scope:
        raise ValueError("correction scope must match target scope")
    metadata = request.semantic_metadata
    target_metadata = target.semantic_metadata
    if metadata.policy_revision != target_metadata.policy_revision:
        raise ValueError("correction policy revision must match target")
    if metadata.visibility_scope != target_metadata.visibility_scope:
        raise ValueError("correction visibility scope must match target")
    if metadata.record_kind != target_metadata.record_kind:
        raise ValueError("correction record kind must match target")
    if metadata.scope_digest != target_metadata.scope_digest:
        raise ValueError("correction scope digest must match target")
    target_vector = target_metadata.source_revision_vector
    request_vector = metadata.source_revision_vector
    if request_vector != target_vector:
        raise ValueError("correction source revision vector must match target")
    if metadata.source_event_refs != target_metadata.source_event_refs:
        raise ValueError("correction source linkage must match target")
    target_source_refs = {
        target.provenance.source_ref,
        *target.provenance.source_ref_lineage,
        *target.provenance.evidence_refs,
    }
    if not target_source_refs.intersection(target_metadata.source_event_refs):
        raise ValueError("correction source linkage is absent from target")


__all__ = [
    "DEFAULT_NODE_TYPE_REGISTRY",
    "DEFAULT_RELATION_TYPE_REGISTRY",
    "HeavenlyNodeTypeRegistry",
    "HeavenlyRelationTypeRegistry",
    "validate_correction_request",
]
