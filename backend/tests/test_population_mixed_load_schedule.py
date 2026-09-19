from collections import Counter

import pytest

from scripts.verification.population_mixed_load import MixedLoadSchedule


def test_runner_keeps_absolute_arrivals_while_first_request_is_blocked():
    import asyncio
    from scripts.verification.population_mixed_load import MixedLoadRunner

    async def exercise():
        first_started, second_started = asyncio.Event(), asyncio.Event()
        async def health(event):
            if event.ordinal == 1:
                first_started.set()
                await second_started.wait()
            else:
                assert first_started.is_set()
                second_started.set()
            return {"response": "ok", "ordinal": event.ordinal}
        runner = MixedLoadRunner({"health": health}, capacity=2)
        report = await asyncio.wait_for(runner.run(1, MixedLoadSchedule(100, 7, "one_x")), 5)
        assert report["failed"] == 0 and report["dispatched"] == 2
        assert report["peak_in_flight"] == 2
        rows = report["requests"]
        assert rows[1]["expected_at"] - rows[0]["expected_at"] == .5
        assert rows[0]["finished_at"] >= rows[1]["issued_at"]
        assert all(row["issued_at"] >= row["expected_at"] for row in rows)
        assert rows[0]["result"] == {"response": "ok", "ordinal": 1}
        # 调度器只报告调用完成；它没有资格把 handler 返回认定为 authority commit。
        assert "committed" not in report and "passed" not in report
    asyncio.run(exercise())


def test_runner_records_capacity_failure_and_drain_timeout_without_losing_offered_keys():
    import asyncio
    from scripts.verification.population_mixed_load import MixedLoadRunner

    async def exercise():
        async def blocked(event):
            await asyncio.Event().wait()
        runner = MixedLoadRunner({"health": blocked}, capacity=1, drain_seconds=.01)
        report = await runner.run(1, MixedLoadSchedule(100, 7, "one_x"))
        assert report["offered"] == 2 and report["dispatched"] == 1 and report["failed"] == 2
        assert [row["status"] for row in report["requests"]] == ["drain_timeout", "capacity_exhausted"]
        assert len({row["key"] for row in report["requests"]}) == 2
        assert report["peak_in_flight"] == 1
    asyncio.run(exercise())


def test_runner_keeps_a_failed_request_and_continues_the_remaining_recipe():
    import asyncio
    from scripts.verification.population_mixed_load import MixedLoadRunner

    async def exercise():
        async def health(event):
            if event.ordinal == 1:
                raise RuntimeError("private provider error must not enter evidence")
            return {"response": "ok"}
        report = await MixedLoadRunner({"health": health}).run(1, MixedLoadSchedule(100, 1, "one_x"))
        assert report["failed"] == 1 and report["dispatched"] == 2
        assert report["requests"][0]["error"] == "RuntimeError"
        assert "private provider" not in str(report)
        assert report["requests"][1]["status"] == "handler_finished"
    asyncio.run(exercise())


def test_wall_clock_recipe_is_replayable_and_seed_keys_are_disjoint():
    schedule = MixedLoadSchedule(population=100, seed=7, mode="one_x")
    events = list(schedule.events(1800))
    assert events == list(schedule.events(1800))
    assert [event.at_ms for event in events] == sorted(event.at_ms for event in events)
    counts = Counter(event.kind for event in events)
    assert counts == {
        "window_due": 1800, "regular_due": 1800, "due_peak": 6,
        "health": 3600, "ws_read": 1800, "fact": 900, "interaction": 360,
        "owner_contention": 30, "character_model": 30, "siming_model": 30,
        "provider_timeout": 1, "slow_consumer": 1, "resume_consumer": 1,
        "disconnect": 1, "reconnect": 1, "sqlite_busy": 1, "sqlite_release": 1,
    }
    keys = {event.transaction_id for event in events}
    assert len(keys) == len(events)
    assert keys.isdisjoint(event.transaction_id for event in MixedLoadSchedule(100, 8, "one_x").events(1800))
    at_timeout = [event.kind for event in events if event.at_ms == 300_000]
    assert at_timeout.index("provider_timeout") < at_timeout.index("character_model")
    peak = next(event for event in events if event.kind == "due_peak")
    assert peak.at_ms == 300_000 and peak.window_index == 300 and len(peak.actor_indices) == 10
    regular = next(event for event in events if event.kind == "regular_due")
    assert len(regular.actor_indices) == len(set(regular.actor_indices)) == 36


def test_acceleration_changes_windows_not_external_request_or_fault_wall_clock():
    short = list(MixedLoadSchedule(10_000, 0, "ten_x").events(3))
    counts = Counter(event.kind for event in short)
    assert counts == {"window_due": 30, "regular_due": 30, "health": 6, "ws_read": 3, "fact": 1}
    long = list(MixedLoadSchedule(10_000, 0, "ten_x").events(7200))
    peaks = [event for event in long if event.kind == "due_peak"]
    assert peaks[0].at_ms == 30_000 and len(peaks[0].actor_indices) == 100
    faults = [event for event in long if event.kind == "disconnect"]
    assert [event.at_ms for event in faults] == [900_000, 2_700_000, 4_500_000, 6_300_000]
    for start, end, duration_ms in (("disconnect", "reconnect", 2000), ("slow_consumer", "resume_consumer", 5000), ("sqlite_busy", "sqlite_release", 2000)):
        assert [event.at_ms + duration_ms for event in long if event.kind == start] == [event.at_ms for event in long if event.kind == end]
    # 只产生有限前缀；不预建万人或两小时任务列表。
    iterator = MixedLoadSchedule(2, 0, "one_x").events(10**9)
    assert next(iterator).at_ms == 500


@pytest.mark.parametrize("population,seed,mode", [(0, 0, "one_x"), (True, 0, "one_x"), (10, -1, "one_x"), (10, True, "one_x"), (10, 0, "virtual")])
def test_invalid_load_recipe_is_rejected(population, seed, mode):
    with pytest.raises(ValueError):
        MixedLoadSchedule(population, seed, mode)

@pytest.mark.parametrize('late_error', [False, True])
def test_drain_timeout_cannot_be_overwritten_by_cancel_suppressing_handler(late_error):
    import asyncio
    from scripts.verification.population_mixed_load import MixedLoadRunner

    async def exercise():
        async def handler(event):
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                if late_error:
                    raise RuntimeError('late cleanup error')
                return {'cleanup_only': True}
        report = await MixedLoadRunner({'health': handler}, drain_seconds=.01).run(
            1, MixedLoadSchedule(100, 7, 'one_x'))
        assert report['failed'] == report['dispatched'] == report['offered'] == 2
        assert all(row['status'] == 'drain_timeout' for row in report['requests'])
        if late_error:
            assert all(row['error'] == 'RuntimeError' for row in report['requests'])
        else:
            assert all(row['result'] == {'cleanup_only': True} for row in report['requests'])
    asyncio.run(exercise())
