from app.services.event_trace_service import EventTraceService


def test_event_trace_records_observable_steps() -> None:
    trace = EventTraceService()
    trace.record("player_connected")
    trace.record("dialogue_response")
    trace.record("action_resolution_result")
    assert trace.summary() == [
        "player_connected",
        "dialogue_response",
        "action_resolution_result",
    ]
