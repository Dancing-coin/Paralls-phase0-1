from __future__ import annotations

from dataclasses import replace
from functools import wraps
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from types import FunctionType

import pytest

from app.services.authority_event_bus import InMemoryAuthorityEventBus
from app.gameplay.event_store import GameplayEventStoreSnapshotError
from test_population_durable_cadence_recovery import _publisher, _runtime


def _run(path, windows=40):
    world = _runtime(path)
    bus = InMemoryAuthorityEventBus()
    publisher = _publisher(world, bus)
    first = None
    for index in range(windows):
        cadence = world.build_population_cadence(window_start=index * 60, window_end=(index + 1) * 60)
        first = first or cadence
        assert publisher(cadence) is not None
    return world, publisher, bus, first


def test_long_reopen_uses_two_checkpoints_and_eight_window_tail(tmp_path, monkeypatch):
    path = tmp_path / "g.db"
    source, publisher, _, first = _run(path)
    expected = source.export_recovery_state()
    assert source.store.list_pending_projection_refresh() == []
    assert len(publisher._records) <= 2
    assert len(source._confirmed_receipts) <= 2
    assert len(source._confirmed_fingerprints) <= 2
    checkpoints = source.store.list_projection_checkpoints(projector_id="population-recovery:world")
    assert len(checkpoints) == 2
    target = _runtime(path)
    reads = []
    original = target.store.read_stream

    def read(stream, **kwargs):
        if stream.startswith("population-cadence:"):
            assert kwargs.get("limit") is not None
            reads.append(kwargs)
        return original(stream, **kwargs)

    monkeypatch.setattr(target.store, "read_stream", read)
    monkeypatch.setattr(target.store, "list_outbox", lambda **_: pytest.fail("no full outbox restore scan"))
    bus = InMemoryAuthorityEventBus()
    restored = _publisher(target, bus)
    assert restored.confirmed_tick == 2400
    assert restored.replayed_windows == 8
    assert reads[0]["from_revision"] == 33
    assert target.export_recovery_state() == expected
    assert bus.list_events(include_realtime=True) == []
    before = target.store.export_snapshot()
    assert restored(first)
    assert target.confirm_population_cadence(first).status == "idempotent_replay"
    assert target.store.export_snapshot() == before
    assert target.export_recovery_state() == expected
    with pytest.raises(ValueError, match="confirmation_conflict"):
        restored(first.model_copy(update={"window_end": 61}))


def test_latest_checkpoint_corruption_falls_back_but_both_corrupt_fail_closed(tmp_path):
    path = tmp_path / "g.db"
    world, _, _, _ = _run(path)
    expected = world.export_recovery_state()
    checkpoints = world.store.list_projection_checkpoints(projector_id="population-recovery:world")
    assert len(checkpoints) == 2
    world.store.save_projection_checkpoint(checkpoints[0].model_copy(update={"projection_hash": "corrupt"}))
    restored_world = _runtime(path)
    restored = _publisher(restored_world, InMemoryAuthorityEventBus())
    assert restored.replayed_windows == 24
    assert restored_world.export_recovery_state() == expected
    # 回退重放会修复新代次；再次破坏两个实际保存的代次。
    for checkpoint in world.store.list_projection_checkpoints(projector_id="population-recovery:world"):
        world.store.save_projection_checkpoint(checkpoint.model_copy(update={"projection_hash": "corrupt"}))
    fresh = _runtime(path)
    before = fresh.export_recovery_state()
    with pytest.raises(ValueError, match="recovery_checkpoint"):
        _publisher(fresh, InMemoryAuthorityEventBus())
    assert fresh.export_recovery_state() == before


@pytest.mark.parametrize("container", ["{", "{}"], ids=["invalid-json", "missing-fields"])
def test_checkpoint_container_corruption_has_independent_generation_fallback(tmp_path, monkeypatch, container):
    path = tmp_path / "g.db"
    world, _, _, _ = _run(path)
    expected = world.export_recovery_state()
    checkpoints = world.store.list_projection_checkpoints(projector_id="population-recovery:world")
    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE checkpoints SET value=? WHERE id=?", (container, checkpoints[0].checkpoint_id))
    target = _runtime(path)
    reads = []
    original = target.store.read_stream

    def read(stream, **kwargs):
        if stream.startswith("population-cadence:"):
            reads.append(kwargs)
        return original(stream, **kwargs)

    monkeypatch.setattr(target.store, "read_stream", read)
    bus = InMemoryAuthorityEventBus()
    restored = _publisher(target, bus)
    assert restored.replayed_windows == 24
    assert reads[0] == {"from_revision": 17, "limit": 33}
    assert target.export_recovery_state() == expected
    assert bus.list_events(include_realtime=True) == []
    # 回退已修复新代；再破坏两行，不能把坏容器当成从未保存过 checkpoint。
    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE checkpoints SET value=? WHERE projector_id=?", (container, "population-recovery:world"))
    fresh = _runtime(path)
    before = fresh.export_recovery_state()
    with pytest.raises(ValueError, match="recovery_checkpoint_unavailable"):
        _publisher(fresh, InMemoryAuthorityEventBus())
    assert fresh.export_recovery_state() == before


def test_checkpoint_database_read_failure_does_not_try_another_generation(tmp_path):
    path = tmp_path / "g.db"
    _run(path, windows=32)
    target = _runtime(path)
    with sqlite3.connect(path) as connection:
        connection.execute("DROP TABLE checkpoints")
    before = target.export_recovery_state()
    with pytest.raises(GameplayEventStoreSnapshotError) as failure:
        _publisher(target, InMemoryAuthorityEventBus())
    assert str(failure.value.__cause__) == "gameplay_snapshot_read_failed"
    assert target.export_recovery_state() == before


@pytest.mark.parametrize("wrapped", [False, True], ids=["replacement", "functools-wraps"])
def test_kernel_implementation_change_is_rejected_even_without_tail(tmp_path, monkeypatch, wrapped):
    from app.population_continuity import world as module
    from app.population_continuity.recovery import population_kernel_digest

    path = tmp_path / "g.db"
    _run(path, windows=32)
    original = module.advance_b0_row
    original_digest = population_kernel_digest()

    def changed(**kwargs):
        return replace(original(**kwargs), due_ticks=())

    if wrapped:
        changed = wraps(original)(changed)
    monkeypatch.setattr(module, "advance_b0_row", changed)
    assert population_kernel_digest() != original_digest
    target = _runtime(path)
    before = target.export_recovery_state()
    with pytest.raises(ValueError, match="recovery_checkpoint"):
        _publisher(target, InMemoryAuthorityEventBus())
    assert target.export_recovery_state() == before


def test_kernel_digest_is_stable_across_source_paths_and_newlines(tmp_path, monkeypatch):
    from app.population_continuity import recovery, world

    expected = recovery.population_kernel_digest()
    source_root = Path(recovery.__file__).parent
    for source in source_root.glob("*.py"):
        (tmp_path / source.name).write_bytes(source.read_text(encoding="utf-8").replace("\n", "\r\n").encode("utf-8"))
    original = world.advance_b0_row
    relocated = FunctionType(original.__code__.replace(co_filename=str(tmp_path / Path(original.__code__.co_filename).name)),
                             original.__globals__, original.__name__, original.__defaults__, original.__closure__)
    monkeypatch.setattr(recovery, "__file__", str(tmp_path / "recovery.py"))
    monkeypatch.setattr(world, "advance_b0_row", relocated)
    assert recovery.population_kernel_digest() == expected


def test_checkpoint_write_failure_blocks_next_window_and_retries_without_publish(tmp_path, monkeypatch):
    path = tmp_path / "g.db"
    world, publisher, bus, _ = _run(path, windows=15)
    original = world.store.save_projection_checkpoints_atomic

    def fail(checkpoints):
        if any(checkpoint.projector_id == "population-recovery:world" for checkpoint in checkpoints):
            raise OSError("checkpoint offline")
        original(checkpoints)

    monkeypatch.setattr(world.store, "save_projection_checkpoints_atomic", fail)
    cadence = world.build_population_cadence(window_start=900, window_end=960)
    with pytest.raises(OSError, match="checkpoint offline"):
        publisher(cadence)
    assert publisher.confirmed_tick == 900
    assert world.population_hot_state.read("one")["last_update_tick"] == 960
    with pytest.raises(ValueError, match="history_gap"):
        publisher(world.build_population_cadence(window_start=960, window_end=1020))
    monkeypatch.setattr(world.store, "save_projection_checkpoints_atomic", original)
    assert publisher(cadence)
    assert publisher.confirmed_tick == 960
    assert len(bus.list_events(include_realtime=True)) == 16
    restored = _publisher(_runtime(path), InMemoryAuthorityEventBus())
    assert restored.confirmed_tick == 960
    assert restored.replayed_windows == 0


def test_receipt_and_full_checkpoint_roll_back_together(tmp_path):
    path = tmp_path / "g.db"
    world, publisher, _, _ = _run(path, windows=15)
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TRIGGER fail_full BEFORE INSERT ON checkpoints WHEN NEW.projector_id='population-recovery:world' BEGIN SELECT RAISE(ABORT,'full failed'); END")
    cadence = world.build_population_cadence(window_start=900, window_end=960)
    with pytest.raises(GameplayEventStoreSnapshotError):
        publisher(cadence)
    assert world.store.get_projection_checkpoint(f"population-receipt:world:{cadence.cadence_id}") is None
    assert publisher.confirmed_tick == 900
    assert world.store.get_outbox(f"outbox:population-runtime:{cadence.cadence_id}").delivery_state == "delivered"
    with sqlite3.connect(path) as connection:
        connection.execute("DROP TRIGGER fail_full")
    fresh = _runtime(path)
    restored = _publisher(fresh, InMemoryAuthorityEventBus())
    assert restored.confirmed_tick == 960
    assert restored.replayed_windows == 16
    assert world.population_hot_state.export_rows() == fresh.population_hot_state.export_rows()


def test_pending_followed_by_delivered_gap_never_skips_first_window(tmp_path):
    path = tmp_path / "g.db"
    world, _, _, first = _run(path, windows=2)
    world.store.mark_outbox_retryable(f"outbox:population-runtime:{first.cadence_id}", "interrupted delivery")
    fresh = _runtime(path)
    before = fresh.export_recovery_state()
    with pytest.raises(ValueError, match="delivery_gap"):
        _publisher(fresh, InMemoryAuthorityEventBus())
    assert fresh.export_recovery_state() == before


def test_publish_success_then_delivery_write_failure_remains_recoverable(tmp_path, monkeypatch):
    path = tmp_path / "g.db"
    world = _runtime(path)
    bus = InMemoryAuthorityEventBus()
    publisher = _publisher(world, bus)
    cadence = world.build_population_cadence(window_start=0, window_end=60)
    monkeypatch.setattr(world.store, "mark_outbox_delivered", lambda _: (_ for _ in ()).throw(OSError("delivery marker failed")))
    with pytest.raises(OSError):
        publisher(cadence)
    assert len(bus.list_events(include_realtime=True)) == 1
    assert publisher.confirmed_tick == 0
    fresh = _runtime(path)
    recovered_bus = InMemoryAuthorityEventBus()
    recovered = _publisher(fresh, recovered_bus)
    assert recovered(cadence)
    assert len(recovered_bus.list_events(include_realtime=True)) == 1
    assert fresh.store.get_stream_head("population-cadence:world") == 1


def test_driver_rebuild_uses_constant_cursor_without_history_sets(tmp_path):
    from app.world_runtime.population_driver import PopulationCadenceDriver

    world, publisher, _, _ = _run(tmp_path / "g.db", windows=18)
    driver = PopulationCadenceDriver(world_runtime=world, publish_window=publisher, window_size=60, catch_up_limit=2)
    assert driver.current_tick == 1080
    assert not hasattr(driver, "_published_cadence_ids") and not hasattr(driver, "_runtime_history")
    assert not hasattr(world, "published_population_cadence_ids")
    assert not driver.tick(1080).published_cadence_ids
    assert len(driver.tick(1200).published_cadence_ids) == 2


def test_process_exit_after_checkpoint_recovers_without_tail_or_redelivery(tmp_path):
    path = tmp_path / "g.db"
    _run(path, windows=15)
    root = Path(__file__).resolve().parents[2]
    script = '''
import os, sys
from test_population_durable_cadence_recovery import _runtime, _publisher
from app.services.authority_event_bus import InMemoryAuthorityEventBus
world = _runtime(sys.argv[1])
publisher = _publisher(world, InMemoryAuthorityEventBus())
original = world.store.save_projection_checkpoints_atomic
def save(checkpoints):
    original(checkpoints)
    if any(checkpoint.projector_id == "population-recovery:world" for checkpoint in checkpoints):
        os._exit(23)
world.store.save_projection_checkpoints_atomic = save
publisher(world.build_population_cadence(window_start=900, window_end=960))
raise AssertionError("fault cut not reached")
'''
    env = dict(os.environ, PYTHONPATH=os.pathsep.join((str(root / "backend"), str(root / "backend/tests"))))
    process = subprocess.run([sys.executable, "-c", script, str(path)], env=env, cwd=root, capture_output=True, text=True, timeout=30)
    assert process.returncode == 23, process.stderr
    world = _runtime(path)
    bus = InMemoryAuthorityEventBus()
    publisher = _publisher(world, bus)
    assert publisher.confirmed_tick == 960 and publisher.replayed_windows == 0
    assert bus.list_events(include_realtime=True) == []


def test_real_main_assembly_reopens_without_republishing_owner_facts(tmp_path, monkeypatch):
    from app import main

    original_settings = main.settings
    monkeypatch.setattr(main, "settings", main.settings.model_copy(update={"heavenly_graph_path": str(tmp_path / "graph.db")}))
    try:
        main._reset_runtime_state(restore_gameplay=True)
        driver = main._build_population_driver()
        assert driver is not None
        for _ in range(18):
            result = driver.tick(driver.current_tick + 86400)
            assert len(result.published_cadence_ids) == 1 and not result.rejected_windows
        expected = driver.world_runtime.export_recovery_state()
        sequence = main.gameplay_event_store.get_last_global_sequence()
        main._reset_runtime_state(restore_gameplay=True)
        restored = main._build_population_driver()
        assert restored is not None and restored.current_tick == 18 * 86400
        assert restored.world_runtime.export_recovery_state() == expected
        assert main.gameplay_event_store.get_last_global_sequence() == sequence
    finally:
        monkeypatch.setattr(main, "settings", original_settings)
        main.reset_runtime_state()


def test_full_checkpoint_materializes_and_validates_recovery_state_once(tmp_path, monkeypatch):
    from app.population_continuity.recovery import PopulationRecoveryState
    world, publisher, _, _ = _run(tmp_path / 'single-validation.db', windows=15)
    original = PopulationRecoveryState.model_dump
    validations = []
    def dump(state, **kwargs):
        # 原 consistent_state 验证器每次完整验证均计算这份 digest 输入。
        if kwargs.get('exclude') == {'state_digest'}:
            validations.append((state.confirmed_tick, len(state.actors)))
        return original(state, **kwargs)
    monkeypatch.setattr(PopulationRecoveryState, 'model_dump', dump)
    cadence = world.build_population_cadence(window_start=900, window_end=960)
    assert publisher(cadence) is not None
    assert validations == [(960, 2)]
    checkpoints = world.store.list_projection_checkpoints(projector_id='population-recovery:world')
    assert len(checkpoints) == 1
    assert checkpoints[0].state['recovery_state']['confirmed_tick'] == 960


@pytest.mark.parametrize('damage', ['digest', 'field', 'receipt', 'context'])
def test_full_checkpoint_still_rejects_invalid_nested_state_before_saving(tmp_path, monkeypatch, damage):
    from copy import deepcopy
    from app.population_continuity.recovery import recovery_digest
    world, publisher, _, _ = _run(tmp_path / 'invalid-nested.db', windows=15)
    original = world._build_recovery_state_payload
    def damaged():
        state = deepcopy(original())
        if damage == 'digest':
            state['state_digest'] = 'sha256:' + '0' * 64
        else:
            if damage == 'field':
                state['actors'][0]['fatigue'] = 'not-a-number'
            elif damage == 'receipt':
                state['last_receipt']['window_end'] += 1
            else:
                state['context_digest'] = 'sha256:' + '0' * 64
            state['state_digest'] = recovery_digest({k: v for k, v in state.items() if k != 'state_digest'})
        return state
    monkeypatch.setattr(world, '_build_recovery_state_payload', damaged)
    cadence = world.build_population_cadence(window_start=900, window_end=960)
    with pytest.raises(ValueError):
        publisher(cadence)
    assert world.store.list_projection_checkpoints(projector_id='population-recovery:world') == []
    # 公共导出仍完整验证；有效格式但错误世界 context 则由安装边界拒绝。
    if damage != 'context':
        with pytest.raises(ValueError):
            world.export_recovery_state()
    else:
        target = _runtime(tmp_path / 'other.db')
        with pytest.raises(ValueError, match='context_mismatch'):
            target.restore_recovery_state(world.export_recovery_state())
