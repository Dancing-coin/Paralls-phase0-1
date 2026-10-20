"""Backend-owned timeline follows confirmed cadence, including durable reopen."""
import asyncio
from dataclasses import replace

import pytest

from test_combat_faction_admin_application import runtime


@pytest.mark.asyncio
async def test_runtime_timeline_is_owned_and_resumes_confirmed_cadence(runtime):
    main, payload, start = runtime

    async def command(fn):
        return await asyncio.wrap_future(main.runtime_execution.submit(fn))

    def snapshot():
        driver = main._population_runtime_driver
        return driver.clock.timeline, driver.clock.temporal_profile, driver.current_tick

    timeline, profile, before = await command(snapshot)
    assert timeline.timeline_id == "population:" + payload["world_ref"]
    assert timeline.world_scope_ref == payload["world_ref"]
    assert timeline.advancement_owner_ref == "population-driver:" + payload["world_ref"]
    assert timeline.current_step == before
    assert timeline.profile_revision == profile.revision == "population-seconds:v1"
    assert profile.canonical_unit_ref == "second"

    def invalid_sources():
        driver = main._population_runtime_driver
        original = driver.mapping
        rows = main.gameplay_event_store.read_events()
        for change in ({"source_unit_ref": "frame"}, {"revision": "stale"},
                       {"target_timeline_ref": "population:other"}):
            driver.mapping = replace(original, **change)
            try:
                assert driver.tick(driver.current_tick + driver.window_size).rejected_windows
            finally:
                driver.mapping = original
        assert main.gameplay_event_store.read_events() == rows
        with pytest.raises(ValueError, match="mapped_advance_required"):
            driver.clock.advance(before + driver.window_size)

    await command(invalid_sources)

    def rejected():
        driver = main._population_runtime_driver
        original = driver.publish_window
        driver.publish_window = lambda cadence: None
        try:
            return driver.tick(driver.current_tick + driver.window_size)
        finally:
            driver.publish_window = original

    assert (await command(rejected)).rejected_windows
    assert await command(snapshot) == (timeline, profile, before)

    def advance():
        driver = main._population_runtime_driver
        return driver.tick(driver.current_tick + driver.window_size)

    result = await command(advance)
    assert result.published_cadence_ids and not result.rejected_windows
    advanced, _, confirmed = await command(snapshot)
    assert confirmed > before
    assert advanced.current_step == confirmed
    assert advanced.authoritative_revision == timeline.authoritative_revision + 1
    await main._stop_population_runtime_on_shutdown()
    await start()
    reopened, _, cursor = await command(snapshot)
    assert reopened.timeline_id == timeline.timeline_id
    assert reopened.advancement_owner_ref == timeline.advancement_owner_ref
    assert reopened.profile_revision == profile.revision
    # Startup can confirm another legitimate cadence; it cannot rewind.
    assert cursor >= confirmed
    assert reopened.current_step == cursor
