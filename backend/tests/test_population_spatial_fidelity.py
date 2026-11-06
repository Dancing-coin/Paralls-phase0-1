from __future__ import annotations

import pytest

from app.population_continuity.spatial_fidelity import (
    FIDELITY_ORDER,
    ActorPositionSet,
    RegionFidelityBudget,
    RegionFidelitySelector,
    SpatialPosition,
)


def _position(kind: str, region: str = "region:bakery", **updates: object) -> SpatialPosition:
    values: dict[str, object] = {
        "kind": kind,
        "region_ref": region,
        "source_ref": f"owner:{kind}",
        "revision": 1,
    }
    values.update(updates)
    return SpatialPosition(**values)


def _all_positions(region: str = "region:bakery") -> tuple[SpatialPosition, ...]:
    return tuple(_position(kind, region) for kind in ("truth", "body", "perception", "presentation"))


def test_four_fidelity_tiers_are_ordered() -> None:
    assert FIDELITY_ORDER == ("B0", "B1", "B2", "B3")


def test_four_position_kinds_are_distinct() -> None:
    positions = ActorPositionSet(actor_ref="character:a", positions=_all_positions())

    for kind in ("truth", "body", "perception", "presentation"):
        assert positions.for_kind(kind) is not None


def test_each_position_names_its_own_source() -> None:
    positions = ActorPositionSet(actor_ref="character:a", positions=_all_positions())

    sources = {p.source_ref for p in positions.positions}

    # Truth, body, perception and presentation are owned by different systems.
    assert len(sources) == 4


def test_duplicate_position_kind_is_rejected() -> None:
    with pytest.raises(ValueError, match="duplicate_position_kind"):
        ActorPositionSet(
            actor_ref="character:a",
            positions=(_position("truth"), _position("truth", region="region:other")),
        )


def test_alignment_requires_all_four_views_and_one_region() -> None:
    aligned = ActorPositionSet(actor_ref="character:a", positions=_all_positions())
    partial = ActorPositionSet(actor_ref="character:a", positions=(_position("truth"),))

    assert aligned.is_aligned()
    # A missing view is not agreement.
    assert not partial.is_aligned()


def test_divergent_positions_are_not_aligned() -> None:
    positions = _all_positions()[:-1] + (_position("presentation", "region:elsewhere"),)
    position_set = ActorPositionSet(actor_ref="character:a", positions=positions)

    # world moved the actor but presentation has not caught up: expected, and
    # visible precisely because the views are kept separate.
    assert not position_set.is_aligned()


def test_budget_rejects_unknown_tier() -> None:
    with pytest.raises(ValueError, match="unknown_fidelity_tier"):
        RegionFidelityBudget(region_ref="region:bakery", allowance={"B5": 1})


def test_budget_rejects_negative_allowance() -> None:
    with pytest.raises(ValueError, match="negative_fidelity_allowance"):
        RegionFidelityBudget(region_ref="region:bakery", allowance={"B3": -1})


def test_requested_tier_is_granted_when_budget_allows() -> None:
    budget = RegionFidelityBudget(region_ref="region:bakery", allowance={"B3": 2})

    admission = RegionFidelitySelector().admit(
        actor_ref="character:a", requested_tier="B3", budget=budget, occupancy={}
    )

    assert admission.granted_tier == "B3"
    assert not admission.downgraded


def test_exhausted_region_downgrades_instead_of_refusing() -> None:
    budget = RegionFidelityBudget(region_ref="region:bakery", allowance={"B3": 1, "B2": 1})

    admission = RegionFidelitySelector().admit(
        actor_ref="character:b",
        requested_tier="B3",
        budget=budget,
        occupancy={"B3": 1},
    )

    assert admission.granted_tier == "B2"
    assert admission.downgraded
    assert admission.reason == "region_budget_downgrade"


def test_downgrade_walks_one_step_at_a_time() -> None:
    budget = RegionFidelityBudget(
        region_ref="region:bakery", allowance={"B3": 1, "B2": 1, "B1": 1}
    )

    admission = RegionFidelitySelector().admit(
        actor_ref="character:c",
        requested_tier="B3",
        budget=budget,
        occupancy={"B3": 1, "B2": 1},
    )

    assert admission.granted_tier == "B1"


def test_b0_is_a_floor_never_refused() -> None:
    budget = RegionFidelityBudget(region_ref="region:bakery", allowance={})

    admission = RegionFidelitySelector().admit(
        actor_ref="character:a", requested_tier="B3", budget=budget, occupancy={}
    )

    # Refusing entirely would stop the actor from advancing at all.
    assert admission.granted_tier == "B0"
    assert admission.reason == "b0_floor_reached"


def test_unknown_requested_tier_is_rejected() -> None:
    budget = RegionFidelityBudget(region_ref="region:bakery", allowance={"B3": 1})

    with pytest.raises(ValueError, match="unknown_fidelity_tier"):
        RegionFidelitySelector().admit(
            actor_ref="character:a", requested_tier="B9", budget=budget, occupancy={}
        )
