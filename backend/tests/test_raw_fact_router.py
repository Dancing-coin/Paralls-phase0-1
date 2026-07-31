from app.models.raw_fact import RawFactEvent
from app.models.visual_fact import VisualFactEvent
from app.models.capture_clock import same_capture_tick
from app.services.candidate_percept_service import compile_candidate_percepts
from app.services.fact_handlers.spatial_access_fact_handler import SpatialAccessFactHandler
from app.services.per_character_percept_filter import filter_candidate_for_actor
from app.services.fact_router import build_raw_fact_authority_ack, route_raw_fact_event


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


def test_raw_fact_fast_authority_ack_does_not_require_visual_handler_context() -> None:
    event = RawFactEvent(
        fact_family="visual_fact",
        fact_type="light_level_drop",
        relation_type="environment_light_drop",
        producer_ts=123,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        source={
            "layer": "L1",
            "system": "godot.raw_fact_emitter",
            "actor_id": "char_c",
        },
        targets={"environment_id": "env_lamp"},
    )

    ack = build_raw_fact_authority_ack(event, source_type="raw_fact_event")

    assert ack["message_type"] == "ack"
    assert ack["payload"]["accepted"] is True
    assert ack["payload"]["source_type"] == "raw_fact_event"
    assert ack["payload"]["route"] == "authority_visual_fact"
    assert ack["payload"]["fact_key"] == "environment_light_drop"


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


def test_raw_fact_event_preserves_capture_clock_identity_through_fact_chain() -> None:
    event = RawFactEvent(
        fact_family="visual_fact",
        fact_type="fixed_gaze_on_target",
        relation_type="actor_looks_at_object",
        producer_ts=900,
        capture_root_id="capture_root:godot_main:room_demo:scene_demo:zone_focus:77",
        capture_id="capture:capture_root:godot_main:room_demo:scene_demo:zone_focus:77:fact:char_b",
        clock_domain="godot_main",
        monotonic_tick=77,
        source_frame_index=12,
        wall_clock_ts=900,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        source={"layer": "L1", "system": "godot.raw_fact_emitter", "actor_id": "char_b"},
        targets={"object_id": "obj_letter"},
    )

    candidate = compile_candidate_percepts(event)[0]
    perceived = filter_candidate_for_actor(candidate, actor_id="char_b")

    assert event.capture_root_id == candidate.capture_root_id
    assert perceived is not None
    assert perceived.capture_root_id == event.capture_root_id
    assert perceived.capture_id == event.capture_id
    assert perceived.clock_domain == "godot_main"
    assert perceived.monotonic_tick == 77
    assert perceived.source_frame_index == 12
    assert same_capture_tick(event, perceived)


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

    payload = event.model_dump()

    assert payload == {
        "event_type": "raw_fact_event",
        "fact_family": "visual_fact",
        "fact_type": "fixed_gaze_on_target",
        "relation_type": "actor_looks_at_actor",
        "producer_ts": 123,
        "capture_root_id": "capture_root:legacy_producer_ts:room_demo:scene_demo:zone_focus:123",
        "capture_id": "capture:capture_root:legacy_producer_ts:room_demo:scene_demo:zone_focus:123:fact:char_c",
        "clock_domain": "legacy_producer_ts",
        "monotonic_tick": 123,
        "source_frame_index": None,
        "wall_clock_ts": 123,
        "sample_ref_id": payload["sample_ref_id"],
        "world_anchor_id": "world_anchor:actor:char_a",
        "subject_ref": "char_c",
        "target_ref": "char_a",
        "source_ref_lineage": [
            payload["sample_ref_id"],
            "raw_fact_event:visual_fact:fixed_gaze_on_target:123",
        ],
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
    assert payload["sample_ref_id"].startswith("sample_ref:visual_fact:")


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


def test_visual_fact_event_preserves_explicit_capture_clock_fields() -> None:
    event = VisualFactEvent(
        actor_id="char_c",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        producer_ts=123,
        capture_root_id="capture_root:godot_main:room_demo:scene_demo:zone_focus:77",
        capture_id="capture:capture_root:godot_main:room_demo:scene_demo:zone_focus:77:fact:char_c",
        clock_domain="godot_main",
        monotonic_tick=77,
        source_frame_index=12,
        wall_clock_ts=123,
        fact_type="fixed_gaze_on_target",
        relation_type="actor_looks_at_actor",
        target_actor_id="char_a",
    )

    assert event.capture_root_id == "capture_root:godot_main:room_demo:scene_demo:zone_focus:77"
    assert event.capture_id.endswith(":fact:char_c")
    assert event.clock_domain == "godot_main"
    assert event.monotonic_tick == 77
    assert event.source_frame_index == 12


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

    assert auditory_messages[0]["message_type"] == "ack"
    assert auditory_messages[0]["payload"]["accepted"] is True
    assert auditory_messages[0]["payload"]["source_type"] == "raw_fact_event"
    assert auditory_messages[0]["payload"]["route"] == "authority_auditory_fact"
    assert auditory_messages[0]["payload"]["fact_key"] == "speaker_active"
    assert spatial_messages[0]["payload"]["route"] == "authority_spatial_access_fact"
    assert visual_messages[0]["payload"]["route"] == "authority_visual_fact"


def test_authority_ack_payloads_include_backend_confirmed_fact_keys() -> None:
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
    auditory_event = RawFactEvent(
        fact_family="auditory_fact",
        fact_type="speaker_active",
        relation_type="speech_mode_changed",
        producer_ts=714,
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
    )
    role_state_event = RawFactEvent(
        fact_family="role_state_fact",
        fact_type="role_state_transition",
        relation_type="runtime_state_changed",
        producer_ts=715,
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

    visual_messages = route_raw_fact_event(
        visual_event,
        source_type="raw_fact_event",
        context=object(),
        visual_fact_handler=lambda event, source_type, _context: [
            {
                "message_type": "ack",
                "payload": {
                    "accepted": True,
                    "source_type": source_type,
                    "route": "authority_visual_fact",
                    "fact_key": event.relation_type,
                    "fact_type": event.fact_type,
                    "relation_type": event.relation_type,
                },
            }
        ],
    )
    auditory_messages = route_raw_fact_event(auditory_event, source_type="raw_fact_event")
    role_state_messages = route_raw_fact_event(role_state_event, source_type="raw_fact_event")

    assert visual_messages[0]["payload"]["fact_key"] == "actor_looks_at_actor"
    assert visual_messages[0]["payload"]["fact_type"] == "fixed_gaze_on_target"
    assert visual_messages[0]["payload"]["relation_type"] == "actor_looks_at_actor"
    assert auditory_messages[0]["payload"]["fact_key"] == "speaker_active"
    assert auditory_messages[0]["payload"]["fact_type"] == "speaker_active"
    assert auditory_messages[0]["payload"]["relation_type"] == "speech_mode_changed"
    assert role_state_messages[0]["payload"]["fact_key"] == "role_state_transition"
    assert role_state_messages[0]["payload"]["fact_type"] == "role_state_transition"
    assert role_state_messages[0]["payload"]["relation_type"] == "runtime_state_changed"


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

        assert messages[0]["message_type"] == "ack"
        assert messages[0]["payload"]["accepted"] is True
        assert messages[0]["payload"]["source_type"] == "raw_fact_event"
        assert messages[0]["payload"]["route"] == "authority_auditory_fact"
        assert messages[0]["payload"]["fact_key"] == fact_type
        assert messages[0]["payload"]["relation_type"] == relation_type


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

        assert messages[0]["message_type"] == "ack"
        assert messages[0]["payload"]["accepted"] is True
        assert messages[0]["payload"]["source_type"] == "raw_fact_event"
        assert messages[0]["payload"]["route"] == route
        assert messages[0]["payload"]["fact_family"] == fact_family
        assert messages[0]["payload"]["fact_key"] == "probe_fact"
