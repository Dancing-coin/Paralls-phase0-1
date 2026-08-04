import hashlib
import json

from pydantic import TypeAdapter

from app.models.siming_heavenly_memory import (
    SimingCompiledContext,
    SimingContextRequest,
    SimingHeavenlyMemoryEntry,
)
from app.services.siming_heavenly_graph_port import HeavenlyGraphPort


class SimingContextCompiler:
    def __init__(self, graph: HeavenlyGraphPort) -> None:
        self._graph = graph
        self._entry_adapter = TypeAdapter(SimingHeavenlyMemoryEntry)

    def compile(self, request: SimingContextRequest) -> SimingCompiledContext:
        seed_node_ids = sorted(set(request.seed_node_ids))
        subgraph = self._graph.query_subgraph(
            scope=request.scope,
            seed_node_ids=seed_node_ids,
            relation_types=request.relation_types,
            direction="both",
            max_depth=4,
            valid_at=request.valid_at,
            recorded_at=request.recorded_at,
            node_limit=request.node_limit,
            relation_limit=request.relation_limit,
        )
        entries = []
        for node in sorted(subgraph.nodes, key=lambda node: node.node_id):
            if not node.node_type.startswith("memory:"):
                continue
            entry = self._entry_adapter.validate_python(node.attributes)
            if node.node_id != entry.entry_id or node.node_type != f"memory:{entry.domain}":
                raise ValueError("memory node identity must match its entry data")
            entries.append(entry)
        buckets = {
            "world_fact": [], "causal_timeline": [], "actor_cognition": [],
            "storyline_obligation": [], "intervention_outcome": [], "convergence_strategy": [],
        }
        for entry in entries:
            buckets[entry.domain].append(entry)
        for bucket in buckets.values():
            bucket.sort(key=lambda entry: entry.entry_id)
        node_refs = sorted(node.node_id for node in subgraph.nodes)
        relation_refs = sorted(relation.relation_id for relation in subgraph.relations)
        payload = {
            "request": request.model_dump(mode="json"),
            "entries": [entry.model_dump(mode="json") for entry in entries],
            "node_refs": node_refs,
            "relation_refs": relation_refs,
            "truncated": subgraph.truncated,
        }
        context_hash = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return SimingCompiledContext(
            request=request,
            world_facts=buckets["world_fact"],
            causal_timeline=buckets["causal_timeline"],
            actor_cognition=buckets["actor_cognition"],
            storyline_obligations=buckets["storyline_obligation"],
            intervention_outcomes=buckets["intervention_outcome"],
            convergence_strategies=buckets["convergence_strategy"],
            selected_node_refs=node_refs,
            selected_relation_refs=relation_refs,
            truncated=subgraph.truncated,
            context_hash=context_hash,
        )
