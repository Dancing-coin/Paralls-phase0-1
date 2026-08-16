from __future__ import annotations

import pytest

from test_infra_economy_scheduled_transfer_obligation import _service_with_accounts

from app.gameplay.economy_runtime import EconomyAuthorityService, EconomyProjector, EconomyRuntimeError, ScheduledAccountTransferPolicyInstance
from app.gameplay.event_store import GameplayEventStore
from app.world_runtime.obligations import (
    ObligationLifecycleProjection,
    ObligationSettlementCoordinator,
)


POLICY_REF = "policy:economy:scheduled-transfer:alice-to-bob@1"


def _policy(*, amount_cap: int = 4) -> ScheduledAccountTransferPolicyInstance:
    return ScheduledAccountTransferPolicyInstance(
        policy_instance_ref=POLICY_REF,
        policy_revision="1",
        debit_account_id="account:alice",
        credit_account_id="account:bob",
        amount_cap=amount_cap,
        active_from_tick=0,
        active_until_tick=16,
    )


def _cross_currency_service() -> tuple[GameplayEventStore, EconomyAuthorityService]:
    store = GameplayEventStore()
    service = EconomyAuthorityService(store=store)
    assert service.open_account(
        command_id="economy-policy:open:alice",
        account_id="account:alice",
        owner_ref="actor:alice",
        currency_ref="currency:coin",
        initial_balance=10,
        idempotency_key="economy-policy:open:alice",
        causation_id="cause:economy-policy:open:alice",
        correlation_id="corr:economy-policy:open:alice",
        expected_revision=0,
    ).committed
    assert service.open_account(
        command_id="economy-policy:open:bob",
        account_id="account:bob",
        owner_ref="actor:bob",
        currency_ref="currency:gem",
        initial_balance=0,
        idempotency_key="economy-policy:open:bob",
        causation_id="cause:economy-policy:open:bob",
        correlation_id="corr:economy-policy:open:bob",
        expected_revision=1,
    ).committed
    return store, service


def _register_policy(
    service: EconomyAuthorityService,
    *,
    key: str = "economy-policy:register",
    expected_revision: int = 2,
):
    return service.register_scheduled_transfer_policy_instance(
        policy=_policy(),
        command_id=key,
        idempotency_key=key,
        causation_id=f"cause:{key}",
        correlation_id=f"corr:{key}",
        expected_revision=expected_revision,
        privacy_scope="authority_only",
    )


def _revoke_policy(
    service: EconomyAuthorityService,
    *,
    key: str = "economy-policy:revoke",
    expected_revision: int,
):
    return service.revoke_scheduled_transfer_policy_instance(
        policy_instance_ref=POLICY_REF,
        policy_revision="1",
        command_id=key,
        idempotency_key=key,
        causation_id=f"cause:{key}",
        correlation_id=f"corr:{key}",
        expected_revision=expected_revision,
        privacy_scope="authority_only",
    )


def _open_bound_obligation(
    service: EconomyAuthorityService,
    *,
    command_id: str,
    transfer_ref: str,
    expected_revision: int,
):
    result = service.open_scheduled_account_transfer_obligation(
        command_id=command_id,
        transfer_ref=transfer_ref,
        debit_account_id="account:alice",
        credit_account_id="account:bob",
        amount=4,
        due_tick=8,
        policy_instance_ref=POLICY_REF,
        idempotency_key=command_id,
        causation_id=f"cause:{command_id}",
        correlation_id=f"corr:{command_id}",
        expected_revision=expected_revision,
    )
    assert result.committed and result.obligation is not None
    return result.obligation


def _coordinator(store: GameplayEventStore, service: EconomyAuthorityService) -> ObligationSettlementCoordinator:
    return ObligationSettlementCoordinator(
        store=store,
        lifecycle_registrations=(service.scheduled_account_transfer_obligation_registration(),),
    )


def test_economy_registers_scheduled_transfer_policy_instance_on_existing_stream() -> None:
    store, service = _service_with_accounts()

    result = service.register_scheduled_transfer_policy_instance(
        policy=_policy(),
        command_id="economy-policy:register",
        idempotency_key="economy-policy:register",
        causation_id="cause:economy-policy:register",
        correlation_id="corr:economy-policy:register",
        expected_revision=2,
        privacy_scope="authority_only",
    )

    assert result.committed
    assert result.resulting_stream_revisions == {"gameplay:economy": 3}
    assert store.read_events()[-1].event_type == "gameplay.economy.scheduled_transfer_policy_registered"


def test_economy_policy_instance_rejects_project_scope_without_write() -> None:
    store, service = _service_with_accounts()
    before = store.export_snapshot()

    result = service.register_scheduled_transfer_policy_instance(
        policy=_policy(),
        command_id="economy-policy:private",
        idempotency_key="economy-policy:private",
        causation_id="cause:economy-policy:private",
        correlation_id="corr:economy-policy:private",
        expected_revision=2,
        privacy_scope="project",
    )

    assert not result.committed
    assert result.failure is not None and result.failure.error_code == "economy_policy_privacy_denied"
    assert store.export_snapshot() == before


def test_economy_policy_instance_rejects_stale_revision_without_write() -> None:
    store, service = _service_with_accounts()
    before = store.export_snapshot()

    result = service.register_scheduled_transfer_policy_instance(
        policy=_policy(),
        command_id="economy-policy:stale",
        idempotency_key="economy-policy:stale",
        causation_id="cause:economy-policy:stale",
        correlation_id="corr:economy-policy:stale",
        expected_revision=1,
        privacy_scope="authority_only",
    )

    assert not result.committed
    assert result.failure is not None and result.failure.error_code == "revision_conflict"
    assert store.export_snapshot() == before


def test_economy_policy_instance_replays_an_exact_duplicate_without_write() -> None:
    store, service = _service_with_accounts()
    first = service.register_scheduled_transfer_policy_instance(
        policy=_policy(),
        command_id="economy-policy:register",
        idempotency_key="economy-policy:register",
        causation_id="cause:economy-policy:register",
        correlation_id="corr:economy-policy:register",
        expected_revision=2,
        privacy_scope="authority_only",
    )
    before = store.export_snapshot()

    replayed = service.register_scheduled_transfer_policy_instance(
        policy=_policy(),
        command_id="economy-policy:register",
        idempotency_key="economy-policy:register",
        causation_id="cause:economy-policy:register",
        correlation_id="corr:economy-policy:register",
        expected_revision=2,
        privacy_scope="authority_only",
    )

    assert first.committed and replayed.committed
    assert replayed.idempotency_status == "duplicate_replayed"
    assert store.export_snapshot() == before


def test_economy_policy_instance_rejects_changed_duplicate_without_write() -> None:
    store, service = _service_with_accounts()
    assert service.register_scheduled_transfer_policy_instance(
        policy=_policy(),
        command_id="economy-policy:register",
        idempotency_key="economy-policy:register",
        causation_id="cause:economy-policy:register",
        correlation_id="corr:economy-policy:register",
        expected_revision=2,
        privacy_scope="authority_only",
    ).committed
    before = store.export_snapshot()

    rejected = service.register_scheduled_transfer_policy_instance(
        policy=_policy(amount_cap=5),
        command_id="economy-policy:register",
        idempotency_key="economy-policy:register",
        causation_id="cause:economy-policy:register",
        correlation_id="corr:economy-policy:register",
        expected_revision=3,
        privacy_scope="authority_only",
    )

    assert not rejected.committed
    assert rejected.failure is not None and rejected.failure.error_code == "idempotency_key_reused"
    assert store.export_snapshot() == before


def test_economy_policy_instance_rejects_cross_currency_registration_without_write() -> None:
    store, service = _cross_currency_service()
    before = store.export_snapshot()

    with pytest.raises(EconomyRuntimeError, match="economy_policy_invalid"):
        service.register_scheduled_transfer_policy_instance(
            policy=_policy(),
            command_id="economy-policy:cross-currency",
            idempotency_key="economy-policy:cross-currency",
            causation_id="cause:economy-policy:cross-currency",
            correlation_id="corr:economy-policy:cross-currency",
            expected_revision=2,
            privacy_scope="authority_only",
        )

    assert store.export_snapshot() == before


def test_economy_policy_instance_rejects_invalid_interval_without_write() -> None:
    store, service = _service_with_accounts()
    before = store.export_snapshot()

    with pytest.raises(EconomyRuntimeError, match="economy_policy_invalid"):
        service.register_scheduled_transfer_policy_instance(
            policy=_policy().model_copy(update={"active_from_tick": 12, "active_until_tick": 8}, deep=True),
            command_id="economy-policy:bad-interval",
            idempotency_key="economy-policy:bad-interval",
            causation_id="cause:economy-policy:bad-interval",
            correlation_id="corr:economy-policy:bad-interval",
            expected_revision=2,
            privacy_scope="authority_only",
        )

    assert store.export_snapshot() == before


def test_economy_policy_instance_allows_explicit_binding_and_pins_registration_snapshot() -> None:
    store, service = _service_with_accounts()
    registration = _register_policy(service)

    result = service.open_scheduled_account_transfer_obligation(
        command_id="scheduled-transfer:policy-bound",
        transfer_ref="scheduled-transfer:alice-to-bob:policy-bound",
        debit_account_id="account:alice",
        credit_account_id="account:bob",
        amount=4,
        due_tick=8,
        policy_instance_ref=POLICY_REF,
        idempotency_key="scheduled-transfer:policy-bound",
        causation_id="cause:scheduled-transfer:policy-bound",
        correlation_id="corr:scheduled-transfer:policy-bound",
        expected_revision=3,
    )

    assert registration.committed and result.committed and result.obligation is not None
    opening = store.read_events()[-1]
    assert opening.event_type == "gameplay.economy.scheduled_transfer_obligation_opened"
    assert opening.payload["policy_instance_ref"] == POLICY_REF
    assert opening.payload["policy_registration_event_id"] == registration.committed_event_ids[0]
    assert f"policy_instance:{POLICY_REF}" in result.obligation.source_refs
    assert f"policy_registration_event:{registration.committed_event_ids[0]}" in result.obligation.source_refs


def test_economy_legacy_open_without_policy_instance_ref_remains_compatible() -> None:
    store, service = _service_with_accounts()
    assert _register_policy(service).committed

    result = service.open_scheduled_account_transfer_obligation(
        command_id="scheduled-transfer:legacy-open",
        transfer_ref="scheduled-transfer:alice-to-bob:legacy-open",
        debit_account_id="account:alice",
        credit_account_id="account:bob",
        amount=4,
        due_tick=8,
        idempotency_key="scheduled-transfer:legacy-open",
        causation_id="cause:scheduled-transfer:legacy-open",
        correlation_id="corr:scheduled-transfer:legacy-open",
        expected_revision=3,
    )

    assert result.committed
    assert store.read_events()[-1].payload.get("policy_instance_ref") is None


@pytest.mark.parametrize(
    ("label", "open_kwargs", "expected_error"),
    (
        (
            "missing",
            {"policy_instance_ref": "policy:economy:scheduled-transfer:missing@1"},
            "economy_policy_instance_missing",
        ),
        (
            "wrong_accounts",
            {
                "policy_instance_ref": POLICY_REF,
                "credit_account_id": "account:carol",
            },
            "economy_policy_instance_mismatch",
        ),
        (
            "over_cap",
            {"policy_instance_ref": POLICY_REF, "amount": 5},
            "economy_policy_instance_cap_exceeded",
        ),
        (
            "outside_interval",
            {"policy_instance_ref": POLICY_REF, "due_tick": 17},
            "economy_policy_instance_interval_mismatch",
        ),
    ),
)
def test_economy_policy_instance_explicit_binding_rejects_invalid_admission_without_write(
    label: str,
    open_kwargs: dict[str, object],
    expected_error: str,
) -> None:
    store, service = _service_with_accounts()
    expected_revision = 3
    if label == "wrong_accounts":
        assert service.open_account(
            command_id="economy-policy:open:carol",
            account_id="account:carol",
            owner_ref="actor:carol",
            currency_ref="currency:coin",
            initial_balance=0,
            idempotency_key="economy-policy:open:carol",
            causation_id="cause:economy-policy:open:carol",
            correlation_id="corr:economy-policy:open:carol",
            expected_revision=2,
        ).committed
        expected_revision = 4
    assert _register_policy(service, expected_revision=expected_revision - 1).committed
    before = store.export_snapshot()

    result = service.open_scheduled_account_transfer_obligation(**({
        "command_id": f"scheduled-transfer:{label}",
        "transfer_ref": f"scheduled-transfer:alice-to-bob:{label}",
        "debit_account_id": "account:alice",
        "credit_account_id": "account:bob",
        "amount": 4,
        "due_tick": 8,
        "idempotency_key": f"scheduled-transfer:{label}",
        "causation_id": f"cause:scheduled-transfer:{label}",
        "correlation_id": f"corr:scheduled-transfer:{label}",
        "expected_revision": expected_revision,
    } | open_kwargs))

    assert not result.committed
    assert result.append_result.failure is not None
    assert result.append_result.failure.error_code == expected_error
    assert store.export_snapshot() == before


def test_economy_revokes_scheduled_transfer_policy_instance_and_restores_manual_open() -> None:
    store, service = _service_with_accounts()
    assert _register_policy(service).committed

    revoked = service.revoke_scheduled_transfer_policy_instance(
        policy_instance_ref=POLICY_REF,
        policy_revision="1",
        command_id="economy-policy:revoke",
        idempotency_key="economy-policy:revoke",
        causation_id="cause:economy-policy:revoke",
        correlation_id="corr:economy-policy:revoke",
        expected_revision=3,
        privacy_scope="authority_only",
    )

    assert revoked.committed
    assert revoked.resulting_stream_revisions == {"gameplay:economy": 4}
    assert store.read_events()[-1].event_type == "gameplay.economy.scheduled_transfer_policy_revoked"
    assert EconomyProjector().rebuild(store.read_events()).scheduled_transfer_policies == {}
    before = store.export_snapshot()
    rejected = service.open_scheduled_account_transfer_obligation(
        command_id="scheduled-transfer:after-revoke:bound",
        transfer_ref="scheduled-transfer:alice-to-bob:after-revoke:bound",
        debit_account_id="account:alice",
        credit_account_id="account:bob",
        amount=4,
        due_tick=8,
        policy_instance_ref=POLICY_REF,
        idempotency_key="scheduled-transfer:after-revoke:bound",
        causation_id="cause:scheduled-transfer:after-revoke:bound",
        correlation_id="corr:scheduled-transfer:after-revoke:bound",
        expected_revision=4,
    )
    assert not rejected.committed
    assert rejected.append_result.failure is not None
    assert rejected.append_result.failure.error_code == "economy_policy_instance_missing"
    assert store.export_snapshot() == before
    reopened = service.open_scheduled_account_transfer_obligation(
        command_id="scheduled-transfer:after-revoke",
        transfer_ref="scheduled-transfer:alice-to-bob:after-revoke",
        debit_account_id="account:alice",
        credit_account_id="account:bob",
        amount=4,
        due_tick=8,
        idempotency_key="scheduled-transfer:after-revoke",
        causation_id="cause:scheduled-transfer:after-revoke",
        correlation_id="corr:scheduled-transfer:after-revoke",
        expected_revision=4,
    )
    assert reopened.committed


def test_economy_policy_instance_registration_outbox_is_authority_scoped_and_redacted() -> None:
    store, service = _service_with_accounts()

    result = _register_policy(service)

    assert result.committed
    outbox = store.list_outbox()[-1]
    assert outbox.audience == "authority:economy"
    assert outbox.topic == "economy.policy.scoped_projection"
    assert outbox.payload_projection == {
        "policy_instance_ref": POLICY_REF,
        "event_type": "gameplay.economy.scheduled_transfer_policy_registered",
    }


def test_economy_policy_instance_registration_receipt_is_derived_from_append_result() -> None:
    _store, service = _service_with_accounts()

    result = _register_policy(service)
    receipt = service.account_settlement_receipt_for(result=result, privacy_scope="authority")

    assert result.committed
    assert receipt.committed_event_ids == tuple(result.committed_event_ids)
    assert receipt.audit_refs == (f"economy_transaction:{result.transaction_id}",)


def test_economy_policy_instance_registration_receipt_rejects_nonauthority_scope_without_write() -> None:
    store, service = _service_with_accounts()
    result = _register_policy(service)
    before = store.export_snapshot()

    with pytest.raises(EconomyRuntimeError, match="economy_account_receipt_scope_denied"):
        service.account_settlement_receipt_for(result=result, privacy_scope="public")

    assert store.export_snapshot() == before


def test_economy_policy_instance_revocation_outbox_is_authority_scoped_and_redacted() -> None:
    store, service = _service_with_accounts()
    assert _register_policy(service).committed

    result = _revoke_policy(service, expected_revision=3)

    assert result.committed
    outbox = store.list_outbox()[-1]
    assert outbox.audience == "authority:economy"
    assert outbox.topic == "economy.policy.scoped_projection"
    assert outbox.payload_projection == {
        "policy_instance_ref": POLICY_REF,
        "event_type": "gameplay.economy.scheduled_transfer_policy_revoked",
    }


def test_economy_policy_instance_revocation_receipt_is_derived_from_append_result() -> None:
    _store, service = _service_with_accounts()
    assert _register_policy(service).committed

    result = _revoke_policy(service, expected_revision=3)
    receipt = service.account_settlement_receipt_for(result=result, privacy_scope="authority")

    assert result.committed
    assert receipt.committed_event_ids == tuple(result.committed_event_ids)
    assert receipt.audit_refs == (f"economy_transaction:{result.transaction_id}",)


def test_economy_policy_instance_revocation_receipt_rejects_nonauthority_scope_without_write() -> None:
    store, service = _service_with_accounts()
    assert _register_policy(service).committed
    result = _revoke_policy(service, expected_revision=3)
    before = store.export_snapshot()

    with pytest.raises(EconomyRuntimeError, match="economy_account_receipt_scope_denied"):
        service.account_settlement_receipt_for(result=result, privacy_scope="public")

    assert store.export_snapshot() == before


def test_economy_policy_instance_projection_full_and_checkpoint_tail_replay_match() -> None:
    store, service = _service_with_accounts()
    assert _register_policy(service).committed
    checkpoint = store.export_snapshot()
    assert _revoke_policy(service, expected_revision=3).committed

    tail_store = GameplayEventStore.from_snapshot(checkpoint)
    assert tail_store.append_batch(store.read_transactions()[-1]).committed

    full = EconomyProjector().rebuild(store.read_events())
    tail = EconomyProjector().rebuild(tail_store.read_events())

    assert full.scheduled_transfer_policies == {}
    assert full.scheduled_transfer_policies == tail.scheduled_transfer_policies
    assert full.balances == tail.balances == {"account:alice": 10, "account:bob": 0}


def test_economy_policy_instance_bound_due_settlement_succeeds() -> None:
    store, service = _service_with_accounts()
    registration = _register_policy(service)
    obligation = _open_bound_obligation(
        service,
        command_id="scheduled-transfer:policy-bound:settle",
        transfer_ref="scheduled-transfer:alice-to-bob:policy-bound:settle",
        expected_revision=3,
    ).model_copy(update={"status": "due"})
    coordinator = _coordinator(store, service)

    plan = coordinator.plan_settle(
        obligation=obligation,
        fragments=(service.build_scheduled_account_transfer_settlement_fragment(obligation=obligation),),
        principal_ref=EconomyAuthorityService._PRINCIPAL,
    )

    assert plan.ready and plan.owner_commit_batch is not None
    result = service.commit_obligation_batch(plan.owner_commit_batch)

    assert registration.committed and result.committed
    assert EconomyProjector().rebuild(store.read_events()).balances == {
        "account:alice": 6,
        "account:bob": 4,
    }
    terminal = ObligationLifecycleProjection(
        (service.scheduled_account_transfer_obligation_registration(),)
    ).rebuild(store.read_events()).terminal[obligation.obligation_id]
    assert terminal.status == "settled"


def test_economy_policy_instance_bound_cancellation_succeeds() -> None:
    store, service = _service_with_accounts()
    assert _register_policy(service).committed
    obligation = _open_bound_obligation(
        service,
        command_id="scheduled-transfer:policy-bound:cancel",
        transfer_ref="scheduled-transfer:alice-to-bob:policy-bound:cancel",
        expected_revision=3,
    )
    coordinator = _coordinator(store, service)

    plan = coordinator.plan_cancel(
        obligation=obligation,
        fragment=service.build_scheduled_account_transfer_cancellation_fragment(
            obligation=obligation,
            reason_ref="reason:policy-bound-cancel",
        ),
        principal_ref=EconomyAuthorityService._PRINCIPAL,
        reason_ref="reason:policy-bound-cancel",
    )

    assert plan.ready and plan.owner_commit_batch is not None
    result = service.commit_obligation_batch(plan.owner_commit_batch)

    assert result.committed
    assert EconomyProjector().rebuild(store.read_events()).balances == {
        "account:alice": 10,
        "account:bob": 0,
    }
    terminal = ObligationLifecycleProjection(
        (service.scheduled_account_transfer_obligation_registration(),)
    ).rebuild(store.read_events()).terminal[obligation.obligation_id]
    assert terminal.status == "cancelled"


def test_economy_policy_instance_bound_expiry_succeeds() -> None:
    store, service = _service_with_accounts()
    assert _register_policy(service).committed
    obligation = _open_bound_obligation(
        service,
        command_id="scheduled-transfer:policy-bound:expire",
        transfer_ref="scheduled-transfer:alice-to-bob:policy-bound:expire",
        expected_revision=3,
    ).model_copy(update={"status": "due"})
    coordinator = _coordinator(store, service)

    plan = coordinator.plan_expire(
        obligation=obligation,
        fragment=service.build_scheduled_account_transfer_expiry_fragment(
            obligation=obligation,
            reason_ref="reason:policy-bound-expire",
        ),
        principal_ref=EconomyAuthorityService._PRINCIPAL,
        reason_ref="reason:policy-bound-expire",
    )

    assert plan.ready and plan.owner_commit_batch is not None
    result = service.commit_obligation_batch(plan.owner_commit_batch)

    assert result.committed
    assert EconomyProjector().rebuild(store.read_events()).balances == {
        "account:alice": 10,
        "account:bob": 0,
    }
    terminal = ObligationLifecycleProjection(
        (service.scheduled_account_transfer_obligation_registration(),)
    ).rebuild(store.read_events()).terminal[obligation.obligation_id]
    assert terminal.status == "expired"


def test_economy_policy_instance_bound_due_settlement_survives_policy_revocation() -> None:
    store, service = _service_with_accounts()
    assert _register_policy(service).committed
    opened = _open_bound_obligation(
        service,
        command_id="scheduled-transfer:policy-bound:revoked-settle",
        transfer_ref="scheduled-transfer:alice-to-bob:policy-bound:revoked-settle",
        expected_revision=3,
    )
    assert _revoke_policy(service, key="economy-policy:revoke:bound-settle", expected_revision=4).committed
    obligation = service.scheduled_account_transfer_obligation_for(
        obligation_id=opened.obligation_id
    ).model_copy(update={"status": "due"})
    coordinator = _coordinator(store, service)

    plan = coordinator.plan_settle(
        obligation=obligation,
        fragments=(service.build_scheduled_account_transfer_settlement_fragment(obligation=obligation),),
        principal_ref=EconomyAuthorityService._PRINCIPAL,
    )

    assert plan.ready and plan.owner_commit_batch is not None
    result = service.commit_obligation_batch(plan.owner_commit_batch)

    assert result.committed
    assert EconomyProjector().rebuild(store.read_events()).balances == {
        "account:alice": 6,
        "account:bob": 4,
    }


def test_economy_policy_instance_bound_cancellation_survives_policy_revocation() -> None:
    store, service = _service_with_accounts()
    assert _register_policy(service).committed
    opened = _open_bound_obligation(
        service,
        command_id="scheduled-transfer:policy-bound:revoked-cancel",
        transfer_ref="scheduled-transfer:alice-to-bob:policy-bound:revoked-cancel",
        expected_revision=3,
    )
    assert _revoke_policy(service, key="economy-policy:revoke:bound-cancel", expected_revision=4).committed
    obligation = service.scheduled_account_transfer_obligation_for(
        obligation_id=opened.obligation_id
    )
    coordinator = _coordinator(store, service)

    plan = coordinator.plan_cancel(
        obligation=obligation,
        fragment=service.build_scheduled_account_transfer_cancellation_fragment(
            obligation=obligation,
            reason_ref="reason:policy-bound-revoked-cancel",
        ),
        principal_ref=EconomyAuthorityService._PRINCIPAL,
        reason_ref="reason:policy-bound-revoked-cancel",
    )

    assert plan.ready and plan.owner_commit_batch is not None
    result = service.commit_obligation_batch(plan.owner_commit_batch)

    assert result.committed
    assert EconomyProjector().rebuild(store.read_events()).balances == {
        "account:alice": 10,
        "account:bob": 0,
    }


def test_economy_policy_instance_bound_expiry_survives_policy_revocation() -> None:
    store, service = _service_with_accounts()
    assert _register_policy(service).committed
    opened = _open_bound_obligation(
        service,
        command_id="scheduled-transfer:policy-bound:revoked-expire",
        transfer_ref="scheduled-transfer:alice-to-bob:policy-bound:revoked-expire",
        expected_revision=3,
    )
    assert _revoke_policy(service, key="economy-policy:revoke:bound-expire", expected_revision=4).committed
    obligation = service.scheduled_account_transfer_obligation_for(
        obligation_id=opened.obligation_id
    ).model_copy(update={"status": "due"})
    coordinator = _coordinator(store, service)

    plan = coordinator.plan_expire(
        obligation=obligation,
        fragment=service.build_scheduled_account_transfer_expiry_fragment(
            obligation=obligation,
            reason_ref="reason:policy-bound-revoked-expire",
        ),
        principal_ref=EconomyAuthorityService._PRINCIPAL,
        reason_ref="reason:policy-bound-revoked-expire",
    )

    assert plan.ready and plan.owner_commit_batch is not None
    result = service.commit_obligation_batch(plan.owner_commit_batch)

    assert result.committed
    assert EconomyProjector().rebuild(store.read_events()).balances == {
        "account:alice": 10,
        "account:bob": 0,
    }
