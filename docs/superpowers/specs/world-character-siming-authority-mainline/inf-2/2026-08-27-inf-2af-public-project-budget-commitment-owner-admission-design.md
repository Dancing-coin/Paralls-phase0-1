# INF-2AF Public-Project Budget Commitment Owner-Admission Contract

Status: `implemented and verified narrow vertical; generic budget/payment remains blocked`

## Exact Row

```text
committed Construction public_project_step_completed@1
  project_step_ref = project-step:public-project:workshop-bench@1
-> existing EconomyAuthorityService
-> one public_project_budget_commitment_recorded@1 fact
```

This records a fixed economic budget commitment for the named public-project
step. It is a planning/authorization fact, not a payment: it does not debit or
credit an account, reserve an account balance, create material or inventory,
or imply that the project was purchased or reimbursed.

## Fixed Contract

| Field | Rule |
| --- | --- |
| capability / outcome | `capability:economy-public-project-budget-commitment@1` / `outcome:economy-public-project-budget-commitment-recorded@1` |
| owner | existing `EconomyAuthorityService` (`actor_gameplay.economy_domain`) |
| source | exactly one committed project-visible `gameplay.construction_production.public_project_step_completed` event with fixed `project-step:public-project:workshop-bench@1` |
| source pins | Construction source stream/head, source event revision, facility/project refs, accepted Organization fulfillment id/revision, and original Production evidence/schedule pins |
| target stream / event | `gameplay:economy` / `gameplay.economy.public_project_budget_commitment_recorded@1` |
| privacy | authority-only; no public economy projection or account detail is emitted |
| fixed policy | `policy:economy-public-project-budget-commitment@1`; amount `12`; currency `currency:local`; status `committed` |
| subject | fixed project step, facility and project refs derived from source; commitment ref `budget-commitment:public-project:workshop-bench@1:{project_ref}` |
| idempotency | owner-derived `economy:public-project-budget:{source_event_id}:{source_revision}:{economy_head}:v1` |
| receipt / replay | append-derived `GameplayEventStore.append_batch()` receipt; existing Economy projector full/checkpoint-tail replay |
| lifecycle | v1 terminal commitment; no debit, credit, payment, transfer, release, refund, compensation, retry-as-new or generic budget API |

## Zero-Write Rules

Unknown/missing/private/non-project source, wrong event/step, stale source or
Economy head, missing facility/project binding, changed source vector, duplicate
or changed duplicate, caller-selected amount/currency/account/owner/stream/event
/privacy, and any material/payment/transfer fragment reject before append.
Exact replay returns the original Economy receipt.

## Conflict Matrix

Disposition: `new` existing Economy owner extension. Construction owns the
project-step fact; Economy owns a separate authority-only budget commitment.
The row is distinct from wage, tax, delivery, negotiated exchange, account
reservation, and payment rows. No new owner, package registry, router,
coordinator, writer, settlement authority, or second runtime is introduced.
