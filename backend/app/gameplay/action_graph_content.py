"""Immutable, package-local orchestration for registered action primitives.

The graph layer deliberately does not own execution or world truth.  It only
validates a finite composition of existing ``ActionPrimitiveDefinition``
records before an owner runtime is allowed to execute a window.
"""

from __future__ import annotations

from hashlib import sha256
import json
from typing import Iterable

from pydantic import ConfigDict, Field

from app.gameplay.models import StrictGameplayModel
from app.gameplay.shared_contracts import ActionPrimitiveDefinition


class ActionGraphNode(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    node_ref: str = Field(min_length=1)
    primitive_ref: str = Field(min_length=1)
    phase: str = Field(min_length=1)
    duration_window: tuple[int, int]
    cancel_targets: tuple[str, ...] = ()
    condition_refs: tuple[str, ...] = ()
    asset_ref: str = Field(min_length=1)
    contact_marker_refs: tuple[str, ...] = ()


class ActionGraphEdge(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    from_node: str = Field(min_length=1)
    to_node: str = Field(min_length=1)
    trigger: str = Field(min_length=1)
    priority: int = Field(ge=0)
    condition_refs: tuple[str, ...] = ()


class ActionGraphDefinition(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    graph_ref: str = Field(min_length=1)
    graph_revision: str = Field(min_length=1)
    action_family: str = Field(min_length=1)
    role_refs: tuple[str, ...] = ()
    primitive_refs: tuple[str, ...] = ()
    nodes: tuple[ActionGraphNode, ...] = Field(min_length=1)
    edges: tuple[ActionGraphEdge, ...] = ()
    capability_refs: tuple[str, ...] = ()
    observation_requirements: tuple[str, ...] = ()
    asset_refs: tuple[str, ...] = ()
    interruption_policy: str = Field(min_length=1)
    recovery_policy: str = Field(min_length=1)
    policy_revision: str = Field(min_length=1)


class ActionGraphAdmissionResult(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    accepted: bool
    graph_digest: str | None = None
    error_code: str | None = None

    @classmethod
    def admit(
        cls,
        graph: ActionGraphDefinition,
        *,
        primitive_catalog: Iterable[ActionPrimitiveDefinition],
    ) -> "ActionGraphAdmissionResult":
        primitives = {primitive.action_ref: primitive for primitive in primitive_catalog}
        node_refs = tuple(node.node_ref for node in graph.nodes)
        if len(set(node_refs)) != len(node_refs):
            return cls._reject("action_graph_node_duplicate")
        if len(set(graph.primitive_refs)) != len(graph.primitive_refs):
            return cls._reject("action_graph_primitive_duplicate")
        if len(set(graph.role_refs)) != len(graph.role_refs):
            return cls._reject("action_graph_role_duplicate")
        if len(set(graph.asset_refs)) != len(graph.asset_refs):
            return cls._reject("action_graph_asset_duplicate")
        if tuple(sorted(graph.primitive_refs)) != graph.primitive_refs:
            return cls._reject("action_graph_array_not_canonical")
        if tuple(sorted(graph.role_refs)) != graph.role_refs:
            return cls._reject("action_graph_array_not_canonical")

        for primitive_ref in graph.primitive_refs:
            if primitive_ref not in primitives:
                return cls._reject("action_graph_primitive_unknown")
        primitive_refs = set(graph.primitive_refs)
        for node in graph.nodes:
            if node.primitive_ref not in primitive_refs:
                return cls._reject("action_graph_primitive_unknown")
            if node.duration_window[0] < 0 or node.duration_window[1] <= node.duration_window[0]:
                return cls._reject("action_graph_duration_invalid")
            if len(set(node.cancel_targets)) != len(node.cancel_targets):
                return cls._reject("action_graph_cancel_target_duplicate")
            if any(target not in node_refs for target in node.cancel_targets):
                return cls._reject("action_graph_cancel_target_unknown")

        node_set = set(node_refs)
        adjacency: dict[str, list[str]] = {node_ref: [] for node_ref in node_refs}
        edge_keys: set[tuple[str, str, str]] = set()
        trigger_targets: dict[tuple[str, str], str] = {}
        for edge in graph.edges:
            if edge.from_node not in node_set or edge.to_node not in node_set:
                return cls._reject("action_graph_edge_node_unknown")
            key = (edge.from_node, edge.to_node, edge.trigger)
            if key in edge_keys:
                return cls._reject("action_graph_edge_duplicate")
            edge_keys.add(key)
            trigger_key = (edge.from_node, edge.trigger)
            previous_target = trigger_targets.get(trigger_key)
            if previous_target is not None and previous_target != edge.to_node:
                return cls._reject("action_graph_edge_conflict")
            trigger_targets[trigger_key] = edge.to_node
            adjacency[edge.from_node].append(edge.to_node)

        start_ref = node_refs[0]
        reachable = _reachable(start_ref, adjacency)
        if reachable != node_set:
            return cls._reject("action_graph_node_unreachable")
        if _has_cycle(node_refs, adjacency):
            return cls._reject("action_graph_cycle_invalid")

        terminal_nodes = {node.node_ref for node in graph.nodes if node.phase == "terminal"}
        recovery_nodes = {node.node_ref for node in graph.nodes if node.phase == "recovery"}
        if len(terminal_nodes) != 1:
            return cls._reject("action_graph_terminal_invalid")
        if not recovery_nodes or not _can_reach_any(recovery_nodes, terminal_nodes, adjacency):
            return cls._reject("action_graph_recovery_path_missing")

        digest_payload = graph.model_dump(mode="json")
        digest = "sha256:" + sha256(
            json.dumps(digest_payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return cls(accepted=True, graph_digest=digest)

    @classmethod
    def _reject(cls, error_code: str) -> "ActionGraphAdmissionResult":
        return cls(accepted=False, error_code=error_code)


def _reachable(start: str, adjacency: dict[str, list[str]]) -> set[str]:
    seen: set[str] = set()
    pending = [start]
    while pending:
        current = pending.pop()
        if current in seen:
            continue
        seen.add(current)
        pending.extend(adjacency.get(current, ()))
    return seen


def _has_cycle(nodes: tuple[str, ...], adjacency: dict[str, list[str]]) -> bool:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> bool:
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        if any(visit(child) for child in adjacency.get(node, ())):
            return True
        visiting.remove(node)
        visited.add(node)
        return False

    return any(visit(node) for node in nodes)


def _can_reach_any(starts: set[str], targets: set[str], adjacency: dict[str, list[str]]) -> bool:
    return any(targets.intersection(_reachable(start, adjacency)) for start in starts)


__all__ = [
    "ActionGraphAdmissionResult",
    "ActionGraphDefinition",
    "ActionGraphEdge",
    "ActionGraphNode",
]
