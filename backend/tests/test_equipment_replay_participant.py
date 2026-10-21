"""Equipment domain checkpoint recovery inside the existing mixed-owner cut."""
from copy import deepcopy
from dataclasses import replace

import pytest

from app.gameplay.equipment_runtime import EquipmentProjector
from app.gameplay.inventory_runtime import ItemDefinition
from app.world_runtime.replay_checkpoint import _tail_hash
from test_equipment_stage3_recovery import ACTOR, _body, _seed, _service
from test_resource_replay_participant import _prepare, _run
from test_status_application_lifecycle import application
from test_world_replay_checkpoint_application import capture, tail_call


async def _prepare_equipment(application):
    main, start, advance = await _prepare(application)
    assert (await _equip(main)).committed
    return main, start, advance


async def _equip(main):
    def equip():
        main.inventory_authority_service._registry.register_item(ItemDefinition("item:sword", "1", 3, 2))
        inventory, _, owner = _service(main.gameplay_event_store)
        _seed(main.gameplay_event_store, inventory)
        return owner.equip(command_id="cmd:equip", actor_ref=ACTOR, item_id="item:sword:1",
            source_container_id="container:bag", slot_key="right_hand", body=_body(),
            idempotency_key="equip", causation_id="cause", correlation_id="corr")

    return await _run(main, equip)


async def _unequip(main):
    return await _run(main, lambda: _service(main.gameplay_event_store)[2].unequip(
        command_id="cmd:unequip", actor_ref=ACTOR, activation_id="activation:cmd:equip",
        destination_container_id="container:hand", body=_body(), idempotency_key="unequip",
        causation_id="cause", correlation_id="corr"))


@pytest.mark.asyncio
async def test_equipment_mixed_cut_restores_active_checkpoint_after_durable_reopen(application, monkeypatch):
    main, start, _ = await _prepare_equipment(application)
    cut = await capture(main)
    assert cut.status == "consistent", cut.diagnostics
    saved = cut.checkpoint.state["participants"]
    assert saved["versions"]["equipment"] == 1
    assert "resource" in saved
    row = saved["equipment"]["actors"][ACTOR]
    assert row["active_by_slot"] == {"right_hand": "activation:cmd:equip"}
    assert row["activations"]["activation:cmd:equip"]["modifier_instance_ids"]
    assert (await _unequip(main)).committed
    tail = await tail_call(main)
    assert tail.status == "verified", tail.diagnostics
    old_store = main.gameplay_event_store
    await main._stop_population_runtime_on_shutdown()
    await start()
    assert main.gameplay_event_store is not old_store
    main.inventory_authority_service._registry.register_item(ItemDefinition("item:sword", "1", 3, 2))
    checkpoints = []
    original = EquipmentProjector.rebuild

    def observe(self, actor_ref, events, *, checkpoint=None):
        if checkpoint is not None:
            checkpoints.append(checkpoint)
        return original(self, actor_ref, events, checkpoint=checkpoint)

    monkeypatch.setattr(EquipmentProjector, "rebuild", observe)
    before = await _run(main, lambda: main.gameplay_event_store.export_snapshot())
    result = await tail_call(main, tail.payload)
    assert result.status == "verified", result.diagnostics
    assert result.result["result_digest"] == result.result["full_digest"]
    assert checkpoints and checkpoints[0].active_by_slot == {"right_hand": "activation:cmd:equip"}
    restored = checkpoints[0].activations["activation:cmd:equip"]
    assert list(restored.ability_grant_ids) == row["activations"]["activation:cmd:equip"]["ability_grant_ids"]
    assert list(restored.modifier_instance_ids) == row["activations"]["activation:cmd:equip"]["modifier_instance_ids"]
    state = result.result["participants"]["equipment"]["actors"][ACTOR]
    assert state["activations"] == state["active_by_slot"] == {}
    assert state["ended_activation_ids"] == ["activation:cmd:equip"]
    assert await _run(main, lambda: main.gameplay_event_store.export_snapshot()) == before


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", ["state", "event_ref", "digest", "decoder", "omit", "version_omitted"])
async def test_equipment_participant_corruption_is_zero_write(application, fault):
    main, _, _ = await _prepare_equipment(application)
    assert (await capture(main)).status == "consistent"
    tail = await tail_call(main)
    assert tail.status == "verified", tail.diagnostics
    bad = deepcopy(tail.payload)
    equipment = bad["participants"]["equipment"]
    if fault == "state":
        equipment["actors"][ACTOR]["activations"]["activation:cmd:equip"]["modifier_instance_ids"] = []
    elif fault == "event_ref":
        equipment["event_refs"][0]["event_digest"] = "changed"
    elif fault == "digest":
        equipment["view_digest"] = "changed"
    elif fault == "decoder":
        bad["participants"]["versions"]["equipment"] = 99
    elif fault == "omit":
        del bad["participants"]["equipment"]
    else:
        del bad["participants"]["versions"]["equipment"]
    bad["digest"] = _tail_hash(bad)
    before = await _run(main, lambda: main.gameplay_event_store.export_snapshot())
    result = await tail_call(main, bad)
    assert result.status in {"incomplete", "divergent"}
    assert result.result is None
    assert await _run(main, lambda: main.gameplay_event_store.export_snapshot()) == before


def test_equipment_projector_checkpoint_tail_preserves_multislot_and_ended_history():
    from test_equipment_runtime import _service as runtime_service, _create_sword, _create_greatsword, _body as runtime_body
    from test_equipment_runtime import ACTOR as actor

    store, inventory, owner = runtime_service()
    _create_sword(store, inventory)
    _create_greatsword(store, inventory)
    assert owner.equip(command_id="two-hands", actor_ref=actor, item_id="item:greatsword:1",
        source_container_id="container:bag", slot_key="right_hand", body=runtime_body(),
        idempotency_key="two-hands", causation_id="cause", correlation_id="corr").committed
    events = store.read_stream(f"gameplay:equipment:{actor}")
    projector = EquipmentProjector()
    checkpoint = projector.rebuild(actor, events)
    assert len(checkpoint.active_by_slot) == 2
    boundary = store.get_last_global_sequence()
    assert owner.unequip(command_id="remove", actor_ref=actor, activation_id="activation:two-hands",
        destination_container_id="container:bag", body=runtime_body(), idempotency_key="remove",
        causation_id="cause", correlation_id="corr").committed
    events = store.read_stream(f"gameplay:equipment:{actor}")
    tail = [event for event in events if event.global_sequence > boundary]
    resumed = projector.rebuild(actor, tail, checkpoint=checkpoint)
    assert resumed == projector.rebuild(actor, events)
    assert projector.rebuild(actor, [], checkpoint=resumed) == resumed
    assert len(checkpoint.active_by_slot) == 2  # restoring must not mutate saved state
    with pytest.raises(ValueError, match="equipment_checkpoint_actor_mismatch"):
        projector.rebuild(actor, tail, checkpoint=replace(checkpoint, actor_ref="other"))
    with pytest.raises(ValueError, match="equipment_checkpoint_digest_invalid"):
        projector.rebuild(actor, tail, checkpoint=replace(checkpoint, active_by_slot={}))


@pytest.mark.asyncio
async def test_equipment_added_after_cut_replays_without_recapture(application):
    main, start, _ = await _prepare(application)
    cut = await capture(main)
    assert cut.status == "consistent", cut.diagnostics
    assert cut.checkpoint.state["participants"]["equipment"]["actors"] == {}
    assert (await _equip(main)).committed
    tail = await tail_call(main)
    assert tail.status == "verified", tail.diagnostics
    old_store = main.gameplay_event_store
    await main._stop_population_runtime_on_shutdown()
    await start()
    assert main.gameplay_event_store is not old_store
    main.inventory_authority_service._registry.register_item(ItemDefinition("item:sword", "1", 3, 2))
    before = await _run(main, lambda: main.gameplay_event_store.export_snapshot())
    result = await tail_call(main, tail.payload)
    assert result.status == "verified", result.diagnostics
    assert result.result["participants"]["equipment"]["actors"][ACTOR]["active_by_slot"] == {
        "right_hand": "activation:cmd:equip"}
    assert result.result["full_digest"] == result.result["result_digest"]
    assert await _run(main, lambda: main.gameplay_event_store.export_snapshot()) == before


@pytest.mark.parametrize("fault", ["schema", "unknown_type", "wrong_stream", "wrong_actor"])
def test_equipment_event_scope_cannot_be_silently_dropped(monkeypatch, fault):
    from app.gameplay.event_store import GameplayEventStore
    from app.world_runtime.replay_participants import _equipment_participant

    store = GameplayEventStore()
    inventory, _, owner = _service(store)
    _seed(store, inventory)
    assert owner.equip(command_id="cmd:equip", actor_ref=ACTOR, item_id="item:sword:1",
        source_container_id="container:bag", slot_key="right_hand", body=_body(),
        idempotency_key="equip", causation_id="cause", correlation_id="corr").committed
    event = store.read_stream(f"gameplay:equipment:{ACTOR}")[0]
    updates = {"schema": {"schema_version": 99},
        "unknown_type": {"event_type": "gameplay.equipment.unknown"},
        "wrong_stream": {"stream_id": "gameplay:other:actor"},
        "wrong_actor": {"payload": dict(event.payload, actor_ref="actor:wrong")}}[fault]
    monkeypatch.setattr(store, "read_events", lambda: [event.model_copy(update=updates)])
    with pytest.raises(ValueError, match="replay_equipment_event_scope_unsupported"):
        _equipment_participant(store)
