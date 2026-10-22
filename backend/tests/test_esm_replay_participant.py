"""ESM owner receipts and source cuts in common replay."""
from copy import deepcopy

import pytest

from app.gameplay.event_store import DurableGameplayEventStore, GameplayEventStore
from app.gameplay.settlement_plan import build_multi_stream_atomic_event_batch
from app.models.player_input import InteractIntent
from app.services.esm_service import ESMService
from app.world_runtime import replay_participants


def _settle(store, key="esm:1", action="use", *, with_source=False):
    reads = {}
    if with_source:
        source = build_multi_stream_atomic_event_batch(command_id="source:esm",
            principal_ref="authority:test:esm-source", expected_revisions={"source:esm": 0},
            event_specs={"source:esm": (("gameplay.test.esm_source", {"fact": "pinned"}),)},
            idempotency_key="source:esm", causation_id="source:esm", correlation_id="source:esm")
        assert store.append_batch(source).committed
        reads = {"source:esm": 1}
    service = ESMService(store=store)
    event = InteractIntent(player_id="character_agent", room_id="room_demo", scene_id="scene_demo",
        zone_id="zone_focus", actor_id="char_a", intent_type="interact_intent", producer_ts=10,
        target_object_id="obj_worktable", interaction_type=action, turn_id="turn:esm",
        execution_contract_ref=key)
    request = service.build_action_request(event)
    result, receipt = service.settle_object_interaction(
        event, action_request=request, actor_position=(-0.9, 0.85, -2.0),
        read_stream_revisions=reads)
    assert result.settlement_status == "committed" and receipt.committed
    return result, receipt


def _participant(store, **kwargs):
    return replay_participants._esm_participant(store, **kwargs)


def test_empty_esm_participant_is_explicit_and_read_only():
    store = GameplayEventStore()
    before = store.export_snapshot()
    saved = _participant(store)
    assert saved["event_refs"] == [] and saved["source_refs"] == []
    replay_participants._validate_esm_participant(store, saved)
    assert store.export_snapshot() == before


def test_esm_participant_captures_durable_owner_receipts_and_reopens(tmp_path):
    path = tmp_path / "esm-replay.sqlite3"
    store = DurableGameplayEventStore(path)
    _settle(store, with_source=True)
    saved = _participant(store)
    assert len(saved["event_refs"]) == 1
    transaction = store.get_transaction(saved["event_refs"][0]["transaction_id"])
    assert transaction.idempotency_record.principal_ref == "authority:esm:object"
    assert saved["event_refs"][0]["transaction_digest"]
    assert saved["event_refs"][0]["receipt_digest"]
    assert saved["source_refs"]
    assert "current_state" not in repr(saved)
    replay_participants._validate_esm_participant(store, saved)
    store.close()

    reopened = DurableGameplayEventStore(path)
    try:
        assert _participant(reopened) == saved
        replay_participants._validate_esm_participant(reopened, saved)
    finally:
        reopened.close()


def test_esm_participant_historical_cut_excludes_later_owner_event():
    store = GameplayEventStore()
    _settle(store)
    first_sequence = store.get_last_global_sequence()
    first = _participant(store, boundary_sequence=first_sequence)
    _settle(store, key="esm:2", action="finish_use")
    assert _participant(store, boundary_sequence=first_sequence) == first
    replay_participants._validate_esm_participant(store, first, boundary_sequence=first_sequence)
    assert len(_participant(store)["event_refs"]) == 2


def test_esm_is_manifest_versioned_and_missing_history_fails_closed():
    from app.world_runtime.replay_checkpoint import _manifest

    store = GameplayEventStore()
    base = dict(schema_version=1, versions={"participant_manifest": 1, "batch_input": 1,
        "batch_operation": 1, "population_recovery": 1, "status_events": 1, "migration_events": 1},
        timeline={}, profile={}, mapping={}, confirmed_tick=0, window_ticks=1, owner_revisions={},
        batches={"batch:esm": {}}, external_dependencies={}, random_context={},
        population={"schema_version": 1}, status={"schema_version": 1, "actors": {}},
        migration={"schema_version": 1})
    assert "esm" not in _manifest(base, {"batch:esm"})["versions"]
    _settle(store)
    esm = _participant(store)
    with pytest.raises(ValueError, match="replay_saved_esm_projection_mismatch"):
        replay_participants._validate_esm_participant(store, None)
    current = deepcopy(base)
    current["versions"]["esm"] = 1
    current["esm"] = esm
    assert _manifest(current, {"batch:esm"})["esm"] == esm


@pytest.mark.parametrize("fault", ["event", "transaction", "receipt", "source", "omitted"])
def test_esm_participant_rejects_tampering_without_writes(fault):
    store = GameplayEventStore()
    _settle(store)
    saved = _participant(store)
    bad = deepcopy(saved)
    if fault == "event":
        bad["event_refs"][0]["event_digest"] = "forged"
    elif fault == "transaction":
        bad["event_refs"][0]["transaction_digest"] = "forged"
    elif fault == "receipt":
        bad["event_refs"][0]["receipt_digest"] = "forged"
    elif fault == "source":
        store = GameplayEventStore()
        _settle(store, with_source=True)
        saved = _participant(store)
        bad = deepcopy(saved)
        bad["source_refs"][0]["event_digest"] = "forged"
    else:
        bad["event_refs"] = []
    before = store.export_snapshot()
    with pytest.raises(ValueError):
        replay_participants._validate_esm_participant(store, bad)
    assert store.export_snapshot() == before
