"""Fairness aggregation arithmetic for the Phase-1 fair-judge Siming.

The five fairness dimensions were previously computed but never combined, so
the governor had no single imbalance reading to act on.  This module implements
the weighted mean and the dominant-type selection exactly as the canonical
schema specifies, as a pure function over dimension snapshots.
"""

from __future__ import annotations

from dataclasses import dataclass

# Weights are part of the published contract, not tuning knobs: changing them
# changes what "balanced" means, so they live here together with the code that
# consumes them.
DIMENSION_WEIGHTS: dict[str, float] = {
    "information_distribution": 0.30,
    "participation_distribution": 0.28,
    "conversation_access_fairness": 0.18,
    "suspicion_heat_distribution": 0.12,
    "evidence_visibility_distribution": 0.12,
}

# Which imbalance an imbalanced dimension manifests as.
DIMENSION_TO_IMBALANCE: dict[str, str] = {
    "information_distribution": "information_starvation",
    "participation_distribution": "participation_starvation",
    "conversation_access_fairness": "private_channel_lock",
    "evidence_visibility_distribution": "evidence_bottleneck",
    "suspicion_heat_distribution": "suspicion_runaway",
}

# Fixed dominance order.  It is deliberately *not* the weight order: evidence
# scarcity outranks suspicion even though they carry the same weight, because a
# missing-evidence state blocks recovery while suspicion is merely risky.
DOMINANCE_ORDER: tuple[str, ...] = (
    "information_starvation",
    "participation_starvation",
    "private_channel_lock",
    "evidence_bottleneck",
    "suspicion_runaway",
)

# A dimension must exceed this normalized imbalance to be named dominant.  Below
# it, calling a type dominant would invite intervention on noise.
DOMINANCE_THRESHOLD = 0.2

COMPUTABLE_STATUSES = frozenset({"fresh", "degraded", "partial"})


@dataclass(frozen=True)
class FairnessAggregate:
    score: float
    dominant: str
    reasons: tuple[str, ...]


def _normalized_imbalance(score: float) -> float:
    """Clamp a dimension's imbalance score into 0..1.

    Dimension scores are *severity*: 0.0 means healthy and 1.0 maximally
    imbalanced (the monitor maps ``ok`` to 0.0 and ``high`` to 0.9).  The
    aggregate therefore follows the same direction -- a higher
    ``global_imbalance_score`` means a less fair world.
    """
    return min(1.0, max(0.0, float(score)))


def compute_fairness_aggregate(dimensions: dict[str, object]) -> FairnessAggregate:
    """Combine dimension snapshots into one imbalance reading.

    Only dimensions that are both computable (``status`` in
    :data:`COMPUTABLE_STATUSES`) and carry a numeric score participate.  A
    dimension that is unavailable is excluded from the mean rather than counted
    as zero, and the exclusion is reported in ``reasons`` so "no data" is never
    mistaken for "balanced".
    """
    weighted_total = 0.0
    weight_sum = 0.0
    reasons: list[str] = []
    imbalances: dict[str, float] = {}

    for dimension_id, weight in DIMENSION_WEIGHTS.items():
        dimension = dimensions.get(dimension_id)
        if dimension is None:
            reasons.append(f"{dimension_id}:missing")
            continue
        status = str(getattr(dimension, "status", ""))
        score = getattr(dimension, "score", None)
        if status not in COMPUTABLE_STATUSES or not isinstance(score, (int, float)):
            reasons.append(f"{dimension_id}:{status or 'unknown'}")
            continue
        normalized = _normalized_imbalance(float(score))
        weighted_total += normalized * weight
        weight_sum += weight
        imbalance = DIMENSION_TO_IMBALANCE[dimension_id]
        imbalances[imbalance] = max(imbalances.get(imbalance, 0.0), normalized)

    if weight_sum == 0.0:
        reasons.append("no_computable_dimension")
        return FairnessAggregate(score=0.0, dominant="balanced", reasons=tuple(reasons))

    score = min(1.0, max(0.0, weighted_total / weight_sum))
    dominant = "balanced"
    for candidate in DOMINANCE_ORDER:
        if imbalances.get(candidate, 0.0) > DOMINANCE_THRESHOLD:
            dominant = candidate
            break
    return FairnessAggregate(score=score, dominant=dominant, reasons=tuple(reasons))


__all__ = [
    "COMPUTABLE_STATUSES",
    "DIMENSION_WEIGHTS",
    "DIMENSION_TO_IMBALANCE",
    "DOMINANCE_ORDER",
    "DOMINANCE_THRESHOLD",
    "FairnessAggregate",
    "compute_fairness_aggregate",
]
