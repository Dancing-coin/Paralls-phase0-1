import pytest

from test_siming_esm_protocol_stub import _make_siming_env_event


@pytest.mark.parametrize("change, expected", [("light_level_drop", "environment_state_result"),
                                               ("unsupported", "constraint_state_result")])
def test_real_bus_subscription_delivers_to_esm_and_returns_correlated_result(change, expected):
    from app import main
    main.reset_runtime_state()
    event = _make_siming_env_event(room_id="room_demo")
    event.payload["requested_change_type"] = change
    main.authority_event_bus.publish(event)
    results = [item for item in main.authority_event_bus.list_events(room_id=event.room_id)
        if item.correlation_id == event.correlation_id and item.payload.get("result_type") == expected]
    assert len(results) == 1
    assert results[0].payload["request_ref"] == event.event_id
    assert results[0].source.system == "esm"
    if change == "unsupported":
        assert not any(item.payload.get("result_type") == "environment_state_result"
            for item in main.authority_event_bus.list_events(room_id=event.room_id)
            if item.correlation_id == event.correlation_id)
