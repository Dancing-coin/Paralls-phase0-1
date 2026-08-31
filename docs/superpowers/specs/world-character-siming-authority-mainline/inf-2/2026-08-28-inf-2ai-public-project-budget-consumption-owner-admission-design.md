# INF-2AI Public-Project Budget Consumption Owner-Admission Contract

Status: `implemented and verified narrow vertical; generic budget/payment remains blocked`

## Exact Row

```text
committed project-scoped INF-4AG
  gameplay.organization.public_workshop_activity_recorded@1
  (activity_kind=public_workshop_session, status=completed)
+ committed authority-only INF-2AH
  gameplay.economy.budget_reserved@1
  (reservation_ref, project_ref, facility_ref, 12 currency:local)
-> existing EconomyAuthorityService
-> one gameplay.economy.public_project_budget_consumed@1
```

This row records consumption of the one fixed public-project reservation after
the matching workshop activity. It does not debit or credit an account, release
or refund a reservation, transfer funds, or create any material, inventory,
production, weather, maintenance, social, population, or generic budget fact.

## Fixed Contract

| Field | Fixed rule |
| --- | --- |
| capability / outcome | `capability:economy-public-project-budget-consumption@1` / `outcome:economy-public-project-budget-consumed@1` |
| descriptor / catalog | `descriptor:economy-public-project-budget-consumption@1` / `inf:economy-public-project-budget-consumption@1` |
| owner | existing `EconomyAuthorityService` (`actor_gameplay.economy_domain`) |
| source | exact INF-2AH reservation, exact INF-2AF commitment, and project-visible INF-4AG completed workshop activity |
| predicate | `predicate:economy-public-project-budget-reserved-and-workshop-activity@1` |
| target | `gameplay:economy` / `gameplay.economy.public_project_budget_consumed@1`, one event only |
| fixed payload | reservation/commitment/activity refs and revisions, facility/project binding, `amount_minor=12`, `currency_ref=currency:local`, `status=consumed` |
| privacy | `authority_only`; activity source remains project-scoped and is never widened |
| idempotency | Economy derives `economy:public-project-budget-consumption:{commitment_event_id}:{commitment_revision}:{reservation_event_id}:{reservation_revision}:{activity_event_id}:{activity_revision}:{economy_head}:{activity_stream}:{activity_head}:v1` |
| receipt / replay | append-derived `GameplayEventStore.append_batch()` receipt; `public_project_budget_consumption_projection` full/checkpoint-tail replay |
| lifecycle | v1 terminal consumed marker; no release, reversal, refund, retry-as-new, compensation or fanout |

The owner re-reads all three committed source events and current stream heads
before constructing the envelope. Caller-supplied owner, stream, event,
amount, currency, reservation, activity, privacy, receipt, or compensation
coordinates are rejected before append.

## Zero-Write Rules

Unknown, missing, private, stale, malformed, mismatched, or duplicate
commitment/reservation/activity; wrong terms, activity kind or status; project
or facility binding conflict; missing reservation provenance; stale Economy or
Organization head; missing catalog/descriptor; malformed or changed
idempotency; multiple semantic consumption attempts; and any request for
release, payment, transfer, refund, material, output, or compensation reject
before mutation. Exact duplicate delivery returns the original receipt.

## Replay And Isolation

The Economy projector validates the pinned commitment, reservation and
activity provenance, including the fixed commitment and activity provider,
service, policy and
descriptor identity, while rebuilding the consumed map. Full and
checkpoint-tail reads must produce the same refs, payloads and projection hash.
INF-2AF and INF-2AH remain independent source/ reservation facts; INF-4AG
remains the Organization activity fact. This row is not a generic budget
lifecycle or settlement authority.
