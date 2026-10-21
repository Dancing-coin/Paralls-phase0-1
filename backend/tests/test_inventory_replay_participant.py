"""Complete Inventory projection in the existing scoped replay cut."""
import asyncio
from copy import deepcopy

import pytest

from app.gameplay.inventory_runtime import ContainerSpec, InventoryProjector
from app.world_runtime.replay_checkpoint import _tail_hash
from test_status_application_lifecycle import application
from test_world_batch_settlement_application import inputs, submit
from test_world_replay_checkpoint_application import capture, tail_call


ACTOR = "actor:inventory-replay"


async def _run(main, callback):
    return await asyncio.wrap_future(main.runtime_execution.submit(callback))


async def _prepare(application):
    main, start, advance = application
    await start()
    await advance(86400)
    plan, window = inputs(main)
    await submit(main, plan=plan, window=window, budget=0)

    def seed():
        owner = main.inventory_authority_service
        args = dict(actor_ref=ACTOR, causation_id="replay", correlation_id="replay")
        assert owner.create_container(command_id="inv:bag", spec=ContainerSpec("container:bag", 20, 20, 4),
            idempotency_key="bag", **args).committed
        assert owner.instantiate(command_id="inv:item", item_id="item:bread:replay", definition_id="item:bread@1",
            quantity=3, container_id="container:bag", idempotency_key="item", **args).committed
        assert owner.reserve_item(command_id="inv:reserve", item_id="item:bread:replay",
            reservation_ref="reservation:replay", quantity=1, idempotency_key="reserve", **args).committed
        assert owner.reserve_commerce_capacity(command_id="inv:capacity", capacity_reservation_ref="capacity:replay",
            available_quantity=2, idempotency_key="capacity", **args).committed

    await _run(main, seed)
    return main, start


@pytest.mark.asyncio
async def test_inventory_full_projection_checkpoint_tail_after_durable_reopen(application, monkeypatch):
    main, start = await _prepare(application)
    cut = await capture(main)
    assert cut.status == "consistent", cut.diagnostics
    saved = cut.checkpoint.state["participants"]
    assert saved["versions"]["inventory_domain"] == 1
    row = saved["inventory_domain"]["actors"][ACTOR]
    assert row["items"]["item:bread:replay"]["reserved_quantity"] == 1
    assert row["reservations"]["reservation:replay"]["quantity"] == 1
    assert row["capacity_reservations"]["capacity:replay"]["available_quantity"] == 2

    def settle():
        owner = main.inventory_authority_service
        args = dict(actor_ref=ACTOR, causation_id="replay", correlation_id="replay")
        assert owner.consume_reservation(command_id="inv:consume", reservation_ref="reservation:replay",
            idempotency_key="consume", **args).committed

    await _run(main, settle)
    tail = await tail_call(main)
    assert tail.status == "verified", tail.diagnostics
    old_store = main.gameplay_event_store
    await main._stop_population_runtime_on_shutdown()
    await start()
    assert main.gameplay_event_store is not old_store
    checkpoints = []
    original = InventoryProjector.rebuild

    def observe(self, actor_ref, events, *, checkpoint=None, referenced_events=None):
        if checkpoint is not None:
            checkpoints.append(checkpoint)
        return original(self, actor_ref, events, checkpoint=checkpoint, referenced_events=referenced_events)

    monkeypatch.setattr(InventoryProjector, "rebuild", observe)
    before = await _run(main, lambda: main.gameplay_event_store.export_snapshot())
    result = await tail_call(main, tail.payload)
    assert result.status == "verified", result.diagnostics
    assert result.result["result_digest"] == result.result["full_digest"]
    assert checkpoints and checkpoints[0].reservations["reservation:replay"].quantity == 1
    current = result.result["participants"]["inventory_domain"]["actors"][ACTOR]
    assert current["items"]["item:bread:replay"]["quantity"] == 2
    assert current["reservations"] == {}
    assert await _run(main, lambda: main.gameplay_event_store.export_snapshot()) == before


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", ["state", "event_ref", "digest", "version", "omit"])
async def test_inventory_domain_corruption_is_zero_write(application, fault):
    main, _ = await _prepare(application)
    assert (await capture(main)).status == "consistent"
    tail = await tail_call(main)
    assert tail.status == "verified", tail.diagnostics
    bad = deepcopy(tail.payload)
    participant = bad["participants"]["inventory_domain"]
    if fault == "state":
        participant["actors"][ACTOR]["locations"]["item:bread:replay"] = "container:forged"
    elif fault == "event_ref":
        participant["event_refs"][0]["event_digest"] = "forged"
    elif fault == "digest":
        participant["view_digest"] = "forged"
    elif fault == "version":
        bad["participants"]["versions"]["inventory_domain"] = 99
    else:
        del bad["participants"]["inventory_domain"]
    bad["digest"] = _tail_hash(bad)
    before = await _run(main, lambda: main.gameplay_event_store.export_snapshot())
    result = await tail_call(main, bad)
    assert result.status in {"incomplete", "divergent"}
    assert result.result is None
    assert await _run(main, lambda: main.gameplay_event_store.export_snapshot()) == before


@pytest.mark.asyncio
async def test_inventory_actor_added_after_cut_replays_without_recapture(application):
    main, start, advance = application
    await start()
    await advance(86400)
    plan, window = inputs(main)
    await submit(main, plan=plan, window=window, budget=0)
    cut = await capture(main)
    assert cut.status == "consistent", cut.diagnostics
    assert ACTOR not in cut.checkpoint.state["participants"]["inventory_domain"]["actors"]
    assert (await _run(main, lambda: main.inventory_authority_service.create_container(
        command_id="inv:added", actor_ref=ACTOR, spec=ContainerSpec("container:added", 10, 10, 1),
        idempotency_key="added", causation_id="replay", correlation_id="replay"))).committed
    tail = await tail_call(main)
    assert tail.status == "verified", tail.diagnostics
    old_store = main.gameplay_event_store
    await main._stop_population_runtime_on_shutdown()
    await start()
    assert main.gameplay_event_store is not old_store
    before = await _run(main, lambda: main.gameplay_event_store.export_snapshot())
    result = await tail_call(main, tail.payload)
    assert result.status == "verified", result.diagnostics
    assert result.result["participants"]["inventory_domain"]["actors"][ACTOR]["containers"]["container:added"]["capacity_weight"] == 10
    assert result.result["full_digest"] == result.result["result_digest"]
    assert await _run(main, lambda: main.gameplay_event_store.export_snapshot()) == before


@pytest.mark.parametrize("fault", ["schema", "unknown_type", "wrong_stream", "wrong_actor"])
def test_inventory_domain_event_scope_cannot_be_silently_dropped(monkeypatch, fault):
    from app.gameplay.event_store import GameplayEventStore
    from app.gameplay.inventory_runtime import InventoryAuthorityService, InventoryDefinitionRegistry
    from app.world_runtime.replay_participants import _inventory_domain_participant

    store = GameplayEventStore()
    authority = InventoryAuthorityService(store=store, registry=InventoryDefinitionRegistry())
    assert authority.create_container(command_id="inv:scope", actor_ref=ACTOR,
        spec=ContainerSpec("container:scope", 10, 10, 1), idempotency_key="scope",
        causation_id="scope", correlation_id="scope").committed
    event = store.read_stream(f"gameplay:inventory:{ACTOR}")[0]
    updates = {"schema": {"schema_version": 99},
        "unknown_type": {"event_type": "gameplay.inventory.unknown"},
        "wrong_stream": {"stream_id": "gameplay:other:actor"},
        "wrong_actor": {"payload": dict(event.payload, actor_ref="actor:wrong")}}[fault]
    monkeypatch.setattr(store, "read_events", lambda: [event.model_copy(update=updates)])
    with pytest.raises(ValueError, match="replay_inventory_domain_event_scope_unsupported"):
        _inventory_domain_participant(store, authority)
