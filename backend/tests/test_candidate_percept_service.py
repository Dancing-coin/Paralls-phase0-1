from app.models.candidate_percept import CandidatePerceptEvent
from app.models.raw_fact import RawFactEvent
from app.services.candidate_percept_service import compile_candidate_percepts


def test_candidate_percept_event_shape() -> None:
    event = CandidatePerceptEvent(
        event_type="candidate_percept_event",
        percept_channel="visual",
        source_fact_family="visual_fact",
        source_fact_type="fixed_gaze_on_target",
        producer_ts=100,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        source_actor_id="char_c",
        target_actor_id="char_a",
        audience_scope="candidate",
        observability={"visual": True},
        causation_id="vf:100",
        correlation_id="vf:100",
    )

    payload = event.model_dump()

    assert payload["event_type"] == "candidate_percept_event"
    assert payload["percept_channel"] == "visual"
    assert payload["source_fact_family"] == "visual_fact"
    assert payload["target_actor_id"] == "char_a"


def test_compile_visual_fact_to_candidate_percept() -> None:
    event = RawFactEvent(
        fact_family="visual_fact",
        fact_type="fixed_gaze_on_target",
        relation_type="actor_looks_at_actor",
        producer_ts=200,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        source={"layer": "L1", "system": "godot.raw_fact_emitter", "actor_id": "char_c"},
        targets={"actor_id": "char_a"},
    )

    compiled = compile_candidate_percepts(event)

    assert len(compiled) == 1
    assert compiled[0].percept_channel == "visual"
    assert compiled[0].source_fact_family == "visual_fact"
    assert compiled[0].target_actor_id == "char_a"


def test_compile_spatial_access_fact_to_candidate_percept() -> None:
    event = RawFactEvent(
        fact_family="spatial_access_fact",
        fact_type="actor_approached_actor",
        relation_type="actor_approached_actor",
        producer_ts=201,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        source={"layer": "L1", "system": "godot.raw_fact_emitter", "actor_id": "char_c"},
        targets={"actor_id": "char_b"},
        world={"distance_m": 2.4},
        effect_kind="replace",
        subject_key="nearby_actor_refs",
    )

    compiled = compile_candidate_percepts(event)

    assert len(compiled) == 1
    assert compiled[0].percept_channel == "spatial"
    assert compiled[0].source_fact_family == "spatial_access_fact"
    assert compiled[0].target_actor_id == "char_b"


def test_compile_targeted_auditory_facts_to_candidate_percepts() -> None:
    speaker_active = RawFactEvent(
        fact_family="auditory_fact",
        fact_type="speaker_active",
        relation_type="speech_mode_changed",
        producer_ts=300,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        source={"layer": "L1", "system": "godot.raw_fact_emitter", "actor_id": "char_a"},
        targets={"actor_id": "char_c"},
        observability={"auditory": True},
        acoustics={"speech_mode": "normal", "reachability": "clear", "ambient_noise": "quiet"},
    )
    reachability_changed = RawFactEvent(
        fact_family="auditory_fact",
        fact_type="auditory_reachability_changed",
        relation_type="auditory_reachability_changed",
        producer_ts=301,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        source={"layer": "L1", "system": "godot.raw_fact_emitter", "actor_id": "char_a"},
        targets={"actor_id": "char_c"},
        observability={"auditory": True},
        acoustics={"speech_mode": "normal", "reachability": "clear", "ambient_noise": "quiet"},
    )

    speaker_candidates = compile_candidate_percepts(speaker_active)
    reachability_candidates = compile_candidate_percepts(reachability_changed)

    assert len(speaker_candidates) == 1
    assert speaker_candidates[0].percept_channel == "auditory"
    assert speaker_candidates[0].target_actor_id == "char_c"
    assert speaker_candidates[0].source_fact_type == "speaker_active"
    assert len(reachability_candidates) == 1
    assert reachability_candidates[0].percept_channel == "auditory"
    assert reachability_candidates[0].target_actor_id == "char_c"
    assert reachability_candidates[0].source_fact_type == "auditory_reachability_changed"


def test_compile_ambient_noise_changed_keeps_environmental_audio_system_only_for_now() -> None:
    event = RawFactEvent(
        fact_family="auditory_fact",
        fact_type="ambient_noise_changed",
        relation_type="auditory_context_shift",
        producer_ts=302,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        source={"layer": "L1", "system": "godot.raw_fact_emitter", "actor_id": "char_a"},
        targets={},
        observability={"auditory": True},
        acoustics={"speech_mode": "normal", "reachability": "clear", "ambient_noise": "quiet"},
    )

    assert compile_candidate_percepts(event) == []


def test_compile_olfactory_fact_to_candidate_percept() -> None:
    event = RawFactEvent(
        fact_family="olfactory_fact",
        fact_type="odor_state_changed",
        relation_type="odor_state_changed",
        producer_ts=303,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        source={"layer": "L1", "system": "godot.raw_fact_emitter", "actor_id": "char_c"},
        targets={"environment_id": "env_lamp"},
        observability={"auditory": False, "visual": False},
    )

    compiled = compile_candidate_percepts(event)

    assert len(compiled) == 1
    assert compiled[0].percept_channel == "olfactory"
    assert compiled[0].target_environment_id == "env_lamp"


def test_compile_thermal_fact_to_candidate_percept() -> None:
    event = RawFactEvent(
        fact_family="thermal_fact",
        fact_type="thermal_proximity_changed",
        relation_type="thermal_proximity_changed",
        producer_ts=304,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        source={"layer": "L1", "system": "godot.raw_fact_emitter", "actor_id": "char_c"},
        targets={"object_id": "obj_letter"},
        observability={"auditory": False, "visual": False},
    )

    compiled = compile_candidate_percepts(event)

    assert len(compiled) == 1
    assert compiled[0].percept_channel == "thermal"
    assert compiled[0].target_object_id == "obj_letter"


def test_compile_tactile_fact_to_candidate_percept() -> None:
    event = RawFactEvent(
        fact_family="tactile_fact",
        fact_type="contact_started",
        relation_type="contact_started",
        producer_ts=305,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        source={"layer": "L1", "system": "godot.raw_fact_emitter", "actor_id": "char_c"},
        targets={"actor_id": "char_a"},
        observability={"auditory": False, "visual": False},
    )

    compiled = compile_candidate_percepts(event)

    assert len(compiled) == 1
    assert compiled[0].percept_channel == "tactile"
    assert compiled[0].target_actor_id == "char_a"
