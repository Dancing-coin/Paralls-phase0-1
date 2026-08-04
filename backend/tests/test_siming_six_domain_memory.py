from app.models.siming_heavenly_graph import GraphProvenance, GraphValidity, HeavenlyGraphScope
from app.models.siming_heavenly_memory import WorldFactMemoryEntry
from app.services.in_memory_heavenly_graph import InMemoryHeavenlyGraphAdapter
from app.services.siming_heavenly_memory import SimingHeavenlyMemoryService


def _scope() -> HeavenlyGraphScope:
    return HeavenlyGraphScope(world_id="world:demo", session_id="session:demo", story_branch_id="branch:main")


def _provenance(ref: str) -> GraphProvenance:
    return GraphProvenance(source_kind="authority_event", source_ref=ref, causation_id=ref, correlation_id="corr:memory", producer_system="system_l6")


def _entry(entry_id: str, value: str) -> WorldFactMemoryEntry:
    return WorldFactMemoryEntry(entry_id=entry_id, world_anchor_id="obj_bell", state_key="heard", state_value=value, authority_result_ref=f"authority:{entry_id}")


def test_conflicting_claims_are_preserved_as_distinct_entries() -> None:
    service = SimingHeavenlyMemoryService(InMemoryHeavenlyGraphAdapter())
    scope = _scope()
    for index, value in enumerate(["heard", "not_heard"]):
        entry = _entry(f"claim:bell:{value}", value)
        service.write_entry(scope=scope, entry=entry, validity=GraphValidity(valid_from=10), recorded_at=10, revision=1, supersedes_revision=None, provenance=_provenance(entry.entry_id), transaction_id=f"tx:{index}", idempotency_key=f"memory:{entry.entry_id}")
    assert {entry.entry_id for entry in service.list_domain(scope, "world_fact", valid_at=20)} == {"claim:bell:heard", "claim:bell:not_heard"}
