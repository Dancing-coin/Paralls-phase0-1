from app.character_agent.profile.effective_profile import resolve_effective_profile


def test_effective_profile_applies_drift_reweights_without_mutating_base_profile():
    base_profile = {
        "need_hierarchy_layer": {
            "base_weights": {
                "physiological": 0.2,
                "safety": 0.8,
                "belonging": 0.6,
                "esteem": 0.5,
                "self_actualization": 0.4,
            }
        },
        "long_term_personality_drift_layer": {
            "need_reweights": {"safety": 0.1},
            "trust_reweights": {},
            "expression_reweights": {},
            "stable_shifts": [],
            "reinforced_patterns": [],
            "weakened_patterns": [],
            "drift_policy": {
                "minimum_cross_scene_count": 3,
                "minimum_confirming_events": 8,
                "minimum_time_span": "long_arc",
                "require_non_transient_evidence": True,
            },
        },
    }

    effective = resolve_effective_profile(base_profile)

    assert effective["need_hierarchy_layer"]["effective_weights"]["safety"] == 0.9
    assert base_profile["need_hierarchy_layer"]["base_weights"]["safety"] == 0.8
