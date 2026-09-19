import asyncio
from threading import Thread, get_ident

from app.debug_stream import DebugStream


def test_snapshot_and_subscribe_captures_history_and_future_events_without_gap() -> None:
    stream = DebugStream()
    first = stream.publish({"message_type": "debug", "summary": "first"})

    history, queue = stream.snapshot_and_subscribe()
    second = stream.publish({"message_type": "debug", "summary": "second"})

    assert [event["sequence"] for event in history] == [first["sequence"]]
    assert queue.get_nowait()["sequence"] == second["sequence"]

    try:
        queue.get_nowait()
    except asyncio.QueueEmpty:
        pass
    else:
        raise AssertionError("queue should only contain future events after snapshot subscription")

    stream.unsubscribe(queue)


def test_owner_publish_wakes_loop_waiter_with_an_independent_snapshot() -> None:
    async def check() -> None:
        stream = DebugStream()
        queue = stream.subscribe()
        loop_thread = get_ident()
        original_put = queue.put_nowait

        def checked_put(value):
            assert get_ident() == loop_thread
            original_put(value)

        queue.put_nowait = checked_put
        waiter = asyncio.create_task(queue.get())
        await asyncio.sleep(0)
        source = {"detail": {"actors": ["a"]}}
        errors = []

        def publish():
            try:
                returned = stream.publish(source)
                returned["detail"]["actors"].append("returned")
                source["detail"]["actors"].append("source")
            except BaseException as exc:
                errors.append(exc)

        worker = Thread(target=publish)
        worker.start()
        worker.join(timeout=1)
        assert not worker.is_alive()
        assert not errors
        event = await asyncio.wait_for(waiter, 1)
        assert event["detail"]["actors"] == ["a"]
        event["detail"]["actors"].append("subscriber")
        history = stream.history()
        assert history[0]["detail"]["actors"] == ["a"]
        history[0]["detail"]["actors"].append("history")
        assert stream.history()[0]["detail"]["actors"] == ["a"]
        stream.unsubscribe(queue)

    asyncio.run(check(), debug=True)


def test_unsubscribe_discards_already_scheduled_owner_delivery() -> None:
    async def check() -> None:
        stream = DebugStream()
        queue = stream.subscribe()
        worker = Thread(target=lambda: stream.publish({"summary": "late"}))
        worker.start()
        worker.join(timeout=1)
        assert not worker.is_alive()
        stream.unsubscribe(queue)
        await asyncio.sleep(0)
        assert queue.empty()

    asyncio.run(check(), debug=True)


def test_debug_overflow_closes_slow_subscription_without_stalling_fast_one() -> None:
    async def check() -> None:
        stream = DebugStream()
        slow = stream.subscribe()
        fast = stream.subscribe()
        for index in range(105):
            await asyncio.to_thread(stream.publish, {"summary": str(index)})
            event = await asyncio.wait_for(fast.get(), 1)
            assert event["sequence"] == index + 1
        assert slow.qsize() == 1
        assert slow.get_nowait() is None
        stream.unsubscribe(fast)

    asyncio.run(check(), debug=True)


def test_owner_burst_schedules_only_one_bounded_drain() -> None:
    async def check() -> None:
        from unittest.mock import patch

        stream = DebugStream()
        queue = stream.subscribe()
        loop = asyncio.get_running_loop()
        with patch.object(loop, "call_soon_threadsafe", wraps=loop.call_soon_threadsafe) as schedule:
            worker = Thread(target=lambda: [stream.publish({"summary": str(i)}) for i in range(1000)])
            worker.start()
            worker.join(timeout=2)
            assert not worker.is_alive()
            assert schedule.call_count == 1
        await asyncio.sleep(0)
        assert queue.qsize() == 1
        assert queue.get_nowait() is None

    asyncio.run(check(), debug=True)


def test_reset_terminates_old_subscription_and_restarts_history_cut() -> None:
    async def check() -> None:
        stream = DebugStream()
        old = stream.subscribe()
        await asyncio.to_thread(stream.publish, {"summary": "old"})
        await asyncio.to_thread(stream.clear)
        assert await asyncio.wait_for(old.get(), 1) is None
        stream.publish({"summary": "new"})
        history, current = stream.snapshot_and_subscribe()
        assert [(event["sequence"], event["summary"]) for event in history] == [(1, "new")]
        stream.publish({"summary": "next"})
        assert (await asyncio.wait_for(current.get(), 1))["sequence"] == 2
        assert old.empty()
        stream.unsubscribe(current)

    asyncio.run(check(), debug=True)
