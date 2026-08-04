from app.models.siming_heavenly_graph import GraphProvenance, GraphValidity, HeavenlyGraphScope
from app.models.siming_heavenly_memory import SimingContextRequest, WorldFactMemoryEntry
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
