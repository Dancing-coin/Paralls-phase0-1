from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.population_continuity.activation_policy import resolve_participation
from app.population_continuity.simulation_contracts import ParticipationPolicy


def policy(**updates: object) -> ParticipationPolicy:
    values = dict(
        policy_ref="policy:prototype", revision="1", allowed_tiers=("B0", "B1", "B2", "B3"),
        allowed_modules=("needs", "schedule"), forbidden_dimensions=(), upgrade_triggers=(),
        b0_expiry_tick=100, review_tick=120,
    )
    values.update(updates)
    return ParticipationPolicy(**values)


def test_individual_policy_cannot_relax_prototype_permissions() -> None:
    prototype = policy(allowed_tiers=("B1", "B3"), allowed_modules=("needs",))
    individual = policy(policy_ref="policy:individual", forbidden_dimensions=("household.members",))
    result = resolve_participation(policies=(prototype, individual), tick=10)
    assert result.allowed_tiers == ("B1", "B3")
    assert result.recommended_tier == "B1"
    assert result.allowed_modules == ("needs",)
    assert result.forbidden_dimensions == ("household.members",)
    assert result.status == "resolved"


def test_missing_policy_preserves_protection_and_defers() -> None:
    result = resolve_participation(policies=(), tick=10)
    assert result.status == "defer"
    assert result.allowed_tiers == ()
    assert result.recommended_tier is None


def test_disjoint_permissions_do_not_choose_a_fallback_tier() -> None:
    result = resolve_participation(
        policies=(policy(allowed_tiers=("B0",)), policy(policy_ref="policy:individual", allowed_tiers=("B3",))),
        tick=10,
    )
    assert result.status == "defer"
    assert result.recommended_tier is None


def test_b0_expiry_is_exclusive_at_the_deadline() -> None:
    result = resolve_participation(policies=(policy(),), tick=100)
    assert "B0" not in result.allowed_tiers
    assert result.recommended_tier == "B1"
    assert result.b0_expiry_tick == 100


def test_review_deadline_requires_a_new_policy_resolution() -> None:
    result = resolve_participation(policies=(policy(),), tick=120)
    assert result.status == "defer"
    assert result.recommended_tier is None


def test_policy_order_does_not_change_resolution_or_pins() -> None:
    a = policy(upgrade_triggers=("player_intersection",), forbidden_dimensions=("private_memory",))
    b = policy(policy_ref="policy:individual", revision="2", upgrade_triggers=("care_conflict",))
    first = resolve_participation(policies=(a, b), tick=10)
    second = resolve_participation(policies=(b, a), tick=10)
    assert first == second
    assert first.upgrade_triggers == ("care_conflict", "player_intersection")
    assert dict(first.source_policy_pins) == {"policy:individual": "2", "policy:prototype": "1"}
    with pytest.raises(TypeError):
        first.source_policy_pins["policy:individual"] = "3"


def test_duplicate_policy_identity_is_rejected() -> None:
    with pytest.raises(ValueError, match="participation_policy_duplicate"):
        resolve_participation(policies=(policy(), policy(revision="2")), tick=10)


@pytest.mark.parametrize("updates", [{"allowed_tiers": ("B4",)}, {"review_tick": True}, {"arbitrary": 1}])
def test_policy_schema_rejects_invalid_or_extra_fields(updates: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        policy(**updates)


@pytest.mark.parametrize("tick", [True, -1, 1.5])
def test_resolution_requires_a_valid_simulation_tick(tick: object) -> None:
    with pytest.raises(ValueError, match="participation_tick_invalid"):
        resolve_participation(policies=(policy(),), tick=tick)
