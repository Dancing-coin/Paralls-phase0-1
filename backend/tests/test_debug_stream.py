import asyncio

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
