from app.main import _as_world_result_envelope
from app.world_runtime.models import WorldEntityRef
from app.world_runtime.projection import project_world_result_delta


def test_project_world_result_delta_maps_environment_result_to_delta() -> None:
    payload = {
        "result_type": "environment_state_result",
        "target_environment_id": "env_lamp",
        "producer_ts": 10,
        "current_state": "alerted",
    }

    delta = project_world_result_delta(payload)

    assert delta is not None
    assert delta.entity == WorldEntityRef(entity_type="environment", entity_id="env_lamp")
    assert delta.changed_fields["current_state"] == "alerted"


def test_project_world_result_delta_returns_none_when_no_entity_ref_exists() -> None:
    assert project_world_result_delta({"result_type": "noop"}) is None


def test_world_result_envelope_includes_world_runtime_delta_when_available() -> None:
    payload = {
        "result_id": "result_env_1",
        "result_type": "environment_state_result",
        "room_id": "room_demo",
        "scene_id": "scene_demo",
        "zone_id": "zone_focus",
        "actor_id": "char_a",
        "target_environment_id": "env_lamp",
        "current_state": "alerted",
        "producer_ts": 10,
        "causation_id": "cause_env_1",
        "correlation_id": "corr_env_1",
    }

    envelope = _as_world_result_envelope(payload)

    assert envelope["payload"]["world_runtime_delta"]["entity"] == {
        "entity_type": "environment",
        "entity_id": "env_lamp",
        "zone_id": None,
    }
