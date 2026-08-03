from decimal import Decimal

import pytest

from app.gameplay.effective_stats import EffectiveStatError, EffectiveStatResolver, StatBaseline, StatModifier


def _modifier(modifier_id: str, operation: str, value: str, **overrides: object) -> StatModifier:
    values = {
        "modifier_id": modifier_id,
        "stat_id": "combat.power",
        "operation": operation,
        "value": Decimal(value),
        "stacking_key": modifier_id,
        "source_ref": f"source:{modifier_id}",
        "source_event_id": f"evt:{modifier_id}",
    }
    values.update(overrides)
    return StatModifier(**values)


def test_resolver_is_order_independent_and_explains_condition_rejection() -> None:
    baseline = StatBaseline(stat_id="combat.power", value=Decimal("10"), source_ref="profile:warrior")
    modifiers = [
        _modifier("add", "additive", "3"),
        _modifier("multiply", "multiplicative", "2"),
        _modifier("cap", "clamp_max", "24"),
        _modifier("inactive", "additive", "99", condition_ref="condition:blessed"),
    ]
    resolver = EffectiveStatResolver()

    first = resolver.resolve(baseline, modifiers)
    second = resolver.resolve(baseline, list(reversed(modifiers)))

    assert first.effective_value == Decimal("24")
    assert first.explanation_digest == second.explanation_digest
    assert first.rejected_modifier_reasons == {"inactive": "condition_false"}


def test_resolver_applies_stacking_policy_and_rejects_unresolved_exclusive_conflict() -> None:
    baseline = StatBaseline(stat_id="combat.power", value=Decimal("10"), source_ref="profile:warrior")
    resolver = EffectiveStatResolver()
    high = _modifier("high", "additive", "5", stacking_key="blessing", stacking_policy="highest")
    low = _modifier("low", "additive", "2", stacking_key="blessing", stacking_policy="highest")

    result = resolver.resolve(baseline, [low, high])
    assert result.effective_value == Decimal("15")
    assert result.rejected_modifier_reasons == {"low": "lower_priority"}

    with pytest.raises(EffectiveStatError, match="modifier_conflict_unresolved"):
        resolver.resolve(
            baseline,
            [
                _modifier("a", "override", "11", stacking_key="override-a"),
                _modifier("b", "override", "12", stacking_key="override-b"),
            ],
        )
