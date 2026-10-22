"""Receipt-backed private learning facts in the common durable replay cut."""
import asyncio
from copy import deepcopy

import pytest

from app.gameplay.event_store import GameplayEventStore
from test_registered_learning_authority import setup, source
from test_status_application_lifecycle import application
from test_world_batch_settlement_application import inputs, submit
from test_world_replay_checkpoint_application import capture, tail_call


def participant(store, **kwargs):
    from app.world_runtime.replay_participants import _learning_participant
    return _learning_participant(store, **kwargs)


def validate(store, saved, **kwargs):
    from app.world_runtime.replay_participants import _validate_learning_participant
    return _validate_learning_participant(store, saved, **kwargs)


def test_empty_learning_participant_is_explicit_and_read_only():
    store = GameplayEventStore()
    before = store.export_snapshot()
    saved = participant(store)
    assert saved["streams"] == {} and saved["event_refs"] == []
    validate(store, saved)
    validate(store, None)  # Old manifests with no learning facts stay readable.
    assert store.export_snapshot() == before


def test_learning_historical_cut_excludes_later_commits():
    store, owner, _, request = setup()
    first = owner.settle(request, caller_principal="service:learning")
    cut = store.get_last_global_sequence()
    saved = participant(store)
    evidence = source(store, command="practice:2")
    second = owner.settle(request.model_copy(update=dict(command_id="learn:2", idempotency_key="learn:2",
        evidence_refs=(evidence,), expected_source_revisions={"practice:char_a": 2}, expected_revision=1)),
        caller_principal="service:learning")
    assert second.committed
    before = store.export_snapshot()
    assert participant(store, boundary_sequence=cut) == saved
    validate(store, saved, boundary_sequence=cut)
    row = saved["streams"][owner.stream_id(request.world_ref, request.actor_id)]
    assert row["actor_id"] == "char_a" and row["world_ref"] == request.world_ref
    assert row["revision"] == 1 and row["source_event_refs"] == first.committed_event_ids
    assert row["states"][0]["visibility"]["scope"] == "actor_private:char_a"
    assert participant(store)["streams"][row["stream_id"]]["revision"] == 2
    assert store.export_snapshot() == before


@pytest.mark.parametrize("fault", ["state", "refs", "omitted", "receipt", "transaction"])
def test_learning_corruption_rejects_without_writes(fault, monkeypatch):
    store, owner, _, request = setup()
    receipt = owner.settle(request, caller_principal="service:learning")
    saved = participant(store)
    bad = deepcopy(saved)
    row = bad["streams"][owner.stream_id(request.world_ref, request.actor_id)]
    if fault == "state":
        row["states"][0]["proficiency"] = .99
    elif fault == "refs":
        row["source_event_refs"] = ["forged"]
    elif fault == "omitted":
        bad = None
    elif fault == "receipt":
        original = store.get_by_idempotency
        monkeypatch.setattr(store, "get_by_idempotency", lambda principal, key:
            None if principal == owner.PRINCIPAL else original(principal, key))
    else:
        original = store.get_transaction
        monkeypatch.setattr(store, "get_transaction", lambda ref:
            None if ref == receipt.transaction_id else original(ref))
    before = store.export_snapshot()
    with pytest.raises(ValueError):
        validate(store, bad)
    assert store.export_snapshot() == before


@pytest.mark.asyncio
@pytest.mark.parametrize("learn_before_cut", [False, True])
async def test_learning_application_cut_tail_reopens_and_rejects_tampering(application, learn_before_cut):
    from app.world_runtime.replay_checkpoint import _tail_hash

    main, start, advance = application
    await start()
    await advance(86400)
    plan, window = inputs(main)
    assert (await submit(main, plan=plan, window=window, budget=1)).receipts

    def learn():
        store, owner, _, request = setup(main.gameplay_event_store)
        return owner.settle(request, caller_principal="service:learning")

    if learn_before_cut:
        assert (await asyncio.wrap_future(main.runtime_execution.submit(learn))).committed
    cut = await capture(main)
    assert cut.status == "consistent", cut.diagnostics
    assert "learning" in cut.checkpoint.state["participants"]
    if not learn_before_cut:
        assert (await asyncio.wrap_future(main.runtime_execution.submit(learn))).committed
    tail = await tail_call(main)
    assert tail.status == "verified", tail.diagnostics
    await main._stop_population_runtime_on_shutdown()
    await start()
    before = await asyncio.wrap_future(main.runtime_execution.submit(
        lambda: main.gameplay_event_store.export_snapshot()))
    replayed = await tail_call(main, tail.payload)
    assert replayed.status == "verified", replayed.diagnostics
    assert replayed.result["full_digest"] == replayed.result["result_digest"]
    assert replayed.result["participants"]["learning"]["streams"]
    bad = deepcopy(tail.payload)
    row = next(iter(bad["participants"]["learning"]["streams"].values()))
    row["states"][0]["rank"] = "master"
    bad["digest"] = _tail_hash(bad)
    assert (await tail_call(main, bad)).status != "verified"
    assert await asyncio.wrap_future(main.runtime_execution.submit(
        lambda: main.gameplay_event_store.export_snapshot())) == before
