from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.services.siming_fairness_aggregate import (
    DIMENSION_WEIGHTS,
    DOMINANCE_ORDER,
    compute_fairness_aggregate,
)


@dataclass(frozen=True)
class _Dimension:
    status: str
    score: float


def _all(score: float, *, status: str = "fresh") -> dict[str, _Dimension]:
    return {key: _Dimension(status=status, score=score) for key in DIMENSION_WEIGHTS}


def test_all_healthy_dimensions_score_zero_and_are_balanced() -> None:
    # Dimension scores are severity: 0.0 is healthy.
    result = compute_fairness_aggregate(_all(0.0))

    assert result.score == pytest.approx(0.0)
    assert result.dominant == "balanced"
    assert result.reasons == ()


def test_all_dimensions_maximally_imbalanced_scores_one() -> None:
    result = compute_fairness_aggregate(_all(1.0))

    assert result.score == pytest.approx(1.0)
    # Information starvation leads the fixed order.
    assert result.dominant == "information_starvation"


def test_aggregate_is_a_weighted_mean_of_computable_dimensions() -> None:
    dimensions = _all(0.0)
    dimensions["information_distribution"] = _Dimension(status="fresh", score=1.0)

    result = compute_fairness_aggregate(dimensions)

    # The heaviest dimension (0.30) carries the whole imbalance.
    assert result.score == pytest.approx(0.30, abs=1e-9)


def test_unavailable_dimension_is_excluded_not_counted_as_zero() -> None:
    dimensions = _all(0.0)
    dimensions["suspicion_heat_distribution"] = _Dimension(status="unavailable", score=1.0)

    result = compute_fairness_aggregate(dimensions)

    # Excluded from the mean, so the reading stays healthy...
    assert result.score == pytest.approx(0.0)
    # ...but the exclusion is reported rather than hidden.
    assert "suspicion_heat_distribution:unavailable" in result.reasons


def test_no_computable_dimension_is_not_reported_as_balanced_data() -> None:
    dimensions = {key: _Dimension(status="unavailable", score=0.0) for key in DIMENSION_WEIGHTS}

    result = compute_fairness_aggregate(dimensions)

    assert result.score == 0.0
    assert result.dominant == "balanced"
    assert "no_computable_dimension" in result.reasons


def test_missing_dimension_is_reported() -> None:
    dimensions = _all(0.0)
    del dimensions["evidence_visibility_distribution"]

    result = compute_fairness_aggregate(dimensions)

    assert "evidence_visibility_distribution:missing" in result.reasons


def test_dominance_threshold_avoids_naming_noise_as_dominant() -> None:
    dimensions = _all(0.0)
    # A 0.1 imbalance is below the 0.2 threshold.
    dimensions["participation_distribution"] = _Dimension(status="fresh", score=0.1)

    result = compute_fairness_aggregate(dimensions)

    assert result.dominant == "balanced"


def test_dominance_uses_fixed_order_not_weight_order() -> None:
    dimensions = _all(0.0)
    # Evidence bottleneck outranks suspicion in the fixed order even though both
    # dimensions carry the same weight.
    dimensions["evidence_visibility_distribution"] = _Dimension(status="fresh", score=1.0)
    dimensions["suspicion_heat_distribution"] = _Dimension(status="fresh", score=1.0)

    result = compute_fairness_aggregate(dimensions)

    assert result.dominant == "evidence_bottleneck"
    assert DOMINANCE_ORDER.index("evidence_bottleneck") < DOMINANCE_ORDER.index(
        "suspicion_runaway"
    )


def test_weights_are_the_published_contract() -> None:
    assert DIMENSION_WEIGHTS == {
        "information_distribution": 0.30,
        "participation_distribution": 0.28,
        "conversation_access_fairness": 0.18,
        "suspicion_heat_distribution": 0.12,
        "evidence_visibility_distribution": 0.12,
    }
    assert sum(DIMENSION_WEIGHTS.values()) == pytest.approx(1.0)


def test_partial_status_still_contributes() -> None:
    dimensions = _all(0.0)
    dimensions["conversation_access_fairness"] = _Dimension(status="partial", score=1.0)

    result = compute_fairness_aggregate(dimensions)

    assert result.score == pytest.approx(0.18)
    assert result.dominant == "private_channel_lock"
