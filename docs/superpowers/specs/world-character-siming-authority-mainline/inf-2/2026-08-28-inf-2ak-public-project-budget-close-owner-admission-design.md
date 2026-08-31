# INF-2AK Public-Project Budget Close Owner-Admission Contract

Status: `implemented narrow vertical; broader budget lifecycle remains blocked`

## Exact Row

```text
committed INF-2AI
  gameplay.economy.public_project_budget_consumed@1
+ committed INF-4AJ
  gameplay.organization.public_project_execution_recorded@1
  (status=funded_and_executed, matching project/facility)
-> existing EconomyAuthorityService
-> one gameplay.economy.public_project_budget_closed@1
```

The row records only the Economy-owned terminal close marker after the
Organization owner has recorded funded execution. It does not mutate an
account, release or refund a reservation, make a payment or transfer, or
create material, inventory, production, weather, maintenance, social,
population, or generic lifecycle facts.

## Fixed Contract

| Field | Fixed rule |
| --- | --- |
| capability / outcome | `capability:economy-public-project-budget-close@1` / `outcome:economy-public-project-budget-closed@1` |
| descriptor / catalog | `descriptor:economy-public-project-budget-close@1` / `inf:economy-public-project-budget-close@1` |
| owner | existing `EconomyAuthorityService` (`actor_gameplay.economy_domain`) |
| sources | exact INF-2AI consumed marker and exact INF-4AJ `funded_and_executed` project execution |
| predicate | `predicate:economy-public-project-budget-consumed-and-project-executed@1` |
| target | `gameplay:economy` / `gameplay.economy.public_project_budget_closed@1`, one event only |
| payload | owner-derived closure ref, project/facility binding, source event/revision pins, `status=closed`, fixed policy/descriptor/catalog pins, terminal marker |
| privacy | `authority_only`; the project execution source remains project-scoped |
| idempotency | Economy derives a key from consumed event/revision, execution event/revision, Economy head, execution stream/head, and `v1` |
| receipt / replay | append-derived `GameplayEventStore.append_batch()` receipt; `public_project_budget_close_projection` full/checkpoint-tail replay |
| lifecycle | v1 terminal close marker; no re-open, retry-as-new, release, refund, payment, transfer, compensation, or fanout |

Before envelope construction the owner rereads both committed source events,
checks exact source catalog/policy/descriptor pins, project/facility binding,
privacy and current stream heads, and requires the immutable catalog operation.
No caller-selected owner, stream, event, privacy, revision, receipt, or
fragment is accepted.

## Zero-Write Rules

Unknown, missing, private, stale, malformed, mismatched, duplicate, multiple,
or unadmitted source events; wrong execution status; provenance or
facility/project binding conflict; Economy or Organization revision conflict;
changed idempotency; catalog/descriptor mismatch; and any request for account
mutation, release, refund, payment, transfer, material, output, compensation,
reopen, retry, or generic lifecycle behavior reject before append. An exact
duplicate returns the original append result.

## Replay And Isolation

The Economy projector validates both source events and all close payload pins
before rebuilding the closure map. Full and checkpoint-tail projection reads
must be identical. INF-2AI remains the consumed marker and INF-4AJ remains
the Organization execution fact; this row is not a generic budget lifecycle
or settlement authority.

The close projection revalidates each stored closure against its committed
INF-2AI consumed marker and INF-4AJ execution, including source revisions,
privacy, fixed catalog identity, status, and facility/project binding. Forged
or missing provenance fails closed during full or checkpoint-tail replay.
