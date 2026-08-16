from __future__ import annotations

from app.gameplay.econ1_economy_runtime import EconomyAuthority
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.shared_contracts import GameplayCommandEnvelope, ScheduledObligation
from app.world_runtime.obligations import ObligationLifecycleProjection, ObligationLifecycleRegistration, ObligationSettlementCoordinator
from app.world_runtime.simulation_clock import SimulationClock


WORKER = "character:ava"
STREAM = f"gameplay:economy:wage:{WORKER}"
POLICY = "policy:economy_wage_accrual"


def _command(*, key: str = "economy:wage:open:1", expected_revision: int = 0, scope: str = "project") -> GameplayCommandEnvelope:
    return GameplayCommandEnvelope(
        command_id=f"command:{key}", command_type="gameplay.economy.open_wage_obligation", command_version=1,
        principal_ref=EconomyAuthority._PRINCIPAL, actor_ref=WORKER, idempotency_key=key,
        expected_revisions={STREAM: expected_revision}, causation_id=f"cause:{key}", correlation_id=f"corr:{key}",
        source_ref=EconomyAuthority._PRINCIPAL, submitted_at="2026-08-14T00:00:00Z", payload={"visibility_scope": scope},
    )


def _registration() -> ObligationLifecycleRegistration:
    return ObligationLifecycleRegistration(
        policy_ref=POLICY, policy_revision="1", owner_ref=EconomyAuthority._PRINCIPAL,
        stream_pattern="gameplay:economy:wage:{worker_ref}", opened_event_type="gameplay.economy.wage_obligation_opened",
        settled_event_type="gameplay.economy.wage_obligation_settled", cancelled_event_type="gameplay.economy.wage_obligation_cancelled",
        visibility_scope="project",
    )


def _open(store: GameplayEventStore, **overrides: object):
    values: dict[str, object] = {
        "command": _command(), "accrual_ref": "accrual:bakery:1", "organization_ref": "organization:bakery",
        "work_evidence_refs": ("evidence:production:1",), "wage_amount_minor": 75, "due_tick": 4, "policy_revision": "1",
    }
    values.update(overrides)
    return EconomyAuthority(store=store).open_wage_obligation(**values)


def _obligation(*, revision: int = 1, status: str = "due") -> ScheduledObligation:
    return ScheduledObligation(
        obligation_id=f"obligation:economy:wage:{WORKER}:accrual:bakery:1", owner_ref=EconomyAuthority._PRINCIPAL,
        due_tick=4, policy_revision="1", status=status, source_refs=(POLICY,),
        idempotency_key="economy:wage:settle:1", expected_revisions={STREAM: revision}, visibility_scope="project",
    )


def test_economy_wage_obligation_opens_on_existing_owner_stream() -> None:
    store = GameplayEventStore()

    result = _open(store)

    assert result.committed is True
    assert store.read_events()[0].event_type == "gameplay.economy.wage_obligation_opened"
    lifecycle = ObligationLifecycleProjection((_registration(),)).rebuild(store.read_events())
    assert lifecycle.open[_obligation().obligation_id].due_tick == 4


def test_economy_wage_due_is_clock_selected_and_owner_settled() -> None:
    store = GameplayEventStore(); _open(store)
    due = SimulationClock(world_ref="world:demo", catch_up_budget=1).advance(4, (_obligation(),)).due[0]
    authority = EconomyAuthority(store=store)
    coordinator = ObligationSettlementCoordinator(store=store, lifecycle_registrations=(_registration(),))
    plan = coordinator.plan_settle(
        obligation=due,
        fragments=(authority.build_wage_obligation_settlement_fragment(obligation=due),),
        principal_ref="world_runtime.caller",
    )

    assert plan.ready and plan.owner_commit_batch is not None
    result = authority.commit_obligation_batch(plan.owner_commit_batch)
    assert result.committed
    assert [event.event_type for event in store.read_events()][-2:] == ["gameplay.economy.wage_accrued", "gameplay.economy.wage_obligation_settled"]
    assert ObligationLifecycleProjection((_registration(),)).rebuild(store.read_events()).terminal[due.obligation_id].status == "settled"


def test_economy_wage_open_duplicate_and_changed_duplicate_are_distinct() -> None:
    store = GameplayEventStore(); first = _open(store); duplicate = _open(store)
    changed = _open(store, wage_amount_minor=80)

    assert first.committed and duplicate.idempotency_status == "duplicate_replayed"
    assert changed.committed is False and changed.failure is not None and changed.failure.error_code == "idempotency_key_reused"
    assert len(store.read_events()) == 1


def test_economy_wage_rejects_reopened_obligation_identity_without_writes() -> None:
    store = GameplayEventStore(); assert _open(store).committed
    before = len(store.read_events())

    reopened = _open(store, command=_command(key="economy:wage:reopen", expected_revision=1))

    assert reopened.committed is False
    assert reopened.failure is not None and reopened.failure.error_code == "economy_wage_obligation_already_open"
    assert len(store.read_events()) == before


def test_economy_wage_rejects_stale_scope_and_terminal_without_writes() -> None:
    store = GameplayEventStore(); _open(store)
    before = len(store.read_events())
    stale = _open(store, command=_command(key="economy:wage:stale", expected_revision=0))
    private = _open(store, command=_command(key="economy:wage:private", expected_revision=1, scope="actor:character:ava"))
    terminal = ObligationSettlementCoordinator(store=store, lifecycle_registrations=(_registration(),)).settle(
        obligation=_obligation(status="settled"), fragments=(), principal_ref="world_runtime.caller",
    )

    assert stale.failure is not None and stale.failure.error_code == "revision_conflict"
    assert private.failure is not None and private.failure.error_code == "economy_wage_obligation_privacy_denied"
    assert terminal.error_code == "obligation_not_settleable"
    assert len(store.read_events()) == before


def test_economy_wage_settlement_rejects_changed_owner_stream_revision_without_write() -> None:
    store = GameplayEventStore(); _open(store)
    obligation = _obligation()
    assert _open(store, command=_command(key="economy:wage:open:2", expected_revision=1), accrual_ref="accrual:bakery:2").committed
    before = len(store.read_events())

    rejected = ObligationSettlementCoordinator(store=store, lifecycle_registrations=(_registration(),)).settle(
        obligation=obligation,
        fragments=(EconomyAuthority(store=store).build_wage_obligation_settlement_fragment(obligation=obligation),),
        principal_ref="world_runtime.caller",
    )

    assert rejected.error_code == "revision_conflict"
    assert len(store.read_events()) == before


def test_economy_wage_checkpoint_tail_replay_and_project_outbox_are_scoped() -> None:
    store = GameplayEventStore(); _open(store)
    obligation = _obligation(); authority = EconomyAuthority(store=store)
    coordinator = ObligationSettlementCoordinator(store=store, lifecycle_registrations=(_registration(),))
    plan = coordinator.plan_settle(obligation=obligation, fragments=(authority.build_wage_obligation_settlement_fragment(obligation=obligation),), principal_ref="world_runtime.caller")
    assert plan.ready and plan.owner_commit_batch is not None
    assert authority.commit_obligation_batch(plan.owner_commit_batch).committed

    assert {entry.audience for entry in store.list_outbox()} == {"project"}
    assert coordinator.replay().projection_hash == coordinator.replay(checkpoint_at=1).projection_hash
