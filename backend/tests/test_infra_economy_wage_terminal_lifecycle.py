from __future__ import annotations

from app.gameplay.econ1_economy_runtime import EconomyAuthority
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.shared_contracts import ScheduledObligation
from app.world_runtime.obligations import ObligationLifecycleProjection, ObligationLifecycleRegistration, ObligationSettlementCoordinator


WORKER = "character:ava"
STREAM = f"gameplay:economy:wage:{WORKER}"
POLICY = "policy:economy_wage_accrual"


def _registration() -> ObligationLifecycleRegistration:
    return EconomyAuthority.wage_obligation_lifecycle_registration()


def test_economy_wage_registration_is_authority_owned_and_closed() -> None:
    registration = EconomyAuthority.wage_obligation_lifecycle_registration()

    assert registration.policy_ref == POLICY
    assert registration.policy_revision == "1"
    assert registration.owner_ref == EconomyAuthority._PRINCIPAL
    assert registration.stream_pattern == "gameplay:economy:wage:{worker_ref}"
    assert registration.opened_event_type == "gameplay.economy.wage_obligation_opened"
    assert registration.settled_event_type == "gameplay.economy.wage_obligation_settled"
    assert registration.cancelled_event_type == "gameplay.economy.wage_obligation_cancelled"
    assert registration.retry_event_type == "gameplay.economy.wage_obligation_retry_scheduled"
    assert registration.expired_event_type == "gameplay.economy.wage_obligation_expired"
    assert registration.compensated_event_type == "gameplay.economy.wage_obligation_compensated"
    assert registration.visibility_scope == "project"


def _obligation(*, revision: int = 1, status: str = "due", retry_policy: dict[str, object] | None = None, compensation_policy: dict[str, object] | None = None) -> ScheduledObligation:
    return ScheduledObligation(
        obligation_id=f"obligation:economy:wage:{WORKER}:accrual:one", owner_ref=EconomyAuthority._PRINCIPAL,
        due_tick=4, policy_revision="1", status=status, source_refs=(POLICY,), idempotency_key="economy:wage:one",
        expected_revisions={STREAM: revision}, visibility_scope="project", retry_policy=retry_policy or {}, compensation_policy=compensation_policy or {},
    )


def _opened_store() -> GameplayEventStore:
    from test_infra_economy_wage_obligation import _open
    store = GameplayEventStore()
    assert _open(store, accrual_ref="accrual:one").committed
    return store


def test_economy_wage_retry_is_owner_fragment_event_derived() -> None:
    store = _opened_store(); authority = EconomyAuthority(store=store)
    obligation = _obligation(retry_policy={"attempt": 1, "max_attempts": 2})
    coordinator = ObligationSettlementCoordinator(store=store, lifecycle_registrations=(_registration(),))
    before = store.export_snapshot()

    plan = coordinator.plan_retry(
        obligation=obligation,
        fragment=authority.build_wage_obligation_retry_fragment(obligation=obligation, next_due_tick=6),
        principal_ref="world_runtime.caller",
    )

    assert plan.ready and plan.owner_commit_batch is not None
    assert store.export_snapshot() == before
    result = authority.commit_obligation_batch(plan.owner_commit_batch)
    assert result.committed is True
    assert ObligationLifecycleProjection((_registration(),)).rebuild(store.read_events()).open[obligation.obligation_id].due_tick == 6


def test_economy_wage_cancel_is_owner_fragment_event_derived() -> None:
    store = _opened_store(); authority = EconomyAuthority(store=store)
    obligation = _obligation(status="open")
    coordinator = ObligationSettlementCoordinator(store=store, lifecycle_registrations=(_registration(),))

    plan = coordinator.plan_cancel(
        obligation=obligation,
        fragment=authority.build_wage_obligation_cancel_fragment(obligation=obligation, reason_ref="reason:work_void"),
        principal_ref="world_runtime.caller", reason_ref="reason:work_void",
    )

    assert plan.ready and plan.owner_commit_batch is not None
    result = authority.commit_obligation_batch(plan.owner_commit_batch)
    assert result.committed is True
    assert ObligationLifecycleProjection((_registration(),)).rebuild(store.read_events()).terminal[obligation.obligation_id].status == "cancelled"


def test_economy_wage_expiry_plan_is_zero_write_and_owner_commit_is_append_derived() -> None:
    store = _opened_store(); authority = EconomyAuthority(store=store)
    obligation = _obligation(status="due")
    coordinator = ObligationSettlementCoordinator(store=store, lifecycle_registrations=(_registration(),))
    before = store.export_snapshot()

    plan = coordinator.plan_expire(
        obligation=obligation,
        fragment=authority.build_wage_obligation_expiry_fragment(obligation=obligation, reason_ref="reason:wage_window_elapsed"),
        principal_ref="world_runtime.caller",
        reason_ref="reason:wage_window_elapsed",
    )

    assert plan.ready and plan.owner_commit_batch is not None
    assert store.export_snapshot() == before
    result = authority.commit_obligation_batch(plan.owner_commit_batch)
    assert result.committed is True
    assert result.committed_event_ids
    assert result.resulting_stream_revisions == {STREAM: 2}
    assert ObligationLifecycleProjection((_registration(),)).rebuild(store.read_events()).terminal[obligation.obligation_id].status == "expired"
    assert [event.event_type for event in store.read_events()][-1:] == ["gameplay.economy.wage_obligation_expired"]


def test_economy_wage_expiry_is_idempotent_and_rejects_stale_or_terminal_without_writes() -> None:
    store = _opened_store(); authority = EconomyAuthority(store=store)
    obligation = _obligation(status="due")
    coordinator = ObligationSettlementCoordinator(store=store, lifecycle_registrations=(_registration(),))
    fragment = authority.build_wage_obligation_expiry_fragment(obligation=obligation, reason_ref="reason:wage_window_elapsed")
    first_plan = coordinator.plan_expire(obligation=obligation, fragment=fragment, principal_ref="world_runtime.caller", reason_ref="reason:wage_window_elapsed")
    assert first_plan.ready and first_plan.owner_commit_batch is not None
    first = authority.commit_obligation_batch(first_plan.owner_commit_batch)
    duplicate = coordinator.plan_expire(obligation=obligation, fragment=fragment, principal_ref="world_runtime.caller", reason_ref="reason:wage_window_elapsed")
    before = len(store.read_events())
    stale = coordinator.plan_expire(
        obligation=_obligation(revision=1, status="due"),
        fragment=authority.build_wage_obligation_expiry_fragment(obligation=_obligation(revision=1, status="due"), reason_ref="reason:late"),
        principal_ref="world_runtime.other",
        reason_ref="reason:late",
    )
    terminal = coordinator.plan_expire(
        obligation=_obligation(revision=2, status="expired"),
        fragment=authority.build_wage_obligation_expiry_fragment(obligation=_obligation(revision=2, status="expired"), reason_ref="reason:terminal"),
        principal_ref="world_runtime.other",
        reason_ref="reason:terminal",
    )

    assert first.committed is True
    assert duplicate.idempotency_status == "duplicate_replayed" and duplicate.duplicate_result is not None
    assert stale.error_code == "revision_conflict"
    assert terminal.error_code == "obligation_not_expirable"
    assert len(store.read_events()) == before


def test_economy_wage_expiry_is_project_scoped_and_checkpoint_tail_replayable() -> None:
    store = _opened_store(); authority = EconomyAuthority(store=store)
    obligation = _obligation(status="due")
    coordinator = ObligationSettlementCoordinator(store=store, lifecycle_registrations=(_registration(),))

    plan = coordinator.plan_expire(
        obligation=obligation,
        fragment=authority.build_wage_obligation_expiry_fragment(obligation=obligation, reason_ref="reason:wage_window_elapsed"),
        principal_ref="world_runtime.caller",
        reason_ref="reason:wage_window_elapsed",
    )

    assert plan.ready and plan.owner_commit_batch is not None
    result = authority.commit_obligation_batch(plan.owner_commit_batch)
    assert result.committed is True
    assert {entry.audience for entry in store.list_outbox()} == {"project"}
    assert coordinator.project_receipt(scope="public")["audit_refs"] == ()
    assert coordinator.replay().projection_hash == coordinator.replay(checkpoint_at=1).projection_hash


def test_economy_wage_retry_is_idempotent_and_stale_retry_is_zero_write() -> None:
    store = _opened_store(); authority = EconomyAuthority(store=store)
    obligation = _obligation(retry_policy={"attempt": 1, "max_attempts": 2})
    coordinator = ObligationSettlementCoordinator(store=store, lifecycle_registrations=(_registration(),))
    fragment = authority.build_wage_obligation_retry_fragment(obligation=obligation, next_due_tick=6)
    first_plan = coordinator.plan_retry(obligation=obligation, fragment=fragment, principal_ref="world_runtime.caller")
    assert first_plan.ready and first_plan.owner_commit_batch is not None
    first = authority.commit_obligation_batch(first_plan.owner_commit_batch)
    duplicate = coordinator.plan_retry(obligation=obligation, fragment=fragment, principal_ref="world_runtime.caller")
    before = len(store.read_events())
    stale = coordinator.plan_retry(
        obligation=obligation,
        fragment=authority.build_wage_obligation_retry_fragment(obligation=obligation, next_due_tick=6),
        principal_ref="world_runtime.other",
    )

    assert first.committed is True
    assert duplicate.idempotency_status == "duplicate_replayed" and duplicate.duplicate_result is not None
    assert stale.error_code == "revision_conflict"
    assert len(store.read_events()) == before


def test_economy_wage_retry_rejects_changed_duplicate_without_append() -> None:
    store = _opened_store(); authority = EconomyAuthority(store=store)
    obligation = _obligation(retry_policy={"attempt": 1, "max_attempts": 2})
    coordinator = ObligationSettlementCoordinator(store=store, lifecycle_registrations=(_registration(),))
    first_plan = coordinator.plan_retry(
        obligation=obligation,
        fragment=authority.build_wage_obligation_retry_fragment(obligation=obligation, next_due_tick=6),
        principal_ref="world_runtime.caller",
    )
    assert first_plan.ready and first_plan.owner_commit_batch is not None
    assert authority.commit_obligation_batch(first_plan.owner_commit_batch).committed
    before = len(store.read_events())

    rejected = coordinator.plan_retry(
        obligation=obligation,
        fragment=authority.build_wage_obligation_retry_fragment(obligation=obligation, next_due_tick=7),
        principal_ref="world_runtime.caller",
    )

    assert not rejected.ready and rejected.error_code == "idempotency_key_reused"
    assert len(store.read_events()) == before


def test_economy_wage_expiry_rejects_changed_duplicate_without_append() -> None:
    store = _opened_store(); authority = EconomyAuthority(store=store)
    obligation = _obligation(status="due")
    coordinator = ObligationSettlementCoordinator(store=store, lifecycle_registrations=(_registration(),))
    first_plan = coordinator.plan_expire(
        obligation=obligation,
        fragment=authority.build_wage_obligation_expiry_fragment(obligation=obligation, reason_ref="reason:wage_window_elapsed"),
        principal_ref="world_runtime.caller", reason_ref="reason:wage_window_elapsed",
    )
    assert first_plan.ready and first_plan.owner_commit_batch is not None
    assert authority.commit_obligation_batch(first_plan.owner_commit_batch).committed
    before = len(store.read_events())

    changed = obligation.model_copy(update={"due_tick": obligation.due_tick + 1})
    rejected = coordinator.plan_expire(
        obligation=changed,
        fragment=authority.build_wage_obligation_expiry_fragment(obligation=changed, reason_ref="reason:wage_window_elapsed"),
        principal_ref="world_runtime.caller", reason_ref="reason:wage_window_elapsed",
    )

    assert not rejected.ready and rejected.error_code == "idempotency_key_reused"
    assert len(store.read_events()) == before


def test_economy_wage_compensation_is_settled_only_and_replayable() -> None:
    store = _opened_store(); authority = EconomyAuthority(store=store)
    coordinator = ObligationSettlementCoordinator(store=store, lifecycle_registrations=(_registration(),))
    due = _obligation()
    settlement_plan = coordinator.plan_settle(
        obligation=due, fragments=(authority.build_wage_obligation_settlement_fragment(obligation=due),),
        principal_ref="world_runtime.caller",
    )
    assert settlement_plan.ready and settlement_plan.owner_commit_batch is not None
    assert authority.commit_obligation_batch(settlement_plan.owner_commit_batch).committed
    settled = _obligation(revision=3, status="settled", compensation_policy={"kind": "reverse_accrual"})

    compensation_plan = coordinator.plan_compensate(
        obligation=settled,
        fragment=authority.build_wage_obligation_compensation_fragment(obligation=settled, reason_ref="reason:correction"),
        principal_ref="world_runtime.caller",
    )

    assert compensation_plan.ready and compensation_plan.owner_commit_batch is not None
    result = authority.commit_obligation_batch(compensation_plan.owner_commit_batch)
    assert result.committed is True
    assert [event.event_type for event in store.read_events()][-2:] == ["gameplay.economy.wage_accrual_compensated", "gameplay.economy.wage_obligation_compensated"]
    assert ObligationLifecycleProjection((_registration(),)).rebuild(store.read_events()).terminal[settled.obligation_id].status == "compensated"
    assert coordinator.replay().projection_hash == coordinator.replay(checkpoint_at=1).projection_hash


def test_economy_wage_compensation_rejects_changed_duplicate_without_append() -> None:
    store = _opened_store(); authority = EconomyAuthority(store=store)
    coordinator = ObligationSettlementCoordinator(store=store, lifecycle_registrations=(_registration(),))
    due = _obligation()
    settlement_plan = coordinator.plan_settle(
        obligation=due, fragments=(authority.build_wage_obligation_settlement_fragment(obligation=due),),
        principal_ref="world_runtime.caller",
    )
    assert settlement_plan.ready and settlement_plan.owner_commit_batch is not None
    assert authority.commit_obligation_batch(settlement_plan.owner_commit_batch).committed
    settled = _obligation(revision=3, status="settled", compensation_policy={"kind": "reverse_accrual"})
    compensation_plan = coordinator.plan_compensate(
        obligation=settled,
        fragment=authority.build_wage_obligation_compensation_fragment(obligation=settled, reason_ref="reason:correction"),
        principal_ref="world_runtime.caller",
    )
    assert compensation_plan.ready and compensation_plan.owner_commit_batch is not None
    assert authority.commit_obligation_batch(compensation_plan.owner_commit_batch).committed
    before = len(store.read_events())

    rejected = coordinator.plan_compensate(
        obligation=settled,
        fragment=authority.build_wage_obligation_compensation_fragment(obligation=settled, reason_ref="reason:different"),
        principal_ref="world_runtime.caller",
    )

    assert not rejected.ready and rejected.error_code == "idempotency_key_reused"
    assert len(store.read_events()) == before


def test_economy_wage_terminal_cancel_and_unsettled_compensation_are_zero_write() -> None:
    store = _opened_store(); authority = EconomyAuthority(store=store)
    coordinator = ObligationSettlementCoordinator(store=store, lifecycle_registrations=(_registration(),))
    settled = _obligation(status="settled", compensation_policy={"kind": "reverse_accrual"})
    before = len(store.read_events())

    cancellation = coordinator.plan_cancel(
        obligation=settled,
        fragment=authority.build_wage_obligation_cancel_fragment(obligation=settled, reason_ref="reason:late"),
        principal_ref="world_runtime.caller", reason_ref="reason:late",
    )
    try:
        authority.build_wage_obligation_compensation_fragment(
            obligation=_obligation(compensation_policy={"kind": "reverse_accrual"}), reason_ref="reason:early"
        )
    except ValueError as exc:
        compensation_error = str(exc)
    else:
        compensation_error = "accepted"

    assert cancellation.error_code == "obligation_not_cancellable"
    assert compensation_error == "economy_wage_obligation_compensation_invalid"
    assert len(store.read_events()) == before
