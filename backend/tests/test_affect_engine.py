from app.character_agent.logic.affect_engine import AffectEngine
from app.character_agent.models.dynamic_state import CharacterDynamicState, TensionState
from app.character_agent.models.need_tension import NeedTensionDelta, NeedTensionState


def test_character_dynamic_state_supports_affect_tension_and_motivation_groups() -> None:
    state = CharacterDynamicState(
        actor_id="char_a",
        vigilance_level=0.4,
        distraction_level=0.2,
        affect_valence=-0.1,
    )

    assert state.affect_state.fear == 0.0
    assert state.tension_state.stress_load == 0.0
    assert state.motivation_state.motivation_stack == []


def test_need_tension_state_defaults_pressures_and_sources() -> None:
    state = NeedTensionState(actor_id="char_a")

    assert state.physiological_pressure == 0.0
    assert state.safety_pressure == 0.0
    assert state.belonging_pressure == 0.0
    assert state.esteem_pressure == 0.0
    assert state.self_actualization_pressure == 0.0
    assert state.recent_satisfaction == {}
    assert state.dominant_need == ""
    assert state.secondary_need == ""
    assert state.motivation_stack == []
    assert state.pressure_sources == []


def test_need_tension_delta_accepts_need_aliases_and_normalizes_to_pressure_mapping() -> None:
    delta = NeedTensionDelta(
        physiological=0.1,
        safety=0.2,
        belonging=0.4,
        esteem=0.3,
        self_actualization=0.5,
        pressure_sources=["x"],
    )

    assert delta.physiological == 0.1
    assert delta.safety == 0.2
    assert delta.belonging == 0.4
    assert delta.esteem == 0.3
    assert delta.self_actualization == 0.5
    assert delta.as_mapping() == {
        "physiological_pressure": 0.1,
        "safety_pressure": 0.2,
        "belonging_pressure": 0.4,
        "esteem_pressure": 0.3,
        "self_actualization_pressure": 0.5,
        "pressure_sources": ["x"],
    }


def test_character_dynamic_state_preserves_group_only_fields_from_typed_tension_state_input() -> None:
    state = CharacterDynamicState(
        actor_id="char_a",
        vigilance_level=0.4,
        distraction_level=0.2,
        tension_state=TensionState(
            chronic_safety_tension=0.7,
            relationship_fatigue=0.2,
        ),
    )

    assert state.tension_state.chronic_safety_tension == 0.7
    assert state.tension_state.relationship_fatigue == 0.2


def test_character_dynamic_state_model_dump_preserves_grouped_fields_for_round_trip() -> None:
    state = CharacterDynamicState(
        actor_id="char_a",
        vigilance_level=0.4,
        distraction_level=0.2,
        tension_state=TensionState(
            social_pressure=0.3,
            chronic_safety_tension=0.7,
            relationship_fatigue=0.2,
        ),
    )

    dumped = state.model_dump()
    reloaded = CharacterDynamicState(**dumped)

    assert "tension_state" in dumped
    assert dumped["tension_state"]["chronic_safety_tension"] == 0.7
    assert reloaded.tension_state.chronic_safety_tension == 0.7
    assert reloaded.tension_state.relationship_fatigue == 0.2


def test_affect_engine_derives_dynamic_state_delta_from_need_tension_delta() -> None:
    engine = AffectEngine()
    effective_profile = {
        "temperament_response_layer": {
            "baseline_temperament": {
                "emotional_reactivity": 0.5,
            }
        }
    }
    need_delta = NeedTensionDelta(safety=0.6, esteem=0.2)

    result = engine.evaluate(effective_profile=effective_profile, need_delta=need_delta)

    assert result == {
        "dynamic_state_delta": {
            "vigilance_level": 0.3,
            "stress_load": 0.4,
            "affect_valence": -0.8,
        }
    }


def test_affect_engine_preserves_zero_emotional_reactivity() -> None:
    engine = AffectEngine()
    effective_profile = {
        "temperament_response_layer": {
            "baseline_temperament": {
                "emotional_reactivity": 0.0,
            }
        }
    }
    need_delta = NeedTensionDelta(safety=0.6, esteem=0.2)

    result = engine.evaluate(effective_profile=effective_profile, need_delta=need_delta)

    assert result == {
        "dynamic_state_delta": {
            "vigilance_level": 0.0,
            "stress_load": 0.4,
            "affect_valence": -0.8,
        }
    }


def test_affect_engine_returns_empty_delta_without_active_pressures() -> None:
    engine = AffectEngine()

    result = engine.evaluate(effective_profile={}, need_delta=NeedTensionDelta())

    assert result == {"dynamic_state_delta": {}}


def test_affect_engine_falls_back_for_malformed_emotional_reactivity() -> None:
    engine = AffectEngine()
    effective_profile = {
        "temperament_response_layer": {
            "baseline_temperament": {
                "emotional_reactivity": "bad-reactivity",
            }
        }
    }
    need_delta = NeedTensionDelta(safety=0.6, esteem=0.2)

    result = engine.evaluate(effective_profile=effective_profile, need_delta=need_delta)

    assert result == {
        "dynamic_state_delta": {
            "vigilance_level": 0.3,
            "stress_load": 0.4,
            "affect_valence": -0.8,
        }
    }


def test_affect_engine_falls_back_for_non_finite_emotional_reactivity() -> None:
    engine = AffectEngine()
    effective_profile = {
        "temperament_response_layer": {
            "baseline_temperament": {
                "emotional_reactivity": "nan",
            }
        }
    }
    need_delta = NeedTensionDelta(safety=0.6, esteem=0.2)

    result = engine.evaluate(effective_profile=effective_profile, need_delta=need_delta)

    assert result == {
        "dynamic_state_delta": {
            "vigilance_level": 0.3,
            "stress_load": 0.4,
            "affect_valence": -0.8,
        }
    }


def test_affect_engine_rejects_bool_emotional_reactivity() -> None:
    engine = AffectEngine()
    effective_profile = {
        "temperament_response_layer": {
            "baseline_temperament": {
                "emotional_reactivity": True,
            }
        }
    }
    need_delta = NeedTensionDelta(safety=0.6, esteem=0.2)

    result = engine.evaluate(effective_profile=effective_profile, need_delta=need_delta)

    assert result == {
        "dynamic_state_delta": {
            "vigilance_level": 0.3,
            "stress_load": 0.4,
            "affect_valence": -0.8,
        }
    }


def test_affect_engine_clamps_negative_emotional_reactivity() -> None:
    engine = AffectEngine()
    effective_profile = {
        "temperament_response_layer": {
            "baseline_temperament": {
                "emotional_reactivity": -0.5,
            }
        }
    }
    need_delta = NeedTensionDelta(safety=0.6, esteem=0.2)

    result = engine.evaluate(effective_profile=effective_profile, need_delta=need_delta)

    assert result == {
        "dynamic_state_delta": {
            "vigilance_level": 0.0,
            "stress_load": 0.4,
            "affect_valence": -0.8,
        }
    }


def test_affect_engine_clamps_oversized_emotional_reactivity() -> None:
    engine = AffectEngine()
    effective_profile = {
        "temperament_response_layer": {
            "baseline_temperament": {
                "emotional_reactivity": 2.0,
            }
        }
    }
    need_delta = NeedTensionDelta(safety=0.6, esteem=0.2)

    result = engine.evaluate(effective_profile=effective_profile, need_delta=need_delta)

    assert result == {
        "dynamic_state_delta": {
            "vigilance_level": 0.6,
            "stress_load": 0.4,
            "affect_valence": -0.8,
        }
    }
