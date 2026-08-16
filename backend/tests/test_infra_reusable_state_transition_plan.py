from app.gameplay.semantic_effects import (
    EffectApplication,
    EffectLifecycleEvaluator,
    ResistanceProfile,
    StateDefinition,
)
from app.gameplay.semantic_registry import SemanticRegistry


def _application(effect_ref: str = "effect:test") -> EffectApplication:
    return EffectApplication(
        effect_ref=effect_ref,
        target_component_ref="entity:test",
        magnitude=100,
        stack_key="test",
        expires_at_tick=12,
        causal_chain_id="chain:test",
    )


def _resistance(effect_ref: str = "effect:test") -> ResistanceProfile:
    return ResistanceProfile(
        effect_ref=effect_ref,
        source_ref="entity:test",
        modifier_basis_points=2_500,
        revision=1,
    )


def test_reusable_state_plan_exposes_apply_policy_and_expiry_without_write_capability() -> None:
    plan = EffectLifecycleEvaluator().plan_apply(
        _application(),
        resistance=_resistance(),
        state=StateDefinition(state_ref="state:test", stack_policy="refresh", stack_limit=1, expiry_policy="scheduled"),
        existing_stacks=0,
    )

    assert plan.accepted
    assert plan.operation == "refresh"
    assert plan.effect_ref == "effect:test"
    assert plan.state_ref == "state:test"
    assert plan.next_stacks == 1
    assert plan.effective_magnitude == 75
    assert plan.expiry_obligation is not None
    assert plan.expiry_obligation["due_tick"] == 12
    assert not hasattr(plan, "append_batch")


def test_reusable_state_plan_has_distinct_replace_add_and_reject_decisions() -> None:
    evaluator = EffectLifecycleEvaluator()
    for policy, expected_operation in (("add", "add"), ("replace", "replace")):
        plan = evaluator.plan_apply(
            _application(),
            resistance=_resistance(),
            state=StateDefinition(state_ref="state:test", stack_policy=policy, stack_limit=2, expiry_policy="none"),
            existing_stacks=1,
        )
        assert plan.accepted and plan.operation == expected_operation

    rejected = evaluator.plan_apply(
        _application(),
        resistance=_resistance(),
        state=StateDefinition(state_ref="state:test", stack_policy="reject", stack_limit=1, expiry_policy="none"),
        existing_stacks=1,
    )
    assert not rejected.accepted
    assert rejected.operation == "reject"
    assert rejected.next_stacks == 1


def test_reusable_state_plan_covers_dispel_and_transform_as_owner_proposals() -> None:
    state = StateDefinition(
        state_ref="state:test",
        stack_policy="refresh",
        stack_limit=1,
        expiry_policy="scheduled",
        transform_targets=("state:recovered",),
    )
    evaluator = EffectLifecycleEvaluator()
    dispel = evaluator.plan_dispel(state=state, existing_stacks=1)
    transform = evaluator.plan_transform(state=state, existing_stacks=1, target_state_ref="state:recovered")

    assert dispel.accepted and dispel.operation == "dispel" and dispel.next_stacks == 0
    assert transform.accepted and transform.operation == "transform"
    assert transform.next_state_ref == "state:recovered"


def test_same_pure_plan_shape_is_usable_for_registered_survival_construction_and_ecology_rows() -> None:
    evaluator = EffectLifecycleEvaluator()
    rows = SemanticRegistry.closed_state_owner_contracts()
    selected = [
        row for row in rows
        if row.owner_ref in {
            "actor_gameplay.survival_domain",
            "actor_gameplay.construction_production_domain",
            "authority:ecology",
        }
    ]

    assert len(selected) >= 3
    for row in selected:
        effect_ref = row.effect_ref
        plan = evaluator.plan_apply(
            _application(effect_ref),
            resistance=_resistance(effect_ref),
            state=row.definition,
            existing_stacks=0,
        )
        assert plan.accepted
        assert plan.state_ref == row.state_ref
        assert plan.operation in {"add", "replace", "refresh"}
