from __future__ import annotations

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.semantic_effects import EffectApplication, ResistanceProfile, StateDefinition
from app.gameplay.shared_contracts import GameplayCommandEnvelope
from app.gameplay.survival_runtime import SurvivalAuthority, SurvivalStateExpiryPolicy
from app.world_runtime.obligations import ObligationLifecycleRegistration, ObligationSettlementCoordinator


def _command(*, expected_revision: int = 0, key: str = "inf2q:survival:open") -> GameplayCommandEnvelope:
    return GameplayCommandEnvelope(
        command_id=f"command:{key}",
        command_type="gameplay.survival.apply_state",
        command_version=1,
        principal_ref="actor_gameplay.survival_domain",
        actor_ref="character:ava",
        project_ref="project:demo",
        idempotency_key=key,
        expected_revisions={"gameplay:survival:character:ava": expected_revision},
        causation_id=f"cause:{key}",
        correlation_id=f"corr:{key}",
        source_ref="proposal:semantic:cold",
        submitted_at="2026-08-15T00:00:00Z",
        payload={},
    )


def _application() -> EffectApplication:
    return EffectApplication(
        effect_ref="effect:cold_exposure",
        target_component_ref="character:ava",
        magnitude=100,
        stack_key="cold",
        expires_at_tick=8,
        causal_chain_id="chain:cold:1",
    )


def _resistance() -> ResistanceProfile:
    return ResistanceProfile(
        effect_ref="effect:cold_exposure",
        source_ref="character:ava",
        modifier_basis_points=2_500,
        revision=1,
    )


def _definition() -> StateDefinition:
    return StateDefinition(
        state_ref="state:cold",
        stack_policy="add",
        stack_limit=2,
        expiry_policy="scheduled",
    )


def _registration() -> ObligationLifecycleRegistration:
    return ObligationLifecycleRegistration(
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
    )


def _open_due_state(store: GameplayEventStore):
    authority = SurvivalAuthority(store=store)
    opened = authority.apply_effect_state(
        command=_command(),
        application=_application(),
        resistance=_resistance(),
        definition=_definition(),
    )
    assert opened.committed is True
    obligation = SurvivalStateExpiryPolicy().build_obligation(
        actor_ref="character:ava",
        state_ref="state:cold",
        due_tick=8,
        expected_revision=2,
        status="due",
    )
    fragment = authority.build_state_expiry_fragment(
        obligation=obligation,
        actor_ref="character:ava",
        state_ref="state:cold",
        expected_revision=2,
    )
    return authority, obligation, fragment


def test_direct_coordinator_settle_without_owner_commit_is_zero_write() -> None:
    store = GameplayEventStore()
    _authority, obligation, fragment = _open_due_state(store)
    coordinator = ObligationSettlementCoordinator(
        store=store,
        lifecycle_registrations=(_registration(),),
    )
    before = store.export_snapshot()

    result = coordinator.settle(
        obligation=obligation,
        fragments=(fragment,),
        principal_ref="world_runtime.caller",
    )

    assert result.committed is False
    assert result.error_code == "coordinator_owner_commit_required"
    assert store.export_snapshot() == before


def test_coordinator_rejects_store_append_callback_as_non_owner_zero_write() -> None:
    store = GameplayEventStore()
    _authority, obligation, fragment = _open_due_state(store)
    coordinator = ObligationSettlementCoordinator(store=store, lifecycle_registrations=(_registration(),))
    before = store.export_snapshot()

    result = coordinator.settle(
        obligation=obligation,
        fragments=(fragment,),
        principal_ref="world_runtime.caller",
        owner_commit=store.append_batch,
    )

    assert result.committed is False
    assert result.error_code == "owner_commit_authority_mismatch"
    assert store.export_snapshot() == before


def test_direct_coordinator_settle_with_owner_callback_remains_zero_write() -> None:
    store = GameplayEventStore()
    authority, obligation, fragment = _open_due_state(store)
    coordinator = ObligationSettlementCoordinator(store=store, lifecycle_registrations=(_registration(),))
    before = store.export_snapshot()
    transactions_before = len(store.read_transactions())

    result = coordinator.settle(
        obligation=obligation,
        fragments=(fragment,),
        principal_ref="world_runtime.caller",
        owner_commit=authority.commit_obligation_batch,
    )

    assert result.committed is False
    assert result.error_code == "coordinator_direct_write_disallowed"
    assert len(store.read_transactions()) == transactions_before
    assert store.export_snapshot() == before


def test_plan_settle_is_zero_write_and_survival_authority_commits_planned_batch() -> None:
    store = GameplayEventStore()
    authority, obligation, fragment = _open_due_state(store)
    coordinator = ObligationSettlementCoordinator(
        store=store,
        lifecycle_registrations=(_registration(),),
    )
    before = store.export_snapshot()
    transactions_before = len(store.read_transactions())

    plan = coordinator.plan_settle(
        obligation=obligation,
        fragments=(fragment,),
        principal_ref="world_runtime.caller",
    )

    assert plan.ready is True
    assert plan.idempotency_status == "new_commit"
    assert plan.owner_commit_batch is not None
    assert plan.duplicate_result is None
    assert plan.receipt is None
    assert store.export_snapshot() == before

    result = authority.commit_obligation_batch(plan.owner_commit_batch)

    assert result.committed is True
    assert len(store.read_transactions()) == transactions_before + 1
    assert result.committed_event_ids
    assert result.resulting_stream_revisions == {"gameplay:survival:character:ava": 4}
    assert [event.event_type for event in store.read_events()][-2:] == [
        "gameplay.survival.state_expired",
        "gameplay.survival.obligation_settled",
    ]
    assert coordinator.replay().projection_hash == coordinator.replay(checkpoint_at=2).projection_hash


def test_plan_cancel_is_zero_write_and_survival_authority_commits_planned_batch() -> None:
    store = GameplayEventStore()
    authority, obligation, _fragment = _open_due_state(store)
    open_obligation = obligation.model_copy(update={"status": "open"})
    fragment = authority.build_state_dispel_fragment(
        obligation=open_obligation,
        actor_ref="character:ava",
        state_ref="state:cold",
        expected_revision=2,
        reason_ref="reason:remedy",
    )
    coordinator = ObligationSettlementCoordinator(store=store, lifecycle_registrations=(_registration(),))
    before = store.export_snapshot()

    plan = coordinator.plan_cancel(
        obligation=open_obligation,
        fragment=fragment,
        principal_ref="world_runtime.caller",
        reason_ref="reason:remedy",
    )

    assert plan.ready and plan.owner_commit_batch is not None
    assert store.export_snapshot() == before
    assert authority.commit_obligation_batch(plan.owner_commit_batch).committed
    assert [event.event_type for event in store.read_events()][-2:] == [
        "gameplay.survival.state_dispelled",
        "gameplay.survival.obligation_cancelled",
    ]
