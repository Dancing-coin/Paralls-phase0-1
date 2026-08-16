from __future__ import annotations

from app.gameplay.construction_production_runtime import (
    ConstructionDueCompletionPolicy,
    ConstructionProductionAuthority,
    Facility,
    ProductionRun,
    Recipe,
)
from app.gameplay.event_store import GameplayEventStore
from app.world_runtime.obligations import ObligationLifecycleRegistration, ObligationSettlementCoordinator
from app.world_runtime.simulation_clock import SimulationClock


def _policy() -> ConstructionDueCompletionPolicy:
    return ConstructionDueCompletionPolicy(
        policy_ref="policy:construction_due_completion",
        policy_revision="1",
    )


def _run() -> ProductionRun:
    return ProductionRun(
        run_ref="run:bakery:1",
        facility_ref="facility:bakery:1",
        recipe_ref="recipe:bread:1",
        started_tick=0,
        finish_tick=3,
        output_item="item:bread",
    )


def _recipe() -> Recipe:
    return Recipe(recipe_ref="recipe:bread:1", inputs={}, output_item="item:bread", duration_ticks=3)


def _registration() -> ObligationLifecycleRegistration:
    return ObligationLifecycleRegistration(policy_ref="policy:construction_due_completion", policy_revision="1", owner_ref="actor_gameplay.construction_production_domain", stream_pattern="gameplay:construction_production:{facility_ref}", opened_event_type="gameplay.construction_production.run_started", settled_event_type="gameplay.construction_production.obligation_settled", cancelled_event_type="gameplay.construction_production.obligation_cancelled", visibility_scope="project")


def _lifecycle_fragment(policy: ConstructionDueCompletionPolicy, run: ProductionRun, *, expected_revision: int = 0):
    obligation = policy.build_obligation(run=run, expected_revision=expected_revision)
    return obligation, policy.build_fragment(run=run, recipe=_recipe(), tick=3, expected_revision=expected_revision, obligation=obligation, settled_event_type="gameplay.construction_production.obligation_settled")


def _start_due_run(store: GameplayEventStore, run: ProductionRun) -> None:
    assert ConstructionProductionAuthority(store=store).settle_start_run(
        facility=Facility(
            facility_ref=run.facility_ref,
            plot_ref="plot:bakery:1",
            facility_kind="bakery",
            condition=1,
        ),
        recipe=_recipe(),
        run_ref=run.run_ref,
        tick=0,
        command_id=f"command:production:start:{run.run_ref}",
        idempotency_key=f"idem:production:start:{run.run_ref}",
        causation_id=f"cause:production:start:{run.run_ref}",
        correlation_id=f"corr:production:{run.run_ref}",
    ).committed


def test_production_due_policy_uses_clock_then_owner_fragment_then_event_spine() -> None:
    policy = _policy()
    run = _run()
    store = GameplayEventStore()
    authority = ConstructionProductionAuthority(store=store)
    _start_due_run(store, run)
    obligation = policy.build_obligation(run=run, expected_revision=1)
    due = SimulationClock(world_ref="world:1").advance(3, (obligation,)).due

    obligation, fragment = _lifecycle_fragment(policy, run, expected_revision=1)
    plan = ObligationSettlementCoordinator(store=store, lifecycle_registrations=(_registration(),)).plan_settle(
        obligation=due[0],
        fragments=(fragment,),
        principal_ref="world_runtime.caller",
    )
    assert plan.ready is True
    assert plan.owner_commit_batch is not None
    result = authority.commit_obligation_batch(plan.owner_commit_batch)

    assert result.committed is True
    assert store.read_events()[1].event_type == "gameplay.construction_production.run_finished"
    assert store.list_outbox()[-1].audience == "project"


def test_production_due_policy_duplicate_replays_without_second_write() -> None:
    policy = _policy()
    run = _run()
    store = GameplayEventStore()
    authority = ConstructionProductionAuthority(store=store)
    coordinator = ObligationSettlementCoordinator(store=store, lifecycle_registrations=(_registration(),))
    _start_due_run(store, run)
    obligation, fragment = _lifecycle_fragment(policy, run, expected_revision=1)

    first = coordinator.plan_settle(obligation=obligation, fragments=(fragment,), principal_ref="world_runtime.caller")
    assert first.ready is True and first.owner_commit_batch is not None
    assert authority.commit_obligation_batch(first.owner_commit_batch).committed
    duplicate = coordinator.plan_settle(obligation=obligation, fragments=(fragment,), principal_ref="world_runtime.caller")

    assert duplicate.idempotency_status == "duplicate_replayed"
    assert len(store.read_events()) == 3


def test_production_due_policy_revision_conflict_is_zero_write() -> None:
    policy = _policy()
    run = _run()
    store = GameplayEventStore()
    _start_due_run(store, run)

    obligation, fragment = _lifecycle_fragment(policy, run, expected_revision=2)
    result = ObligationSettlementCoordinator(store=store, lifecycle_registrations=(_registration(),)).plan_settle(
        obligation=obligation,
        fragments=(fragment,),
        principal_ref="world_runtime.caller",
    )

    assert result.ready is False
    assert result.error_code == "revision_conflict"
    assert [event.event_type for event in store.read_events()] == ["gameplay.construction_production.run_started"]


def test_production_due_policy_cancelled_obligation_is_zero_write() -> None:
    policy = _policy()
    run = _run()
    store = GameplayEventStore()

    obligation, fragment = _lifecycle_fragment(policy, run)
    result = ObligationSettlementCoordinator(store=store, lifecycle_registrations=(_registration(),)).plan_settle(
        obligation=obligation.model_copy(update={"status": "cancelled"}),
        fragments=(fragment,),
        principal_ref="world_runtime.caller",
    )

    assert result.ready is False
    assert result.error_code == "obligation_not_settleable"
    assert store.read_events() == []


def test_unregistered_retry_and_compensation_are_zero_write() -> None:
    policy = _policy()
    run = _run()
    obligation, fragment = _lifecycle_fragment(policy, run)
    retry_store = GameplayEventStore()
    retry = ObligationSettlementCoordinator(store=retry_store, lifecycle_registrations=(_registration(),)).plan_settle(
        obligation=obligation.model_copy(update={"retry_policy": {"max_attempts": 1}}),
        fragments=(fragment,),
        principal_ref="world_runtime.caller",
    )
    compensation_store = GameplayEventStore()
    compensation = ObligationSettlementCoordinator(store=compensation_store, lifecycle_registrations=(_registration(),)).plan_settle(
        obligation=obligation.model_copy(update={"compensation_policy": {"event": "ecology.retry"}}),
        fragments=(fragment,),
        principal_ref="world_runtime.caller",
    )

    assert retry.error_code == "obligation_retry_unsupported"
    assert retry_store.read_events() == []
    assert compensation.error_code == "obligation_compensation_unsupported"
    assert compensation_store.read_events() == []


def test_production_due_policy_public_receipt_is_filtered_and_replay_matches() -> None:
    policy = _policy()
    run = _run()
    store = GameplayEventStore()
    authority = ConstructionProductionAuthority(store=store)
    _start_due_run(store, run)
    coordinator = ObligationSettlementCoordinator(store=store, lifecycle_registrations=(_registration(),))
    obligation, fragment = _lifecycle_fragment(policy, run, expected_revision=1)
    plan = coordinator.plan_settle(
        obligation=obligation,
        fragments=(fragment,),
        principal_ref="world_runtime.caller",
    )
    assert plan.ready is True and plan.owner_commit_batch is not None
    assert authority.commit_obligation_batch(plan.owner_commit_batch).committed
    duplicate = coordinator.plan_settle(
        obligation=obligation,
        fragments=(fragment,),
        principal_ref="world_runtime.caller",
    )
    assert duplicate.receipt is not None
    coordinator._receipts[obligation.idempotency_key] = duplicate.receipt

    assert coordinator.project_receipt(scope="public")["audit_refs"] == ()
    assert coordinator.replay().projection_hash == coordinator.replay(checkpoint_at=1).projection_hash
