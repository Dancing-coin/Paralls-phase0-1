from __future__ import annotations

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import ProjectionCheckpoint
from app.population_continuity.siming_contracts import PopulationCadenceInput
from app.population_continuity.store_projection_assembler import assemble_committed_population_projections

from test_gameplay_event_store_contract import _batch, _event, _outbox


def test_event_store_indexes_stream_and_transaction_tails() -> None:
    store = GameplayEventStore()
    store.append_batch(
        _batch(
            tx="tx:index:first",
            command_id="cmd:index:first",
            key="key:index:first",
            events=[
                _event("evt:index:1", stream_id="stream:index", tx="tx:index:first", command_id="cmd:index:first"),
                _event("evt:index:2", stream_id="stream:index", tx="tx:index:first", command_id="cmd:index:first"),
            ],
            outbox_entries=[
                _outbox("evt:index:1", tx="tx:index:first"),
                _outbox("evt:index:2", tx="tx:index:first"),
            ],
            expected={"stream:index": 0},
        )
    )
    store.append_batch(
        _batch(
            tx="tx:index:second",
            command_id="cmd:index:second",
            key="key:index:second",
            events=[
                _event("evt:index:3", stream_id="stream:index", tx="tx:index:second", command_id="cmd:index:second"),
            ],
            outbox_entries=[_outbox("evt:index:3", tx="tx:index:second")],
            expected={"stream:index": 2},
        )
    )

    assert [event.event_id for event in store.read_stream("stream:index", from_revision=2)] == [
        "evt:index:2",
        "evt:index:3",
    ]
    assert [event.event_id for event in store.read_events(global_sequence_after=2)] == ["evt:index:3"]
    assert [batch.transaction_id for batch in store.read_transactions(global_position=2)] == [
        "tx:index:first",
        "tx:index:second",
    ]
    assert [event.event_id for event in store._events_by_stream["stream:index"]] == [
        "evt:index:1",
        "evt:index:2",
        "evt:index:3",
    ]
    assert store._transaction_end_sequences == [2, 3]


def test_event_store_rebuilds_incremental_indexes_from_snapshot() -> None:
    store = GameplayEventStore()
    store.append_batch(
        _batch(
            events=[_event("evt:index:restore", stream_id="stream:index:restore")],
            outbox_entries=[_outbox("evt:index:restore")],
            expected={"stream:index:restore": 0},
        )
    )

    restored = GameplayEventStore.from_snapshot(store.export_snapshot())

    assert [event.event_id for event in restored.read_stream("stream:index:restore")] == ["evt:index:restore"]
    assert restored._transaction_end_sequences == [1]


def test_population_assembler_reads_after_projection_checkpoint() -> None:
    store = GameplayEventStore()
    cadence = PopulationCadenceInput(
        cadence_id="cadence:incremental:1",
        world_ref="world:incremental",
        world_mode_ref="mode:incremental",
        world_mode_revision="mode:1",
        cadence_source_ref="world:incremental",
        cadence_source_revision=0,
        window_start=0,
        window_end=1,
        base_checkpoint_ref="checkpoint:incremental:1",
        base_checkpoint_digest="sha256:checkpoint",
        base_revision_vector={"gameplay:population": 0},
        policy_revision="policy:population:v1",
        selector_revision="selector:population:v1",
        ruleset_revision="rules:population:v1",
        deterministic_seed="seed:incremental:1",
        catch_up_limit=10,
        budget=10,
        report_scope="public",
    )
    checkpoint = ProjectionCheckpoint(
        checkpoint_id="checkpoint:population:0",
        projector_id="population-continuity",
        projector_version="1",
        projection_schema_version=1,
        source_revision_vector={"gameplay:population": 0},
        last_global_sequence=3,
        state={"population_projections": []},
        projection_hash="sha256:empty",
    )
    observed: list[dict[str, object]] = []
    original = store.read_events

    def read_events(**kwargs: object):
        observed.append(kwargs)
        return original(**kwargs)

    store.read_events = read_events  # type: ignore[method-assign]

    assert assemble_committed_population_projections(
        store=store,
        cadence=cadence,
        organization_projection={},
        checkpoint=checkpoint,
    ) == ()
    assert observed == [{"global_sequence_after": 3}]
