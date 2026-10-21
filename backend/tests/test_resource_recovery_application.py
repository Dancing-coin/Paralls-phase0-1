"""Production Population callback and real resource owner/Durable store proof."""
import asyncio
from pathlib import Path

import pytest

from app.character_agent.profile.registry import CharacterProfileRegistry
from app.gameplay.event_store import DurableGameplayEventStore
from app.gameplay.resource_body_runtime import ResourceBodyRuntimeProjector
from app.gameplay.resource_materialization import (
    CharacterResourceMaterializationCaller,
    ResourceMaterializationAuthorityService,
)
from test_status_application_lifecycle import application


async def _run(main, callback):
    return await asyncio.wrap_future(main.runtime_execution.submit(callback))


@pytest.mark.asyncio
async def test_resource_recovery_application_population_callback_and_durable_restart(application):
    main, start, advance = application
    await start()
    store = main.gameplay_event_store
    assert isinstance(store, DurableGameplayEventStore)
    first_caller = main.resource_recovery_caller

    def materialize():
        registry = CharacterProfileRegistry.from_directory(
            Path(__file__).resolve().parents[2] / "assets/characters/profiles"
        )
        caller = CharacterResourceMaterializationCaller(
            authority=ResourceMaterializationAuthorityService(store=store, registry=registry)
        )
        driver = main._population_runtime_driver
        return caller.materialize(
            actor_ref="char_a", world_ref=driver.world_runtime.mode.world_ref,
            timeline_ref=driver.clock.timeline.timeline_id,
            world_tick=driver.current_tick, idempotency_key="app:resource-materialize",
            expected_revision=0,
        )

    assert (await _run(main, materialize)).committed
    await advance(86400)
    assert main.resource_recovery_failures == []
    events = await _run(main, lambda: store.read_stream("gameplay:resources:char_a"))
    recovered = [event for event in events if event.event_type == "gameplay.resource.recovered"]
    assert len(recovered) == 3
    assert all(event.visibility_policy == "authority_only" for event in recovered)
    assert all(event.payload["confirmed_world_tick"] == 86400 for event in recovered)
    first_refs = [event.event_id for event in events]

    # run_forever retries the callback at the same confirmed boundary.
    await advance(86400)
    assert main.resource_recovery_failures == []
    assert await _run(main, lambda: [e.event_id for e in store.read_stream("gameplay:resources:char_a")]) == first_refs

    await main._stop_population_runtime_on_shutdown()
    assert store._closed
    await start()
    assert main.gameplay_event_store is not store
    assert main.resource_recovery_caller is not first_caller
    await advance(172800)
    assert main.resource_recovery_failures == []
    new_events = await _run(main, lambda: main.gameplay_event_store.read_stream("gameplay:resources:char_a"))
    assert len(new_events) == 9
    projector = ResourceBodyRuntimeProjector()
    full = projector.rebuild_resources("char_a", new_events)
    tail = projector.rebuild_resources("char_a", new_events[6:],
        checkpoint=projector.rebuild_resources("char_a", new_events[:6]))
    assert tail == full
    assert full.entries["core.stamina"].current == 100
    assert full.entries["core.mana"].current == 80
    assert full.entries["core.action_points"].current == 6
