from pathlib import Path

from app.models.siming_heavenly_graph import (
    GraphProvenance,
    GraphValidity,
    HeavenlyGraphNode,
    HeavenlyGraphScope,
    HeavenlyGraphWriteBatch,
)
from app.models.siming_heavenly_memory import (
    ActorCognitionMemoryEntry,
    CausalTimelineMemoryEntry,
    ConvergenceStrategyMemoryEntry,
    InterventionOutcomeMemoryEntry,
    SimingHeavenlyMemoryEntry,
    StorylineObligationMemoryEntry,
    WorldFactMemoryEntry,
)
from app.services.in_memory_heavenly_graph import InMemoryHeavenlyGraphAdapter
from app.services.siming_heavenly_memory import SimingHeavenlyMemoryService
from app.services.sqlite_heavenly_graph import SQLiteHeavenlyGraphAdapter


def _scope() -> HeavenlyGraphScope:
    return HeavenlyGraphScope(
        world_id="world:demo",
        session_id="session:demo",
        story_branch_id="branch:main",
    )


def _provenance(ref: str) -> GraphProvenance:
    return GraphProvenance(
        source_kind="authority_event",
        source_ref=ref,
        causation_id=ref,
        correlation_id="corr:memory",
        producer_system="system_l6",
    )


def _entries() -> list[SimingHeavenlyMemoryEntry]:
    return [
        WorldFactMemoryEntry(
            entry_id="fact:letter:removed",
            world_anchor_id="obj_letter",
            state_key="surface_state",
            state_value="removed_from_surface",
            authority_result_ref="authority:letter:removed",
            evidence_refs=["visual:letter:removed"],
        ),
        CausalTimelineMemoryEntry(
            entry_id="cause:letter:removed",
            cause_ref="fact:letter:removed",
            effect_ref="story:N3",
            relation_type="CAUSED_BY",
        ),
        ActorCognitionMemoryEntry(
            entry_id="cognition:char_b:letter",
            actor_id="char_b",
            revision_vector={"event": "1", "observation": "1"},
            completeness="complete",
            supporting_memory_refs=["actor_memory_surface:char_b:observation:1"],
        ),
        StorylineObligationMemoryEntry(
            entry_id="obligation:O6",
            record_type="obligation",
            lifecycle="open",
            supporting_fact_refs=["fact:letter:removed"],
        ),
        InterventionOutcomeMemoryEntry(
            entry_id="outcome:letter:proposal",
            stage="proposal",
            correlation_id="corr:letter",
        ),
        ConvergenceStrategyMemoryEntry(
            entry_id="strategy:letter",
            reachable_attractor_refs=["attractor:aftermath"],
            open_obligation_refs=["obligation:O6"],
        ),
    ]


def _write(
    service: SimingHeavenlyMemoryService,
    scope: HeavenlyGraphScope,
    entry: SimingHeavenlyMemoryEntry,
    *,
    revision: int = 1,
    valid_from: int = 10,
    recorded_at: int = 10,
    supersedes_revision: int | None = None,
) -> None:
    service.write_entry(
        scope=scope,
        entry=entry,
        validity=GraphValidity(valid_from=valid_from),
        recorded_at=recorded_at,
        revision=revision,
        supersedes_revision=supersedes_revision,
        provenance=_provenance(f"authority:{entry.entry_id}:{revision}"),
        transaction_id=f"tx:{entry.entry_id}:{revision}",
        idempotency_key=f"memory:{entry.entry_id}:{revision}",
    )


def test_service_round_trips_all_six_domains() -> None:
    graph = InMemoryHeavenlyGraphAdapter()
    service = SimingHeavenlyMemoryService(graph)
    scope = _scope()

    for entry in _entries():
        _write(service, scope, entry)

    assert [
        len(service.list_domain(scope, entry.domain, valid_at=20))
        for entry in _entries()
    ] == [1] * 6


def test_list_domain_sorts_node_ids_without_adapter_ordering() -> None:
    graph = InMemoryHeavenlyGraphAdapter()
    scope = _scope()
    writer = SimingHeavenlyMemoryService(graph)
    for entry_id in ["fact:z", "fact:a"]:
        _write(
            writer,
            scope,
            WorldFactMemoryEntry(
                entry_id=entry_id,
                world_anchor_id="obj_letter",
                state_key="surface_state",
                state_value="removed_from_surface",
                authority_result_ref=f"authority:{entry_id}",
            ),
        )

    class ReversingGraph:
        def query_nodes(self, query: object) -> list[HeavenlyGraphNode]:
            return list(reversed(graph.query_nodes(query)))

    result = SimingHeavenlyMemoryService(ReversingGraph()).list_domain(
        scope,
        "world_fact",
        valid_at=20,
    )

    assert [entry.entry_id for entry in result] == ["fact:a", "fact:z"]


def test_conflicting_claims_and_temporal_revisions_are_preserved() -> None:
    service = SimingHeavenlyMemoryService(InMemoryHeavenlyGraphAdapter())
    scope = _scope()
    old = WorldFactMemoryEntry(
        entry_id="fact:bell",
        world_anchor_id="obj_bell",
        state_key="heard",
        state_value="heard",
        authority_result_ref="authority:bell:heard",
    )
    new = old.model_copy(
        update={
            "state_value": "not_heard",
            "authority_result_ref": "authority:bell:not_heard",
        }
    )
    conflict = WorldFactMemoryEntry(
        entry_id="fact:bell:other_claim",
        world_anchor_id="obj_bell",
        state_key="heard",
        state_value="heard",
        authority_result_ref="authority:bell:other_claim",
    )
    _write(service, scope, old)
    _write(
        service,
        scope,
        new,
        revision=2,
        valid_from=20,
        recorded_at=20,
        supersedes_revision=1,
    )
    _write(service, scope, conflict)

    assert service.get_entry(
        scope=scope,
        entry_id="fact:bell",
        valid_at=15,
        recorded_at=30,
    ) == old
    assert service.get_entry(
        scope=scope,
        entry_id="fact:bell",
        valid_at=25,
        recorded_at=15,
    ) == old
    assert service.get_entry(
        scope=scope,
        entry_id="fact:bell",
        valid_at=25,
        recorded_at=30,
    ) == new
    assert {entry.entry_id for entry in service.list_domain(scope, "world_fact", valid_at=25)} == {
        "fact:bell",
        "fact:bell:other_claim",
    }


def test_write_entry_replays_idempotently() -> None:
    service = SimingHeavenlyMemoryService(InMemoryHeavenlyGraphAdapter())
    scope = _scope()
    entry = _entries()[0]
    batch = dict(
        scope=scope,
        entry=entry,
        validity=GraphValidity(valid_from=10),
        recorded_at=10,
        revision=1,
        supersedes_revision=None,
        provenance=_provenance("authority:letter:removed:1"),
        transaction_id="tx:letter:removed:1",
        idempotency_key="memory:letter:removed:1",
    )

    assert service.write_entry(**batch).applied is True
    replay = service.write_entry(**batch)
    assert replay.applied is False
    assert replay.replayed is True


def test_list_domain_excludes_projection_nodes() -> None:
    graph = InMemoryHeavenlyGraphAdapter()
    service = SimingHeavenlyMemoryService(graph)
    scope = _scope()
    entry = _entries()[0]
    _write(service, scope, entry)
    graph.write_batch(
        HeavenlyGraphWriteBatch(
            transaction_id="tx:projection",
            idempotency_key="projection:context",
            scope=scope,
            nodes=[
                HeavenlyGraphNode(
                    node_id="projection:context",
                    node_type="projection:context",
                    scope=scope,
                    validity=GraphValidity(valid_from=10),
                    recorded_at=10,
                    revision=1,
                    provenance=_provenance("projection:context"),
                    attributes={"derived_from": "context:1"},
                )
            ],
        )
    )

    assert [entry.entry_id for entry in service.list_domain(scope, "world_fact", valid_at=20)] == [
        "fact:letter:removed"
    ]


def test_sqlite_restart_recalls_all_six_domains(tmp_path: Path) -> None:
    path = tmp_path / "siming-heavenly.sqlite3"
    scope = _scope()
    graph = SQLiteHeavenlyGraphAdapter(path)
    service = SimingHeavenlyMemoryService(graph)
    for entry in _entries():
        _write(service, scope, entry)
    graph.close()

    reopened = SQLiteHeavenlyGraphAdapter(path)
    restored = SimingHeavenlyMemoryService(reopened)
    try:
        assert [
            len(restored.list_domain(scope, entry.domain, valid_at=20))
            for entry in _entries()
        ] == [1] * 6
    finally:
        reopened.close()
