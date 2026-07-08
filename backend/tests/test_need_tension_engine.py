from collections.abc import Mapping

from app.character_agent.logic.need_tension_engine import NeedTensionEngine


def test_need_tension_engine_raises_safety_and_esteem_pressure_for_public_threat() -> None:
    engine = NeedTensionEngine()
    effective_profile = {
        "need_hierarchy_layer": {
            "effective_weights": {
                "physiological": 0.2,
                "safety": 0.8,
                "belonging": 0.6,
                "esteem": 0.7,
                "self_actualization": 0.3,
            },
            "deprivation_sensitivity": {
                "physiological": 0.2,
                "safety": 0.9,
                "belonging": 0.6,
                "esteem": 0.8,
                "self_actualization": 0.2,
            },
        }
    }
    event = {"event_tags": ["public_dismissal", "spatial_uncertainty"]}

    delta = engine.evaluate(effective_profile=effective_profile, event=event)

    assert delta.safety > 0.0
    assert delta.esteem > 0.0
    assert "public_dismissal" in delta.pressure_sources


def test_need_tension_engine_deduplicates_and_sorts_pressure_sources() -> None:
    engine = NeedTensionEngine()
    effective_profile = {
        "need_hierarchy_layer": {
            "effective_weights": {
                "safety": 0.8,
                "esteem": 0.7,
            },
            "deprivation_sensitivity": {
                "safety": 0.9,
                "esteem": 0.8,
            },
        }
    }
    event = {"event_tags": ["spatial_uncertainty", "public_dismissal", "public_dismissal"]}

    delta = engine.evaluate(effective_profile=effective_profile, event=event)

    assert delta.pressure_sources == ["public_dismissal", "spatial_uncertainty"]


def test_need_tension_engine_falls_back_to_base_weights_when_effective_weights_are_absent() -> None:
    engine = NeedTensionEngine()
    effective_profile = {
        "need_hierarchy_layer": {
            "base_weights": {
                "safety": 0.8,
            },
            "deprivation_sensitivity": {
                "safety": 0.5,
            },
        }
    }
    event = {"event_tags": ["spatial_uncertainty"]}

    delta = engine.evaluate(effective_profile=effective_profile, event=event)

    assert delta.as_mapping() == {
        "safety_pressure": 0.1,
        "pressure_sources": ["spatial_uncertainty"],
    }


def test_need_tension_engine_omits_untriggered_pressures_for_noop_event() -> None:
    engine = NeedTensionEngine()
    effective_profile = {
        "need_hierarchy_layer": {
            "effective_weights": {
                "safety": 0.8,
                "esteem": 0.7,
            },
            "deprivation_sensitivity": {
                "safety": 0.9,
                "esteem": 0.8,
            },
        }
    }
    event: Mapping[str, object] = {"event_tags": []}

    delta = engine.evaluate(effective_profile=effective_profile, event=event)

    assert delta.as_mapping() == {"pressure_sources": []}


def test_need_tension_engine_falls_back_for_malformed_profile_scalars() -> None:
    engine = NeedTensionEngine()
    effective_profile = {
        "need_hierarchy_layer": {
            "effective_weights": {
                "safety": "bad-weight",
                "esteem": 0.7,
            },
            "deprivation_sensitivity": {
                "safety": 0.9,
                "esteem": "bad-sensitivity",
            },
        }
    }
    event = {"event_tags": ["public_dismissal", "spatial_uncertainty"]}

    delta = engine.evaluate(effective_profile=effective_profile, event=event)

    assert delta.safety == 0.0
    assert delta.esteem == 0.0
    assert delta.as_mapping() == {
        "safety_pressure": 0.0,
        "esteem_pressure": 0.0,
        "pressure_sources": ["public_dismissal", "spatial_uncertainty"],
    }


def test_need_tension_engine_falls_back_for_non_finite_profile_scalars() -> None:
    engine = NeedTensionEngine()
    effective_profile = {
        "need_hierarchy_layer": {
            "effective_weights": {
                "safety": "nan",
                "esteem": "inf",
            },
            "deprivation_sensitivity": {
                "safety": 0.9,
                "esteem": 0.8,
            },
        }
    }
    event = {"event_tags": ["public_dismissal", "spatial_uncertainty"]}

    delta = engine.evaluate(effective_profile=effective_profile, event=event)

    assert delta.safety == 0.0
    assert delta.esteem == 0.0
    assert delta.as_mapping() == {
        "safety_pressure": 0.0,
        "esteem_pressure": 0.0,
        "pressure_sources": ["public_dismissal", "spatial_uncertainty"],
    }


def test_need_tension_engine_rejects_bool_profile_scalars() -> None:
    engine = NeedTensionEngine()
    effective_profile = {
        "need_hierarchy_layer": {
            "effective_weights": {
                "safety": True,
                "esteem": 0.7,
            },
            "deprivation_sensitivity": {
                "safety": 0.9,
                "esteem": False,
            },
        }
    }
    event = {"event_tags": ["public_dismissal", "spatial_uncertainty"]}

    delta = engine.evaluate(effective_profile=effective_profile, event=event)

    assert delta.safety == 0.0
    assert delta.esteem == 0.0
    assert delta.as_mapping() == {
        "safety_pressure": 0.0,
        "esteem_pressure": 0.0,
        "pressure_sources": ["public_dismissal", "spatial_uncertainty"],
    }


def test_need_tension_engine_clamps_out_of_range_profile_scalars() -> None:
    engine = NeedTensionEngine()
    effective_profile = {
        "need_hierarchy_layer": {
            "effective_weights": {
                "safety": -2.0,
                "esteem": 2.0,
            },
            "deprivation_sensitivity": {
                "safety": 3.0,
                "esteem": 3.0,
            },
        }
    }
    event = {"event_tags": ["public_dismissal", "spatial_uncertainty"]}

    delta = engine.evaluate(effective_profile=effective_profile, event=event)

    assert delta.safety == 0.0
    assert delta.esteem == 0.25
    assert delta.as_mapping() == {
        "safety_pressure": 0.0,
        "esteem_pressure": 0.25,
        "pressure_sources": ["public_dismissal", "spatial_uncertainty"],
    }
