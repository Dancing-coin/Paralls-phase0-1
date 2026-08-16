from __future__ import annotations

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import OwnerAuthorizedFragment
from app.gameplay.shared_contracts import ScheduledObligation
from app.gameplay.econ1_economy_runtime import EconomyAuthority
from app.gameplay.survival_runtime import NeedDefinition, NeedState, SurvivalAuthority, SurvivalMode, SurvivalPolicy
from app.gameplay.construction_production_runtime import ConstructionProductionAuthority, ProductionRun, Recipe
from app.world_runtime.obligations import ObligationSettlementCoordinator


def _obligation(*, status: str = "due", expected_revision: int = 0) -> ScheduledObligation:
    return ScheduledObligation(
        obligation_id="obligation:farm:1",
        owner_ref="authority:farm",
        due_tick=10,
        policy_revision="policy:1",
        status=status,
        idempotency_key="obligation:farm:1",
        expected_revisions={"farm:1": expected_revision},
        visibility_scope="project",
    )


def _fragment(*, expected_revision: int = 0) -> OwnerAuthorizedFragment:
    return OwnerAuthorizedFragment(
        fragment_id="fragment:farm:1",
        owner_principal_ref="authority:farm",
        source_rule_ref="obligation:farm:1",
        expected_revisions={"farm:1": expected_revision},
        event_specs={"farm:1": (("farm.obligation.settled", {"obligation_id": "obligation:farm:1"}),)},
        event_visibility_policies={"farm:1": ("project",)},
    )


def test_unregistered_due_obligation_is_zero_write_rejected() -> None:
    store = GameplayEventStore()
    plan = ObligationSettlementCoordinator(store=store).plan_settle(
        obligation=_obligation(), fragments=(_fragment(),), principal_ref="world_runtime.caller"
    )
    assert not plan.ready
    assert plan.error_code == "obligation_policy_unregistered"
    assert store.read_events() == []
    assert store.list_outbox() == []


def test_unregistered_due_obligation_duplicate_is_zero_write_rejected() -> None:
    store = GameplayEventStore()
    coordinator = ObligationSettlementCoordinator(store=store)
    coordinator.plan_settle(obligation=_obligation(), fragments=(_fragment(),), principal_ref="world_runtime.caller")
    plan = coordinator.plan_settle(obligation=_obligation(), fragments=(_fragment(),), principal_ref="world_runtime.caller")
    assert not plan.ready
    assert plan.error_code == "obligation_policy_unregistered"
    assert store.read_events() == []


def test_obligation_revision_conflict_is_zero_write() -> None:
    store = GameplayEventStore()
    plan = ObligationSettlementCoordinator(store=store).plan_settle(
        obligation=_obligation(expected_revision=1), fragments=(_fragment(expected_revision=1),), principal_ref="world_runtime.caller"
    )
    assert plan.ready is False
    assert plan.error_code == "obligation_policy_unregistered"
    assert store.read_events() == []


def test_closed_or_unauthorized_fragment_is_zero_write() -> None:
    store = GameplayEventStore()
    coordinator = ObligationSettlementCoordinator(store=store, authorized_owners=frozenset({"authority:other"}))
    plan = coordinator.plan_settle(obligation=_obligation(status="closed"), fragments=(_fragment(),), principal_ref="world_runtime.caller")
    assert plan.ready is False
    assert plan.error_code == "obligation_not_settleable"
    assert store.read_events() == []
    plan = coordinator.plan_settle(obligation=_obligation(), fragments=(_fragment(),), principal_ref="world_runtime.caller")
    assert plan.error_code == "obligation_policy_unregistered"
    assert store.read_events() == []


def test_obligation_full_and_checkpoint_tail_replay_match_and_scope_is_filtered() -> None:
    store = GameplayEventStore()
    coordinator = ObligationSettlementCoordinator(store=store)
    coordinator.plan_settle(obligation=_obligation(), fragments=(_fragment(),), principal_ref="world_runtime.caller")
    assert coordinator.replay().projection_hash == coordinator.replay(checkpoint_at=0).projection_hash
    assert coordinator.project_receipt(scope="public")["audit_refs"] == ()


def test_economy_due_fragment_settles_only_through_coordinator() -> None:
    store = GameplayEventStore()
    fragment = EconomyAuthority.build_commerce_wage_accrual_fragment(
        commitment_ref="commitment:1", organization_ref="organization:1", worker_ref="character:char_a", wage_obligation_ref="obligation:wage:1",
        work_evidence_refs=("evidence:work:1",), wage_amount_minor=10, wage_policy_revision="policy:wage:1", expected_revision=0,
    )
    plan = ObligationSettlementCoordinator(store=store).plan_settle(
        obligation=ScheduledObligation(obligation_id="obligation:wage:1", owner_ref=fragment.owner_principal_ref, due_tick=1, policy_revision="policy:wage:1", status="due", idempotency_key="obligation:wage:1", expected_revisions=dict(fragment.expected_revisions), visibility_scope="project"),
        fragments=(fragment,), principal_ref="world_runtime.caller",
    )
    assert not plan.ready
    assert plan.error_code == "obligation_policy_unregistered"
    assert store.read_events() == []


def test_survival_due_fragment_rejects_bad_mode_without_writing() -> None:
    store = GameplayEventStore()
    policy = SurvivalPolicy(policy_ref="policy:survival:1", mode=SurvivalMode.SIMULATION, revision="1")
    fragment = SurvivalAuthority.build_due_tick_fragment(actor_ref="character:char_a", policy=policy, definition=NeedDefinition(need_ref="need:hunger", category="body", decay_per_tick=0.1), state=NeedState(need_ref="need:hunger", value=1, last_tick=0), tick=2, expected_revision=0)
    plan = ObligationSettlementCoordinator(store=store).plan_settle(obligation=ScheduledObligation(obligation_id="obligation:survival:1", owner_ref=fragment.owner_principal_ref, due_tick=2, policy_revision="1", status="due", idempotency_key="obligation:survival:1", expected_revisions=dict(fragment.expected_revisions), visibility_scope="project"), fragments=(fragment,), principal_ref="world_runtime.caller")
    assert not plan.ready
    assert plan.error_code == "obligation_policy_unregistered"
    assert store.read_events() == []


def test_production_due_fragment_checks_finish_before_coordinator_write() -> None:
    store = GameplayEventStore()
    run = ProductionRun(run_ref="run:1", facility_ref="facility:1", recipe_ref="recipe:1", started_tick=0, finish_tick=3, output_item="item:bread")
    recipe = Recipe(recipe_ref="recipe:1", inputs={}, output_item="item:bread", duration_ticks=3)
    fragment = ConstructionProductionAuthority.build_due_finish_fragment(run=run, recipe=recipe, tick=3, expected_revision=0)
    plan = ObligationSettlementCoordinator(store=store).plan_settle(obligation=ScheduledObligation(obligation_id="obligation:production:1", owner_ref=fragment.owner_principal_ref, due_tick=3, policy_revision="policy:production:1", status="due", idempotency_key="obligation:production:1", expected_revisions=dict(fragment.expected_revisions), visibility_scope="project"), fragments=(fragment,), principal_ref="world_runtime.caller")
    assert not plan.ready
    assert plan.error_code == "obligation_policy_unregistered"
    assert store.read_events() == []
