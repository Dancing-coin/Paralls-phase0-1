from __future__ import annotations

import sys

from common import repo_root

sys.path.insert(0, str(repo_root() / "backend"))

from app.gameplay.economy_runtime import EconomyAuthorityService
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.phase4_commerce import BoundedCreditProposal, CommercialPolicy, GovernmentCreditAuthority, InspectionEvidence, PermitApplication
from verify_phase4_common import replay_evidence, run_focused, write_report


policy = CommercialPolicy(policy_ref="policy:commerce:v1", jurisdiction_ref="jurisdiction:bakery-district", revision=1, public_digest="sha256:policy:commerce:v1", permit_class="permit:food-service", tax_rate_basis_points=500, credit_limit_minor=100, due_calendar_ref="calendar:monthly")
ok, log = run_focused("backend/tests/test_phase4_government_credit.py")
store = GameplayEventStore()
accounts = EconomyAuthorityService(store=store)
accounts.open_account(command_id="verify:p4c:creditor", account_id="account:landlord", owner_ref="organization:landlord", currency_ref="currency:local", initial_balance=100, idempotency_key="creditor", causation_id="verify", correlation_id="p4c")
accounts.open_account(command_id="verify:p4c:debtor", account_id="account:bakery-a", owner_ref="organization:bakery-a", currency_ref="currency:local", initial_balance=10, idempotency_key="debtor", causation_id="verify", correlation_id="p4c")
authority = GovernmentCreditAuthority(store=store)
permit = authority.decide_permit(policy, PermitApplication(application_ref="permit:verify", organization_ref="organization:bakery-a", jurisdiction_ref=policy.jurisdiction_ref, permit_class=policy.permit_class, policy_revision=policy.policy_ref, evidence_refs=("evidence:permit",)), approved=True, idempotency_key="permit")
inspection = authority.record_inspection(policy, InspectionEvidence(inspection_ref="inspection:verify", organization_ref="organization:bakery-a", jurisdiction_ref=policy.jurisdiction_ref, policy_revision=policy.policy_ref, evidence_ref="evidence:inspection", passed=True), idempotency_key="inspection")
tax = authority.assess_tax(policy, organization_ref="organization:bakery-a", period_ref="period:verify", taxable_amount_minor=80, evidence_refs=("evidence:taxable",), idempotency_key="tax")
proposal = BoundedCreditProposal(proposal_ref="credit:verify", borrower_organization_ref="organization:bakery-a", creditor_ref="organization:landlord", jurisdiction_ref=policy.jurisdiction_ref, policy_revision=policy.policy_ref, amount_minor=50, due_tick=8, evidence_refs=("evidence:credit",))
credit = authority.issue_bounded_credit(policy, proposal, contract_id="contract:verify", debt_id="debt:verify", creditor_account_id="account:landlord", debtor_account_id="account:bakery-a", currency_ref="currency:local", idempotency_key="credit")
overdue = authority.mark_overdue_or_default(debt_id="debt:verify", due_tick=8, tick=9, defaulted=False, idempotency_key="overdue")
default = authority.mark_overdue_or_default(debt_id="debt:verify", due_tick=8, tick=10, defaulted=True, idempotency_key="default")
stale = authority.decide_permit(policy, PermitApplication(application_ref="permit:stale", organization_ref="organization:bakery-a", jurisdiction_ref=policy.jurisdiction_ref, permit_class=policy.permit_class, policy_revision="policy:commerce:v0", evidence_refs=("evidence:stale",)), approved=True, idempotency_key="stale")
full, checkpoint_tail = replay_evidence(store.read_events())
public = authority.project_policy(policy, scope="public")
raise SystemExit(write_report("phase4c-government-credit", {
    "overall_passed": ok and permit.committed and inspection.committed and tax.committed and credit.committed and default.committed and stale.zero_write and full.succeeded and checkpoint_tail.succeeded and full.projection_hash == checkpoint_tail.projection_hash,
    "focused_log": log,
    "policy_quote_digest": policy.public_digest,
    "atomic_receipt": credit.receipt.transaction_id if credit.receipt else None,
    "revision_vector": credit.revision_vector,
    "replay_hash": f"sha256:{full.projection_hash}",
    "checkpoint_tail_hash": f"sha256:{checkpoint_tail.projection_hash}",
    "privacy_redaction": {"view": public, "credit_limit_excluded": "credit_limit_minor" not in public},
    "failure_zero_write": stale.zero_write,
    "stage_outcomes": {"permit": permit.committed, "inspection": inspection.committed, "tax": tax.committed, "credit": credit.committed, "overdue": overdue.committed, "default": default.committed, "default_error": default.error_code, "stale_zero_write": stale.zero_write},
}))
