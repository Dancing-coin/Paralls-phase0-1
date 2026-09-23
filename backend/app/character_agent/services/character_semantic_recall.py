from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

from app.character_agent.gateway.memory_recall import CharacterMemoryRecallPolicy, MissingRequiredMemoryEvidence
from app.character_agent.models.turn_context import CharacterTurnContext
from app.models.siming_heavenly_graph import (
    BehaviorTurnQuery, CausalPathQuery, ConflictSetQuery, GraphReaderContext,
    PerspectiveQuery, SourceImpactQuery,
)


@dataclass(frozen=True)
class SemanticRecallCard:
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
    memory: Mapping[str, list[dict[str, object]]] = field(default_factory=dict)
    metadata: Mapping[str, object] = field(default_factory=dict)


class CharacterSemanticRecallService:
    """Bounded, actor-private semantic recall. This facade never writes graph state."""

    def __init__(self, memory_recall_policy: CharacterMemoryRecallPolicy | None = None, *, graph: Any | None = None,
                 scope_resolver: Callable[[str], Any] | None = None,
                 memory_reader: Callable[[str], Mapping[str, object]] | None = None,
                 max_graph_results: int = 100, card_budget: int = 128, token_budget: int = 2400) -> None:
        self._policy = memory_recall_policy or CharacterMemoryRecallPolicy()
        self._graph, self._scope_resolver, self._memory_reader = graph, scope_resolver, memory_reader
        self._max_graph_results = max(1, min(1000, max_graph_results))
        self._card_budget, self._token_budget = max(1, card_budget), max(1, token_budget)

    def select(self, actor_id: str, context: Mapping[str, object], *, turn_context: CharacterTurnContext) -> SemanticRecallResult:
        if not isinstance(turn_context, CharacterTurnContext) or actor_id != turn_context.actor_id:
            raise ValueError("semantic recall actor does not match canonical turn context")
        context = dict(context)
        raw_memory = context.get("memory", context.get("memory_bundle"))
        if not isinstance(raw_memory, Mapping) and self._memory_reader is not None:
            raw_memory = self._memory_reader(actor_id)
        memory = self._validate_memory(raw_memory, actor_id)
        policy = self._policy.select(memory, context=context)
        missing = list(policy.metadata.get("missing_required_refs", []))
        if missing:
            raise MissingRequiredMemoryEvidence(missing)
        selected = tuple(str(x) for x in policy.metadata.get("selected_memory_refs", []))
        omitted = tuple(self._all_refs(memory) - set(selected))
        cards: dict[str, SemanticRecallCard] = {
            ref: SemanticRecallCard(ref=ref, payload=deepcopy(payload), source_refs=self._source_refs(payload))
            for ref, payload in self._selected_entries(policy.memory)
        }
        reader = self._reader_context(turn_context)
        relations: set[str] = set(); causal: set[str] = set(); conflicts: set[str] = set(); perspectives: set[str] = set()
        revisions = self._revision_map(turn_context.memory_revision_vector)
        incomplete = "token_budget_exhausted" if policy.metadata.get("truncated") else None
        graph_truncated = False
        if self._graph is not None and reader is not None:
            query_count = result_count = 0
            for kind, query in self._queries(actor_id, turn_context, cards, reader):
                if query_count >= 16 or result_count >= self._max_graph_results * 8:
                    incomplete = "graph_budget_exhausted"
                    break
                query_count += 1
                try:
                    result = self._graph.query_semantic(query)
                except Exception:
                    incomplete = incomplete or "graph_unavailable"
                    continue
                valid, reason = self._validated_result(result, actor_id, turn_context, reader)
                if not valid:
                    incomplete = incomplete or reason or "stale_read_set"
                    continue
                graph_truncated |= bool(getattr(result, "truncated", False))
                result_count += len(getattr(result, "nodes", []) or []) + len(getattr(result, "relations", []) or [])
                refs, rels = self._result_refs(result, actor_id)
                relations.update(rels)
                revisions.update(self._revision_map(getattr(result, "revision_vector", None)))
                if kind == "causal": causal.update(refs)
                elif kind == "conflict": conflicts.update(refs)
                elif kind == "perspective": perspectives.update(refs)
                self._merge_cards(kind, result, cards, actor_id)
        profiles = [context.get("profile"), context.get("effective_profile")]
        required_cards = {ref for ref in selected if ref.startswith("knowledge:") and any(isinstance(p, Mapping) and isinstance(p.get("capability_constraint_layer"), Mapping) and p["capability_constraint_layer"].get("memory_retention") == "strong" for p in profiles)}
        cards, card_truncated, missing_cards = self._bound_cards(cards, required_cards)
        if missing_cards:
            raise MissingRequiredMemoryEvidence(missing_cards)
        truncated = bool(policy.metadata.get("truncated") or graph_truncated or card_truncated)
        if card_truncated and not incomplete: incomplete = "token_budget_exhausted"
        digest_payload = {"context": context, "turn": turn_context.model_dump(), "scope": reader.model_dump() if reader else None, "revision": revisions,
                          "cards": [(ref, card.evidence_status, card.source_refs, card.relation_refs) for ref, card in sorted(cards.items())],
                          "relations": sorted(relations), "causal": sorted(causal), "conflicts": sorted(conflicts), "perspectives": sorted(perspectives)}
        context_hash = hashlib.sha256(json.dumps(digest_payload, sort_keys=True, default=str, separators=(",", ":")).encode()).hexdigest()
        metadata = dict(policy.metadata)
        metadata.update({"semantic_selected_refs": list(selected), "semantic_omitted_refs": list(omitted), "relation_refs": sorted(relations),
                         "causal_refs": sorted(causal), "conflict_refs": sorted(conflicts), "perspective_refs": sorted(perspectives),
                         "revision_vector": revisions, "incomplete_reason": incomplete, "cards": [c.ref for c in cards.values()]})
        ordered = tuple(cards[ref] for ref in sorted(cards))
        return SemanticRecallResult(cards=ordered, selected_refs=selected, omitted_refs=omitted,
            relation_refs=tuple(sorted(relations)), causal_refs=tuple(sorted(causal)), conflict_refs=tuple(sorted(conflicts)),
            perspective_refs=tuple(sorted(perspectives)), revision_vector=revisions, context_hash=context_hash,
            truncated=truncated, incomplete_reason=incomplete, cards_by_ref={c.ref: c for c in ordered},
            memory=deepcopy(policy.memory), metadata=metadata)

    def _validate_memory(self, raw: object, actor_id: str) -> dict[str, list[dict[str, object]]]:
        if not isinstance(raw, Mapping): return {}
        out: dict[str, list[dict[str, object]]] = {}
        for key, value in raw.items():
            if not isinstance(value, list): continue
            entries = []
            for item in value:
                if not isinstance(item, Mapping): continue
                owner = item.get("actor_id")
                if key != "working_memory" and not owner: raise ValueError("semantic recall memory actor scope is required")
                if owner and str(owner) != actor_id: raise ValueError("semantic recall memory actor scope mismatch")
                entries.append(dict(item))
            out[str(key)] = entries
        return out

    def _reader_context(self, turn: CharacterTurnContext) -> GraphReaderContext | None:
        if not self._scope_resolver or not turn.branch_id: return None
        scope = self._scope_resolver(turn.actor_id)
        if scope is None:
            return None
        if scope.owner_actor_id not in (None, turn.actor_id) or scope.story_branch_id != turn.branch_id:
            raise ValueError("semantic recall scope does not match canonical turn")
        return GraphReaderContext(reader_principal=turn.actor_id, allowed_visibility_scopes=("actor_private", "public", "branch_only"),
            world_id=scope.world_id, session_id=scope.session_id, story_branch_id=turn.branch_id,
            valid_at=turn.valid_at, recorded_at=turn.producer_ts, policy_revision=turn.policy_revision)

    def _queries(self, actor: str, turn: CharacterTurnContext, cards: Mapping[str, SemanticRecallCard], reader: GraphReaderContext):
        scope = self._scope_resolver(actor) if self._scope_resolver else None; kw = {"context": reader, "scope": scope, "limit": self._max_graph_results}
        seeds = [self._node_id(ref) for ref in cards]
        yield "behavior", BehaviorTurnQuery(**kw, turn_id=turn.turn_id, correlation_id=turn.correlation_id, actor_id=actor)
        yield "causal", CausalPathQuery(**kw, seed_node_ids=seeds, max_depth=2, node_limit=self._max_graph_results, relation_limit=self._max_graph_results * 2, max_paths=20)
        yield "perspective", PerspectiveQuery(**kw, actor_ref=actor, visibility_scopes=["actor_private", "public", "branch_only"])
        for card in cards.values():
            claim = card.payload.get("claim") if isinstance(card.payload, Mapping) else None
            if isinstance(claim, Mapping) and claim.get("subject_ref"):
                yield "conflict", ConflictSetQuery(**kw, subject_ref=str(claim["subject_ref"]), property_key=str(claim.get("predicate") or "state"))
            source = (card.payload.get("source_event_id") or card.payload.get("source_ref")) if isinstance(card.payload, Mapping) else None
            if source: yield "source", SourceImpactQuery(**kw, source_ref=str(source))

    def _validated_result(self, result: object, actor: str, turn: CharacterTurnContext, reader: GraphReaderContext):
        if getattr(result, "policy_revision", reader.policy_revision) != reader.policy_revision: return False, "stale_read_set"
        rv = self._revision_map(getattr(result, "revision_vector", None)); pins = self._revision_map(turn.memory_revision_vector)
        if any(k not in pins or pins[k] < v for k, v in rv.items()): return False, "stale_read_set"
        for node in getattr(result, "nodes", []) or []:
            scope = getattr(node, "scope", None); validity = getattr(node, "validity", None); metadata = getattr(node, "semantic_metadata", None)
            if scope and (scope.world_id != reader.world_id or scope.session_id != reader.session_id or scope.story_branch_id != reader.story_branch_id): return False, "stale_read_set"
            if scope and getattr(metadata, "visibility_scope", None) == "actor_private" and scope.owner_actor_id != actor: return False, "visibility_denied"
            if metadata and (getattr(metadata, "policy_revision", reader.policy_revision) != reader.policy_revision or getattr(metadata, "scope_digest", "scope:actor-private") != "scope:actor-private"): return False, "stale_read_set"
            if validity and not validity.contains(turn.valid_at): return False, "stale_read_set"
            if getattr(node, "recorded_at", turn.producer_ts) > turn.producer_ts: return False, "stale_read_set"
        for relation in getattr(result, "relations", []) or []:
            scope = getattr(relation, "scope", None); validity = getattr(relation, "validity", None); metadata = getattr(relation, "semantic_metadata", None)
            if scope and (scope.world_id != reader.world_id or scope.session_id != reader.session_id or scope.story_branch_id != reader.story_branch_id): return False, "stale_read_set"
            if scope and getattr(metadata, "visibility_scope", None) == "actor_private" and scope.owner_actor_id != actor: return False, "visibility_denied"
            if metadata and getattr(metadata, "policy_revision", reader.policy_revision) != reader.policy_revision: return False, "stale_read_set"
            if validity and not validity.contains(turn.valid_at): return False, "stale_read_set"
            if getattr(relation, "recorded_at", turn.producer_ts) > turn.producer_ts: return False, "stale_read_set"
        node_refs = {self._canonical_ref(self._node_ref(node)) for node in getattr(result, "nodes", []) or []}
        if any(self._canonical_ref(str(ref)) not in node_refs for ref in getattr(result, "selected_node_refs", []) or []): return False, "visibility_denied"
        return True, None

    def _merge_cards(self, kind: str, result: object, cards: dict[str, SemanticRecallCard], actor: str):
        for node in getattr(result, "nodes", []) or []:
            scope = getattr(node, "scope", None); metadata = getattr(node, "semantic_metadata", None)
            if getattr(metadata, "visibility_scope", None) == "actor_private" and getattr(scope, "owner_actor_id", None) != actor: continue
            ref = self._canonical_ref(self._node_ref(node))
            if not ref: continue
            old = cards.get(ref); status = "disputed" if kind == "conflict" else (old.evidence_status if old else "graph_context")
            src = tuple(dict.fromkeys((old.source_refs if old else ()) + tuple(getattr(getattr(node, "provenance", None), "source_ref", "") for _ in [0] if getattr(getattr(node, "provenance", None), "source_ref", ""))))
            rels = tuple(str(getattr(x, "relation_id", "")) for x in getattr(result, "relations", []) or [] if self._canonical_ref(str(getattr(x, "source_node_id", ""))).endswith(ref) or self._canonical_ref(str(getattr(x, "target_node_id", ""))).endswith(ref))
            cards[ref] = SemanticRecallCard(ref=ref, payload=deepcopy(getattr(node, "attributes", {}) or (old.payload if old else {})), evidence_status=status, source_refs=src, relation_refs=tuple(dict.fromkeys((old.relation_refs if old else ()) + rels)))

    def _result_refs(self, result: object, actor: str):
        valid_relation_ids = {str(getattr(x, "relation_id", "")) for x in getattr(result, "relations", []) or []}
        refs, rels = set(), {str(x) for x in getattr(result, "selected_relation_refs", []) or [] if str(x) in valid_relation_ids}
        for node in getattr(result, "nodes", []) or []:
            scope = getattr(node, "scope", None); metadata = getattr(node, "semantic_metadata", None)
            if getattr(metadata, "visibility_scope", None) == "actor_private" and getattr(scope, "owner_actor_id", None) != actor: continue
            ref = self._canonical_ref(self._node_ref(node))
            if ref: refs.add(ref)
        return {x for x in refs if x}, rels

    def _bound_cards(self, cards: dict[str, SemanticRecallCard], required: set[str] | None = None):
        required = required or set()
        kept = {}; used = 0; truncated = False
        for ref in sorted(cards):
            cost = max(1, len(json.dumps(cards[ref].payload, default=str)) // 4)
            if len(kept) >= self._card_budget or used + cost > self._token_budget:
                if ref in required: return kept, True, sorted(required - set(kept) | {ref})
                truncated = True; continue
            kept[ref] = cards[ref]; used += cost
        return kept, truncated, []

    def _selected_entries(self, memory: Mapping[str, object]):
        prefixes = {"working_memory":"working", "event_memories":"event", "observation_memories":"observation", "knowledge_memories":"knowledge", "social_memories":"social", "higher_order_memories":"higher_order"}
        for pool, prefix in prefixes.items():
            for item in memory.get(pool, []) if isinstance(memory.get(pool, []), list) else []:
                if isinstance(item, Mapping):
                    ident = str(item.get("memory_id") or item.get("event_id") or item.get("source_event_id") or "")
                    if ident: yield f"{prefix}:{ident}", item

    def _all_refs(self, memory): return {ref for ref, _ in self._selected_entries(memory)}
    def _source_refs(self, payload): return tuple(str(x) for x in [payload.get("source_event_id"), payload.get("source_ref")] if x) if isinstance(payload, Mapping) else ()
    def _node_id(self, ref):
        parts = str(ref).split(":", 1); return f"actor-memory:{parts[0]}:{parts[1]}" if len(parts) == 2 else str(ref)
    def _node_ref(self, node):
        attrs = getattr(node, "attributes", {}) or {}; node_id = str(getattr(node, "node_id", "") or "")
        if isinstance(attrs, Mapping):
            for key in ("ref", "memory_ref", "event_ref", "node_ref"):
                if attrs.get(key): return str(attrs[key])
        return node_id.removeprefix("actor-memory:")
    def _canonical_ref(self, ref):
        ref = str(ref or "");
        if ref.startswith("actor-memory:"): ref = ref[len("actor-memory:"):]
        return ref
    def _revision_map(self, value):
        if hasattr(value, "model_dump"): value = value.model_dump()
        return {str(k): int(v) for k, v in value.items() if isinstance(v, int) and not isinstance(v, bool)} if isinstance(value, Mapping) else {}


__all__ = ["CharacterSemanticRecallService", "SemanticRecallCard", "SemanticRecallResult"]
