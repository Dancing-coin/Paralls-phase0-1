from __future__ import annotations

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.debt_runtime import DebtProjector
from app.gameplay.economy_runtime import EconomyAuthorityService, EconomyProjector
from app.gameplay.phase4_commerce import (
    BoundedCreditProposal,
    CommercialPolicy,
    GovernmentCreditAuthority,
    InspectionEvidence,
    PermitApplication,
)


def _policy() -> CommercialPolicy:
    return CommercialPolicy(
        policy_ref="policy:commerce:v1",
        jurisdiction_ref="jurisdiction:bakery-district",
        revision=1,
        public_digest="sha256:policy:commerce:v1",
        permit_class="permit:food-service",
        tax_rate_basis_points=500,
        credit_limit_minor=100,
        due_calendar_ref="calendar:monthly",
    )


def test_policy_pins_jurisdiction_and_public_digest() -> None:
    policy = _policy()

    assert policy.tax_rate_basis_points == 500
    assert policy.public_digest.startswith("sha256:")


def test_permit_denial_and_stale_policy_leave_zero_writes() -> None:
    store = GameplayEventStore()
    authority = GovernmentCreditAuthority(store=store)
    denied = authority.decide_permit(
        _policy(),
        PermitApplication(
            application_ref="permit-application:1",
            organization_ref="organization:bakery-a",
            jurisdiction_ref="jurisdiction:bakery-district",
            permit_class="permit:food-service",
            policy_revision="policy:commerce:v1",
            evidence_refs=(),
        ),
        approved=False,
        idempotency_key="p4c:permit-denied",
    )
    stale = authority.decide_permit(
        _policy(),
        PermitApplication(
            application_ref="permit-application:stale",
            organization_ref="organization:bakery-a",
            jurisdiction_ref="jurisdiction:bakery-district",
            permit_class="permit:food-service",
            policy_revision="policy:commerce:v0",
            evidence_refs=("evidence:permit:1",),
        ),
        approved=True,
        idempotency_key="p4c:permit-stale",
    )

    assert denied.committed
    assert stale.zero_write
    assert stale.error_code == "policy_revision_stale"


def test_permit_class_mismatch_is_structured_zero_write() -> None:
    store = GameplayEventStore()
    result = GovernmentCreditAuthority(store=store).decide_permit(
        _policy(),
        PermitApplication(
            application_ref="permit-application:wrong-class",
            organization_ref="organization:bakery-a",
            jurisdiction_ref="jurisdiction:bakery-district",
            permit_class="permit:retail",
            policy_revision="policy:commerce:v1",
            evidence_refs=("evidence:permit:wrong-class",),
        ),
        approved=True,
        idempotency_key="p4c:permit-wrong-class",
    )

    assert result.zero_write
    assert result.error_code == "permit_class_mismatch"
    assert store.read_events() == []


def test_inspection_tax_and_bounded_credit_keep_owners_separate() -> None:
    store = GameplayEventStore()
    authority = GovernmentCreditAuthority(store=store)
    inspection = authority.record_inspection(
        _policy(),
        InspectionEvidence(
            inspection_ref="inspection:1",
            organization_ref="organization:bakery-a",
            jurisdiction_ref="jurisdiction:bakery-district",
            policy_revision="policy:commerce:v1",
            evidence_ref="evidence:inspection:1",
            passed=True,
        ),
        idempotency_key="p4c:inspection",
    )
    tax = authority.assess_tax(
        _policy(), organization_ref="organization:bakery-a", period_ref="period:1", taxable_amount_minor=80,
        evidence_refs=("evidence:taxable:period:1",), idempotency_key="p4c:tax"
    )
    assert inspection.committed and tax.committed
    assert EconomyProjector().rebuild(store.read_events()).tax_due["organization:bakery-a:period:1"].assessed_amount_minor == 4
    tax_due = EconomyProjector().rebuild(store.read_events()).tax_due["organization:bakery-a:period:1"]
    assert tax_due.evidence_refs == ("evidence:taxable:period:1",)
    assert tax_due.source_digest.startswith("sha256:")
    event_types = {event.event_type for event in store.read_events()}
    assert "gameplay.government.inspection_recorded" in event_types
    assert "gameplay.economy.tax_due_recorded" in event_types
    assert all("bank" not in event_type for event_type in event_types)
    assert any(
        fragment.owner_principal_ref == "actor_gameplay.government_domain"
        for batch in store.read_transactions()
        for fragment in batch.owner_fragments
    )


def test_credit_limit_rejection_and_public_projection_redaction() -> None:
    store = GameplayEventStore()
    authority = GovernmentCreditAuthority(store=store)
    rejected = authority.validate_bounded_credit_proposal(
        _policy(),
        BoundedCreditProposal(
            proposal_ref="credit:too-large",
            borrower_organization_ref="organization:bakery-a",
            creditor_ref="organization:landlord",
            jurisdiction_ref="jurisdiction:bakery-district",
            policy_revision="policy:commerce:v1",
            amount_minor=101,
            due_tick=10,
            evidence_refs=("evidence:period:1",),
        ),
    )

    assert rejected.zero_write
    assert rejected.error_code == "credit_limit_exceeded"
    public = authority.project_policy(_policy(), scope="public")
    assert "credit_limit_minor" not in public


def test_credit_proposal_without_existing_account_and_debt_refs_is_zero_write() -> None:
    authority = GovernmentCreditAuthority(store=GameplayEventStore())

    result = authority.validate_bounded_credit_proposal(
        _policy(),
        BoundedCreditProposal(
            proposal_ref="credit:missing-owner-refs",
            borrower_organization_ref="organization:bakery-a",
            creditor_ref="organization:landlord",
            jurisdiction_ref="jurisdiction:bakery-district",
            policy_revision="policy:commerce:v1",
            amount_minor=60,
            due_tick=10,
            evidence_refs=("evidence:period:1",),
        ),
    )

    assert result.zero_write
    assert result.error_code == "credit_owner_parameters_required"


def test_credit_grant_or_evidence_mismatch_rejects_before_debt_owner_write() -> None:
    store = GameplayEventStore()
    authority = GovernmentCreditAuthority(store=store)
    proposal = BoundedCreditProposal(
        proposal_ref="credit:bad-grant",
        borrower_organization_ref="organization:bakery-a",
        creditor_ref="organization:landlord",
        jurisdiction_ref="jurisdiction:bakery-district",
        policy_revision="policy:commerce:v1",
        amount_minor=10,
        due_tick=10,
        evidence_refs=("not-evidence",),
        credit_grant_ref="grant:commercial:stale",
    )

    result = authority.validate_bounded_credit_proposal(_policy(), proposal)

    assert result.zero_write
    assert result.error_code == "credit_grant_stale"
    assert store.read_events() == []


def test_bounded_credit_uses_existing_debt_contract_and_account_owners_for_grant_and_repayment() -> None:
    store = GameplayEventStore()
    accounts = EconomyAuthorityService(store=store)
    accounts.open_account(command_id="p4c:landlord-account", account_id="account:landlord", owner_ref="organization:landlord", currency_ref="currency:local", initial_balance=100, idempotency_key="p4c:landlord-account", causation_id="cause", correlation_id="corr")
    accounts.open_account(command_id="p4c:bakery-account", account_id="account:bakery-a", owner_ref="organization:bakery-a", currency_ref="currency:local", initial_balance=10, idempotency_key="p4c:bakery-account", causation_id="cause", correlation_id="corr")
    authority = GovernmentCreditAuthority(store=store)
    proposal = BoundedCreditProposal(proposal_ref="credit:owner-path", borrower_organization_ref="organization:bakery-a", creditor_ref="organization:landlord", jurisdiction_ref="jurisdiction:bakery-district", policy_revision="policy:commerce:v1", amount_minor=50, due_tick=10, evidence_refs=("evidence:period:1",))

    issued = authority.issue_bounded_credit(
        _policy(), proposal, contract_id="contract:credit:owner-path", debt_id="debt:credit:owner-path", creditor_account_id="account:landlord", debtor_account_id="account:bakery-a", currency_ref="currency:local", idempotency_key="p4c:owner-credit"
    )
    repaid = authority.repay_bounded_credit(debt_id="debt:credit:owner-path", debtor_account_id="account:bakery-a", creditor_account_id="account:landlord", amount_minor=50, idempotency_key="p4c:owner-repay")

    assert issued.committed and repaid.committed
    assert EconomyProjector().rebuild(store.read_events()).balances == {"account:bakery-a": 10, "account:landlord": 100}
    event_types = {event.event_type for event in store.read_events()}
    assert {"gameplay.contract.simple_debt_created", "gameplay.debt.claim_issued", "gameplay.debt.claim_satisfied"} <= event_types


def test_overdue_credit_is_owned_by_debt_and_rejects_non_overdue_without_writes() -> None:
    store = GameplayEventStore()
    accounts = EconomyAuthorityService(store=store)
    accounts.open_account(command_id="p4c:overdue-creditor", account_id="account:creditor", owner_ref="organization:landlord", currency_ref="currency:local", initial_balance=100, idempotency_key="p4c:overdue-creditor", causation_id="cause", correlation_id="corr")
    accounts.open_account(command_id="p4c:overdue-debtor", account_id="account:debtor", owner_ref="organization:bakery-a", currency_ref="currency:local", initial_balance=0, idempotency_key="p4c:overdue-debtor", causation_id="cause", correlation_id="corr")
    authority = GovernmentCreditAuthority(store=store)
    proposal = BoundedCreditProposal(proposal_ref="credit:overdue", borrower_organization_ref="organization:bakery-a", creditor_ref="organization:landlord", jurisdiction_ref="jurisdiction:bakery-district", policy_revision="policy:commerce:v1", amount_minor=50, due_tick=10, evidence_refs=("evidence:period:1",))
    assert authority.issue_bounded_credit(_policy(), proposal, contract_id="contract:overdue", debt_id="debt:overdue", creditor_account_id="account:creditor", debtor_account_id="account:debtor", currency_ref="currency:local", idempotency_key="p4c:overdue-issue").committed

    early = authority.mark_overdue_or_default(debt_id="debt:overdue", due_tick=10, tick=10, idempotency_key="p4c:overdue-early")
    mismatched = authority.mark_overdue_or_default(debt_id="debt:overdue", due_tick=9, tick=11, idempotency_key="p4c:overdue-mismatch")
    overdue = authority.mark_overdue_or_default(debt_id="debt:overdue", due_tick=10, tick=11, idempotency_key="p4c:overdue-mark")
    defaulted = authority.mark_overdue_or_default(debt_id="debt:overdue", due_tick=10, tick=12, defaulted=True, idempotency_key="p4c:default-mark")

    assert early.zero_write and early.error_code == "credit_not_overdue"
    assert mismatched.zero_write and mismatched.error_code == "economy_debt_due_tick_mismatch"
    assert overdue.committed and overdue.settlement_plan is not None
    assert defaulted.committed and defaulted.settlement_plan is not None
    assert {"gameplay.debt.claim_overdue", "gameplay.debt.claim_defaulted"} <= {event.event_type for event in store.read_events()}


def test_overdue_credit_can_be_repaid_through_debt_owner() -> None:
    store = GameplayEventStore()
    accounts = EconomyAuthorityService(store=store)
    accounts.open_account(command_id="p4c:repay-creditor", account_id="account:repay-creditor", owner_ref="organization:landlord", currency_ref="currency:local", initial_balance=100, idempotency_key="p4c:repay-creditor", causation_id="cause", correlation_id="corr")
    accounts.open_account(command_id="p4c:repay-debtor", account_id="account:repay-debtor", owner_ref="organization:bakery-a", currency_ref="currency:local", initial_balance=0, idempotency_key="p4c:repay-debtor", causation_id="cause", correlation_id="corr")
    authority = GovernmentCreditAuthority(store=store)
    proposal = BoundedCreditProposal(proposal_ref="credit:overdue-repay", borrower_organization_ref="organization:bakery-a", creditor_ref="organization:landlord", jurisdiction_ref="jurisdiction:bakery-district", policy_revision="policy:commerce:v1", amount_minor=50, due_tick=10, evidence_refs=("evidence:period:1",))
    assert authority.issue_bounded_credit(_policy(), proposal, contract_id="contract:overdue-repay", debt_id="debt:overdue-repay", creditor_account_id="account:repay-creditor", debtor_account_id="account:repay-debtor", currency_ref="currency:local", idempotency_key="p4c:overdue-repay-issue").committed

    assert authority.mark_overdue_or_default(debt_id="debt:overdue-repay", due_tick=10, tick=11, idempotency_key="p4c:overdue-repay-mark").committed
    repaid = authority.repay_bounded_credit(debt_id="debt:overdue-repay", debtor_account_id="account:repay-debtor", creditor_account_id="account:repay-creditor", amount_minor=50, idempotency_key="p4c:overdue-repay-pay")

    assert repaid.committed
    assert {claim.status for claim in DebtProjector().rebuild(store.read_events()).claims.values()} == {"satisfied"}
