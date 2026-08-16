from __future__ import annotations

import pytest

from app.gameplay.construction_production_runtime import ConstructionProductionAuthority, Facility, ProductionRun, Recipe
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import OwnerAuthorizedFragment
from app.gameplay.semantic_effects import EffectApplication, ResistanceProfile, StateDefinition
from app.gameplay.shared_contracts import GameplayCommandEnvelope
from app.gameplay.shared_contracts import ScheduledObligation
from app.gameplay.survival_runtime import SurvivalAuthority, SurvivalState, SurvivalStateExpiryPolicy
from app.world_runtime.obligations import ObligationLifecycleProjection, ObligationLifecycleRegistration, ObligationSettlementCoordinator
from app.world_runtime.simulation_clock import SimulationClock


def _survival_command() -> GameplayCommandEnvelope:
    return GameplayCommandEnvelope(
        command_id="command:survival:open",
        command_type="gameplay.survival.apply_state",
        command_version=1,
        principal_ref="actor_gameplay.survival_domain",
        actor_ref="character:ava",
        project_ref="project:demo",
        idempotency_key="survival:open",
        expected_revisions={"gameplay:survival:character:ava": 0},
        causation_id="cause:survival:open",
        correlation_id="corr:survival:open",
        source_ref="proposal:semantic:cold",
        submitted_at="2026-08-13T00:00:00Z",
    )


def _registrations() -> tuple[ObligationLifecycleRegistration, ...]:
    return (
        ObligationLifecycleRegistration(
            policy_ref="policy:construction_due_completion",
            policy_revision="1",
            owner_ref="actor_gameplay.construction_production_domain",
            stream_pattern="gameplay:construction_production:{facility_ref}",
            opened_event_type="gameplay.construction_production.run_started",
            settled_event_type="gameplay.construction_production.obligation_settled",
            cancelled_event_type="gameplay.construction_production.obligation_cancelled",
            visibility_scope="project",
        ),
        ObligationLifecycleRegistration(
            policy_ref="policy:survival_state_expiry",
            policy_revision="1",
            owner_ref="actor_gameplay.survival_domain",
            stream_pattern="gameplay:survival:{actor_ref}",
            opened_event_type="gameplay.survival.obligation_opened",
            settled_event_type="gameplay.survival.obligation_settled",
            cancelled_event_type="gameplay.survival.obligation_cancelled",
            retry_event_type="gameplay.survival.obligation_retry_scheduled",
            compensated_event_type="gameplay.survival.obligation_compensated",
            visibility_scope="project",
        ),
    )


def test_lifecycle_projection_rebuilds_open_obligations_for_two_registered_owners() -> None:
    store = GameplayEventStore()
    ConstructionProductionAuthority(store=store).settle_start_run(
        facility=Facility(facility_ref="facility:bakery", plot_ref="plot:bakery", facility_kind="bakery", condition=1),
        recipe=Recipe(recipe_ref="recipe:bread", inputs={}, output_item="item:bread", duration_ticks=3),
        run_ref="run:bakery",
        tick=0,
        command_id="command:construction:open",
        idempotency_key="construction:open",
        causation_id="cause:construction:open",
        correlation_id="corr:construction:open",
    )
    SurvivalAuthority(store=store).apply_effect_state(
        command=_survival_command(),
        application=EffectApplication(effect_ref="effect:cold", target_component_ref="character:ava", magnitude=1, stack_key="cold", expires_at_tick=4, causal_chain_id="chain:cold"),
        resistance=ResistanceProfile(effect_ref="effect:cold", source_ref="character:ava", modifier_basis_points=0, revision=1),
        definition=StateDefinition(state_ref="state:cold", stack_policy="add", stack_limit=1, expiry_policy="scheduled"),
    )

    projection = ObligationLifecycleProjection(_registrations()).rebuild(store.read_events())

    assert set(projection.open) == {
        "obligation:construction-production:finish:run:bakery",
        "obligation:survival:state:character:ava:state:cold",
    }
    assert {record.owner_ref for record in projection.open.values()} == {
        "actor_gameplay.construction_production_domain",
        "actor_gameplay.survival_domain",
    }


def test_lifecycle_projection_derives_due_without_writing_a_second_lifecycle_fact() -> None:
    store = GameplayEventStore()
    SurvivalAuthority(store=store).apply_effect_state(
        command=_survival_command(),
        application=EffectApplication(effect_ref="effect:cold", target_component_ref="character:ava", magnitude=1, stack_key="cold", expires_at_tick=4, causal_chain_id="chain:cold"),
        resistance=ResistanceProfile(effect_ref="effect:cold", source_ref="character:ava", modifier_basis_points=0, revision=1),
        definition=StateDefinition(state_ref="state:cold", stack_policy="add", stack_limit=1, expiry_policy="scheduled"),
    )

    projection = ObligationLifecycleProjection(_registrations()).rebuild(store.read_events())

    assert [record.obligation_id for record in projection.due_at(4)] == [
        "obligation:survival:state:character:ava:state:cold"
    ]
    assert len(store.read_events()) == 2


def test_lifecycle_time_view_marks_only_the_bounded_cross_owner_due_prefix() -> None:
    store = GameplayEventStore()
    ConstructionProductionAuthority(store=store).settle_start_run(
        facility=Facility(facility_ref="facility:bakery", plot_ref="plot:bakery", facility_kind="bakery", condition=1),
        recipe=Recipe(recipe_ref="recipe:bread", inputs={}, output_item="item:bread", duration_ticks=3),
        run_ref="run:bakery",
        tick=0,
        command_id="command:construction:time-view",
        idempotency_key="construction:time-view",
        causation_id="cause:construction:time-view",
        correlation_id="corr:construction:time-view",
    )
    SurvivalAuthority(store=store).apply_effect_state(
        command=_survival_command(),
        application=EffectApplication(effect_ref="effect:cold", target_component_ref="character:ava", magnitude=1, stack_key="cold", expires_at_tick=4, causal_chain_id="chain:cold"),
        resistance=ResistanceProfile(effect_ref="effect:cold", source_ref="character:ava", modifier_basis_points=0, revision=1),
        definition=StateDefinition(state_ref="state:cold", stack_policy="add", stack_limit=1, expiry_policy="scheduled"),
    )
    before = store.export_snapshot()

    view = ObligationLifecycleProjection(_registrations()).rebuild(store.read_events()).at_tick(
        4,
        catch_up_limit=1,
    )

    assert view.open["obligation:construction-production:finish:run:bakery"].status == "due"
    assert view.open["obligation:survival:state:character:ava:state:cold"].status == "open"
    assert store.export_snapshot() == before


def test_lifecycle_time_view_checkpoint_tail_replay_matches_full_replay() -> None:
    store = GameplayEventStore()
    ConstructionProductionAuthority(store=store).settle_start_run(
        facility=Facility(facility_ref="facility:bakery", plot_ref="plot:bakery", facility_kind="bakery", condition=1),
        recipe=Recipe(recipe_ref="recipe:bread", inputs={}, output_item="item:bread", duration_ticks=3),
        run_ref="run:bakery",
        tick=0,
        command_id="command:construction:time-checkpoint",
        idempotency_key="construction:time-checkpoint",
        causation_id="cause:construction:time-checkpoint",
        correlation_id="corr:construction:time-checkpoint",
    )
    SurvivalAuthority(store=store).apply_effect_state(
        command=_survival_command(),
        application=EffectApplication(effect_ref="effect:cold", target_component_ref="character:ava", magnitude=1, stack_key="cold", expires_at_tick=4, causal_chain_id="chain:cold"),
        resistance=ResistanceProfile(effect_ref="effect:cold", source_ref="character:ava", modifier_basis_points=0, revision=1),
        definition=StateDefinition(state_ref="state:cold", stack_policy="add", stack_limit=1, expiry_policy="scheduled"),
    )
    events = store.read_events()
    projection = ObligationLifecycleProjection(_registrations())

    full = projection.replay_at(events, tick=4, catch_up_limit=2)
    checkpoint = projection.create_checkpoint(events[:1])
    tail = projection.checkpoint_plus_tail_at(
        checkpoint,
        events[1:],
        tick=4,
        catch_up_limit=2,
    )

    assert tail == full


def test_lifecycle_time_view_rejects_materialized_due_checkpoint_without_write() -> None:
    store = GameplayEventStore()
    SurvivalAuthority(store=store).apply_effect_state(
        command=_survival_command(),
        application=EffectApplication(effect_ref="effect:cold", target_component_ref="character:ava", magnitude=1, stack_key="cold", expires_at_tick=4, causal_chain_id="chain:cold"),
        resistance=ResistanceProfile(effect_ref="effect:cold", source_ref="character:ava", modifier_basis_points=0, revision=1),
        definition=StateDefinition(state_ref="state:cold", stack_policy="add", stack_limit=1, expiry_policy="scheduled"),
    )
    projection = ObligationLifecycleProjection(_registrations())
    materialized_view = projection.replay_at(store.read_events(), tick=4, catch_up_limit=1)
    before = store.export_snapshot()

    with pytest.raises(ValueError, match="obligation_lifecycle_checkpoint_due_invalid"):
        projection.checkpoint_plus_tail_at(
            materialized_view,
            [],
            tick=4,
            catch_up_limit=0,
        )

    assert store.export_snapshot() == before


def test_lifecycle_time_view_preserves_registered_privacy_scope() -> None:
    store = GameplayEventStore()
    SurvivalAuthority(store=store).apply_effect_state(
        command=_survival_command(),
        application=EffectApplication(effect_ref="effect:cold", target_component_ref="character:ava", magnitude=1, stack_key="cold", expires_at_tick=4, causal_chain_id="chain:cold"),
        resistance=ResistanceProfile(effect_ref="effect:cold", source_ref="character:ava", modifier_basis_points=0, revision=1),
        definition=StateDefinition(state_ref="state:cold", stack_policy="add", stack_limit=1, expiry_policy="scheduled"),
    )

    view = ObligationLifecycleProjection(_registrations()).replay_at(
        store.read_events(),
        tick=4,
        catch_up_limit=1,
    )

    assert view.open["obligation:survival:state:character:ava:state:cold"].visibility_scope == "project"


def test_lifecycle_time_view_rejects_invalid_budget_without_write() -> None:
    store = GameplayEventStore()
    SurvivalAuthority(store=store).apply_effect_state(
        command=_survival_command(),
        application=EffectApplication(effect_ref="effect:cold", target_component_ref="character:ava", magnitude=1, stack_key="cold", expires_at_tick=4, causal_chain_id="chain:cold"),
        resistance=ResistanceProfile(effect_ref="effect:cold", source_ref="character:ava", modifier_basis_points=0, revision=1),
        definition=StateDefinition(state_ref="state:cold", stack_policy="add", stack_limit=1, expiry_policy="scheduled"),
    )
    before = store.export_snapshot()

    with pytest.raises(ValueError, match="obligation_catch_up_limit_invalid"):
        ObligationLifecycleProjection(_registrations()).replay_at(
            store.read_events(),
            tick=4,
            catch_up_limit=True,
        )

    assert store.export_snapshot() == before


def test_lifecycle_time_view_rejects_invalid_tick_without_write() -> None:
    store = GameplayEventStore()
    SurvivalAuthority(store=store).apply_effect_state(
        command=_survival_command(),
        application=EffectApplication(effect_ref="effect:cold", target_component_ref="character:ava", magnitude=1, stack_key="cold", expires_at_tick=4, causal_chain_id="chain:cold"),
        resistance=ResistanceProfile(effect_ref="effect:cold", source_ref="character:ava", modifier_basis_points=0, revision=1),
        definition=StateDefinition(state_ref="state:cold", stack_policy="add", stack_limit=1, expiry_policy="scheduled"),
    )
    before = store.export_snapshot()

    with pytest.raises(ValueError, match="obligation_due_tick_invalid"):
        ObligationLifecycleProjection(_registrations()).replay_at(
            store.read_events(),
            tick=-1,
            catch_up_limit=1,
        )

    assert store.export_snapshot() == before


def test_lifecycle_time_view_rejects_boolean_tick_without_write() -> None:
    store = GameplayEventStore()
    SurvivalAuthority(store=store).apply_effect_state(
        command=_survival_command(),
        application=EffectApplication(effect_ref="effect:cold", target_component_ref="character:ava", magnitude=1, stack_key="cold", expires_at_tick=4, causal_chain_id="chain:cold"),
        resistance=ResistanceProfile(effect_ref="effect:cold", source_ref="character:ava", modifier_basis_points=0, revision=1),
        definition=StateDefinition(state_ref="state:cold", stack_policy="add", stack_limit=1, expiry_policy="scheduled"),
    )
    before = store.export_snapshot()

    with pytest.raises(ValueError, match="obligation_due_tick_invalid"):
        ObligationLifecycleProjection(_registrations()).replay_at(
            store.read_events(),
            tick=True,
            catch_up_limit=1,
        )

    assert store.export_snapshot() == before


def test_scheduled_obligation_accepts_canonical_generic_lifecycle_statuses() -> None:
    statuses = ("open", "due", "settled", "cancelled", "expired", "retry", "compensated")

    for status in statuses:
        assert ScheduledObligation(
            obligation_id=f"obligation:status:{status}",
            owner_ref="actor_gameplay.survival_domain",
            due_tick=1,
            policy_revision="1",
            status=status,
            idempotency_key=f"obligation:status:{status}",
        ).status == status


def test_lifecycle_projection_rebuilds_survival_settled_terminal_fact() -> None:
    store = GameplayEventStore()
    authority = SurvivalAuthority(store=store)
    authority.apply_effect_state(
        command=_survival_command(),
        application=EffectApplication(effect_ref="effect:cold", target_component_ref="character:ava", magnitude=1, stack_key="cold", expires_at_tick=4, causal_chain_id="chain:cold"),
        resistance=ResistanceProfile(effect_ref="effect:cold", source_ref="character:ava", modifier_basis_points=0, revision=1),
        definition=StateDefinition(state_ref="state:cold", stack_policy="add", stack_limit=1, expiry_policy="scheduled"),
    )
    policy = SurvivalStateExpiryPolicy()
    obligation = policy.build_obligation(actor_ref="character:ava", state_ref="state:cold", due_tick=4, expected_revision=2, status="due")
    coordinator = ObligationSettlementCoordinator(store=store, lifecycle_registrations=_registrations())
    settlement = coordinator.plan_settle(
        obligation=obligation,
        fragments=(authority.build_state_expiry_fragment(obligation=obligation, actor_ref="character:ava", state_ref="state:cold", expected_revision=2),),
        principal_ref="world_runtime.caller",
    )
    assert settlement.ready is True
    assert settlement.owner_commit_batch is not None
    committed = authority.commit_obligation_batch(settlement.owner_commit_batch)

    projection = ObligationLifecycleProjection(_registrations()).replay_at(
        store.read_events(),
        tick=4,
        catch_up_limit=1,
    )

    assert committed.committed is True
    assert projection.open == {}
    assert projection.terminal[obligation.obligation_id].status == "settled"


def test_registered_survival_retry_reschedules_open_obligation_with_bounded_attempts() -> None:
    store = GameplayEventStore()
    authority = SurvivalAuthority(store=store)
    authority.apply_effect_state(
        command=_survival_command(),
        application=EffectApplication(effect_ref="effect:cold", target_component_ref="character:ava", magnitude=1, stack_key="cold", expires_at_tick=4, causal_chain_id="chain:cold"),
        resistance=ResistanceProfile(effect_ref="effect:cold", source_ref="character:ava", modifier_basis_points=0, revision=1),
        definition=StateDefinition(state_ref="state:cold", stack_policy="add", stack_limit=1, expiry_policy="scheduled"),
    )
    policy = SurvivalStateExpiryPolicy()
    obligation = policy.build_obligation(actor_ref="character:ava", state_ref="state:cold", due_tick=4, expected_revision=2, status="open").model_copy(
        update={"retry_policy": {"max_attempts": 2, "attempt": 1}}
    )
    coordinator = ObligationSettlementCoordinator(store=store, lifecycle_registrations=_registrations())

    plan = coordinator.plan_retry(
        obligation=obligation,
        fragment=authority.build_state_retry_fragment(
            obligation=obligation,
            actor_ref="character:ava",
            state_ref="state:cold",
            next_due_tick=6,
            expected_revision=2,
        ),
        principal_ref="world_runtime.caller",
    )
    assert plan.ready is True
    assert plan.owner_commit_batch is not None
    result = authority.commit_obligation_batch(plan.owner_commit_batch)
    projection = ObligationLifecycleProjection(_registrations()).rebuild(store.read_events())

    assert result.committed is True
    assert projection.open[obligation.obligation_id].status == "retry"
    assert projection.open[obligation.obligation_id].due_tick == 6


def test_retry_lifecycle_reenters_shared_clock_and_owner_settlement() -> None:
    store = GameplayEventStore()
    authority = SurvivalAuthority(store=store)
    authority.apply_effect_state(
        command=_survival_command(),
        application=EffectApplication(effect_ref="effect:cold", target_component_ref="character:ava", magnitude=1, stack_key="cold", expires_at_tick=4, causal_chain_id="chain:cold"),
        resistance=ResistanceProfile(effect_ref="effect:cold", source_ref="character:ava", modifier_basis_points=0, revision=1),
        definition=StateDefinition(state_ref="state:cold", stack_policy="add", stack_limit=1, expiry_policy="scheduled"),
    )
    policy = SurvivalStateExpiryPolicy()
    initial = policy.build_obligation(actor_ref="character:ava", state_ref="state:cold", due_tick=4, expected_revision=2, status="open").model_copy(
        update={"retry_policy": {"max_attempts": 2, "attempt": 1}}
    )
    coordinator = ObligationSettlementCoordinator(store=store, lifecycle_registrations=_registrations())
    retry_plan = coordinator.plan_retry(
        obligation=initial,
        fragment=authority.build_state_retry_fragment(obligation=initial, actor_ref="character:ava", state_ref="state:cold", next_due_tick=6, expected_revision=2),
        principal_ref="world_runtime.caller",
    )
    assert retry_plan.ready is True
    assert retry_plan.owner_commit_batch is not None
    assert authority.commit_obligation_batch(retry_plan.owner_commit_batch).committed is True
    retried = initial.model_copy(update={"due_tick": 6, "status": "retry", "expected_revisions": {"gameplay:survival:character:ava": 3}})
    due = SimulationClock(world_ref="world:demo").advance(6, (retried,)).due

    settlement_plan = coordinator.plan_settle(
        obligation=due[0],
        fragments=(authority.build_state_expiry_fragment(obligation=due[0], actor_ref="character:ava", state_ref="state:cold", expected_revision=3),),
        principal_ref="world_runtime.caller",
    )
    assert settlement_plan.ready is True
    assert settlement_plan.owner_commit_batch is not None
    result = authority.commit_obligation_batch(settlement_plan.owner_commit_batch)

    assert result.committed is True
    assert ObligationLifecycleProjection(_registrations()).rebuild(store.read_events()).terminal[retried.obligation_id].status == "settled"


def test_registered_survival_compensation_restores_only_a_settled_state() -> None:
    store = GameplayEventStore()
    authority = SurvivalAuthority(store=store)
    authority.apply_effect_state(
        command=_survival_command(),
        application=EffectApplication(effect_ref="effect:cold", target_component_ref="character:ava", magnitude=1, stack_key="cold", expires_at_tick=4, causal_chain_id="chain:cold"),
        resistance=ResistanceProfile(effect_ref="effect:cold", source_ref="character:ava", modifier_basis_points=0, revision=1),
        definition=StateDefinition(state_ref="state:cold", stack_policy="add", stack_limit=1, expiry_policy="scheduled"),
    )
    policy = SurvivalStateExpiryPolicy()
    obligation = policy.build_obligation(actor_ref="character:ava", state_ref="state:cold", due_tick=4, expected_revision=2, status="due").model_copy(
        update={"compensation_policy": {"restore": "state:cold"}}
    )
    coordinator = ObligationSettlementCoordinator(store=store, lifecycle_registrations=_registrations())
    settlement_plan = coordinator.plan_settle(
        obligation=obligation,
        fragments=(authority.build_state_expiry_fragment(obligation=obligation, actor_ref="character:ava", state_ref="state:cold", expected_revision=2),),
        principal_ref="world_runtime.caller",
    )
    assert settlement_plan.ready is True
    assert settlement_plan.owner_commit_batch is not None
    assert authority.commit_obligation_batch(settlement_plan.owner_commit_batch).committed is True
    settled = obligation.model_copy(update={"expected_revisions": {"gameplay:survival:character:ava": 4}, "status": "settled"})
    restored = authority.projector().states.get(("character:ava", "state:cold"))
    compensation_plan = coordinator.plan_compensate(
        obligation=settled,
        fragment=authority.build_state_compensation_fragment(
            obligation=settled,
            actor_ref="character:ava",
            restored_state=SurvivalState(state_ref="state:cold", effect_ref="effect:cold", stacks=1, effective_magnitude=1),
            expected_revision=4,
            reason_ref="reason:authority-correction",
        ),
        principal_ref="world_runtime.caller",
    )
    assert compensation_plan.ready is True
    assert compensation_plan.owner_commit_batch is not None
    result = authority.commit_obligation_batch(compensation_plan.owner_commit_batch)
    projection = ObligationLifecycleProjection(_registrations()).rebuild(store.read_events())

    assert restored is None
    assert result.committed is True
    assert authority.projector().states[("character:ava", "state:cold")].stacks == 1
    assert projection.terminal[obligation.obligation_id].status == "compensated"


def test_unregistered_compensation_and_retry_exhaustion_are_zero_write() -> None:
    store = GameplayEventStore()
    authority = SurvivalAuthority(store=store)
    authority.apply_effect_state(
        command=_survival_command(),
        application=EffectApplication(effect_ref="effect:cold", target_component_ref="character:ava", magnitude=1, stack_key="cold", expires_at_tick=4, causal_chain_id="chain:cold"),
        resistance=ResistanceProfile(effect_ref="effect:cold", source_ref="character:ava", modifier_basis_points=0, revision=1),
        definition=StateDefinition(state_ref="state:cold", stack_policy="add", stack_limit=1, expiry_policy="scheduled"),
    )
    policy = SurvivalStateExpiryPolicy()
    exhausted = policy.build_obligation(actor_ref="character:ava", state_ref="state:cold", due_tick=4, expected_revision=2, status="open").model_copy(
        update={"retry_policy": {"max_attempts": 1, "attempt": 2}}
    )
    coordinator = ObligationSettlementCoordinator(store=store, lifecycle_registrations=_registrations())
    retry = coordinator.plan_retry(
        obligation=exhausted,
        fragment=OwnerAuthorizedFragment(
            fragment_id="fragment:forged", owner_principal_ref="actor_gameplay.survival_domain", source_rule_ref="forged",
            expected_revisions={"gameplay:survival:character:ava": 2},
            event_specs={"gameplay:survival:character:ava": (("gameplay.survival.obligation_retry_scheduled", {"obligation_id": exhausted.obligation_id, "next_due_tick": 6}),)},
        ),
        principal_ref="world_runtime.caller",
    )
    unregistered = policy.build_obligation(actor_ref="character:ava", state_ref="state:cold", due_tick=4, expected_revision=2, status="settled").model_copy(
        update={"compensation_policy": {"restore": "state:cold"}}
    )
    compensation = ObligationSettlementCoordinator(store=store, lifecycle_registrations=(_registrations()[0],)).plan_compensate(
        obligation=unregistered,
        fragment=OwnerAuthorizedFragment(
            fragment_id="fragment:forged-comp", owner_principal_ref="actor_gameplay.survival_domain", source_rule_ref="forged",
            expected_revisions={"gameplay:survival:character:ava": 2},
            event_specs={"gameplay:survival:character:ava": (("gameplay.survival.obligation_compensated", {"obligation_id": unregistered.obligation_id}),)},
        ),
        principal_ref="world_runtime.caller",
    )

    assert retry.error_code == "obligation_retry_rejected"
    assert compensation.error_code == "obligation_compensation_unsupported"
    assert len(store.read_events()) == 2


def test_survival_retry_revision_conflict_is_zero_write() -> None:
    store = GameplayEventStore()
    SurvivalAuthority(store=store).apply_effect_state(
        command=_survival_command(),
        application=EffectApplication(effect_ref="effect:cold", target_component_ref="character:ava", magnitude=1, stack_key="cold", expires_at_tick=4, causal_chain_id="chain:cold"),
        resistance=ResistanceProfile(effect_ref="effect:cold", source_ref="character:ava", modifier_basis_points=0, revision=1),
        definition=StateDefinition(state_ref="state:cold", stack_policy="add", stack_limit=1, expiry_policy="scheduled"),
    )
    policy = SurvivalStateExpiryPolicy()
    obligation = policy.build_obligation(actor_ref="character:ava", state_ref="state:cold", due_tick=4, expected_revision=3, status="open").model_copy(
        update={"retry_policy": {"max_attempts": 2, "attempt": 1}}
    )
    result = ObligationSettlementCoordinator(store=store, lifecycle_registrations=_registrations()).plan_retry(
        obligation=obligation,
        fragment=SurvivalAuthority.build_state_retry_fragment(obligation=obligation, actor_ref="character:ava", state_ref="state:cold", next_due_tick=6, expected_revision=3),
        principal_ref="world_runtime.caller",
    )

    assert result.error_code == "revision_conflict"
    assert len(store.read_events()) == 2


def test_survival_compensation_is_idempotent_private_and_checkpoint_replayable() -> None:
    store = GameplayEventStore()
    authority = SurvivalAuthority(store=store)
    authority.apply_effect_state(
        command=_survival_command(),
        application=EffectApplication(effect_ref="effect:cold", target_component_ref="character:ava", magnitude=1, stack_key="cold", expires_at_tick=4, causal_chain_id="chain:cold"),
        resistance=ResistanceProfile(effect_ref="effect:cold", source_ref="character:ava", modifier_basis_points=0, revision=1),
        definition=StateDefinition(state_ref="state:cold", stack_policy="add", stack_limit=1, expiry_policy="scheduled"),
    )
    policy = SurvivalStateExpiryPolicy()
    obligation = policy.build_obligation(actor_ref="character:ava", state_ref="state:cold", due_tick=4, expected_revision=2, status="due").model_copy(
        update={"compensation_policy": {"restore": "state:cold"}}
    )
    coordinator = ObligationSettlementCoordinator(store=store, lifecycle_registrations=_registrations())
    settlement_plan = coordinator.plan_settle(
        obligation=obligation,
        fragments=(authority.build_state_expiry_fragment(obligation=obligation, actor_ref="character:ava", state_ref="state:cold", expected_revision=2),),
        principal_ref="world_runtime.caller",
    )
    assert settlement_plan.ready is True
    assert settlement_plan.owner_commit_batch is not None
    assert authority.commit_obligation_batch(settlement_plan.owner_commit_batch).committed is True
    settled = obligation.model_copy(update={"expected_revisions": {"gameplay:survival:character:ava": 4}, "status": "settled"})
    fragment = authority.build_state_compensation_fragment(
        obligation=settled, actor_ref="character:ava", restored_state=SurvivalState(state_ref="state:cold", effect_ref="effect:cold", stacks=1, effective_magnitude=1), expected_revision=4, reason_ref="reason:authority-correction"
    )
    first_plan = coordinator.plan_compensate(obligation=settled, fragment=fragment, principal_ref="world_runtime.caller")
    assert first_plan.ready is True
    assert first_plan.owner_commit_batch is not None
    first = authority.commit_obligation_batch(first_plan.owner_commit_batch)
    duplicate = coordinator.plan_compensate(obligation=settled, fragment=fragment, principal_ref="world_runtime.caller")

    assert first.committed and duplicate.idempotency_status == "duplicate_replayed" and duplicate.duplicate_result is not None
    assert {entry.audience for entry in store.list_outbox()} == {"project"}
    assert coordinator.project_receipt(scope="public")["audit_refs"] == ()
    assert coordinator.replay().projection_hash == coordinator.replay(checkpoint_at=2).projection_hash
