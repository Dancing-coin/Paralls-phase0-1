# INF-2AH Public-Project Budget Reservation Owner-Admission Contract

Status: `implemented and verified narrow vertical; generic budget/payment remains blocked`

## Exact Row

```text
committed INF-2AF
  gameplay.economy.public_project_budget_commitment_recorded@1
  project_step_ref = project-step:public-project:workshop-bench@1
+ committed project-visible Construction facility_acquired@1
  facility_ref/project_ref/owner_ref binding
-> existing EconomyAuthorityService
-> one gameplay.economy.budget_reserved@1
```

This row reserves the fixed public-project commitment for exactly one
owner-derived `currency:local` account. It does not debit or credit the
account, release a reservation, reimburse, pay, transfer, or create material,
inventory, production, weather, maintenance, social, or population truth.

## Fixed Contract

| Field | Rule |
| --- | --- |
| capability / outcome | `capability:economy-public-project-budget-reservation@1` / `outcome:economy-public-project-budget-reserved@1` |
| descriptor / catalog | `descriptor:economy-public-project-budget-reservation@1`; `inf:economy-public-project-budget-reservation@1` |
| owner | existing `EconomyAuthorityService` (`actor_gameplay.economy_domain`) |
| source | one committed authority-only INF-2AF `public_project_budget_commitment_recorded@1` plus its facility's committed project-visible `facility_acquired@1` |
| eligibility predicate | `predicate:economy-public-project-commitment-owner-account@1`; acquisition `owner_ref` must bind the commitment facility/project |
| target stream / event | `gameplay:economy` / `gameplay.economy.budget_reserved@1` |
| fixed vector | one reservation event, `reservation_ref=reservation:public-project:workshop-bench:{project_ref}`, `amount_minor=12`, `currency_ref=currency:local`, `status=reserved` |
| account selection | exactly one existing Economy account with `owner_ref=acquisition.owner_ref` and `currency_ref=currency:local`; caller never supplies an account |
| privacy | authority-only; no account, balance or reservation detail in project/public views |
| revision fence | exact commitment revision, Economy head, acquisition event revision, and current facility stream head are pinned in the command/read set |
| idempotency | `economy:public-project-budget-reservation:{commitment_event_id}:{commitment_revision}:{acquisition_event_id}:{acquisition_revision}:{economy_head}:{account_id}:v1`, derived by Economy |
| receipt / replay | append-derived `GameplayEventStore.append_batch()` receipt; Economy reservation full/checkpoint-tail replay |
| lifecycle | v1 terminal reservation; no release, cancellation, reimbursement, payment, transfer, reversal, retry-as-new or compensation |

The Economy projector also revalidates the reservation's pinned commitment and
acquisition event identities, revisions, visibility, facility/project binding,
and owner before rebuilding the exact row. A forged provenance payload is a
replay failure, not a partially materialized reservation.

## Zero-Write Rules

Reject before append for unknown/wrong/private/stale commitment or acquisition,
facility/project binding conflict, missing owner account, multiple matching
accounts, wrong currency, insufficient unreserved balance, stale Economy or
facility head, existing reservation, malformed or changed idempotency, catalog
or descriptor mismatch, and caller-selected owner/account/amount/currency/
stream/event/privacy/receipt. Exact duplicate returns the original receipt;
changed duplicate is zero-write.

## Isolation

INF-2AF remains the source commitment fact. INF-2AH only records a reservation
projection and does not consume or generalize `reserve_budget()` into a generic
caller-selected API. No package, router, registry, coordinator, writer,
settlement authority, second runtime, payment, transfer, release, or material
semantics are added.

## Evidence

The focused INF-2AH tests and immutable catalog regression pass, and the
independent `inf2ah-public-project-budget-reservation` Harness proves success,
zero-write ambiguity/missing-account/funds cases, authority privacy,
owner-derived idempotency, append receipt, and full/checkpoint-tail replay.
