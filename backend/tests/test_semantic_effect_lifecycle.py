from __future__ import annotations

from app.gameplay.semantic_effects import (
    EffectApplication,
    EffectLifecycleEvaluator,
    ResistanceProfile,
    StateDefinition,
)
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.semantic_authority import SemanticEffectCommand, SemanticSettlementAuthority
import pytest

from app.gameplay.semantic_registry import (
    MetaRuleDefinition,
    RuleEvaluationInput,
    SemanticRegistry,
    SemanticRegistryError,
    StateLifecyclePolicy,
    TagAssignment,
    TagDefinition,
)
from app.gameplay.survival_runtime import SurvivalAuthority


def test_effect_lifecycle_applies_resistance_and_emits_expiry_obligation() -> None:
    result = EffectLifecycleEvaluator().resolve(
        EffectApplication(
            effect_ref="effect:frost",
            target_component_ref="crop:wheat:1",
            magnitude=100,
            stack_key="frost",
            expires_at_tick=12,
            causal_chain_id="chain:frost:1",
        ),
        resistance=ResistanceProfile(effect_ref="effect:frost", source_ref="crop:wheat:1", modifier_basis_points=2500, revision=1),
        state=StateDefinition(state_ref="state:frosted", stack_policy="refresh", stack_limit=1, expiry_policy="scheduled"),
        existing_stacks=0,
    )
    assert result.accepted is True
    assert result.effective_magnitude == 75
    assert result.next_stacks == 1
    assert result.expiry_obligation is not None
    assert result.expiry_obligation["due_tick"] == 12


def test_effect_lifecycle_rejects_overflow_without_state_mutation() -> None:
    result = EffectLifecycleEvaluator().resolve(
        EffectApplication(effect_ref="effect:frost", target_component_ref="crop:wheat:1", magnitude=10, stack_key="frost", causal_chain_id="chain:frost:1"),
        resistance=ResistanceProfile(effect_ref="effect:frost", source_ref="crop:wheat:1", modifier_basis_points=0, revision=1),
        state=StateDefinition(state_ref="state:frosted", stack_policy="reject", stack_limit=1, expiry_policy="none"),
        existing_stacks=1,
    )
    assert result.accepted is False
    assert result.error_code == "state_stack_limit"
    assert result.next_stacks == 1


def test_state_lifecycle_decides_dispel_without_writing() -> None:
    state = StateDefinition(
        state_ref="state:cold",
        stack_policy="add",
        stack_limit=2,
        expiry_policy="scheduled",
        dispel_allowed=True,
        transform_targets=("state:recovering",),
    )
    evaluator = EffectLifecycleEvaluator()

    dispel = evaluator.resolve_dispel(state=state, existing_stacks=2)
    assert dispel.accepted and dispel.next_stacks == 0


def test_state_lifecycle_decides_fixed_transform_without_writing() -> None:
    state = StateDefinition(
        state_ref="state:cold",
        stack_policy="add",
        stack_limit=2,
        expiry_policy="scheduled",
        transform_targets=("state:recovering",),
    )

    transform = EffectLifecycleEvaluator().resolve_transform(
        state=state,
        existing_stacks=2,
        target_state_ref="state:recovering",
    )

    assert transform.accepted and transform.next_stacks == 1
    assert transform.next_state_ref == "state:recovering"


def test_state_lifecycle_rejects_disallowed_dispel_without_writing() -> None:
    evaluator = EffectLifecycleEvaluator()
    state = StateDefinition(
        state_ref="state:cold",
        stack_policy="replace",
        stack_limit=1,
        expiry_policy="none",
        dispel_allowed=False,
        transform_targets=("state:recovering",),
    )

    dispel = evaluator.resolve_dispel(state=state, existing_stacks=1)
    assert not dispel.accepted and dispel.error_code == "state_dispel_not_allowed"


def test_state_lifecycle_rejects_unregistered_transform_without_writing() -> None:
    state = StateDefinition(
        state_ref="state:cold",
        stack_policy="replace",
        stack_limit=1,
        expiry_policy="none",
        transform_targets=("state:recovering",),
    )

    transform = EffectLifecycleEvaluator().resolve_transform(
        state=state,
        existing_stacks=1,
        target_state_ref="state:arbitrary",
    )

    assert not transform.accepted and transform.error_code == "state_transform_target_unregistered"


def test_closed_guard_composes_tag_status_and_numeric_predicates_without_a_write_path() -> None:
    registry = SemanticRegistry()
    registry.register_tag(
        TagDefinition(
            tag_ref="property:flammable",
            category="property",
            parameter_schema={"temperature": "int"},
            version="1",
        )
    )
    registry.assign_tag(
        TagAssignment(
            entity_ref="thing:torch:1",
            tag_ref="property:flammable",
            parameter_values={"temperature": 80},
            source_ref="fixture",
            revision=1,
        )
    )
    registry.register_meta_rule(
        MetaRuleDefinition(
            rule_ref="rule:torch:ignite:v1",
            rule_version="1",
            trigger_selectors=("fact:heat",),
            guard_expression="all(tag:property:flammable,status:dry,parameter_gte:temperature=70)",
            phase="derive",
            priority=1,
            conflict_policy="exclusive",
            evaluation_budget=1,
            trace_policy="authority_only",
            source_revision="1",
        )
    )

    trace = registry.evaluate(
        RuleEvaluationInput(
            trigger_ref="fact:heat",
            semantic_snapshot=registry.build_snapshot("thing:torch:1", statuses=("dry",)),
        )
    )

    assert trace.guard_results == {"rule:torch:ignite:v1": True}
    assert trace.proposal_digests == ()


def test_closed_guard_all_composition_rejects_when_one_finite_term_is_false() -> None:
    registry = SemanticRegistry()
    registry.register_tag(TagDefinition(tag_ref="property:flammable", category="property", version="1"))
    registry.assign_tag(TagAssignment(entity_ref="thing:torch:1", tag_ref="property:flammable", source_ref="fixture", revision=1))
    registry.register_meta_rule(
        MetaRuleDefinition(
            rule_ref="rule:torch:all:v1",
            rule_version="1",
            trigger_selectors=("fact:heat",),
            guard_expression="all(tag:property:flammable,status:dry)",
            phase="derive",
            priority=1,
            conflict_policy="exclusive",
            evaluation_budget=1,
            trace_policy="authority_only",
            source_revision="1",
        )
    )

    trace = registry.evaluate(RuleEvaluationInput(trigger_ref="fact:heat", semantic_snapshot=registry.build_snapshot("thing:torch:1")))

    assert trace.guard_results == {"rule:torch:all:v1": False}


def test_closed_guard_any_composition_accepts_one_finite_term() -> None:
    registry = SemanticRegistry()
    registry.register_tag(TagDefinition(tag_ref="property:flammable", category="property", version="1"))
    registry.assign_tag(TagAssignment(entity_ref="thing:torch:1", tag_ref="property:flammable", source_ref="fixture", revision=1))
    registry.register_meta_rule(
        MetaRuleDefinition(
            rule_ref="rule:torch:any:v1",
            rule_version="1",
            trigger_selectors=("fact:heat",),
            guard_expression="any(status:wet,tag:property:flammable)",
            phase="derive",
            priority=1,
            conflict_policy="exclusive",
            evaluation_budget=1,
            trace_policy="authority_only",
            source_revision="1",
        )
    )

    trace = registry.evaluate(RuleEvaluationInput(trigger_ref="fact:heat", semantic_snapshot=registry.build_snapshot("thing:torch:1")))

    assert trace.guard_results == {"rule:torch:any:v1": True}


def test_closed_guard_rejects_unbounded_or_malformed_composition_without_mutation() -> None:
    with pytest.raises(ValueError, match="semantic_guard_expression_unsupported"):
        MetaRuleDefinition(
            rule_ref="rule:invalid:v1",
            rule_version="1",
            trigger_selectors=("fact:heat",),
            guard_expression="all(tag:property:flammable,__import__('os'))",
            phase="derive",
            priority=1,
            conflict_policy="exclusive",
            evaluation_budget=1,
            trace_policy="authority_only",
            source_revision="1",
        )


def test_lifecycle_resolution_reaches_existing_authority_append_path() -> None:
    registry = SemanticRegistry()
    registry.register_tag(TagDefinition(tag_ref="type:crop", category="type", version="1"))
    registry.assign_tag(TagAssignment(entity_ref="crop:wheat:1", tag_ref="type:crop", source_ref="test", revision=1))
    snapshot = registry.build_snapshot("crop:wheat:1", source_revision_vector={"semantic": 1})
    store = GameplayEventStore()
    authority = SemanticSettlementAuthority(store=store, registry=registry)
    result = authority.settle_lifecycle(
        SemanticEffectCommand(command_id="effect:frost:1", idempotency_key="effect:frost:1", principal_ref="authority:ecology", owner_ref="authority:crop", stream_id="crop:wheat:1", expected_revision=0, effect_ref="effect:frost", target_ref="crop:wheat:1", semantic_snapshot=snapshot, expected_snapshot_digest=snapshot.digest),
        application=EffectApplication(effect_ref="effect:frost", target_component_ref="crop:wheat:1", magnitude=100, stack_key="frost", expires_at_tick=12, causal_chain_id="chain:frost:1"),
        resistance=ResistanceProfile(effect_ref="effect:frost", source_ref="crop:wheat:1", modifier_basis_points=2500, revision=1),
        state=StateDefinition(state_ref="state:frosted", stack_policy="refresh", stack_limit=1, expiry_policy="scheduled"),
        existing_stacks=0,
    )
    assert result.committed is True
    assert store.read_events()[0].payload["effective_magnitude"] == 75
    assert store.read_events()[0].payload["expiry_obligation"]["due_tick"] == 12


def test_closed_cold_proposal_delegates_to_survival_owner_and_opens_replayable_obligation() -> None:
    registry = SemanticRegistry()
    registry.register_tag(TagDefinition(tag_ref="type:character", category="type", version="1"))
    registry.assign_tag(TagAssignment(entity_ref="character:ava", tag_ref="type:character", source_ref="test", revision=1))
    registry.register_state_lifecycle(
        StateLifecyclePolicy(
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
    )
    snapshot = registry.build_snapshot("character:ava", source_revision_vector={"semantic": 1})
    store = GameplayEventStore()
    result = SemanticSettlementAuthority(store=store, registry=registry).settle_closed_survival_state(
        SemanticEffectCommand(
            command_id="effect:cold:survival:1",
            idempotency_key="effect:cold:survival:1",
            principal_ref="authority:semantic",
            owner_ref="actor_gameplay.survival_domain",
            stream_id="gameplay:survival:character:ava",
            expected_revision=0,
            effect_ref="effect:cold_exposure",
            target_ref="character:ava",
            semantic_snapshot=snapshot,
            expected_snapshot_digest=snapshot.digest,
            privacy_scope="project",
        ),
        application=EffectApplication(
            effect_ref="effect:cold_exposure",
            target_component_ref="character:ava",
            magnitude=100,
            stack_key="cold",
            expires_at_tick=8,
            causal_chain_id="chain:cold:semantic:1",
        ),
        resistance=ResistanceProfile(
            effect_ref="effect:cold_exposure",
            source_ref="character:ava",
            modifier_basis_points=2_500,
            revision=1,
        ),
        state=StateDefinition(
            state_ref="state:cold",
            stack_policy="add",
            stack_limit=2,
            expiry_policy="scheduled",
        ),
    )

    assert result.committed is True
    assert [event.event_type for event in store.read_events()] == [
        "gameplay.survival.state_applied",
        "gameplay.survival.obligation_opened",
    ]
    assert SurvivalAuthority(store=store).projector().open_obligations == {
        "obligation:survival:state:character:ava:state:cold": 8
    }


def test_closed_overheated_proposal_uses_the_registered_survival_owner_row() -> None:
    registry = SemanticRegistry()
    registry.register_tag(TagDefinition(tag_ref="type:character", category="type", version="1"))
    registry.assign_tag(TagAssignment(entity_ref="character:ava", tag_ref="type:character", source_ref="test", revision=1))
    registry.register_state_lifecycle(
        StateLifecyclePolicy(
            state_ref="state:overheated", effect_ref="effect:heat_exposure",
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
    )
    snapshot = registry.build_snapshot("character:ava", source_revision_vector={"semantic": 1})
    store = GameplayEventStore()

    result = SemanticSettlementAuthority(store=store, registry=registry).settle_closed_survival_state(
        SemanticEffectCommand(
            command_id="effect:heat:survival:1", idempotency_key="effect:heat:survival:1",
            principal_ref="authority:semantic", owner_ref="actor_gameplay.survival_domain",
            stream_id="gameplay:survival:character:ava", expected_revision=0,
            effect_ref="effect:heat_exposure", target_ref="character:ava",
            semantic_snapshot=snapshot, expected_snapshot_digest=snapshot.digest, privacy_scope="project",
        ),
        application=EffectApplication(effect_ref="effect:heat_exposure", target_component_ref="character:ava", magnitude=100, stack_key="heat", expires_at_tick=8, causal_chain_id="chain:heat:semantic:1"),
        resistance=ResistanceProfile(effect_ref="effect:heat_exposure", source_ref="character:ava", modifier_basis_points=2_500, revision=1),
        state=StateDefinition(state_ref="state:overheated", stack_policy="add", stack_limit=2, expiry_policy="scheduled"),
    )

    assert result.committed is True
    assert [event.event_type for event in store.read_events()] == [
        "gameplay.survival.state_applied",
        "gameplay.survival.obligation_opened",
    ]
    assert SurvivalAuthority(store=store).projector().states[("character:ava", "state:overheated")].effect_ref == "effect:heat_exposure"


def test_closed_cold_proposal_replays_duplicate_without_second_owner_write() -> None:
    registry = _cold_registry()
    store = GameplayEventStore()
    authority = SemanticSettlementAuthority(store=store, registry=registry)
    first = _settle_cold(authority, registry)
    duplicate = _settle_cold(authority, registry)

    assert first.committed is True
    assert duplicate.committed is True
    assert duplicate.idempotency_status == "duplicate_replayed"
    assert len(store.read_events()) == 2


def test_closed_cold_proposal_rejects_reused_key_with_changed_effect_without_writes() -> None:
    registry = _cold_registry()
    store = GameplayEventStore()
    authority = SemanticSettlementAuthority(store=store, registry=registry)
    assert _settle_cold(authority, registry).committed
    before = len(store.read_events())

    changed = _settle_cold(authority, registry, magnitude=101)

    assert changed.committed is False
    assert changed.failure is not None and changed.failure.error_code == "idempotency_key_reused"
    assert len(store.read_events()) == before


def test_closed_cold_proposal_rejects_stale_survival_revision_without_writes() -> None:
    registry = _cold_registry()
    store = GameplayEventStore()
    authority = SemanticSettlementAuthority(store=store, registry=registry)
    assert _settle_cold(authority, registry).committed
    before = len(store.read_events())

    stale = _settle_cold(authority, registry, expected_revision=0, key="effect:cold:stale")

    assert stale.committed is False
    assert stale.failure is not None and stale.failure.error_code == "revision_conflict"
    assert len(store.read_events()) == before


def test_closed_cold_proposal_rejects_nonproject_privacy_without_writes() -> None:
    registry = _cold_registry()
    store = GameplayEventStore()
    authority = SemanticSettlementAuthority(store=store, registry=registry)
    private = _settle_cold(authority, registry, privacy_scope="authority_only", key="effect:cold:private")

    assert private.failure is not None and private.failure.error_code == "semantic_survival_privacy_scope_denied"
    assert store.read_events() == []


def test_closed_cold_proposal_rejects_unmapped_owner_row_without_writes() -> None:
    registry = _cold_registry()
    store = GameplayEventStore()
    authority = SemanticSettlementAuthority(store=store, registry=registry)
    unmapped = _settle_cold(authority, registry, state_ref="state:burning", key="effect:burning:unmapped")

    assert unmapped.failure is not None and unmapped.failure.error_code == "semantic_state_lifecycle_unknown"
    assert store.read_events() == []


def test_closed_cold_proposal_replays_through_survival_checkpoint_tail_projection() -> None:
    registry = _cold_registry()
    store = GameplayEventStore()
    authority = SemanticSettlementAuthority(store=store, registry=registry)
    assert _settle_cold(authority, registry).committed

    events = store.read_events()
    assert authority.replay_projection().projection_hash == authority.replay_projection(checkpoint_at=1).projection_hash
    assert SurvivalAuthority(store=store).projector().states[("character:ava", "state:cold")].effect_ref == "effect:cold_exposure"
    assert len(events) == 2


def _cold_registry() -> SemanticRegistry:
    registry = SemanticRegistry()
    registry.register_tag(TagDefinition(tag_ref="type:character", category="type", version="1"))
    registry.assign_tag(TagAssignment(entity_ref="character:ava", tag_ref="type:character", source_ref="test", revision=1))
    registry.register_state_lifecycle(
        StateLifecyclePolicy(
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
    )
    return registry


def _settle_cold(
    authority: SemanticSettlementAuthority,
    registry: SemanticRegistry,
    *,
    expected_revision: int = 0,
    key: str = "effect:cold:survival:1",
    privacy_scope: str = "project",
    state_ref: str = "state:cold",
    magnitude: int = 100,
):
    snapshot = registry.build_snapshot("character:ava", source_revision_vector={"semantic": 1})
    return authority.settle_closed_survival_state(
        SemanticEffectCommand(
            command_id=f"command:{key}", idempotency_key=key,
            principal_ref="authority:semantic", owner_ref="actor_gameplay.survival_domain",
            stream_id="gameplay:survival:character:ava", expected_revision=expected_revision,
            effect_ref="effect:cold_exposure", target_ref="character:ava",
            semantic_snapshot=snapshot, expected_snapshot_digest=snapshot.digest, privacy_scope=privacy_scope,
        ),
        application=EffectApplication(effect_ref="effect:cold_exposure", target_component_ref="character:ava", magnitude=magnitude, stack_key="cold", expires_at_tick=8, causal_chain_id="chain:cold:semantic:1"),
        resistance=ResistanceProfile(effect_ref="effect:cold_exposure", source_ref="character:ava", modifier_basis_points=2_500, revision=1),
        state=StateDefinition(state_ref=state_ref, stack_policy="add", stack_limit=2, expiry_policy="scheduled"),
    )
