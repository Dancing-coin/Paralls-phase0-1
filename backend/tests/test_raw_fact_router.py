from app.models.raw_fact import RawFactEvent
from app.models.visual_fact import VisualFactEvent
from app.services.fact_router import route_raw_fact_event


def test_raw_fact_event_accepts_visual_fact_nested_shape() -> None:
    event = RawFactEvent(
        fact_family="visual_fact",
        fact_type="fixed_gaze_on_target",
        relation_type="actor_looks_at_actor",
        producer_ts=123,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        source={
            "layer": "L1",
            "system": "godot.raw_fact_emitter",
            "actor_id": "char_c",
        },
        targets={"actor_id": "char_a"},
    )

    assert event.fact_family == "visual_fact"
    assert event.source.actor_id == "char_c"
    assert event.targets.actor_id == "char_a"


def test_raw_fact_event_accepts_spatial_access_nested_shape() -> None:
    event = RawFactEvent(
        fact_family="spatial_access_fact",
        fact_type="actor_entered_zone",
        relation_type="actor_approached_actor",
        producer_ts=200,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_private",
        source={
            "layer": "L1",
            "system": "godot.raw_fact_emitter",
            "actor_id": "char_c",
        },
        targets={"actor_id": "char_a"},
        world={"distance_m": 1.8, "state_before": "public", "state_after": "local"},
        observability={"visual": True, "auditory": True, "occluded": False},
    )

    assert event.world.distance_m == 1.8
    assert event.world.state_after == "local"
    assert event.observability.auditory is True


def test_visual_fact_event_model_dump_returns_canonical_nested_shape() -> None:
    event = VisualFactEvent(
        actor_id="char_c",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        producer_ts=123,
        fact_type="fixed_gaze_on_target",
        relation_type="actor_looks_at_actor",
        target_actor_id="char_a",
    )

    assert event.model_dump() == {
        "event_type": "raw_fact_event",
        "fact_family": "visual_fact",
        "fact_type": "fixed_gaze_on_target",
        "relation_type": "actor_looks_at_actor",
        "producer_ts": 123,
        "room_id": "room_demo",
        "scene_id": "scene_demo",
        "zone_id": "zone_focus",
        "source": {
            "layer": "L1",
            "system": "godot.raw_fact_emitter",
            "actor_id": "char_c",
            "object_id": "",
            "environment_id": "",
        },
        "targets": {
            "actor_id": "char_a",
            "object_id": "",
            "environment_id": "",
        },
        "world": {
            "position": None,
            "distance_m": None,
            "state_before": "",
            "state_after": "",
        },
        "observability": {
            "visual": False,
            "auditory": False,
            "occluded": False,
        },
        "causation_id": "",
        "correlation_id": "",
    }


def test_visual_fact_event_to_legacy_payload_returns_flat_shape() -> None:
    event = VisualFactEvent(
        actor_id="char_c",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        producer_ts=123,
        fact_type="fixed_gaze_on_target",
        relation_type="actor_looks_at_actor",
        target_actor_id="char_a",
    )

    assert event.to_legacy_payload() == {
        "actor_id": "char_c",
        "room_id": "room_demo",
        "scene_id": "scene_demo",
        "zone_id": "zone_focus",
        "producer_ts": 123,
        "fact_type": "fixed_gaze_on_target",
        "relation_type": "actor_looks_at_actor",
        "target_actor_id": "char_a",
        "target_object_id": None,
        "target_environment_id": None,
    }


def test_visual_fact_event_mixed_shape_preserves_nested_values() -> None:
    event = VisualFactEvent(
        actor_id="flat_actor",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        producer_ts=123,
        fact_type="fixed_gaze_on_target",
        relation_type="actor_looks_at_actor",
        target_actor_id="flat_target",
        source={
            "layer": "L1",
            "system": "godot.raw_fact_emitter",
            "actor_id": "nested_actor",
        },
        targets={"actor_id": "nested_target"},
    )

    assert event.actor_id == "nested_actor"
    assert event.target_actor_id == "nested_target"
    assert event.model_dump()["source"]["actor_id"] == "nested_actor"
    assert event.model_dump()["targets"]["actor_id"] == "nested_target"
    assert event.to_legacy_payload()["actor_id"] == "nested_actor"
    assert event.to_legacy_payload()["target_actor_id"] == "nested_target"


def test_raw_fact_router_rejects_unknown_fact_family() -> None:
    event = RawFactEvent(
        fact_family="unsupported_fact",
        fact_type="anything",
        relation_type="",
        producer_ts=321,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        source={
            "layer": "L1",
            "system": "godot.raw_fact_emitter",
            "actor_id": "char_c",
        },
        targets={},
    )

    messages = route_raw_fact_event(
        event,
        source_type="raw_fact_event",
        visual_fact_handler=lambda *_args, **_kwargs: [],
    )

    assert messages == [
        {
            "message_type": "ack",
            "payload": {
                "accepted": False,
                "source_type": "raw_fact_event",
                "route": "unknown_raw_fact_family",
            },
        }
    ]
