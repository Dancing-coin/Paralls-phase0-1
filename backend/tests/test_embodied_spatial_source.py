"""Controller evidence admission, not independent physics or Godot acceptance."""
from contextlib import closing

import pytest
from pydantic import ValidationError

from app.gameplay.event_store import GameplayEventStore, DurableGameplayEventStore
from app.services.embodied_controller_auth_service import EmbodiedControllerAuthService, EmbodiedControllerEnrollment


def setup_source(store=None):
    from app.world_runtime.embodied_spatial_source import EmbodiedSpatialSource, EmbodiedSpatialScope
    auth = EmbodiedControllerAuthService()
    clock = [1000]
    scope = EmbodiedSpatialScope(actor_id="char_a", room_id="r", scene_id="s", scene_instance_id="s:1",
        zone_id="z", scene_revision=1, source_ref="authored:actor_a@1", spawn_position=(0, 0, 0),
        bounds_min=(-10, -1, -10), bounds_max=(10, 1, 10), max_speed_mps=4,
        physics_ticks_per_second=60, max_age_ms=500)
    store = store if store is not None else GameplayEventStore()
    source = EmbodiedSpatialSource(store=store, auth=auth, scopes=[scope], clock_ms=lambda: clock[0])
    binding = bind(auth)
    return source, store, auth, scope, clock, binding


def bind(auth, connection="c"):
    secret = auth.create_trusted_local_launch_credential(actor_id="char_a", controller_instance_id="godot:a",
        issued_at=0, expires_at=100)
    result = auth.bind_controller(EmbodiedControllerEnrollment(credential_kind="trusted_local_launch",
        credential=secret, actor_id="char_a", controller_instance_id="godot:a", protocol_version=1),
        remote_host="127.0.0.1", now=1, connection_ref=connection)
    assert result.accepted
    return result.binding


def sample(scope, binding, tick=1, position=(0, 0, 0), **changes):
    from app.world_runtime.embodied_spatial_source import EmbodiedSpatialSample
    payload = dict(actor_id=scope.actor_id, room_id=scope.room_id, scene_id=scope.scene_id,
        scene_instance_id=scope.scene_instance_id, zone_id=scope.zone_id, scene_revision=scope.scene_revision,
        connection_epoch=binding.connection_epoch, physics_tick=tick, position=position)
    payload.update(changes)
    return EmbodiedSpatialSample.model_validate(payload)


def read(source, scope):
    return source.read(actor_id=scope.actor_id, room_id=scope.room_id, scene_id=scope.scene_id,
        scene_instance_id=scope.scene_instance_id, zone_id=scope.zone_id, scene_revision=scope.scene_revision)


def test_source_is_missing_until_real_bound_sample_and_exact_duplicate_does_not_refresh():
    source, store, _, scope, clock, binding = setup_source()
    with pytest.raises(ValueError, match="missing"):
        read(source, scope)
    value = sample(scope, binding)
    receipt = source.accept(value, connection_ref="c")
    evidence = read(source, scope)
    assert receipt.committed and evidence.position == (0, 0, 0)
    assert evidence.read_stream_revisions == {source.stream_id("char_a"): 1}
    clock[0] += 501
    assert source.accept(value, connection_ref="c") == receipt
    with pytest.raises(ValueError, match="stale"):
        read(source, scope)
    assert store.get_last_global_sequence() == 1


@pytest.mark.parametrize("changes,connection", [({}, "foreign"), ({"actor_id": "char_b"}, "c"),
    ({"scene_id": "other"}, "c"), ({"scene_instance_id": "s:2"}, "c"),
    ({"zone_id": "other"}, "c"), ({"scene_revision": 2}, "c"), ({"connection_epoch": 2}, "c")])
def test_foreign_or_changed_source_has_zero_write(changes, connection):
    source, store, _, scope, _, binding = setup_source()
    with pytest.raises(ValueError):
        source.accept(sample(scope, binding, **changes), connection_ref=connection)
    assert store.get_last_global_sequence() == 0


@pytest.mark.parametrize("position", [(float("nan"), 0, 0), (float("inf"), 0, 0), (True, 0, 0), (0, 0)])
def test_nonfinite_or_malformed_position_rejected(position):
    _, _, _, scope, _, binding = setup_source()
    with pytest.raises((ValidationError, ValueError)):
        sample(scope, binding, position=position)


def test_tick_cannot_buy_movement_without_elapsed_backend_time():
    source, store, _, scope, clock, binding = setup_source()
    with pytest.raises(ValueError, match="continuity"):
        source.accept(sample(scope, binding, position=(1, 0, 0)), connection_ref="c")
    source.accept(sample(scope, binding), connection_ref="c")
    with pytest.raises(ValueError, match="continuity"):
        source.accept(sample(scope, binding, tick=60000, position=(1, 0, 0)), connection_ref="c")
    clock[0] += 250
    source.accept(sample(scope, binding, tick=16, position=(.8, 0, 0)), connection_ref="c")
    assert read(source, scope).position == (.8, 0, 0)
    assert store.get_last_global_sequence() == 2


def test_changed_duplicate_tick_and_bounds_rejected_without_refresh():
    source, store, _, scope, clock, binding = setup_source()
    source.accept(sample(scope, binding), connection_ref="c")
    clock[0] += 20000
    for value in [sample(scope, binding, position=(.01, 0, 0)),
                  sample(scope, binding, tick=1201, position=(11, 0, 0))]:
        with pytest.raises(ValueError):
            source.accept(value, connection_ref="c")
    assert store.get_last_global_sequence() == 1


def test_revocation_and_reconnect_require_live_continuous_sample():
    source, store, auth, scope, clock, binding = setup_source()
    source.accept(sample(scope, binding), connection_ref="c")
    auth.disconnect_connection("c")
    with pytest.raises(ValueError, match="binding"):
        read(source, scope)
    newer = bind(auth, "new")
    with pytest.raises(ValueError, match="continuity"):
        source.accept(sample(scope, newer, position=(1, 0, 0)), connection_ref="new")
    clock[0] += 100
    source.accept(sample(scope, newer), connection_ref="new")
    assert read(source, scope).position == (0, 0, 0)
    assert store.get_last_global_sequence() == 2


def test_sqlite_reopen_requires_fresh_sample_and_changed_scope_never_reuses_pose(tmp_path):
    path = tmp_path / "world.db"
    with closing(DurableGameplayEventStore(path)) as store:
        source, _, _, scope, _, binding = setup_source(store)
        source.accept(sample(scope, binding), connection_ref="c")
    with closing(DurableGameplayEventStore(path)) as store:
        source, _, auth, scope, _, binding = setup_source(store)
        with pytest.raises(ValueError, match="process"):
            read(source, scope)
        source.accept(sample(scope, binding), connection_ref="c")
        assert read(source, scope).read_stream_revisions == {source.stream_id("char_a"): 2}
        with pytest.raises(ValueError, match="scope"):
            source.read(actor_id="char_a", room_id="r", scene_id="s", scene_instance_id="other",
                zone_id="z", scene_revision=1)


def test_source_revision_prevents_owner_settlement_after_movement():
    from app.services.esm_service import ESMService
    from app.models.player_input import InteractIntent
    source, store, _, scope, clock, binding = setup_source()
    source.accept(sample(scope, binding), connection_ref="c")
    evidence = read(source, scope)
    clock[0] += 100
    source.accept(sample(scope, binding, tick=7, position=(.1, 0, 0)), connection_ref="c")
    owner = ESMService(store=store)
    event = InteractIntent(player_id="character_agent", actor_id="char_a", room_id="r", scene_id="s",
        zone_id="z", intent_type="interact_intent", producer_ts=1, target_object_id="obj_plaque",
        interaction_type="inspect", turn_id="turn:1", execution_contract_ref="exec:1")
    # Position supplied to the owner here is deliberately in range: read CAS,
    # rather than its distance guard, must reject the stale evidence.
    with pytest.raises(ValueError, match="commit_failed"):
        owner.settle_object_interaction(event, action_request=owner.build_action_request(event),
            actor_position=(-3.5, 1.2, -2.8), read_stream_revisions=evidence.read_stream_revisions)
    assert store.get_last_global_sequence() == 2


def test_failed_append_and_lost_response_recover_original_receipt(monkeypatch):
    source, store, _, scope, _, binding = setup_source()
    append = store.append_batch
    def fail(batch):
        raise OSError("disk unavailable")
    monkeypatch.setattr(store, "append_batch", fail)
    with pytest.raises(OSError):
        source.accept(sample(scope, binding), connection_ref="c")
    with pytest.raises(ValueError, match="missing"):
        read(source, scope)
    def lost(batch):
        append(batch)
        raise OSError("response lost")
    monkeypatch.setattr(store, "append_batch", lost)
    with pytest.raises(OSError):
        source.accept(sample(scope, binding), connection_ref="c")
    receipt = source.accept(sample(scope, binding), connection_ref="c")
    assert receipt.committed and store.get_last_global_sequence() == 1
    assert read(source, scope).event_ref == receipt.committed_event_ids[0]


def test_strict_schema_store_accepts_and_recovers_registered_source(tmp_path):
    from app.gameplay.event_schema_registry import EventSchemaRegistry
    from app.world_runtime.embodied_spatial_source import SPATIAL_SAMPLE_SCHEMA
    registry = EventSchemaRegistry()
    registry.register(SPATIAL_SAMPLE_SCHEMA)
    path = tmp_path / "strict.db"
    with closing(DurableGameplayEventStore(path, event_schema_registry=registry)) as store:
        source, _, _, scope, _, binding = setup_source(store)
        receipt = source.accept(sample(scope, binding), connection_ref="c")
    with closing(DurableGameplayEventStore(path, event_schema_registry=registry)) as store:
        source, _, _, scope, _, _ = setup_source(store)
        with pytest.raises(ValueError, match="process"):
            read(source, scope)
        assert store.get_event(receipt.committed_event_ids[0]).event_type == SPATIAL_SAMPLE_SCHEMA.event_type


def test_sampling_and_old_duplicate_use_bounded_history_reads(monkeypatch):
    source, store, _, scope, clock, binding = setup_source()
    first = sample(scope, binding)
    receipt = source.accept(first, connection_ref="c")
    original_read = store.read_stream
    def bounded_read(stream_id, **kwargs):
        assert kwargs.get("limit") == 1
        assert kwargs.get("from_revision") == store.get_stream_head(stream_id)
        return original_read(stream_id, **kwargs)
    monkeypatch.setattr(store, "read_stream", bounded_read)
    for tick in range(2, 12):
        clock[0] += 20
        source.accept(sample(scope, binding, tick=tick), connection_ref="c")
        assert read(source, scope).position == (0, 0, 0)
    assert source.accept(first, connection_ref="c") == receipt
    assert store.get_last_global_sequence() == 11


def test_rebinding_revokes_old_connection_source_and_direct_epoch_revocation():
    source, store, auth, scope, _, binding = setup_source()
    source.accept(sample(scope, binding), connection_ref="c")
    newer = bind(auth, "new")
    with pytest.raises(ValueError, match="binding"):
        read(source, scope)
    with pytest.raises(ValueError, match="binding|epoch"):
        source.accept(sample(scope, binding, tick=2), connection_ref="c")
    source.accept(sample(scope, newer), connection_ref="new")
    auth.revoke_controller_epoch(controller_instance_id=newer.controller_instance_id,
        connection_epoch=newer.connection_epoch)
    with pytest.raises(ValueError, match="binding"):
        read(source, scope)
    assert store.get_last_global_sequence() == 2
