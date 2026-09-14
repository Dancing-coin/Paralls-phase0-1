from __future__ import annotations

import asyncio
import json

import pytest

from app.population_continuity.roster import POPULATION_ACTOR_IDS


@pytest.mark.asyncio
async def test_daily_runtime_advances_all_residents_and_resumes_after_restart(monkeypatch, record_property):
    from app import main

    main.stop_population_runtime()
    main.reset_runtime_state()
    runtime = main.character_agent_runtime
    revisions = {actor: runtime.get_continuity_revision(actor) for actor in POPULATION_ACTOR_IDS}
    memories = {actor: runtime.get_memory_record_bundle(actor) for actor in POPULATION_ACTOR_IDS}
    timeline_sizes = {actor: len(runtime.get_session_timeline(actor)) for actor in POPULATION_ACTOR_IDS}
    truth_before = len(main.gameplay_event_store.read_events())
    observed = []
    main.authority_event_bus.subscribe(
        "population_cadence_event", observed.append, consumer_id="continuous-runtime-proof"
    )
    wake_count = 0

    async def controlled_sleep(seconds):
        nonlocal wake_count
        assert seconds == 86400
        wake_count += 1
        if wake_count == 12:
            main._population_runtime_stop_event.set()
        await asyncio.sleep(0)

    monkeypatch.setattr(main, "_population_runtime_sleep", controlled_sleep)
    try:
        task = main.start_population_runtime()
        assert task is not None and main.start_population_runtime() is task
        await task
        assert len(observed) == 12
        assert all(runtime.get_continuity_revision(actor) > revisions[actor] for actor in POPULATION_ACTOR_IDS)
        # 工作记忆保留连续状态审计；五类长期记忆不能凭 routine 生成内容。
        assert all(runtime.get_memory_record_bundle(actor) == memories[actor] for actor in POPULATION_ACTOR_IDS)
        assert all(not event["payload"].get("memory_candidate_refs") for actor in POPULATION_ACTOR_IDS
                   for event in runtime.get_session_timeline(actor)[timeline_sizes[actor]:]
                   if event["event_type"] == "character_simulation_seed_event")
        assert len(main.gameplay_event_store.read_events()) == truth_before
        assert all(not runtime.supports_actor(actor) for actor in POPULATION_ACTOR_IDS if actor.startswith("resident_"))
        windows = [event.payload["population_cadence"] for event in observed]
        assert all(row["selector_revision"] == "selector:generic:population:v1" for row in windows)
        assert all(row["window_end"] - row["window_start"] == 86400 for row in windows)
        assert all(left["window_end"] == right["window_start"] for left, right in zip(windows, windows[1:]))
        confirmed = main._population_runtime_driver.current_tick
        assert not main._population_runtime_driver.tick(confirmed).published_cadence_ids
        assert len(observed) == 12

        main.stop_population_runtime()
        wake_count = 11
        restarted = main.start_population_runtime()
        assert restarted is not None
        await restarted
        assert len(observed) == 13
        last = observed[-1].payload["population_cadence"]
        assert last["window_start"] == confirmed
        assert main._population_runtime_driver.current_tick == last["window_end"]
        assert len({event.event_id for event in observed}) == 13
        record_property("continuous_runtime_evidence", json.dumps({
            "window_count": len(observed), "actor_ids": list(POPULATION_ACTOR_IDS),
            "window_size": 86400, "restart_scope": "same_process",
            "resumed_at": confirmed, "memory_unchanged": True, "routine_world_writes": 0,
        }))
    finally:
        await main._shutdown_population_runtime()
