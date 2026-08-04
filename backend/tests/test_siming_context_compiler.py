import pytest

from app.models.siming_heavenly_graph import (
    GraphProvenance,
    GraphValidity,
    HeavenlyGraphNode,
    HeavenlyGraphScope,
    HeavenlySubgraphResult,
)
from app.models.siming_heavenly_memory import (
    ActorCognitionMemoryEntry,
    CausalTimelineMemoryEntry,
    ConvergenceStrategyMemoryEntry,
    InterventionOutcomeMemoryEntry,
    SimingContextRequest,
    StorylineObligationMemoryEntry,
    WorldFactMemoryEntry,
)
from app.services.in_memory_heavenly_graph import InMemoryHeavenlyGraphAdapter
from app.services.siming_context_compiler import SimingContextCompiler
from app.services.siming_heavenly_memory import SimingHeavenlyMemoryService


def test_compiler_rebuilds_identical_context_without_cache() -> None:
    graph = InMemoryHeavenlyGraphAdapter()
    scope = HeavenlyGraphScope(world_id="world:demo", session_id="session:demo", story_branch_id="branch:main")
    entry = WorldFactMemoryEntry(entry_id="fact:letter:removed", world_anchor_id="obj_letter", state_key="surface", state_value="removed", authority_result_ref="authority:destroy:1")
    SimingHeavenlyMemoryService(graph).write_entry(scope=scope, entry=entry, validity=GraphValidity(valid_from=10), recorded_at=10, revision=1, supersedes_revision=None, provenance=GraphProvenance(source_kind="authority_event", source_ref="authority:destroy:1", causation_id="authority:destroy:1", correlation_id="corr:destroy", producer_system="system_l6"), transaction_id="tx:destroy", idempotency_key="memory:destroy")
    request = SimingContextRequest(scope=scope, valid_at=20, recorded_at=20, seed_node_ids=[entry.entry_id])
    first = SimingContextCompiler(graph).compile(request)
    second = SimingContextCompiler(graph).compile(request)
    assert second == first
    assert second.context_hash == first.context_hash


class ReversingGraph:
    def __init__(self, scope: HeavenlyGraphScope, nodes: list[HeavenlyGraphNode]) -> None:
        self._scope = scope
        self._nodes = nodes
        self.calls: list[dict[str, object]] = []

    def query_subgraph(self, **kwargs: object) -> HeavenlySubgraphResult:
        self.calls.append(kwargs)
        nodes = self._nodes if len(self.calls) % 2 else list(reversed(self._nodes))
        return HeavenlySubgraphResult(
            scope=self._scope,
            seed_node_ids=list(kwargs["seed_node_ids"]),
            valid_at=kwargs["valid_at"],
            recorded_at=kwargs["recorded_at"],
            nodes=nodes,
        )


def _node(scope: HeavenlyGraphScope, entry: object) -> HeavenlyGraphNode:
    memory = entry
    return HeavenlyGraphNode(
        node_id=memory.entry_id,
        node_type=f"memory:{memory.domain}",
        scope=scope,
        validity=GraphValidity(valid_from=1),
        recorded_at=1,
        revision=1,
        provenance=GraphProvenance(
            source_kind="authority_event",
            source_ref="authority:test",
            causation_id="authority:test",
            correlation_id="corr:test",
            producer_system="system_l6",
        ),
        attributes=memory.model_dump(mode="json"),
    )


def test_compiler_canonicalizes_unordered_graph_context_into_all_six_domains() -> None:
    scope = HeavenlyGraphScope(world_id="world:demo", session_id="session:demo", story_branch_id="branch:main")
    entries = [
        WorldFactMemoryEntry(entry_id="world:b", world_anchor_id="obj_bell", state_key="heard", state_value=True, authority_result_ref="authority:b"),
        WorldFactMemoryEntry(entry_id="world:a", world_anchor_id="obj_bell", state_key="heard", state_value=False, authority_result_ref="authority:a"),
        CausalTimelineMemoryEntry(entry_id="cause:a", cause_ref="world:a", effect_ref="world:b", relation_type="CAUSED_BY"),
        ActorCognitionMemoryEntry(entry_id="actor:a", actor_id="char:a", revision_vector={"memory": "1"}, completeness="complete"),
        StorylineObligationMemoryEntry(entry_id="story:a", record_type="obligation", lifecycle="open"),
        InterventionOutcomeMemoryEntry(entry_id="outcome:a", stage="proposal", correlation_id="corr:test"),
        ConvergenceStrategyMemoryEntry(entry_id="strategy:a"),
    ]
    graph = ReversingGraph(scope, [_node(scope, entry) for entry in entries])
    request = SimingContextRequest(scope=scope, valid_at=2, seed_node_ids=["world:b", "world:a", "world:b"])

    first = SimingContextCompiler(graph).compile(request)
    second = SimingContextCompiler(graph).compile(request)

    assert first == second
    assert first.context_hash == second.context_hash
    assert [entry.entry_id for entry in first.world_facts] == ["world:a", "world:b"]
    assert [len(bucket) for bucket in (first.causal_timeline, first.actor_cognition, first.storyline_obligations, first.intervention_outcomes, first.convergence_strategies)] == [1, 1, 1, 1, 1]
    assert graph.calls[0]["seed_node_ids"] == ["world:a", "world:b"]
    assert graph.calls[0]["direction"] == "both"
    assert graph.calls[0]["max_depth"] == 4
    assert graph.calls[0]["node_limit"] == request.node_limit
    assert graph.calls[0]["relation_limit"] == request.relation_limit


def test_compiler_rejects_memory_node_with_domain_or_id_mismatch() -> None:
    scope = HeavenlyGraphScope(world_id="world:demo", session_id="session:demo", story_branch_id="branch:main")
    entry = WorldFactMemoryEntry(entry_id="fact:actual", world_anchor_id="obj_bell", state_key="heard", state_value=True, authority_result_ref="authority:actual")
    bad_node = _node(scope, entry).model_copy(update={"node_id": "fact:other"})
    graph = ReversingGraph(scope, [bad_node])
    request = SimingContextRequest(scope=scope, valid_at=2, seed_node_ids=["fact:other"])

    with pytest.raises(ValueError, match="identity"):
        SimingContextCompiler(graph).compile(request)


def test_compiler_excludes_memory_outside_the_requested_temporal_bound() -> None:
    graph = InMemoryHeavenlyGraphAdapter()
    scope = HeavenlyGraphScope(world_id="world:demo", session_id="session:demo", story_branch_id="branch:main")
    entry = WorldFactMemoryEntry(entry_id="fact:expired", world_anchor_id="obj_bell", state_key="heard", state_value=True, authority_result_ref="authority:expired")
    SimingHeavenlyMemoryService(graph).write_entry(
        scope=scope,
        entry=entry,
        validity=GraphValidity(valid_from=10, valid_to=20),
        recorded_at=10,
        revision=1,
        supersedes_revision=None,
        provenance=GraphProvenance(source_kind="authority_event", source_ref="authority:expired", causation_id="authority:expired", correlation_id="corr:expired", producer_system="system_l6"),
        transaction_id="tx:expired",
        idempotency_key="memory:expired",
    )

    context = SimingContextCompiler(graph).compile(
        SimingContextRequest(scope=scope, valid_at=20, recorded_at=20, seed_node_ids=[entry.entry_id])
    )

    assert context.world_facts == []
    assert graph.get_node(node_id=entry.entry_id, scope=scope, valid_at=10, recorded_at=20) is not None
