from __future__ import annotations

from app.gameplay.econ1_economy_runtime import EconomyAuthority, OperatingWindow, WageAccrual
from app.gameplay import econ1_economy_runtime
from app.gameplay.economy_runtime import EconomyAuthorityService, EconomyProjector, EconomyRuntimeError
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.governed_contract_catalog import GovernedAuthorityContractError, GovernedAuthorityContractCatalog
from app.gameplay.organization_government_runtime import AttendanceEvidence, OrganizationAuthority
from app.gameplay.replay import GameplayProjectionReplay
from app.gameplay.settlement_plan import build_atomic_event_batch
from app.gameplay.shared_contracts import GameplayCommandEnvelope


WORKER = "character:char_b"
ORG = "org:bakery"
WINDOW = "window:morning"
WAGE_STREAM = f"gameplay:economy:wage:{WORKER}"
WINDOW_STREAM = f"gameplay:organization:window:{WINDOW}"


def _window() -> OperatingWindow:
    return OperatingWindow(
        window_ref=WINDOW,
        organization_ref=ORG,
        opens_at_tick=1,
        closes_at_tick=5,
        policy_revision="policy:window:1",
        source_revision="schedule:1",
    )


def _verified_evidence(*, verification_state: str = "verified", outcome: str = "completed") -> AttendanceEvidence:
    return AttendanceEvidence(
        evidence_ref="evidence:production-completed:bread:1",
        actor_ref=WORKER,
        assignment_ref="assignment:baker",
        work_order_ref="work:bread",
        source_ref="run:bread:1",
        issuer_principal_ref="actor_gameplay.production_domain",
        evidence_kind="production-completed",
        observed_at="2026-08-15T09:00:00Z",
        outcome=outcome,
        verification_state=verification_state,
        source_digest="sha256:production:bread:1",
    )


def _wage_open_command(*, command_id: str, idempotency_key: str, expected_revision: int = 0) -> GameplayCommandEnvelope:
    return GameplayCommandEnvelope(
        command_id=command_id,
        command_type="gameplay.economy.open_wage_obligation",
        command_version=1,
        principal_ref=EconomyAuthority._PRINCIPAL,
        actor_ref=WORKER,
        project_ref=None,
        transaction_id=f"transaction:{command_id}",
        idempotency_key=idempotency_key,
        expected_revisions={WAGE_STREAM: expected_revision},
        causation_id=f"cause:{command_id}",
        correlation_id=f"corr:{command_id}",
        source_ref=EconomyAuthority._PRINCIPAL,
        submitted_at="2026-08-15T09:00:00Z",
        pinned_revisions={"organization_schedule": 1},
        payload={"visibility_scope": "project"},
    )


def _wage_accrual() -> WageAccrual:
    return WageAccrual(
        accrual_ref="accrual:bread:1",
        organization_ref=ORG,
        payee_actor_ref=WORKER,
        work_evidence_refs=("evidence:production-completed:bread:1",),
        wage_policy_revision="policy:wage:1",
        amount=75,
    )


def _record_schedule(store: GameplayEventStore) -> None:
    OrganizationAuthority(store=store).record_schedule(
        command_id="command:schedule:1",
        organization_ref=ORG,
        recipient_ref=WORKER,
        membership_ref="membership:baker",
        assignment_ref="assignment:baker",
        role="baker",
        shift_ref="shift:morning",
        operating_window_ref=WINDOW,
        work_order_ref="work:bread",
        effective_from="2026-08-15T08:00:00Z",
        effective_to=None,
        visibility_scope=f"actor:{WORKER}",
    )


def _replay_events_into_store(events: list[object]) -> GameplayEventStore:
    replayed = GameplayEventStore()
    for index, event in enumerate(events, start=1):
        batch = build_atomic_event_batch(
            command_id=f"replay:{index}",
            principal_ref="replay:test",
            stream_id=event.stream_id,
            expected_revision=replayed.get_stream_head(event.stream_id),
            event_specs=[(event.event_type, event.payload)],
            idempotency_key=f"replay:{index}",
            causation_id="replay",
            correlation_id="replay",
        ).model_copy(
            update={
                "events": [
                    event.model_copy(
                        update={
                            "stream_revision": 0,
                            "global_sequence": 0,
                            "transaction_id": f"transaction:replay:{index}",
                            "command_id": f"replay:{index}",
                        },
                        deep=True,
                    )
                ]
            },
            deep=True,
        )
        assert replayed.append_batch(batch).committed
    return replayed


def test_payroll_window_closure_success_uses_organization_window_owner_and_economy_payment() -> None:
    store = GameplayEventStore()
    organization = OrganizationAuthority(store=store)
    economy = EconomyAuthority(store=store)
    accounts = EconomyAuthorityService(store=store)

    _record_schedule(store)
    schedule = organization.schedule_view_for(
        organization_ref=ORG,
        recipient_ref=WORKER,
        observed_at="2026-08-15T09:00:00Z",
    )
    assert schedule.shift_offers[0]["operating_window_ref"] == WINDOW

    assert organization.open_operating_window(
        command_id="command:window:open",
        idempotency_key="window:open",
        causation_id="cause:window:open",
        correlation_id="corr:window:open",
        window=_window(),
        visibility_scope="project",
    ).committed
    assert economy.open_wage_obligation(
        command=_wage_open_command(command_id="command:wage:open", idempotency_key="wage:open"),
        accrual_ref="accrual:bread:1",
        organization_ref=ORG,
        work_evidence_refs=("evidence:production-completed:bread:1",),
        wage_amount_minor=75,
        due_tick=5,
        policy_revision="policy:wage:1",
    ).committed
    evidence = organization.completed_evidence(_verified_evidence())
    assert organization.close_operating_window(
        command_id="command:window:close",
        idempotency_key="window:close",
        causation_id="cause:window:close",
        correlation_id="corr:window:close",
        organization_ref=ORG,
        window_ref=WINDOW,
        expected_stream_revision=1,
        visibility_scope="project",
    ).committed
    assert organization.record_operating_window_due(
        command_id="command:window:due",
        idempotency_key="window:due",
        causation_id="cause:window:due",
        correlation_id="corr:window:due",
        organization_ref=ORG,
        window_ref=WINDOW,
        expected_stream_revision=2,
        visibility_scope="project",
    ).committed
    assert economy.accrue_wage(
        _wage_accrual(),
        completed_evidence_refs={evidence.evidence_ref},
        command_id="command:wage:accrue",
        idempotency_key="wage:accrue",
        causation_id="cause:wage:accrue",
        correlation_id="corr:wage:accrue",
    ).committed
    assert accounts.open_account(
        command_id="command:account:bakery",
        account_id="account:bakery",
        owner_ref=ORG,
        currency_ref="currency:coin",
        initial_balance=100,
        idempotency_key="account:bakery",
        causation_id="cause:account:bakery",
        correlation_id="corr:account:bakery",
    ).committed
    assert accounts.open_account(
        command_id="command:account:worker",
        account_id="account:worker",
        owner_ref=WORKER,
        currency_ref="currency:coin",
        initial_balance=0,
        idempotency_key="account:worker",
        causation_id="cause:account:worker",
        correlation_id="corr:account:worker",
    ).committed
    assert economy.pay_wage(
        _wage_accrual(),
        payer_account_id="account:bakery",
        payee_account_id="account:worker",
        command_id="command:wage:pay",
        idempotency_key="wage:pay",
        causation_id="cause:wage:pay",
        correlation_id="corr:wage:pay",
    ).committed

    window_events = store.read_stream(WINDOW_STREAM)
    assert [event.event_type for event in window_events] == [
        "gameplay.organization.operating_window_opened",
        "gameplay.organization.operating_window_closed",
        "gameplay.organization.operating_window_due_recorded",
    ]
    assert store.read_transactions()[1].idempotency_record.principal_ref == OrganizationAuthority._PRINCIPAL
    wage_events = store.read_stream(WAGE_STREAM)
    assert [event.event_type for event in wage_events] == [
        "gameplay.economy.wage_obligation_opened",
        "gameplay.economy.wage_accrued",
        "gameplay.economy.wage_paid",
    ]
    balances = EconomyProjector().rebuild(store.read_events()).balances
    assert balances["account:bakery"] == 25
    assert balances["account:worker"] == 75


def test_payroll_window_closure_invalid_or_unverified_evidence_is_zero_write() -> None:
    store = GameplayEventStore()
    organization = OrganizationAuthority(store=store)
    economy = EconomyAuthority(store=store)

    _record_schedule(store)
    before = len(store.read_events())

    try:
        organization.completed_evidence(_verified_evidence(verification_state="pending"))
    except ValueError as error:
        assert str(error) == "work_evidence_invalid"
    else:
        raise AssertionError("expected invalid evidence")

    try:
        economy.accrue_wage(
            _wage_accrual(),
            completed_evidence_refs=set(),
            command_id="command:wage:accrue:bad",
            idempotency_key="wage:accrue:bad",
            causation_id="cause:wage:accrue:bad",
            correlation_id="corr:wage:accrue:bad",
        )
    except ValueError as error:
        assert str(error) == "work_evidence_invalid"
    else:
        raise AssertionError("expected invalid wage accrual evidence")

    assert len(store.read_events()) == before


def test_payroll_wage_accrual_and_overdue_use_formal_settlement_plan_and_actor_outbox(monkeypatch) -> None:
    store = GameplayEventStore()
    authority = EconomyAuthority(store=store)
    seen: list[object] = []
    original = econ1_economy_runtime.SettlementPlan.from_command_envelope

    def observe(command):
        seen.append(command)
        return original(command)

    monkeypatch.setattr(
        econ1_economy_runtime.SettlementPlan,
        "from_command_envelope",
        observe,
    )

    assert authority.accrue_wage(
        _wage_accrual(),
        completed_evidence_refs={"evidence:production-completed:bread:1"},
        command_id="command:wage:accrue",
        idempotency_key="wage:accrue",
        causation_id="cause:wage:accrue",
        correlation_id="corr:wage:accrue",
    ).committed
    assert authority.mark_overdue(
        _wage_accrual(),
        command_id="command:wage:overdue",
        idempotency_key="wage:overdue",
        causation_id="cause:wage:overdue",
        correlation_id="corr:wage:overdue",
    ).committed

    assert len(seen) == 2
    assert seen[0].principal_ref == EconomyAuthority._PRINCIPAL
    assert seen[0].payload["event_type"] == "gameplay.economy.wage_accrued"
    assert seen[1].payload["event_type"] == "gameplay.economy.wage_overdue"
    outbox = store.list_outbox()
    assert [entry.audience for entry in outbox] == [f"actor:{WORKER}", f"actor:{WORKER}"]
    assert outbox[0].payload_projection == {"accrual_ref": "accrual:bread:1", "status": "accrued"}
    assert outbox[1].payload_projection == {"accrual_ref": "accrual:bread:1", "status": "overdue"}


def test_payroll_wage_payment_emits_scoped_actor_and_authority_outbox() -> None:
    store = GameplayEventStore()
    accounts = EconomyAuthorityService(store=store)
    authority = EconomyAuthority(store=store)
    for account_id, owner_ref, balance in (
        ("account:bakery", ORG, 100),
        ("account:worker", WORKER, 0),
    ):
        assert accounts.open_account(
            command_id=f"command:{account_id}",
            account_id=account_id,
            owner_ref=owner_ref,
            currency_ref="currency:coin",
            initial_balance=balance,
            idempotency_key=account_id,
            causation_id=f"cause:{account_id}",
            correlation_id=f"corr:{account_id}",
        ).committed

    assert authority.pay_wage(
        _wage_accrual(),
        payer_account_id="account:bakery",
        payee_account_id="account:worker",
        command_id="command:wage:pay",
        idempotency_key="wage:pay",
        causation_id="cause:wage:pay",
        correlation_id="corr:wage:pay",
    ).committed

    outbox = store.list_outbox()
    wage_outbox = [entry for entry in outbox if entry.topic == "economy.wage.scoped_projection"]
    authority_outbox = [
        entry for entry in outbox if entry.topic == "economy.account.authority_projection"
    ]
    assert len(wage_outbox) == 1
    assert wage_outbox[0].audience == f"actor:{WORKER}"
    assert wage_outbox[0].payload_projection == {
        "accrual_ref": "accrual:bread:1",
        "status": "paid",
    }
    assert [entry.audience for entry in authority_outbox] == ["authority:economy", "authority:economy"]


def test_payroll_wage_payment_materializes_command_settlement_plan(monkeypatch) -> None:
    store = GameplayEventStore()
    accounts = EconomyAuthorityService(store=store)
    authority = EconomyAuthority(store=store)
    for account_id, owner_ref, balance in (
        ("account:bakery", ORG, 100),
        ("account:worker", WORKER, 0),
    ):
        assert accounts.open_account(
            command_id=f"command:{account_id}",
            account_id=account_id,
            owner_ref=owner_ref,
            currency_ref="currency:coin",
            initial_balance=balance,
            idempotency_key=account_id,
            causation_id=f"cause:{account_id}",
            correlation_id=f"corr:{account_id}",
        ).committed

    seen: list[object] = []
    original = econ1_economy_runtime.SettlementPlan.from_command_envelope

    def observe(command):
        seen.append(command)
        return original(command)

    monkeypatch.setattr(
        econ1_economy_runtime.SettlementPlan,
        "from_command_envelope",
        observe,
    )

    assert authority.pay_wage(
        _wage_accrual(),
        payer_account_id="account:bakery",
        payee_account_id="account:worker",
        command_id="command:wage:pay:plan",
        idempotency_key="wage:pay:plan",
        causation_id="cause:wage:pay:plan",
        correlation_id="corr:wage:pay:plan",
    ).committed

    assert len(seen) == 1
    assert seen[0].principal_ref == EconomyAuthority._PRINCIPAL
    assert seen[0].expected_revisions == {
        "gameplay:economy": 2,
        "gameplay:economy:wage:character:char_b": 0,
    }


def test_payroll_window_closure_compatibility_wrapper_delegates_to_organization_owner() -> None:
    store = GameplayEventStore()
    result = EconomyAuthority(store=store).open_window(
        _window(),
        command_id="command:compat:window:open",
        idempotency_key="compat:window:open",
        causation_id="cause:compat:window:open",
        correlation_id="corr:compat:window:open",
    )

    assert result.committed
    transaction = store.read_transactions()[-1]
    assert transaction.idempotency_record.principal_ref == OrganizationAuthority._PRINCIPAL
    assert store.read_events()[-1].stream_id == WINDOW_STREAM


def test_payroll_window_owner_contract_failure_rejects_before_append(monkeypatch) -> None:
    store = GameplayEventStore()

    def reject_contract(**_kwargs):
        raise GovernedAuthorityContractError("governed_authority_contract_owner_mismatch")

    monkeypatch.setattr(GovernedAuthorityContractCatalog, "require_operation", reject_contract)

    result = OrganizationAuthority(store=store).open_operating_window(
        command_id="command:window:catalog-reject",
        idempotency_key="window:catalog-reject",
        causation_id="cause:window:catalog-reject",
        correlation_id="corr:window:catalog-reject",
        window=_window(),
        visibility_scope="project",
    )

    assert not result.committed
    assert result.failure is not None
    assert result.failure.error_code == "governed_authority_contract_owner_mismatch"
    assert store.read_events() == []


def test_payroll_wage_payment_contract_failure_rejects_before_append(monkeypatch) -> None:
    store = GameplayEventStore()
    accounts = EconomyAuthorityService(store=store)
    authority = EconomyAuthority(store=store)
    for account_id, owner_ref, balance in (
        ("account:bakery", ORG, 100),
        ("account:worker", WORKER, 0),
    ):
        assert accounts.open_account(
            command_id=f"command:{account_id}",
            account_id=account_id,
            owner_ref=owner_ref,
            currency_ref="currency:coin",
            initial_balance=balance,
            idempotency_key=account_id,
            causation_id=f"cause:{account_id}",
            correlation_id=f"corr:{account_id}",
        ).committed
    before = store.read_events()

    def reject_contract(**_kwargs):
        raise GovernedAuthorityContractError("governed_authority_contract_stream_mismatch")

    monkeypatch.setattr(GovernedAuthorityContractCatalog, "require_operation", reject_contract)

    try:
        authority.pay_wage(
            _wage_accrual(),
            payer_account_id="account:bakery",
            payee_account_id="account:worker",
            command_id="command:wage:catalog-reject",
            idempotency_key="wage:catalog-reject",
            causation_id="cause:wage:catalog-reject",
            correlation_id="corr:wage:catalog-reject",
        )
    except EconomyRuntimeError as error:
        assert str(error) == "governed_authority_contract_stream_mismatch"
    else:
        raise AssertionError("expected catalog admission rejection")

    assert store.read_events() == before


def test_payroll_window_closure_duplicate_idempotency_replays_without_second_write() -> None:
    store = GameplayEventStore()
    organization = OrganizationAuthority(store=store)
    economy = EconomyAuthority(store=store)
    _record_schedule(store)

    first_window = organization.open_operating_window(
        command_id="command:window:open",
        idempotency_key="window:open",
        causation_id="cause:window:open",
        correlation_id="corr:window:open",
        window=_window(),
        visibility_scope="project",
    )
    duplicate_window = organization.open_operating_window(
        command_id="command:window:open",
        idempotency_key="window:open",
        causation_id="cause:window:open",
        correlation_id="corr:window:open",
        window=_window(),
        visibility_scope="project",
    )
    first_wage = economy.open_wage_obligation(
        command=_wage_open_command(command_id="command:wage:open", idempotency_key="wage:open"),
        accrual_ref="accrual:bread:1",
        organization_ref=ORG,
        work_evidence_refs=("evidence:production-completed:bread:1",),
        wage_amount_minor=75,
        due_tick=5,
        policy_revision="policy:wage:1",
    )
    duplicate_wage = economy.open_wage_obligation(
        command=_wage_open_command(command_id="command:wage:open", idempotency_key="wage:open"),
        accrual_ref="accrual:bread:1",
        organization_ref=ORG,
        work_evidence_refs=("evidence:production-completed:bread:1",),
        wage_amount_minor=75,
        due_tick=5,
        policy_revision="policy:wage:1",
    )

    assert first_window.committed and duplicate_window.committed
    assert duplicate_window.idempotency_status == "duplicate_replayed"
    assert first_wage.committed and duplicate_wage.committed
    assert duplicate_wage.idempotency_status == "duplicate_replayed"
    assert len(store.read_stream(WINDOW_STREAM)) == 1
    assert len(store.read_stream(WAGE_STREAM)) == 1


def test_payroll_window_open_changed_idempotency_key_reuse_is_revision_conflict() -> None:
    store = GameplayEventStore()
    organization = OrganizationAuthority(store=store)

    assert organization.open_operating_window(
        command_id="command:window:open",
        idempotency_key="window:open",
        causation_id="cause:window:open",
        correlation_id="corr:window:open",
        window=_window(),
        visibility_scope="project",
    ).committed

    changed_key = organization.open_operating_window(
        command_id="command:window:open:reused",
        idempotency_key="window:open:reused",
        causation_id="cause:window:open:reused",
        correlation_id="corr:window:open:reused",
        window=_window(),
        visibility_scope="project",
    )

    assert not changed_key.committed
    assert changed_key.failure is not None
    assert changed_key.failure.error_code == "revision_conflict"
    assert len(store.read_stream(WINDOW_STREAM)) == 1


def test_payroll_window_close_changed_idempotency_key_reuse_is_revision_conflict() -> None:
    store = GameplayEventStore()
    organization = OrganizationAuthority(store=store)

    assert organization.open_operating_window(
        command_id="command:window:open",
        idempotency_key="window:open",
        causation_id="cause:window:open",
        correlation_id="corr:window:open",
        window=_window(),
        visibility_scope="project",
    ).committed
    assert organization.close_operating_window(
        command_id="command:window:close",
        idempotency_key="window:close",
        causation_id="cause:window:close",
        correlation_id="corr:window:close",
        organization_ref=ORG,
        window_ref=WINDOW,
        expected_stream_revision=1,
        visibility_scope="project",
    ).committed

    changed_key = organization.close_operating_window(
        command_id="command:window:close:reused",
        idempotency_key="window:close:reused",
        causation_id="cause:window:close:reused",
        correlation_id="corr:window:close:reused",
        organization_ref=ORG,
        window_ref=WINDOW,
        expected_stream_revision=1,
        visibility_scope="project",
    )

    assert not changed_key.committed
    assert changed_key.failure is not None
    assert changed_key.failure.error_code == "revision_conflict"
    assert len(store.read_stream(WINDOW_STREAM)) == 2


def test_payroll_window_due_changed_idempotency_key_reuse_is_revision_conflict() -> None:
    store = GameplayEventStore()
    organization = OrganizationAuthority(store=store)

    assert organization.open_operating_window(
        command_id="command:window:open",
        idempotency_key="window:open",
        causation_id="cause:window:open",
        correlation_id="corr:window:open",
        window=_window(),
        visibility_scope="project",
    ).committed
    assert organization.close_operating_window(
        command_id="command:window:close",
        idempotency_key="window:close",
        causation_id="cause:window:close",
        correlation_id="corr:window:close",
        organization_ref=ORG,
        window_ref=WINDOW,
        expected_stream_revision=1,
        visibility_scope="project",
    ).committed
    assert organization.record_operating_window_due(
        command_id="command:window:due",
        idempotency_key="window:due",
        causation_id="cause:window:due",
        correlation_id="corr:window:due",
        organization_ref=ORG,
        window_ref=WINDOW,
        expected_stream_revision=2,
        visibility_scope="project",
    ).committed

    changed_key = organization.record_operating_window_due(
        command_id="command:window:due:reused",
        idempotency_key="window:due:reused",
        causation_id="cause:window:due:reused",
        correlation_id="corr:window:due:reused",
        organization_ref=ORG,
        window_ref=WINDOW,
        expected_stream_revision=2,
        visibility_scope="project",
    )

    assert not changed_key.committed
    assert changed_key.failure is not None
    assert changed_key.failure.error_code == "revision_conflict"
    assert len(store.read_stream(WINDOW_STREAM)) == 3


def test_payroll_window_closure_changed_window_idempotency_key_is_zero_write() -> None:
    store = GameplayEventStore()
    organization = OrganizationAuthority(store=store)
    assert organization.open_operating_window(
        command_id="command:window:open", idempotency_key="window:open",
        causation_id="cause:window:open", correlation_id="corr:window:open",
        window=_window(), visibility_scope="project",
    ).committed
    changed_open = organization.open_operating_window(
        command_id="command:window:open", idempotency_key="window:open",
        causation_id="cause:window:open", correlation_id="corr:window:open",
        window=_window().model_copy(update={"policy_revision": "policy:window:2"}), visibility_scope="project",
    )
    assert not changed_open.committed
    assert changed_open.failure is not None and changed_open.failure.error_code == "idempotency_key_reused"
    assert organization.close_operating_window(
        command_id="command:window:close", idempotency_key="window:close",
        causation_id="cause:window:close", correlation_id="corr:window:close",
        organization_ref=ORG, window_ref=WINDOW, expected_stream_revision=1, visibility_scope="project",
    ).committed
    changed_close = organization.close_operating_window(
        command_id="command:window:close", idempotency_key="window:close",
        causation_id="cause:window:close", correlation_id="corr:window:close",
        organization_ref="org:other", window_ref=WINDOW, expected_stream_revision=1, visibility_scope="project",
    )
    assert not changed_close.committed
    assert changed_close.failure is not None and changed_close.failure.error_code == "idempotency_key_reused"
    assert organization.record_operating_window_due(
        command_id="command:window:due", idempotency_key="window:due",
        causation_id="cause:window:due", correlation_id="corr:window:due",
        organization_ref=ORG, window_ref=WINDOW, expected_stream_revision=2, visibility_scope="project",
    ).committed
    changed_due = organization.record_operating_window_due(
        command_id="command:window:due", idempotency_key="window:due",
        causation_id="cause:window:due", correlation_id="corr:window:due",
        organization_ref=ORG, window_ref=WINDOW, expected_stream_revision=2, visibility_scope="authority_only",
    )
    assert not changed_due.committed
    assert changed_due.failure is not None and changed_due.failure.error_code == "idempotency_key_reused"
    assert len(store.read_stream(WINDOW_STREAM)) == 3


def test_payroll_window_closure_stale_revision_is_zero_write() -> None:
    store = GameplayEventStore()
    organization = OrganizationAuthority(store=store)
    economy = EconomyAuthority(store=store)

    assert organization.open_operating_window(
        command_id="command:window:open",
        idempotency_key="window:open",
        causation_id="cause:window:open",
        correlation_id="corr:window:open",
        window=_window(),
        visibility_scope="project",
    ).committed
    stale_window = organization.close_operating_window(
        command_id="command:window:close:stale",
        idempotency_key="window:close:stale",
        causation_id="cause:window:close:stale",
        correlation_id="corr:window:close:stale",
        organization_ref=ORG,
        window_ref=WINDOW,
        expected_stream_revision=0,
        visibility_scope="project",
    )
    assert economy.open_wage_obligation(
        command=_wage_open_command(command_id="command:wage:open", idempotency_key="wage:open"),
        accrual_ref="accrual:bread:1",
        organization_ref=ORG,
        work_evidence_refs=("evidence:production-completed:bread:1",),
        wage_amount_minor=75,
        due_tick=5,
        policy_revision="policy:wage:1",
    ).committed
    stale_wage = economy.open_wage_obligation(
        command=_wage_open_command(command_id="command:wage:open:stale", idempotency_key="wage:open:stale"),
        accrual_ref="accrual:bread:2",
        organization_ref=ORG,
        work_evidence_refs=("evidence:production-completed:bread:2",),
        wage_amount_minor=80,
        due_tick=6,
        policy_revision="policy:wage:1",
    )

    assert not stale_window.committed
    assert stale_window.failure is not None and stale_window.failure.error_code == "revision_conflict"
    assert not stale_wage.committed
    assert stale_wage.failure is not None and stale_wage.failure.error_code == "revision_conflict"
    assert len(store.read_stream(WINDOW_STREAM)) == 1
    assert len(store.read_stream(WAGE_STREAM)) == 1


def test_payroll_window_closure_privacy_scope_and_schedule_views_are_bounded() -> None:
    store = GameplayEventStore()
    organization = OrganizationAuthority(store=store)
    _record_schedule(store)

    own = organization.schedule_view_for(
        organization_ref=ORG,
        recipient_ref=WORKER,
        observed_at="2026-08-15T09:00:00Z",
    )
    other = organization.schedule_view_for(
        organization_ref=ORG,
        recipient_ref="character:char_a",
        observed_at="2026-08-15T09:00:00Z",
    )
    denied = organization.open_operating_window(
        command_id="command:window:privacy",
        idempotency_key="window:privacy",
        causation_id="cause:window:privacy",
        correlation_id="corr:window:privacy",
        window=_window(),
        visibility_scope="public",
    )

    assert own.shift_offers and own.work_orders
    assert other.shift_offers == ()
    assert not denied.committed
    assert denied.failure is not None and denied.failure.error_code == "organization_window_visibility_invalid"


def test_payroll_window_closure_explicit_close_can_end_in_overdue() -> None:
    store = GameplayEventStore()
    organization = OrganizationAuthority(store=store)
    economy = EconomyAuthority(store=store)
    accounts = EconomyAuthorityService(store=store)

    _record_schedule(store)
    assert organization.open_operating_window(
        command_id="command:window:open",
        idempotency_key="window:open",
        causation_id="cause:window:open",
        correlation_id="corr:window:open",
        window=_window(),
        visibility_scope="project",
    ).committed
    assert organization.completed_evidence(_verified_evidence()).evidence_ref == "evidence:production-completed:bread:1"
    assert economy.open_wage_obligation(
        command=_wage_open_command(command_id="command:wage:open", idempotency_key="wage:open"),
        accrual_ref="accrual:bread:1",
        organization_ref=ORG,
        work_evidence_refs=("evidence:production-completed:bread:1",),
        wage_amount_minor=75,
        due_tick=5,
        policy_revision="policy:wage:1",
    ).committed
    assert organization.close_operating_window(
        command_id="command:window:close",
        idempotency_key="window:close",
        causation_id="cause:window:close",
        correlation_id="corr:window:close",
        organization_ref=ORG,
        window_ref=WINDOW,
        expected_stream_revision=1,
        visibility_scope="project",
    ).committed
    assert accounts.open_account(
        command_id="command:account:bakery",
        account_id="account:bakery",
        owner_ref=ORG,
        currency_ref="currency:coin",
        initial_balance=0,
        idempotency_key="account:bakery",
        causation_id="cause:account:bakery",
        correlation_id="corr:account:bakery",
    ).committed
    assert accounts.open_account(
        command_id="command:account:worker",
        account_id="account:worker",
        owner_ref=WORKER,
        currency_ref="currency:coin",
        initial_balance=0,
        idempotency_key="account:worker",
        causation_id="cause:account:worker",
        correlation_id="corr:account:worker",
    ).committed

    try:
        economy.pay_wage(
            _wage_accrual(),
            payer_account_id="account:bakery",
            payee_account_id="account:worker",
            command_id="command:wage:pay",
            idempotency_key="wage:pay",
            causation_id="cause:wage:pay",
            correlation_id="corr:wage:pay",
        )
    except EconomyRuntimeError as error:
        assert str(error) == "economy_insufficient_funds"
    else:
        raise AssertionError("expected insufficient funds")

    overdue = economy.mark_overdue(
        _wage_accrual(),
        command_id="command:wage:overdue",
        idempotency_key="wage:overdue",
        causation_id="cause:wage:overdue",
        correlation_id="corr:wage:overdue",
    )

    assert overdue.committed
    assert store.read_stream(WAGE_STREAM)[-1].event_type == "gameplay.economy.wage_overdue"


def test_payroll_settlement_receipt_is_append_derived_and_authority_scoped() -> None:
    store = GameplayEventStore()
    accounts = EconomyAuthorityService(store=store)
    authority = EconomyAuthority(store=store)
    for account_id, owner_ref, balance in (
        ("account:bakery", ORG, 100),
        ("account:worker", WORKER, 0),
    ):
        assert accounts.open_account(
            command_id=f"command:{account_id}",
            account_id=account_id,
            owner_ref=owner_ref,
            currency_ref="currency:coin",
            initial_balance=balance,
            idempotency_key=account_id,
            causation_id=f"cause:{account_id}",
            correlation_id=f"corr:{account_id}",
        ).committed

    result = authority.pay_wage(
        _wage_accrual(),
        payer_account_id="account:bakery",
        payee_account_id="account:worker",
        command_id="command:wage:receipt",
        idempotency_key="wage:receipt",
        causation_id="cause:wage:receipt",
        correlation_id="corr:wage:receipt",
    )
    receipt = authority.payroll_settlement_receipt_for(result=result, privacy_scope="authority")

    assert receipt.transaction_id == result.transaction_id
    assert receipt.committed_event_ids == tuple(result.committed_event_ids)
    assert receipt.stream_revisions == result.resulting_stream_revisions
    assert receipt.audit_refs == (f"payroll_transaction:{result.transaction_id}",)
    assert receipt.zero_write is False

    before_events, before_outbox = store.read_events(), store.list_outbox()
    try:
        authority.payroll_settlement_receipt_for(result=result, privacy_scope="public")
    except EconomyRuntimeError as error:
        assert str(error) == "economy_payroll_receipt_scope_denied"
    else:
        raise AssertionError("public payroll receipt must be rejected")
    assert store.read_events() == before_events
    assert store.list_outbox() == before_outbox


def test_payroll_window_closure_full_and_checkpoint_tail_replay_match() -> None:
    store = GameplayEventStore()
    organization = OrganizationAuthority(store=store)
    economy = EconomyAuthority(store=store)

    _record_schedule(store)
    assert organization.open_operating_window(
        command_id="command:window:open",
        idempotency_key="window:open",
        causation_id="cause:window:open",
        correlation_id="corr:window:open",
        window=_window(),
        visibility_scope="project",
    ).committed
    assert organization.close_operating_window(
        command_id="command:window:close",
        idempotency_key="window:close",
        causation_id="cause:window:close",
        correlation_id="corr:window:close",
        organization_ref=ORG,
        window_ref=WINDOW,
        expected_stream_revision=1,
        visibility_scope="project",
    ).committed
    assert organization.record_operating_window_due(
        command_id="command:window:due",
        idempotency_key="window:due",
        causation_id="cause:window:due",
        correlation_id="corr:window:due",
        organization_ref=ORG,
        window_ref=WINDOW,
        expected_stream_revision=2,
        visibility_scope="project",
    ).committed
    assert economy.open_wage_obligation(
        command=_wage_open_command(command_id="command:wage:open", idempotency_key="wage:open"),
        accrual_ref="accrual:bread:1",
        organization_ref=ORG,
        work_evidence_refs=("evidence:production-completed:bread:1",),
        wage_amount_minor=75,
        due_tick=5,
        policy_revision="policy:wage:1",
    ).committed

    events = store.read_events()
    replay = GameplayProjectionReplay(projector_id="payroll-window", projector_version="1")
    full = replay.full_replay(events)
    checkpoint = replay.create_checkpoint(events[:2])
    tail = replay.checkpoint_plus_tail_replay(checkpoint, events[2:])
    replayed = _replay_events_into_store(events)

    assert full.projection_hash == tail.projection_hash
    assert organization.schedule_view_for(
        organization_ref=ORG,
        recipient_ref=WORKER,
        observed_at="2026-08-15T09:00:00Z",
    ).projection_hash == OrganizationAuthority(store=replayed).schedule_view_for(
        organization_ref=ORG,
        recipient_ref=WORKER,
        observed_at="2026-08-15T09:00:00Z",
    ).projection_hash
    assert organization.operating_window_view_for(
        window_ref=WINDOW,
        recipient_ref="authority:organization",
    ).projection_hash == OrganizationAuthority(store=replayed).operating_window_view_for(
        window_ref=WINDOW,
        recipient_ref="authority:organization",
    ).projection_hash
