from fastapi.testclient import TestClient

from app.main import app, reset_runtime_state, siming_audit_writer
from app.models.siming_runtime_state import NarrativeReadModel


def test_audit_writer_returns_latest_read_model_by_room() -> None:
    reset_runtime_state()
    first = NarrativeReadModel(
        read_model_id="read:room_demo:1",
        schema_version=1,
        producer_system="siming.read_model",
        room_id="room_demo",
        scene_scope="scene/zone",
        world_ts=1,
        sim_tick_ts=2,
    )
    second = first.model_copy(
        update={"read_model_id": "read:room_demo:2", "world_ts": 2, "sim_tick_ts": 3}
    )

    siming_audit_writer.record_read_model(first)
    siming_audit_writer.record_read_model(second)

    latest = siming_audit_writer.latest_read_model(room_id="room_demo")
    assert latest is not None
    assert latest.read_model_id == "read:room_demo:2"


def test_debug_read_model_endpoint_returns_latest_model() -> None:
    reset_runtime_state()
    siming_audit_writer.record_read_model(
        NarrativeReadModel(
            read_model_id="read:room_demo:1",
            schema_version=1,
            producer_system="siming.read_model",
            room_id="room_demo",
            scene_scope="scene/zone",
            world_ts=1,
            sim_tick_ts=2,
            narrative_surface={"active_phase": "rising"},
        )
    )

    response = TestClient(app).get("/debug/siming/read-model/room_demo")

    assert response.status_code == 200
    assert response.json()["read_model_id"] == "read:room_demo:1"
    assert response.json()["narrative_surface"]["active_phase"] == "rising"
