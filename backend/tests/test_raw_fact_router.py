from app.models.raw_fact import RawFactEvent
from app.models.visual_fact import VisualFactEvent
from app.services.fact_handlers.spatial_access_fact_handler import SpatialAccessFactHandler
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


def test_raw_fact_event_accepts_effect_semantics_fields() -> None:
    event = RawFactEvent(
        fact_family="spatial_access_fact",
        fact_type="actor_entered_zone",
        relation_type="actor_entered_zone",
        producer_ts=700,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        source={
            "layer": "L1",
            "system": "godot.raw_fact_emitter",
            "actor_id": "char_c",
        },
        targets={},
        effect_kind="set",
        subject_key="current_zone_id",
        ttl_ms=1500,
    )

    assert event.effect_kind == "set"
    assert event.subject_key == "current_zone_id"
    assert event.ttl_ms == 1500


def test_raw_fact_event_accepts_auditory_fact_shape() -> None:
    event = RawFactEvent(
        fact_family="auditory_fact",
        fact_type="speaker_active",
        relation_type="speech_mode_changed",
        producer_ts=710,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        source={
            "layer": "L1",
            "system": "godot.raw_fact_emitter",
            "actor_id": "char_a",
        },
        targets={"actor_id": "char_c"},
        observability={"auditory": True},
        acoustics={
            "loudness_band": "medium",
            "speech_mode": "normal",
            "reachability": "clear",
            "ambient_noise": "quiet",
        },
    )

    assert event.fact_family == "auditory_fact"
    assert event.observability.auditory is True
    assert event.acoustics.loudness_band == "medium"
    assert event.acoustics.speech_mode == "normal"
    assert event.acoustics.reachability == "clear"
    assert event.acoustics.ambient_noise == "quiet"


def test_raw_fact_event_accepts_expanded_auditory_fact_taxonomy() -> None:
    fact_types = [
        ("auditory_reachability_changed", "auditory_reachability_changed"),
        ("ambient_noise_changed", "auditory_context_shift"),
    ]

    for fact_type, relation_type in fact_types:
        event = RawFactEvent(
            fact_family="auditory_fact",
            fact_type=fact_type,
            relation_type=relation_type,
            producer_ts=711,
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            source={
                "layer": "L1",
                "system": "godot.raw_fact_emitter",
                "actor_id": "char_a",
            },
            targets={"actor_id": "char_c"},
            observability={"auditory": True},
            acoustics={
                "loudness_band": "medium",
                "speech_mode": "normal",
                "reachability": "clear",
                "ambient_noise": "quiet",
            },
        )

        assert event.fact_family == "auditory_fact"
        assert event.fact_type == fact_type


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
        "acoustics": {
            "loudness_band": "",
            "speech_mode": "",
            "reachability": "",
            "ambient_noise": "",
        },
        "effect_kind": "pulse",
        "subject_key": "",
        "ttl_ms": None,
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


def test_visual_fact_event_model_dump_preserves_effect_semantics() -> None:
    event = VisualFactEvent(
        actor_id="char_c",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        producer_ts=701,
        fact_type="light_level_drop",
        relation_type="environment_light_drop",
        target_environment_id="env_lamp",
        effect_kind="set",
        subject_key="environment_state/env_lamp",
    )

    payload = event.model_dump()

    assert payload["effect_kind"] == "set"
    assert payload["subject_key"] == "environment_state/env_lamp"
    assert payload["ttl_ms"] is None


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


def test_spatial_access_fact_handler_tracks_current_zone_id() -> None:
    handler = SpatialAccessFactHandler()

    handler.handle_event(
        RawFactEvent(
            fact_family="spatial_access_fact",
            fact_type="actor_entered_zone",
            relation_type="actor_entered_zone",
            producer_ts=500,
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_threshold",
            source={
                "layer": "L1",
                "system": "godot.raw_fact_emitter",
                "actor_id": "char_c",
            },
            targets={},
        ),
        "raw_fact_event",
    )

    snapshot = handler.get_snapshot("char_c")

    assert snapshot is not None
    assert snapshot.current_zone_id == "zone_threshold"


def test_spatial_access_fact_handler_tracks_nearby_actor_refs() -> None:
    handler = SpatialAccessFactHandler()

    handler.handle_event(
        RawFactEvent(
            fact_family="spatial_access_fact",
            fact_type="actor_approached_actor",
            relation_type="actor_approached_actor",
            producer_ts=501,
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_threshold",
            source={
                "layer": "L1",
                "system": "godot.raw_fact_emitter",
                "actor_id": "char_c",
            },
            targets={"actor_id": "char_a"},
            world={"distance_m": 1.8},
        ),
        "raw_fact_event",
    )

    snapshot = handler.get_snapshot("char_c")

    assert snapshot is not None
    assert snapshot.nearby_actor_refs == ["char_a"]


def test_spatial_access_fact_handler_refreshes_nearby_actor_refs_from_latest_evidence() -> None:
    handler = SpatialAccessFactHandler()

    handler.handle_event(
        RawFactEvent(
            fact_family="spatial_access_fact",
            fact_type="actor_approached_actor",
            relation_type="actor_approached_actor",
            producer_ts=501,
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_threshold",
            source={
                "layer": "L1",
                "system": "godot.raw_fact_emitter",
                "actor_id": "char_c",
            },
            targets={"actor_id": "char_a"},
            world={"distance_m": 1.8},
        ),
        "raw_fact_event",
    )
    handler.handle_event(
        RawFactEvent(
            fact_family="spatial_access_fact",
            fact_type="actor_approached_actor",
            relation_type="actor_approached_actor",
            producer_ts=502,
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_threshold",
            source={
                "layer": "L1",
                "system": "godot.raw_fact_emitter",
                "actor_id": "char_c",
            },
            targets={"actor_id": "char_b"},
            world={"distance_m": 1.2},
        ),
        "raw_fact_event",
    )

    snapshot = handler.get_snapshot("char_c")

    assert snapshot is not None
    assert snapshot.nearby_actor_refs == ["char_b"]


def test_spatial_access_fact_handler_resets_stale_proximity_on_zone_entry() -> None:
    handler = SpatialAccessFactHandler()

    handler.handle_event(
        RawFactEvent(
            fact_family="spatial_access_fact",
            fact_type="actor_approached_actor",
            relation_type="actor_approached_actor",
            producer_ts=503,
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_threshold",
            source={
                "layer": "L1",
                "system": "godot.raw_fact_emitter",
                "actor_id": "char_c",
            },
            targets={"actor_id": "char_a"},
            world={"distance_m": 1.4},
        ),
        "raw_fact_event",
    )
    handler.handle_event(
        RawFactEvent(
            fact_family="spatial_access_fact",
            fact_type="actor_entered_zone",
            relation_type="actor_entered_zone",
            producer_ts=504,
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_private",
            source={
                "layer": "L1",
                "system": "godot.raw_fact_emitter",
                "actor_id": "char_c",
            },
            targets={},
        ),
        "raw_fact_event",
    )

    snapshot = handler.get_snapshot("char_c")

    assert snapshot is not None
    assert snapshot.current_zone_id == "zone_private"
    assert snapshot.nearby_actor_refs == []


def test_spatial_access_fact_handler_tracks_privacy_band_without_membership_inference() -> None:
    handler = SpatialAccessFactHandler()

    handler.handle_event(
        RawFactEvent(
            fact_family="spatial_access_fact",
            fact_type="privacy_boundary_changed",
            relation_type="privacy_boundary_changed",
            producer_ts=502,
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_private",
            source={
                "layer": "L1",
                "system": "godot.raw_fact_emitter",
                "actor_id": "char_c",
            },
            targets={},
            world={"state_before": "public", "state_after": "local"},
        ),
        "raw_fact_event",
    )

    snapshot = handler.get_snapshot("char_c")

    assert snapshot is not None
    assert snapshot.privacy_band == "local"
    assert "candidate_member" not in snapshot.model_dump()
    assert "excluded" not in snapshot.model_dump()
    assert "passive_member" not in snapshot.model_dump()
    assert "active_member" not in snapshot.model_dump()


def test_spatial_access_fact_handler_ignores_incomplete_privacy_change_input() -> None:
    handler = SpatialAccessFactHandler()

    handler.handle_event(
        RawFactEvent(
            fact_family="spatial_access_fact",
            fact_type="privacy_boundary_changed",
            relation_type="privacy_boundary_changed",
            producer_ts=505,
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_private",
            source={
                "layer": "L1",
                "system": "godot.raw_fact_emitter",
                "actor_id": "char_c",
            },
            targets={},
            world={"state_before": "public", "state_after": "local"},
        ),
        "raw_fact_event",
    )
    handler.handle_event(
        RawFactEvent(
            fact_family="spatial_access_fact",
            fact_type="privacy_boundary_changed",
            relation_type="privacy_boundary_changed",
            producer_ts=506,
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_private",
            source={
                "layer": "L1",
                "system": "godot.raw_fact_emitter",
                "actor_id": "char_c",
            },
            targets={},
            world={"state_before": "public", "state_after": ""},
        ),
        "raw_fact_event",
    )

    snapshot = handler.get_snapshot("char_c")

    assert snapshot is not None
    assert snapshot.privacy_band == "local"


def test_spatial_access_fact_handler_clears_nearby_actor_refs_on_clear_effect() -> None:
    handler = SpatialAccessFactHandler()

    handler.handle_event(
        RawFactEvent(
            fact_family="spatial_access_fact",
            fact_type="actor_approached_actor",
            relation_type="actor_approached_actor",
            producer_ts=800,
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            source={
                "layer": "L1",
                "system": "godot.raw_fact_emitter",
                "actor_id": "char_c",
            },
            targets={"actor_id": "char_a"},
            effect_kind="replace",
            subject_key="nearby_actor_refs",
        ),
        "raw_fact_event",
    )
    handler.handle_event(
        RawFactEvent(
            fact_family="spatial_access_fact",
            fact_type="actor_left_actor_range",
            relation_type="actor_left_actor_range",
            producer_ts=801,
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            source={
                "layer": "L1",
                "system": "godot.raw_fact_emitter",
                "actor_id": "char_c",
            },
            targets={},
            effect_kind="clear",
            subject_key="nearby_actor_refs",
        ),
        "raw_fact_event",
    )

    snapshot = handler.get_snapshot("char_c")

    assert snapshot is not None
    assert snapshot.nearby_actor_refs == []


def test_spatial_access_fact_handler_sets_zone_from_effect_subject() -> None:
    handler = SpatialAccessFactHandler()

    handler.handle_event(
        RawFactEvent(
            fact_family="spatial_access_fact",
            fact_type="actor_entered_zone",
            relation_type="actor_entered_zone",
            producer_ts=802,
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_private",
            source={
                "layer": "L1",
                "system": "godot.raw_fact_emitter",
                "actor_id": "char_c",
            },
            targets={},
            effect_kind="set",
            subject_key="current_zone_id",
        ),
        "raw_fact_event",
    )

    snapshot = handler.get_snapshot("char_c")

    assert snapshot is not None
    assert snapshot.current_zone_id == "zone_private"


def test_spatial_access_fact_handler_prunes_expired_nearby_actor_refs_before_next_event() -> None:
    handler = SpatialAccessFactHandler()

    handler.handle_event(
        RawFactEvent(
            fact_family="spatial_access_fact",
            fact_type="actor_approached_actor",
            relation_type="actor_approached_actor",
            producer_ts=1000,
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            source={"layer": "L1", "system": "godot.raw_fact_emitter", "actor_id": "char_c"},
            targets={"actor_id": "char_a"},
            effect_kind="replace",
            subject_key="nearby_actor_refs",
            ttl_ms=1500,
        ),
        "raw_fact_event",
    )

    handler.handle_event(
        RawFactEvent(
            fact_family="spatial_access_fact",
            fact_type="privacy_boundary_changed",
            relation_type="privacy_boundary_changed",
            producer_ts=2601,
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            source={"layer": "L1", "system": "godot.raw_fact_emitter", "actor_id": "char_c"},
            targets={},
            world={"state_before": "local", "state_after": "private"},
            effect_kind="set",
            subject_key="privacy_band",
        ),
        "raw_fact_event",
    )

    snapshot = handler.get_snapshot("char_c")

    assert snapshot is not None
    assert snapshot.nearby_actor_refs == []
    assert snapshot.privacy_band == "private"


def test_spatial_access_fact_handler_resets_nearby_actor_ttl_on_fresh_replace() -> None:
    handler = SpatialAccessFactHandler()

    handler.handle_event(
        RawFactEvent(
            fact_family="spatial_access_fact",
            fact_type="actor_approached_actor",
            relation_type="actor_approached_actor",
            producer_ts=1000,
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            source={"layer": "L1", "system": "godot.raw_fact_emitter", "actor_id": "char_c"},
            targets={"actor_id": "char_a"},
            effect_kind="replace",
            subject_key="nearby_actor_refs",
            ttl_ms=1500,
        ),
        "raw_fact_event",
    )
    handler.handle_event(
        RawFactEvent(
            fact_family="spatial_access_fact",
            fact_type="actor_approached_actor",
            relation_type="actor_approached_actor",
            producer_ts=2000,
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            source={"layer": "L1", "system": "godot.raw_fact_emitter", "actor_id": "char_c"},
            targets={"actor_id": "char_b"},
            effect_kind="replace",
            subject_key="nearby_actor_refs",
            ttl_ms=1500,
        ),
        "raw_fact_event",
    )
    handler.handle_event(
        RawFactEvent(
            fact_family="spatial_access_fact",
            fact_type="privacy_boundary_changed",
            relation_type="privacy_boundary_changed",
            producer_ts=3000,
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            source={"layer": "L1", "system": "godot.raw_fact_emitter", "actor_id": "char_c"},
            targets={},
            world={"state_before": "public", "state_after": "local"},
            effect_kind="set",
            subject_key="privacy_band",
        ),
        "raw_fact_event",
    )

    snapshot = handler.get_snapshot("char_c")

    assert snapshot is not None
    assert snapshot.nearby_actor_refs == ["char_b"]


def test_raw_fact_router_dispatches_spatial_access_fact_without_breaking_visual_fact_support() -> None:
    spatial_handler = SpatialAccessFactHandler()
    spatial_event = RawFactEvent(
        fact_family="spatial_access_fact",
        fact_type="actor_entered_zone",
        relation_type="actor_entered_zone",
        producer_ts=503,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_threshold",
        source={
            "layer": "L1",
            "system": "godot.raw_fact_emitter",
            "actor_id": "char_c",
        },
        targets={},
    )
    visual_event = RawFactEvent(
        fact_family="visual_fact",
        fact_type="fixed_gaze_on_target",
        relation_type="actor_looks_at_actor",
        producer_ts=504,
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

    spatial_messages = route_raw_fact_event(
        spatial_event,
        source_type="raw_fact_event",
        spatial_access_fact_handler=spatial_handler.handle_event,
    )
    visual_messages = route_raw_fact_event(
        visual_event,
        source_type="raw_fact_event",
        context=object(),
        visual_fact_handler=lambda *_args, **_kwargs: [
            {
                "message_type": "ack",
                "payload": {
                    "accepted": True,
                    "source_type": "raw_fact_event",
                    "route": "authority_visual_fact",
                },
            }
        ],
    )

    assert spatial_messages[0] == {
        "message_type": "ack",
        "payload": {
            "accepted": True,
            "source_type": "raw_fact_event",
            "route": "authority_spatial_access_fact",
        },
    }
    assert spatial_messages[1]["message_type"] == "spatial_access_runtime_state_snapshot"
    assert spatial_messages[1]["payload"]["current_zone_id"] == "zone_threshold"
    assert visual_messages == [
        {
            "message_type": "ack",
            "payload": {
                "accepted": True,
                "source_type": "raw_fact_event",
                "route": "authority_visual_fact",
            },
        }
    ]


def test_raw_fact_router_dispatches_auditory_fact_without_breaking_visual_and_spatial_support() -> None:
    spatial_handler = SpatialAccessFactHandler()
    auditory_event = RawFactEvent(
        fact_family="auditory_fact",
        fact_type="speaker_active",
        relation_type="speech_mode_changed",
        producer_ts=711,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        source={
            "layer": "L1",
            "system": "godot.raw_fact_emitter",
            "actor_id": "char_a",
        },
        targets={"actor_id": "char_c"},
        observability={"auditory": True},
        acoustics={
            "loudness_band": "medium",
            "speech_mode": "normal",
            "reachability": "clear",
            "ambient_noise": "quiet",
        },
    )
    spatial_event = RawFactEvent(
        fact_family="spatial_access_fact",
        fact_type="actor_entered_zone",
        relation_type="actor_entered_zone",
        producer_ts=712,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_threshold",
        source={
            "layer": "L1",
            "system": "godot.raw_fact_emitter",
            "actor_id": "char_c",
        },
        targets={},
    )
    visual_event = RawFactEvent(
        fact_family="visual_fact",
        fact_type="fixed_gaze_on_target",
        relation_type="actor_looks_at_actor",
        producer_ts=713,
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

    auditory_messages = route_raw_fact_event(
        auditory_event,
        source_type="raw_fact_event",
    )
    spatial_messages = route_raw_fact_event(
        spatial_event,
        source_type="raw_fact_event",
        spatial_access_fact_handler=spatial_handler.handle_event,
    )
    visual_messages = route_raw_fact_event(
        visual_event,
        source_type="raw_fact_event",
        context=object(),
        visual_fact_handler=lambda *_args, **_kwargs: [
            {
                "message_type": "ack",
                "payload": {
                    "accepted": True,
                    "source_type": "raw_fact_event",
                    "route": "authority_visual_fact",
                },
            }
        ],
    )

    assert auditory_messages == [
        {
            "message_type": "ack",
            "payload": {
                "accepted": True,
                "source_type": "raw_fact_event",
                "route": "authority_auditory_fact",
            },
        }
    ]
    assert spatial_messages[0]["payload"]["route"] == "authority_spatial_access_fact"
    assert visual_messages[0]["payload"]["route"] == "authority_visual_fact"


def test_raw_fact_router_dispatches_expanded_auditory_fact_types() -> None:
    fact_types = [
        ("auditory_reachability_changed", "auditory_reachability_changed"),
        ("ambient_noise_changed", "auditory_context_shift"),
    ]

    for fact_type, relation_type in fact_types:
        event = RawFactEvent(
            fact_family="auditory_fact",
            fact_type=fact_type,
            relation_type=relation_type,
            producer_ts=715,
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            source={
                "layer": "L1",
                "system": "godot.raw_fact_emitter",
                "actor_id": "char_a",
            },
            targets={"actor_id": "char_c"},
            observability={"auditory": True},
            acoustics={
                "loudness_band": "medium",
                "speech_mode": "normal",
                "reachability": "clear",
                "ambient_noise": "quiet",
            },
        )

        messages = route_raw_fact_event(
            event,
            source_type="raw_fact_event",
        )

        assert messages == [
            {
                "message_type": "ack",
                "payload": {
                    "accepted": True,
                    "source_type": "raw_fact_event",
                    "route": "authority_auditory_fact",
                },
            }
        ]


def test_raw_fact_router_accepts_runtime_wired_remaining_l1_fact_families() -> None:
    families_to_routes = {
        "role_state_fact": "authority_role_state_fact",
        "physiology_state_fact": "authority_physiology_fact",
        "tactile_fact": "authority_tactile_fact",
        "thermal_fact": "authority_thermal_fact",
        "olfactory_fact": "authority_olfactory_fact",
    }

    for fact_family, route in families_to_routes.items():
        event = RawFactEvent(
            fact_family=fact_family,
            fact_type="probe_fact",
            relation_type="probe_relation",
            producer_ts=900,
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
        )

        assert messages == [
            {
                "message_type": "ack",
                "payload": {
                    "accepted": True,
                    "source_type": "raw_fact_event",
                    "route": route,
                },
            }
        ]
