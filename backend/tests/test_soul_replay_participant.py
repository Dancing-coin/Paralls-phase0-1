"""Soul facts and their original source cut in the common replay manifest."""
from copy import deepcopy

import pytest

from app.gameplay.event_store import DurableGameplayEventStore, GameplayEventStore
from app.world_runtime import replay_participants
from test_soul_fact_owner import _command, _setup
from test_soul_anchor_owner import ACTOR, WORLD


def participant(store, **kwargs):
    return replay_participants._soul_participant(store, **kwargs)


def validate(store, saved, **kwargs):
    return replay_participants._validate_soul_participant(store, saved, **kwargs)


def test_empty_soul_participant_is_explicit_read_only():
    store = GameplayEventStore()
    before = store.export_snapshot()

    saved = participant(store)

    assert saved["event_refs"] == []
    assert saved["streams"] == {}
    validate(store, saved)
    assert store.export_snapshot() == before


def test_soul_participant_captures_owner_receipts_and_pinned_sources():
    store = GameplayEventStore()
    _, anchors, facts = _setup(store)
    assert anchors.projection(world_ref=WORLD, actor_ref=ACTOR)
    assert facts.settle(_command()).committed

    saved = participant(store)

    assert len(saved["event_refs"]) == 2
    assert all(row["receipt_digest"] for row in saved["event_refs"])
    assert "soul:bounded" not in repr(saved)
    assert "until_revoked" not in repr(saved)
    source_ids = {row["event_id"] for row in saved["source_refs"]}
    assert len(source_ids) > 2
    source_streams = {row["stream_id"] for row in saved["source_refs"]}
    assert any(stream.startswith("presence:") for stream in source_streams)
    assert any(stream.startswith("population:") for stream in source_streams)
    assert any(stream.startswith("gameplay:resources:") for stream in source_streams)
    validate(store, saved)


def test_soul_participant_historical_cut_excludes_later_source_and_owner_events():
    store = GameplayEventStore()
    _, anchors, facts = _setup(store)
    assert anchors.projection(world_ref=WORLD, actor_ref=ACTOR)
    first_cut = store.get_last_global_sequence()
    first = participant(store)
    assert facts.settle(_command()).committed

    assert participant(store, boundary_sequence=first_cut) == first
    validate(store, first, boundary_sequence=first_cut)
    tail = participant(store)
    validate(store, tail, boundary_sequence=store.get_last_global_sequence())
    assert len(tail["event_refs"]) == len(first["event_refs"]) + 1


def test_soul_participant_survives_sqlite_reopen(tmp_path):
    path = tmp_path / "soul-replay.sqlite3"
    store = DurableGameplayEventStore(path)
    _, anchors, facts = _setup(store)
    assert anchors.projection(world_ref=WORLD, actor_ref=ACTOR)
    assert facts.settle(_command()).committed
    saved = participant(store)
    store.close()

    reopened = DurableGameplayEventStore(path)
    try:
        assert participant(reopened) == saved
        validate(reopened, saved)
    finally:
        reopened.close()


@pytest.mark.parametrize("fault", ["projection", "receipt", "transaction", "source", "omitted"])
def test_soul_participant_rejects_tampering_without_writes(fault, monkeypatch):
    store = GameplayEventStore()
    _, anchors, facts = _setup(store)
    assert anchors.projection(world_ref=WORLD, actor_ref=ACTOR)
    assert facts.settle(_command()).committed
    saved = participant(store)
    bad = deepcopy(saved)
    if fault == "projection":
        bad["streams"][next(iter(bad["streams"]))]["projection_digest"] = "forged"
    elif fault == "receipt":
        bad["event_refs"][0]["receipt_digest"] = "forged"
    elif fault == "transaction":
        bad["event_refs"][0]["transaction_digest"] = "forged"
    elif fault == "source":
        bad["source_refs"][0]["event_digest"] = "forged"
    else:
        bad = None
    before = store.export_snapshot()

    with pytest.raises(ValueError):
        validate(store, bad)

    assert store.export_snapshot() == before


def test_soul_participant_rejects_changed_original_source_receipt(monkeypatch):
    store = GameplayEventStore()
    _, anchors, facts = _setup(store)
    assert anchors.projection(world_ref=WORLD, actor_ref=ACTOR)
    assert facts.settle(_command()).committed
    saved = participant(store)
    source_id = saved["source_refs"][0]["event_id"]
    original = store.get_by_idempotency
    def changed(principal, key):
        result = original(principal, key)
        if result is not None and source_id in result.committed_event_ids:
            return result.model_copy(update={"global_sequence_range": (0, 0)})
        return result
    monkeypatch.setattr(store, "get_by_idempotency", changed)

    with pytest.raises(ValueError):
        validate(store, saved)


def test_soul_participant_is_admitted_by_common_checkpoint_manifest():
    from app.world_runtime.replay_checkpoint import _manifest

    soul = participant(GameplayEventStore())
    value = dict(schema_version=1,
        versions={"participant_manifest": 1, "batch_input": 1, "batch_operation": 1,
            "population_recovery": 1, "status_events": 1, "migration_events": 1, "soul": 1},
        batches={}, population={"schema_version": 1}, status={"schema_version": 1},
        migration={"schema_version": 1}, external_dependencies={}, random_context={}, soul=soul)

    assert _manifest(value, ()) == value
