"""持续库存命令只追已提交尾部，仍以完整回放校验事实和投影摘要。"""
import pytest

from app.gameplay.event_store import DurableGameplayEventStore, GameplayEventStore
from app.gameplay.inventory_runtime import InventoryAuthorityService, InventoryProjector, InventoryRuntimeError
from app.gameplay.settlement_plan import build_atomic_event_batch
from test_inventory_runtime import ACTOR, _create, _service


def _noise(store, count, key):
    batch = build_atomic_event_batch(command_id=key, principal_ref="test:noise", stream_id="test:noise",
        expected_revision=store.get_stream_head("test:noise"),
        event_specs=[("test.noise", {"ordinal": i}) for i in range(count)],
        idempotency_key=key, causation_id=key, correlation_id=key)
    assert store.append_batch(batch).committed


def _inventory(store):
    _, registry, _ = _service()
    service = InventoryAuthorityService(store=store, registry=registry)
    _create(service, "container:bag")
    _create(service, "container:hand")
    assert service.instantiate(command_id="item", actor_ref=ACTOR, item_id="stone", definition_id="item:stone",
        quantity=2, container_id="container:bag", idempotency_key="item", causation_id="item", correlation_id="item").committed
    return registry, service


@pytest.mark.parametrize("durable", [False, True])
def test_warm_inventory_only_reads_tail_and_sees_other_owner_writes(tmp_path, monkeypatch, durable):
    store = DurableGameplayEventStore(tmp_path / "inventory.db") if durable else GameplayEventStore()
    registry, service = _inventory(store)
    _noise(store, 600, "noise:prefix")
    service._current_inventory(ACTOR)
    other = InventoryAuthorityService(store=store, registry=registry)
    other._current_inventory(ACTOR)
    cut = store.get_last_global_sequence()
    reads = []
    original = store.read_events

    def read(**kwargs):
        assert kwargs.get("limit", 0) > 0
        assert kwargs["global_sequence_after"] >= cut
        rows = original(**kwargs)
        reads.extend(rows)
        return rows

    monkeypatch.setattr(store, "read_events", read)
    for i in range(8):
        # 独立 Owner 写同一账本，也必须在下一次读取中可见。
        owner = service if i % 2 == 0 else other
        assert owner.move(command_id=f"move:{i}", actor_ref=ACTOR, item_id="stone",
            from_container_id="container:bag" if i % 2 == 0 else "container:hand",
            to_container_id="container:hand" if i % 2 == 0 else "container:bag",
            idempotency_key=f"move:{i}", causation_id="move", correlation_id="move").committed
        actual = service._current_inventory(ACTOR)
        assert actual == InventoryProjector(registry).rebuild(ACTOR, original())
    assert len(reads) <= 16
    for action, quantity in (("reserve", 1), ("release", None), ("reserve", 1), ("consume", None)):
        key = f"{action}:{store.get_last_global_sequence()}"
        args = dict(command_id=key, actor_ref=ACTOR, reservation_ref="reservation:test",
            idempotency_key=key, causation_id=key, correlation_id=key)
        if quantity is not None:
            result = service.reserve_item(**args, item_id="stone", quantity=quantity)
        else:
            result = getattr(service, action + "_reservation")(**args)
        assert result.committed
        assert service._current_inventory(ACTOR) == InventoryProjector(registry).rebuild(ACTOR, original())
    monkeypatch.setattr(store, "read_events", original)
    reopened = DurableGameplayEventStore(tmp_path / "inventory.db") if durable else store
    assert InventoryAuthorityService(store=reopened, registry=registry)._current_inventory(ACTOR) == service._current_inventory(ACTOR)


def test_inventory_tail_failure_keeps_prefix_and_lru_is_bounded(monkeypatch):
    store = GameplayEventStore()
    registry, service = _inventory(store)
    prefix = service._current_inventory(ACTOR)
    saved = service._inventory_cache[ACTOR]
    _noise(store, 300, "noise:tail")
    original = store.read_events
    calls = 0

    def fail_second_page(**kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("read failed")
        return original(**kwargs)

    monkeypatch.setattr(store, "read_events", fail_second_page)
    with pytest.raises(RuntimeError, match="read failed"):
        service._current_inventory(ACTOR)
    assert service._inventory_cache[ACTOR] == saved
    monkeypatch.setattr(store, "read_events", original)
    assert service._current_inventory(ACTOR) == prefix
    for i in range(40):
        service._current_inventory(f"actor:{i}")
        assert len(service._inventory_cache) <= 32
    assert ACTOR not in service._inventory_cache
    assert service._current_inventory(ACTOR) == InventoryProjector(registry).rebuild(ACTOR, original())


def test_inventory_incremental_resolves_old_cross_domain_source_and_rejects_bad_source(monkeypatch):
    from test_inf3ab_grain_harvest_inventory_custody import _source, _inventory, _request, PROVIDER

    store, source = _source()
    service = _inventory(store)
    service._current_inventory(PROVIDER)
    assert service.record_grain_harvest_custody_receipt(**_request(store, source)).committed
    saved = service._inventory_cache[PROVIDER]
    original = store.get_event
    monkeypatch.setattr(store, "get_event", lambda ref: source.model_copy(update={"visibility_policy":"authority_only"}) if ref == source.event_id else original(ref))
    with pytest.raises(InventoryRuntimeError, match="replay_invalid"):
        service._current_inventory(PROVIDER)
    assert service._inventory_cache[PROVIDER] == saved
    monkeypatch.setattr(store, "get_event", original)
    assert service._current_inventory(PROVIDER) == service._projector.rebuild(PROVIDER, store.read_events())


def test_inventory_failed_append_never_installs_proposed_move(monkeypatch):
    store = GameplayEventStore()
    registry, service = _inventory(store)
    prefix = service._current_inventory(ACTOR)
    cut = store.get_last_global_sequence()
    args = dict(command_id="move", actor_ref=ACTOR, item_id="stone", from_container_id="container:bag",
        to_container_id="container:hand", idempotency_key="move", causation_id="move", correlation_id="move")
    with monkeypatch.context() as failure:
        failure.setattr(store, "append_batch", lambda _: (_ for _ in ()).throw(RuntimeError("write failed")))
        with pytest.raises(RuntimeError, match="write failed"):
            service.move(**args)
    assert store.get_last_global_sequence() == cut
    assert service._current_inventory(ACTOR) == prefix
    assert service.move(**args).committed
    assert service._current_inventory(ACTOR) == InventoryProjector(registry).rebuild(ACTOR, store.read_events())
