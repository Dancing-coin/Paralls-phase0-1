import pytest

from app.gameplay.economy_runtime import EconomyAuthorityService, EconomyProjector
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.governed_contract_catalog import GovernedAuthorityContractCatalog, GovernedAuthorityContractError
from app.world_runtime.obligations import ObligationLifecycleProjection, ObligationSettlementCoordinator


POLICY = "policy:economy_tax_due@1"


def _seed_tax_due() -> tuple[GameplayEventStore, EconomyAuthorityService, str]:
    store = GameplayEventStore()
    service = EconomyAuthorityService(store=store)
    result = service.record_tax_due(
        command_id="tax:source:1",
        organization_ref="organization:bakery-a",
        period_ref="period:2026-08",
        assessed_amount_minor=27,
        policy_revision="policy:commercial@7",
        policy_digest="sha256:commercial-policy",
        due_calendar_ref="calendar:monthly",
        evidence_refs=("evidence:taxable:2026-08",),
        source_digest="sha256:tax-source",
        idempotency_key="tax:source:1",
        causation_id="cause:tax:source:1",
        correlation_id="corr:tax:source:1",
    )
    assert result.committed
    return store, service, store.read_events()[-1].event_id


def _registration(service: EconomyAuthorityService):
    return service.tax_obligation_registration()


def _due_obligation(store: GameplayEventStore, service: EconomyAuthorityService):
    view = ObligationLifecycleProjection((_registration(service),)).replay_at(
        store.read_events(), tick=10, catch_up_limit=10
    )
    obligations = view.to_scheduled_obligations()
    assert len(obligations) == 1
    return obligations[0]


def test_tax_obligation_open_is_pinned_to_committed_tax_due_event() -> None:
    store, service, source_event_id = _seed_tax_due()
    opened = service.open_tax_obligation(
        command_id="tax:obligation:open",
        tax_due_event_id=source_event_id,
        due_tick=10,
        idempotency_key="tax:obligation:open",
        causation_id=source_event_id,
        correlation_id="corr:tax:obligation:open",
        expected_revision=1,
    )

    assert opened.committed and opened.obligation is not None
    event = store.read_events()[-1]
    assert event.event_type == "gameplay.economy.tax_obligation_opened"
    assert event.payload["source_tax_due_event_id"] == source_event_id
    assert event.payload["policy_ref"] == POLICY
    assert event.payload["due_tick"] == 10


def test_tax_obligation_open_replays_exact_duplicate_and_rejects_changed_duplicate() -> None:
    store, service, source_event_id = _seed_tax_due()
    first = service.open_tax_obligation(
        command_id="tax:obligation:dup",
        tax_due_event_id=source_event_id,
        due_tick=10,
        idempotency_key="tax:obligation:dup",
        causation_id=source_event_id,
        correlation_id="corr:tax:obligation:dup",
        expected_revision=1,
    )
    before = store.export_snapshot()
    replayed = service.open_tax_obligation(
        command_id="tax:obligation:dup",
        tax_due_event_id=source_event_id,
        due_tick=10,
        idempotency_key="tax:obligation:dup",
        causation_id=source_event_id,
        correlation_id="corr:tax:obligation:dup",
        expected_revision=1,
    )
    assert first.committed and replayed.committed
    assert replayed.append_result.idempotency_status == "duplicate_replayed"
    assert store.export_snapshot() == before

    changed = service.open_tax_obligation(
        command_id="tax:obligation:dup",
        tax_due_event_id=source_event_id,
        due_tick=11,
        idempotency_key="tax:obligation:dup",
        causation_id=source_event_id,
        correlation_id="corr:tax:obligation:dup",
        expected_revision=1,
    )
    assert not changed.committed
    assert changed.append_result.failure is not None
    assert changed.append_result.failure.error_code == "idempotency_key_reused"
    assert store.export_snapshot() == before


def test_tax_obligation_open_rejects_forged_source_and_stale_revision_without_write() -> None:
    store, service, _source_event_id = _seed_tax_due()
    before = store.export_snapshot()
    forged = service.open_tax_obligation(
        command_id="tax:obligation:forged",
        tax_due_event_id="evt:missing",
        due_tick=10,
        idempotency_key="tax:obligation:forged",
        causation_id="evt:missing",
        correlation_id="corr:tax:obligation:forged",
        expected_revision=1,
    )
    assert not forged.committed
    assert forged.append_result.failure is not None
    assert forged.append_result.failure.error_code == "economy_tax_source_missing"
    assert store.export_snapshot() == before


def test_tax_obligation_catalog_gate_rejects_before_append(monkeypatch: pytest.MonkeyPatch) -> None:
    store, service, source_event_id = _seed_tax_due()
    before = store.export_snapshot()

    def reject(**_kwargs: object) -> None:
        raise GovernedAuthorityContractError("tax_catalog_gate_rejected")

    monkeypatch.setattr(GovernedAuthorityContractCatalog, "require_operation", staticmethod(reject))
    result = service.open_tax_obligation(
        command_id="tax:obligation:catalog-gate",
        tax_due_event_id=source_event_id,
        due_tick=10,
        idempotency_key="tax:obligation:catalog-gate",
        causation_id=source_event_id,
        correlation_id="corr:tax:obligation:catalog-gate",
        expected_revision=1,
    )
    assert not result.committed
    assert result.append_result.failure is not None
    assert result.append_result.failure.error_code == "tax_catalog_gate_rejected"
    assert store.export_snapshot() == before

    stale = service.open_tax_obligation(
        command_id="tax:obligation:stale",
        tax_due_event_id=store.read_events()[-1].event_id,
        due_tick=10,
        idempotency_key="tax:obligation:stale",
        causation_id=store.read_events()[-1].event_id,
        correlation_id="corr:tax:obligation:stale",
        expected_revision=0,
    )
    assert not stale.committed
    assert stale.append_result.failure is not None
    assert stale.append_result.failure.error_code == "revision_conflict"
    assert store.export_snapshot() == before


def test_tax_obligation_settlement_is_terminal_only_and_replayable() -> None:
    store, service, source_event_id = _seed_tax_due()
    assert service.open_tax_obligation(
        command_id="tax:obligation:settle:open",
        tax_due_event_id=source_event_id,
        due_tick=10,
        idempotency_key="tax:obligation:settle:open",
        causation_id=source_event_id,
        correlation_id="corr:tax:obligation:settle",
        expected_revision=1,
    ).committed
    due = _due_obligation(store, service)
    coordinator = ObligationSettlementCoordinator(
        store=store, lifecycle_registrations=(_registration(service),)
    )
    plan = coordinator.plan_settle(
        obligation=due,
        fragments=(service.build_tax_obligation_settlement_fragment(obligation=due),),
        principal_ref=EconomyAuthorityService._PRINCIPAL,
    )
    assert plan.ready and plan.owner_commit_batch is not None
    before_balances = EconomyProjector().rebuild(store.read_events()).balances
    result = service.commit_obligation_batch(plan.owner_commit_batch)
    assert result.committed
    assert EconomyProjector().rebuild(store.read_events()).balances == before_balances
    assert store.read_events()[-1].event_type == "gameplay.economy.tax_obligation_settled"
    lifecycle = ObligationLifecycleProjection((_registration(service),)).rebuild(store.read_events())
    assert lifecycle.terminal[due.obligation_id].status == "settled"


@pytest.mark.parametrize("terminal", ["cancel", "expire"])
def test_tax_obligation_cancel_and_expire_are_owner_terminal_events(terminal: str) -> None:
    store, service, source_event_id = _seed_tax_due()
    assert service.open_tax_obligation(
        command_id=f"tax:obligation:{terminal}:open",
        tax_due_event_id=source_event_id,
        due_tick=10,
        idempotency_key=f"tax:obligation:{terminal}:open",
        causation_id=source_event_id,
        correlation_id=f"corr:tax:obligation:{terminal}",
        expected_revision=1,
    ).committed
    obligation = _due_obligation(store, service)
    coordinator = ObligationSettlementCoordinator(
        store=store, lifecycle_registrations=(_registration(service),)
    )
    if terminal == "cancel":
        plan = coordinator.plan_cancel(
            obligation=obligation,
            fragment=service.build_tax_obligation_cancellation_fragment(
                obligation=obligation, reason_ref="reason:cancelled"
            ),
            principal_ref=EconomyAuthorityService._PRINCIPAL,
            reason_ref="reason:cancelled",
        )
    else:
        plan = coordinator.plan_expire(
            obligation=obligation,
            fragment=service.build_tax_obligation_expiry_fragment(
                obligation=obligation, reason_ref="reason:expired"
            ),
            principal_ref=EconomyAuthorityService._PRINCIPAL,
            reason_ref="reason:expired",
        )
    assert plan.ready and plan.owner_commit_batch is not None
    result = service.commit_obligation_batch(plan.owner_commit_batch)
    assert result.committed
    assert store.read_events()[-1].event_type.endswith(f"tax_obligation_{terminal}led") or store.read_events()[-1].event_type.endswith("tax_obligation_expired")


def test_tax_obligation_privacy_redacts_amount_and_evidence_from_outbox() -> None:
    store, service, source_event_id = _seed_tax_due()
    result = service.open_tax_obligation(
        command_id="tax:obligation:privacy",
        tax_due_event_id=source_event_id,
        due_tick=10,
        idempotency_key="tax:obligation:privacy",
        causation_id=source_event_id,
        correlation_id="corr:tax:obligation:privacy",
        expected_revision=1,
    )
    assert result.committed
    event = store.read_events()[-1]
    assert event.visibility_policy == "authority_only"
    assert all(
        "assessed_amount_minor" not in entry.payload_projection
        and "evidence_refs" not in entry.payload_projection
        for entry in store.list_outbox()
    )


def test_tax_obligation_full_and_checkpoint_tail_replay_match() -> None:
    store, service, source_event_id = _seed_tax_due()
    assert service.open_tax_obligation(
        command_id="tax:obligation:replay",
        tax_due_event_id=source_event_id,
        due_tick=10,
        idempotency_key="tax:obligation:replay",
        causation_id=source_event_id,
        correlation_id="corr:tax:obligation:replay",
        expected_revision=1,
    ).committed
    events = store.read_events()
    projection = ObligationLifecycleProjection((_registration(service),))
    full = projection.replay_at(events, tick=10, catch_up_limit=10)
    checkpoint = projection.create_checkpoint(events[:1])
    tail = projection.checkpoint_plus_tail_at(
        checkpoint, events[1:], tick=10, catch_up_limit=10
    )
    assert full == tail
