from __future__ import annotations

import pytest

from app.gameplay.construction_production_runtime import ProductionRun, Recipe
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.semantic_authority import SemanticProductionFinishCommand, SemanticSettlementAuthority
from app.gameplay.semantic_registry import (
    ClosedEffectDefinition,
    ClosedRuleDefinition,
    OwnerMapping,
    RuleSetRevision,
    SemanticRegistry,
    SemanticRegistryError,
    StateLifecyclePolicy,
    TagAssignment,
    TagDefinition,
)


def _registry() -> SemanticRegistry:
    registry = SemanticRegistry()
    registry.register_tag(TagDefinition(tag_ref="type:facility", category="type", version="1"))
    registry.assign_tag(TagAssignment(entity_ref="facility:bakery:1", tag_ref="type:facility", source_ref="fixture", revision=1))
    registry.register_owner_mapping(
        OwnerMapping(
            effect_ref="effect:production_due_finish",
            owner_ref="actor_gameplay.construction_production_domain",
            stream_pattern="gameplay:construction_production:{facility_ref}",
            event_type="gameplay.construction_production.run_finished",
            fragment_builder_ref="ConstructionProductionAuthority.build_due_finish_fragment",
            projection_scope="project",
            revision="1",
        )
    )
    registry.register_closed_effect(
        ClosedEffectDefinition(
            effect_ref="effect:production_due_finish",
            input_schema_ref="schema:production-finish:v1",
            stack_policy="one_shot",
            revision="1",
        )
    )
    registry.register_rule_set(
        RuleSetRevision(
            rule_set_ref="rules:production:v1",
            revision="1",
            active_semantic_set_digest="sha256:semantic",
            rules=(
                ClosedRuleDefinition(
                    rule_ref="rule:production_due_finish:v1",
                    phase="settle",
                    priority=10,
                    specificity=1,
                    conflict_policy="exclusive",
                    handler_ref="handler:production_due_finish",
                    effect_ref="effect:production_due_finish",
                    owner_mapping_ref="effect:production_due_finish",
                ),
            ),
        )
    )
    return registry


def _command(registry: SemanticRegistry) -> SemanticProductionFinishCommand:
    snapshot = registry.build_snapshot("facility:bakery:1", policy_context_ref="policy:production:1", source_revision_vector={"semantic": 1})
    return SemanticProductionFinishCommand(
        command_id="semantic:closed-production:1",
        idempotency_key="semantic:closed-production:1",
        principal_ref="authority:semantic",
        expected_revision=0,
        effect_ref="effect:production_due_finish",
        source_rule_ref="rule:production_due_finish:v1",
        rule_set_revision="rules:production:v1",
        trace_digest="sha256:trace",
        causal_chain_id="chain:production:1",
        semantic_snapshot=snapshot,
        expected_snapshot_digest=snapshot.digest,
        run=ProductionRun(run_ref="run:bakery:1", facility_ref="facility:bakery:1", recipe_ref="recipe:bread:1", started_tick=0, finish_tick=3, output_item="item:bread"),
        recipe=Recipe(recipe_ref="recipe:bread:1", inputs={}, output_item="item:bread", duration_ticks=3),
        tick=3,
    )


def test_closed_ruleset_is_immutable_and_evaluates_the_registered_production_row() -> None:
    registry = _registry()

    evaluation = registry.evaluate_closed_rule_set(
        rule_set_ref="rules:production:v1",
        effect_ref="effect:production_due_finish",
        target_ref="facility:bakery:1",
        semantic_snapshot_digest="sha256:snapshot",
    )

    assert evaluation.rule_refs == ("rule:production_due_finish:v1",)
    assert evaluation.owner_mapping.event_type == "gameplay.construction_production.run_finished"
    assert evaluation.trace_digest.startswith("sha256:")
    with pytest.raises(SemanticRegistryError, match="duplicate"):
        registry.register_rule_set(registry.rule_set("rules:production:v1"))


def test_closed_ruleset_rejects_unmapped_owner_and_durable_lifecycle_without_mutation() -> None:
    registry = _registry()

    with pytest.raises(SemanticRegistryError, match="owner_mapping"):
        registry.evaluate_closed_rule_set(rule_set_ref="rules:production:v1", effect_ref="effect:frost", target_ref="crop:wheat:1", semantic_snapshot_digest="sha256:snapshot")
    with pytest.raises(SemanticRegistryError, match="lifecycle_owner_unregistered"):
        registry.register_state_lifecycle(StateLifecyclePolicy(state_ref="state:frosted", lifecycle="scheduled", revision="1"))
    assert registry.owner_mappings() == (registry.owner_mapping("effect:production_due_finish"),)


def test_survival_state_expiry_lifecycle_is_the_only_registered_scheduled_owner_row() -> None:
    registry = _registry()
    policy = StateLifecyclePolicy(
        state_ref="state:cold", effect_ref="effect:cold_exposure",
        lifecycle="scheduled",
        revision="1",
        owner_ref="actor_gameplay.survival_domain",
        stream_pattern="gameplay:survival:{actor_ref}",
        opened_event_type="gameplay.survival.obligation_opened",
        settled_event_type="gameplay.survival.obligation_settled",
        cancelled_event_type="gameplay.survival.obligation_cancelled",
        fragment_builder_ref="SurvivalAuthority.build_state_expiry_fragment",
        projection_scope="project",
    )

    registry.register_state_lifecycle(policy)

    assert registry.state_lifecycle("state:cold") == policy
    with pytest.raises(SemanticRegistryError, match="lifecycle_owner_unregistered"):
        registry.register_state_lifecycle(
            policy.model_copy(update={"state_ref": "state:unmapped", "owner_ref": "actor_gameplay.economy_domain"})
        )


def test_closed_ruleset_authority_uses_only_registered_production_fragment() -> None:
    registry = _registry()
    store = GameplayEventStore()

    result = SemanticSettlementAuthority(store=store, registry=registry).settle_closed_production_finish(_command(registry))

    assert result.committed is True
    assert store.read_events()[0].event_type == "gameplay.construction_production.run_finished"
    assert store.read_events()[0].payload["rule_set_revision"] == "rules:production:v1"


def test_closed_ruleset_authority_rejects_rule_mapping_mismatch_without_write() -> None:
    registry = _registry()
    store = GameplayEventStore()
    command = _command(registry).model_copy(update={"source_rule_ref": "rule:unknown"}, deep=True)

    result = SemanticSettlementAuthority(store=store, registry=registry).settle_closed_production_finish(command)

    assert result.committed is False
    assert result.failure is not None
    assert result.failure.error_code == "semantic_closed_rule_unknown"
    assert store.read_events() == []


def test_closed_ruleset_trace_is_filtered_independently_by_scope() -> None:
    registry = _registry()
    evaluation = registry.evaluate_closed_rule_set(
        rule_set_ref="rules:production:v1",
        effect_ref="effect:production_due_finish",
        target_ref="facility:bakery:1",
        semantic_snapshot_digest="sha256:snapshot",
    )

    public = registry.project_closed_trace(evaluation, scope="public")
    authority = registry.project_closed_trace(evaluation, scope="authority")

    assert public["rule_refs"] == ()
    assert public["trace_digest"] == evaluation.trace_digest
    assert authority["rule_refs"] == ("rule:production_due_finish:v1",)


def test_closed_ruleset_changed_idempotency_input_is_zero_write() -> None:
    registry = _registry()
    store = GameplayEventStore()
    authority = SemanticSettlementAuthority(store=store, registry=registry)
    first = _command(registry)
    altered = first.model_copy(update={"tick": 4}, deep=True)

    assert authority.settle_closed_production_finish(first).committed is True
    result = authority.settle_closed_production_finish(altered)

    assert result.committed is False
    assert result.failure is not None
    assert result.failure.error_code == "idempotency_key_reused_with_different_payload"
    assert len(store.read_events()) == 1


@pytest.mark.parametrize(
    ("conflict_policy", "expected"),
    [
        ("exclusive", "rule:conflict:v1"),
        ("replace", "rule:conflict:v1"),
        ("minimum", "rule:conflict:v1"),
        ("maximum", "rule:conflict:v1"),
        ("additive", "rule:conflict:v1,rule:conflict:v2"),
    ],
)
def test_closed_ruleset_conflict_policies_are_deterministic(conflict_policy: str, expected: str) -> None:
    registry = SemanticRegistry()
    registry.register_owner_mapping(OwnerMapping(effect_ref="effect:production_due_finish", owner_ref="actor_gameplay.construction_production_domain", stream_pattern="gameplay:construction_production:{facility_ref}", event_type="gameplay.construction_production.run_finished", fragment_builder_ref="ConstructionProductionAuthority.build_due_finish_fragment", projection_scope="project", revision="1"))
    registry.register_closed_effect(ClosedEffectDefinition(effect_ref="effect:production_due_finish", input_schema_ref="schema:production-finish:v1", stack_policy="one_shot", revision="1"))
    registry.register_rule_set(RuleSetRevision(rule_set_ref=f"rules:conflict:{conflict_policy}", revision="1", active_semantic_set_digest="sha256:semantic", rules=(
        ClosedRuleDefinition(rule_ref="rule:conflict:v1", phase="settle", priority=10, specificity=1, conflict_policy=conflict_policy, handler_ref="handler:production_due_finish", effect_ref="effect:production_due_finish", owner_mapping_ref="effect:production_due_finish"),
        ClosedRuleDefinition(rule_ref="rule:conflict:v2", phase="settle", priority=5, specificity=1, conflict_policy=conflict_policy, handler_ref="handler:production_due_finish", effect_ref="effect:production_due_finish", owner_mapping_ref="effect:production_due_finish"),
    )))

    evaluation = registry.evaluate_closed_rule_set(rule_set_ref=f"rules:conflict:{conflict_policy}", effect_ref="effect:production_due_finish", target_ref="facility:bakery:1", semantic_snapshot_digest="sha256:snapshot")

    assert ",".join(evaluation.rule_refs) == expected


@pytest.mark.parametrize("conflict_policy,error", [("reject", "conflict_rejected"), ("suppress", "suppressed")])
def test_closed_ruleset_reject_and_suppress_are_fail_closed(conflict_policy: str, error: str) -> None:
    registry = SemanticRegistry()
    registry.register_owner_mapping(OwnerMapping(effect_ref="effect:production_due_finish", owner_ref="actor_gameplay.construction_production_domain", stream_pattern="gameplay:construction_production:{facility_ref}", event_type="gameplay.construction_production.run_finished", fragment_builder_ref="ConstructionProductionAuthority.build_due_finish_fragment", projection_scope="project", revision="1"))
    registry.register_closed_effect(ClosedEffectDefinition(effect_ref="effect:production_due_finish", input_schema_ref="schema:production-finish:v1", stack_policy="one_shot", revision="1"))
    registry.register_rule_set(RuleSetRevision(rule_set_ref=f"rules:{conflict_policy}", revision="1", active_semantic_set_digest="sha256:semantic", rules=(ClosedRuleDefinition(rule_ref="rule:conflict", phase="settle", priority=1, specificity=1, conflict_policy=conflict_policy, handler_ref="handler:production_due_finish", effect_ref="effect:production_due_finish", owner_mapping_ref="effect:production_due_finish"),)))

    with pytest.raises(SemanticRegistryError, match=error):
        registry.evaluate_closed_rule_set(rule_set_ref=f"rules:{conflict_policy}", effect_ref="effect:production_due_finish", target_ref="facility:bakery:1", semantic_snapshot_digest="sha256:snapshot")


def test_closed_effect_resistance_is_fixed_precision_and_has_no_write_path() -> None:
    registry = _registry()

    resolution = registry.resolve_closed_effect(effect_ref="effect:production_due_finish", magnitude=100, resistance_basis_points=2_500)

    assert resolution.effective_magnitude == 75
    assert resolution.effect_ref == "effect:production_due_finish"
    with pytest.raises(SemanticRegistryError, match="owner_mapping"):
        registry.resolve_closed_effect(effect_ref="effect:frost", magnitude=100, resistance_basis_points=0)


def test_closed_ruleset_production_projection_full_and_checkpoint_tail_replay_match() -> None:
    registry = _registry()
    authority = SemanticSettlementAuthority(store=GameplayEventStore(), registry=registry)

    assert authority.settle_closed_production_finish(_command(registry)).committed is True

    assert authority.replay_projection().projection_hash == authority.replay_projection(checkpoint_at=1).projection_hash
