"""真实 public 确认才接管 B2；来源/角色各自持久化，不把入站当认知完成。"""
from app.population_continuity.conflict_cadence import PopulationConflictPump
from app.population_continuity.conflict_activation import PopulationConflictSource
from app.population_continuity.runtime_publication import RuntimeCadencePublisher
from app.services.authority_event_bus import InMemoryAuthorityEventBus
from test_population_conflict_source import setup as source_setup
from test_population_conflict_activation import conflict
from test_population_durable_cadence_recovery import _runtime


def setup(tmp_path, *, budget=1):
    store, owner, source, archive, admissions = source_setup(tmp_path)
    world = _runtime(tmp_path / "gameplay.sqlite3", source._actors)
    world.mode = world.mode.model_copy(update={"wake_budget": budget})
    # 同一 owner 的两个库；所有 source 查询使用当前 world store。
    source = PopulationConflictSource(store=world.store, world_ref=world.mode.world_ref, roster=world.roster,
        package_registry=source._packages, profiles=source._profiles, policy=source._policy, admissions=admissions)
    pump = PopulationConflictPump(source=source, store=world.store, world=world, admissions=admissions,
        ttl_seconds=30., wall_clock=lambda: 100.)
    admissions._validate_source = pump.validate_admission
    bus = InMemoryAuthorityEventBus()
    publisher = RuntimeCadencePublisher(world_runtime=world, event_bus=bus,
        room_id="room", scene_id="scene", zone_id="zone", conflict_pump=pump)
    return world, owner, source, archive, admissions, pump, bus, publisher


def tick(world, publisher, ordinal):
    return publisher(world.build_population_cadence(window_start=60 * ordinal, window_end=60 * (ordinal + 1)))


def test_confirmed_cadences_admit_distinct_actors_with_real_budget_and_zero_replay_writes(tmp_path, monkeypatch):
    world, owner, source, archive, admissions, pump, bus, publisher = setup(tmp_path)
    try:
        conflict(owner)
        cadence = world.build_population_cadence(window_start=0, window_end=60)
        assert publisher(cadence) is not None
        first = admissions.list_pending()
        assert len(first) == 1 and first[0].actor_id == "char_a"
        assert first[0].producer_ts == 60 and first[0].expires_at == 130.
        assert first[0].source_kind == "run_background_cognition_tick" and first[0].payload == {}
        assert archive.event_count("char_a") == 0
        monkeypatch.setattr(pump, "wall_clock", lambda: 115.)
        assert publisher(cadence) is not None
        assert admissions.list_pending() == first
        assert tick(world, publisher, 1) is not None
        rows = admissions.list_pending()
        assert len(rows) == 2 and rows[0] == first[0]
        assert rows[1].actor_id == "char_b" and rows[1].producer_ts == 120 and rows[1].expires_at == 145.
        assert source.read().wakes == ()
        assert publisher.last_conflict_error is None
    finally:
        archive.close()


def test_child_prefix_failure_does_not_stop_b0_and_next_cadence_only_admits_remaining(tmp_path, monkeypatch):
    world, owner, source, archive, admissions, pump, bus, publisher = setup(tmp_path, budget=4)
    try:
        conflict(owner)
        admit = admissions.admit
        def fail_second(**kwargs):
            if kwargs["actor_id"] == "char_b":
                raise RuntimeError("child temporarily unavailable")
            return admit(**kwargs)
        monkeypatch.setattr(admissions, "admit", fail_second)
        assert tick(world, publisher, 0) is not None
        first = admissions.list_pending()
        assert len(first) == 1 and publisher.confirmed_tick == 60
        assert publisher.last_conflict_error == "RuntimeError"
        monkeypatch.setattr(admissions, "admit", admit)
        monkeypatch.setattr(pump, "wall_clock", lambda: 125.)
        assert tick(world, publisher, 1) is not None
        assert admissions.list_pending()[0] == first[0]
        assert len(admissions.list_pending()) == 2 and publisher.last_conflict_error is None
    finally:
        archive.close()


def test_unconfirmed_public_and_later_source_change_cannot_admit_children(tmp_path, monkeypatch):
    world, owner, source, archive, admissions, pump, bus, publisher = setup(tmp_path)
    try:
        conflict(owner)
        def fail_public(event):
            raise RuntimeError("public unavailable")
        bus.subscribe("population_cadence_event", fail_public)
        assert tick(world, publisher, 0) is None
        assert admissions.list_pending() == ()
        read = source.read
        def close_after_read():
            result = read()
            conflict(owner, "final", 1)
            return result
        monkeypatch.setattr(source, "read", close_after_read)
        bus._subscribers.clear()
        assert tick(world, publisher, 0) is not None
        assert publisher.last_conflict_error == "ValueError"
        assert admissions.list_pending() == ()
        monkeypatch.setattr(source, "read", read)
        assert tick(world, publisher, 1) is not None
        assert source.read().wakes == () and admissions.list_pending() == ()
    finally:
        archive.close()


def test_dual_database_reopen_keeps_original_child_ttl_and_admits_only_unhandled_source(tmp_path):
    world, owner, source, archive, admissions, pump, bus, publisher = setup(tmp_path)
    conflict(owner)
    cadence = world.build_population_cadence(window_start=0, window_end=60)
    assert publisher(cadence) is not None
    original = admissions.list_pending()[0]
    # 上窗 source checkpoint 仍含两角色；第一个 Character 已原子接管，随后模拟进程丢失全部对象。
    assert world.store.get_projection_checkpoint(source.checkpoint_id).state["source_event_ids"]
    archive.close()
    world, owner, source, archive, admissions, pump, bus, publisher = setup(tmp_path)
    try:
        pump.wall_clock = lambda: 200.
        assert publisher.confirmed_tick == 60
        assert publisher(cadence) is not None
        assert admissions.list_pending() == (original,)
        assert tick(world, publisher, 1) is not None
        rows = admissions.list_pending()
        assert rows[0] == original and rows[0].expires_at == 130.
        assert len(rows) == 2 and rows[1].actor_id == "char_b" and rows[1].expires_at == 230.
        assert source.read().wakes == ()
    finally:
        archive.close()
