from copy import deepcopy


_NEED_KEYS = (
    "physiological",
    "safety",
    "belonging",
    "esteem",
    "self_actualization",
)


def resolve_effective_profile(profile: dict[str, object]) -> dict[str, object]:
    effective_profile = deepcopy(profile)
    need_layer = effective_profile.setdefault("need_hierarchy_layer", {})
    if not isinstance(need_layer, dict):
        need_layer = {}
        effective_profile["need_hierarchy_layer"] = need_layer

    drift_layer = effective_profile.get("long_term_personality_drift_layer", {})
    if not isinstance(drift_layer, dict):
        drift_layer = {}

    base_weights = need_layer.get("base_weights", {})
    if not isinstance(base_weights, dict):
        base_weights = {}

    need_reweights = drift_layer.get("need_reweights", {})
    if not isinstance(need_reweights, dict):
        need_reweights = {}

    effective_weights: dict[str, float] = {}
    for key in _NEED_KEYS:
        base = float(base_weights.get(key, 0.0) or 0.0)
        reweight = float(need_reweights.get(key, 0.0) or 0.0)
        effective_weights[key] = max(0.0, min(1.0, base + reweight))

    need_layer["effective_weights"] = effective_weights
    return effective_profile
