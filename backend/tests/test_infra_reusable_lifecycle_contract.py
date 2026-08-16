from __future__ import annotations

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.shared_contracts import ScheduledObligation
from app.world_runtime.obligations import (
    ObligationLifecycleContractRegistry,
    ObligationLifecycleProjection,
    ObligationSettlementCoordinator,
)


def test_reusable_lifecycle_contract_exposes_closed_terminal_operation_shape() -> None:
    registry = ObligationLifecycleContractRegistry
    survival = registry.require(policy_ref="policy:survival_state_expiry", policy_revision="1")
    economy = registry.require(policy_ref="policy:economy_wage_accrual", policy_revision="1")

    assert survival.event_type_for("settle") == "gameplay.survival.obligation_settled"
    assert survival.event_type_for("cancel") == "gameplay.survival.obligation_cancelled"
    assert survival.event_type_for("expire") is None
    assert survival.event_type_for("retry") == "gameplay.survival.obligation_retry_scheduled"
    assert survival.event_type_for("compensate") == "gameplay.survival.obligation_compensated"
    assert economy.event_type_for("expire") == "gameplay.economy.wage_obligation_expired"
    assert economy.event_type_for("compensate") == "gameplay.economy.wage_obligation_compensated"
    assert economy.event_type_for("unknown") is None


def test_default_coordinator_uses_the_same_closed_registration_source() -> None:
    coordinator = ObligationSettlementCoordinator.from_closed_registry(store=GameplayEventStore())

    assert coordinator.registration_for(
        ScheduledObligation(
            obligation_id="obligation:survival:contract",
            owner_ref="actor_gameplay.survival_domain",
            due_tick=4,
            policy_revision="1",
            status="due",
            source_refs=("policy:survival_state_expiry",),
            idempotency_key="obligation:survival:contract",
            expected_revisions={"gameplay:survival:character:ava": 0},
            visibility_scope="project",
        )
    ) is not None
    assert coordinator.registration_for(
        ScheduledObligation(
            obligation_id="obligation:economy:contract",
            owner_ref="actor_gameplay.econ1_economy_domain",
            due_tick=4,
            policy_revision="1",
            status="due",
            source_refs=("policy:economy_wage_accrual",),
            idempotency_key="obligation:economy:contract",
            expected_revisions={"gameplay:economy:wage:ava": 0},
            visibility_scope="project",
        )
    ) is not None


def test_explicit_empty_registration_set_remains_a_zero_write_fence() -> None:
    store = GameplayEventStore()
    obligation = ScheduledObligation(
        obligation_id="obligation:survival:fenced",
        owner_ref="actor_gameplay.survival_domain",
        due_tick=4,
        policy_revision="1",
        status="due",
        source_refs=("policy:survival_state_expiry",),
        idempotency_key="obligation:survival:fenced",
        expected_revisions={"gameplay:survival:character:ava": 0},
        visibility_scope="project",
    )

    plan = ObligationSettlementCoordinator(store=store, lifecycle_registrations=()).plan_settle(
        obligation=obligation,
        fragments=(),
        principal_ref="world_runtime.caller",
    )

    assert not plan.ready
    assert plan.error_code == "obligation_policy_unregistered"
    assert store.read_events() == []


def test_closed_projection_replay_is_identical_for_full_and_checkpoint_tail() -> None:
    projection = ObligationLifecycleProjection(ObligationLifecycleContractRegistry.closed_registrations())
    full = projection.replay_at([], tick=10, catch_up_limit=2)
    checkpoint = projection.create_checkpoint([])
    tail = projection.checkpoint_plus_tail_at(checkpoint, [], tick=10, catch_up_limit=2)

    assert tail == full
    assert full.open == {}
    assert full.terminal == {}
