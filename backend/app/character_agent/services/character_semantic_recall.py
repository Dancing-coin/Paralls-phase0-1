from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

from app.character_agent.gateway.memory_recall import CharacterMemoryRecallPolicy
from app.character_agent.models.turn_context import CharacterTurnContext
from app.models.siming_heavenly_graph import (
    BehaviorTurnQuery,
    CausalPathQuery,
    ConflictSetQuery,
    GraphReaderContext,
    HeavenlyGraphQueryResult,
    PerspectiveQuery,
    SourceImpactQuery,
)


@dataclass(frozen=True)
class SemanticRecallCard:
    """A bounded, read-only evidence card exposed to cognition."""

    ref: str
    payload: Mapping[str, object]
    evidence_status: str = "selected"
    source_refs: tuple[str, ...] = ()
    relation_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class SemanticRecallResult:
    cards: tuple[SemanticRecallCard, ...] = ()
    selected_refs: tuple[str, ...] = ()
    omitted_refs: tuple[str, ...] = ()
    relation_refs: tuple[str, ...] = ()
    causal_refs: tuple[str, ...] = ()
    conflict_refs: tuple[str, ...] = ()
    perspective_refs: tuple[str, ...] = ()
    revision_vector: Mapping[str, int] = field(default_factory=dict)
    context_hash: str = ""
    truncated: bool = False
    incomplete_reason: str | None = None
    cards_by_ref: Mapping[str, SemanticRecallCard] = field(default_factory=dict)
    # Compatibility surface for callers that still need the selected pool view.
    memory: Mapping[str, list[dict[str, object]]] = field(default_factory=dict)
    metadata: Mapping[str, object] = field(default_factory=dict)


class CharacterSemanticRecallService:
    """Facade joining bounded private memory recall to bounded graph reads.

    This object deliberately has no graph write capability. Graph access is
    restricted to ``query_semantic`` and every query is pinned to the canonical
    turn identity, branch, valid-time and revision vector.
    """

    def __init__(
        self,
        memory_recall_policy: CharacterMemoryRecallPolicy | None = None,
        *,
        graph: Any | None = None,
        scope_resolver: Callable[[str], Any] | None = None,
        memory_reader: Callable[[str], Mapping[str, object]] | None = None,
        max_graph_results: int = 100,
    ) -> None:
        self._policy = memory_recall_policy or CharacterMemoryRecallPolicy()
        self._graph = graph
        self._scope_resolver = scope_resolver
        self._memory_reader = memory_reader
        self._max_graph_results = max(1, min(1000, max_graph_results))

    def select(
        self,
        actor_id: str,
        context: Mapping[str, object],
        *,
        turn_context: CharacterTurnContext,
    ) -> SemanticRecallResult:
        if not actor_id or actor_id != turn_context.actor_id:
            raise ValueError("semantic recall actor does not match canonical turn context")
        if not isinstance(turn_context, CharacterTurnContext):
            raise TypeError("turn_context must be CharacterTurnContext")
        source_context = dict(context)
        memory = source_context.get("memory", source_context.get("memory_bundle"))
        if not isinstance(memory, Mapping) and self._memory_reader is not None:
            memory = self._memory_reader(actor_id)
        normalized_memory = {
            str(key): deepcopy(value) if isinstance(value, list) else []
            for key, value in (memory.items() if isinstance(memory, Mapping) else [])
        }
        policy_result = self._policy.select(normalized_memory, context=source_context)
        selected_refs = tuple(str(ref) for ref in policy_result.metadata.get("selected_memory_refs", []))
        omitted_refs = self._omitted_refs(normalized_memory, selected_refs)
        cards = {
            ref: SemanticRecallCard(ref=ref, payload=deepcopy(entry))
            for ref, entry in self._selected_entries(policy_result.memory)
        }
        relation_refs: set[str] = set()
        causal_refs: set[str] = set()
        conflict_refs: set[str] = set()
        perspective_refs: set[str] = set()
        revision_vector: dict[str, int] = self._revision_mapping(turn_context.memory_revision_vector)
        incomplete_reason = "token_budget_exhausted" if policy_result.metadata.get("truncated") else None
        graph_truncated = False

        reader = self._reader_context(turn_context)
        if self._graph is not None and reader is not None:
            queries = self._queries(actor_id, turn_context, source_context, selected_refs, cards, reader)
            for kind, query in queries:
                result = self._safe_query(query)
                if result is None:
                    continue
                graph_truncated = graph_truncated or bool(getattr(result, "truncated", False))
                if getattr(result, "incomplete_reason", None):
                    incomplete_reason = str(result.incomplete_reason)
                revision_vector.update(self._revision_mapping(getattr(result, "revision_vector", None)))
                relation_refs.update(str(ref) for ref in getattr(result, "selected_relation_refs", []) if ref)
                refs = self._result_refs(result, actor_id)
                if kind == "causal":
                    causal_refs.update(refs)
                elif kind == "conflict":
                    conflict_refs.update(refs)
                elif kind == "perspective":
                    perspective_refs.update(refs)
                self._apply_result_cards(kind, result, cards, conflict_refs)

        ordered_cards = tuple(cards[ref] for ref in sorted(cards))
        cards_by_ref = {card.ref: card for card in ordered_cards}
        metadata = dict(policy_result.metadata)
        metadata.update(
            {
                "semantic_selected_refs": list(selected_refs),
                "semantic_omitted_refs": list(omitted_refs),
                "relation_refs": sorted(relation_refs),
                "causal_refs": sorted(causal_refs),
                "conflict_refs": sorted(conflict_refs),
                "perspective_refs": sorted(perspective_refs),
                "revision_vector": dict(revision_vector),
                "incomplete_reason": incomplete_reason,
            }
        )
        return SemanticRecallResult(
            cards=ordered_cards,
            selected_refs=selected_refs,
            omitted_refs=tuple(omitted_refs),
            relation_refs=tuple(sorted(relation_refs)),
            causal_refs=tuple(sorted(causal_refs)),
            conflict_refs=tuple(sorted(conflict_refs)),
            perspective_refs=tuple(sorted(perspective_refs)),
            revision_vector=revision_vector,
            context_hash=str(policy_result.metadata.get("context_hash", "") or ""),
            truncated=bool(policy_result.metadata.get("truncated", False) or graph_truncated),
            incomplete_reason=incomplete_reason,
            cards_by_ref=cards_by_ref,
            memory=deepcopy(policy_result.memory),
            metadata=metadata,
        )

    def _reader_context(self, turn: CharacterTurnContext) -> GraphReaderContext | None:
        if self._scope_resolver is None or not turn.branch_id:
            return None
        scope = self._scope_resolver(turn.actor_id)
        if scope.owner_actor_id not in (None, turn.actor_id):
            raise ValueError("semantic recall scope owner does not match actor")
        if scope.story_branch_id != turn.branch_id:
            raise ValueError("semantic recall branch does not match turn context")
        return GraphReaderContext(
            reader_principal=turn.actor_id,
            allowed_visibility_scopes=("actor_private", "project", "world"),
            world_id=scope.world_id,
            session_id=scope.session_id,
            story_branch_id=turn.branch_id,
            valid_at=turn.valid_at,
            recorded_at=turn.producer_ts,
            policy_revision=turn.policy_revision,
        )

    def _queries(self, actor_id: str, turn: CharacterTurnContext, context: Mapping[str, object], selected_refs: tuple[str, ...], cards: Mapping[str, SemanticRecallCard], reader: GraphReaderContext) -> list[tuple[str, object]]:
        scope = self._scope_resolver(actor_id) if self._scope_resolver else None
        kwargs = {"context": reader, "scope": scope, "limit": self._max_graph_results}
        seed_nodes = [self._node_id(ref) for ref in selected_refs]
        queries: list[tuple[str, object]] = [
            ("behavior", BehaviorTurnQuery(**kwargs, turn_id=turn.turn_id, correlation_id=turn.correlation_id, actor_id=actor_id)),
            ("causal", CausalPathQuery(**kwargs, seed_node_ids=seed_nodes, max_depth=2, node_limit=self._max_graph_results, relation_limit=self._max_graph_results * 2, max_paths=20)),
        ]
        for ref, card in cards.items():
            payload = card.payload
            claim = payload.get("claim") if isinstance(payload, Mapping) else None
            if isinstance(claim, Mapping) and claim.get("subject_ref"):
                queries.append(("conflict", ConflictSetQuery(**kwargs, subject_ref=str(claim["subject_ref"]), property_key=str(claim.get("predicate") or "state"))))
            source_ref = payload.get("source_event_id") if isinstance(payload, Mapping) else None
            if source_ref:
                queries.append(("source", SourceImpactQuery(**kwargs, source_ref=str(source_ref))))
        targets = context.get("attention_targets") or []
        if isinstance(targets, str):
            targets = [targets]
        queries.append(("perspective", PerspectiveQuery(**kwargs, actor_ref=actor_id, visibility_scopes=["actor_private", "project", "world"])))
        return queries

    def _safe_query(self, query: object) -> HeavenlyGraphQueryResult | None:
        try:
            result = self._graph.query_semantic(query)
        except (AttributeError, TypeError, ValueError):
            return None
        return result if isinstance(result, HeavenlyGraphQueryResult) else result

    def _apply_result_cards(self, kind: str, result: object, cards: dict[str, SemanticRecallCard], conflict_refs: set[str]) -> None:
        for node in getattr(result, "nodes", []) or []:
            ref = self._node_ref(node)
            if not ref:
                continue
            metadata = getattr(node, "semantic_metadata", None)
            visibility = getattr(metadata, "visibility_scope", None)
            owner = getattr(getattr(node, "scope", None), "owner_actor_id", None)
            if visibility == "actor_private" and owner not in (None, next(iter(cards.values())).payload.get("actor_id") if cards else owner):
                continue
            if ref in cards:
                status = "disputed" if kind == "conflict" else cards[ref].evidence_status
                cards[ref] = SemanticRecallCard(ref=ref, payload=cards[ref].payload, evidence_status=status, source_refs=cards[ref].source_refs, relation_refs=cards[ref].relation_refs)
            elif kind in {"causal", "perspective"}:
                cards[ref] = SemanticRecallCard(ref=ref, payload=deepcopy(getattr(node, "attributes", {}) or {}), evidence_status="graph_context")
            if kind == "conflict":
                conflict_refs.add(ref)

    def _selected_entries(self, memory: Mapping[str, object]):
        prefixes = {"working_memory": "working", "event_memories": "event", "observation_memories": "observation", "knowledge_memories": "knowledge", "social_memories": "social", "higher_order_memories": "higher_order"}
        for pool, prefix in prefixes.items():
            entries = memory.get(pool, [])
            if not isinstance(entries, list):
                continue
            for entry in entries:
                if isinstance(entry, Mapping):
                    ident = str(entry.get("memory_id") or entry.get("event_id") or entry.get("source_event_id") or "")
                    if ident:
                        yield f"{prefix}:{ident}", entry

    def _omitted_refs(self, memory: Mapping[str, object], selected: tuple[str, ...]) -> list[str]:
        all_refs = [ref for ref, _ in self._selected_entries(memory)]
        return [ref for ref in all_refs if ref not in selected]

    def _node_id(self, ref: str) -> str:
        return ref.replace(":", ":", 1) if ref else ref

    def _node_ref(self, node: object) -> str:
        node_id = str(getattr(node, "node_id", "") or "")
        attrs = getattr(node, "attributes", {}) or {}
        if isinstance(attrs, Mapping):
            for key in ("ref", "memory_ref", "event_ref", "node_ref"):
                if attrs.get(key):
                    return str(attrs[key])
        return node_id.removeprefix("actor-memory:") or node_id

    def _result_refs(self, result: object, actor_id: str) -> set[str]:
        refs = {str(ref) for ref in getattr(result, "selected_node_refs", []) or [] if ref}
        for node in getattr(result, "nodes", []) or []:
            metadata = getattr(node, "semantic_metadata", None)
            scope = getattr(node, "scope", None)
            if getattr(metadata, "visibility_scope", None) == "actor_private" and getattr(scope, "owner_actor_id", None) not in (None, actor_id):
                continue
            ref = self._node_ref(node)
            if ref:
                refs.add(ref)
        return refs

    def _revision_mapping(self, value: object) -> dict[str, int]:
        if value is None:
            return {}
        if hasattr(value, "model_dump"):
            value = value.model_dump()
        return {str(key): int(item) for key, item in dict(value).items() if isinstance(item, int) and not isinstance(item, bool)} if isinstance(value, Mapping) else {}


__all__ = ["CharacterSemanticRecallService", "SemanticRecallCard", "SemanticRecallResult"]
