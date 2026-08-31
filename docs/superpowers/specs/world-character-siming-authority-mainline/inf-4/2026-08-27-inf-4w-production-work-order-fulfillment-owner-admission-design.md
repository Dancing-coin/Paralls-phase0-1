# INF-4W Production Work-Order Fulfillment Owner-Admission Contract

Status: `implemented and verified narrow vertical; generic work-order lifecycle remains blocked`

## Exact Row

```text
committed Organization production_work_contribution_accepted@1
  + its pinned Construction completion source
-> existing OrganizationAuthority
-> one organization.work_order_fulfilled@1 terminal fact
```

This records that the exact organization work order represented by INF-4V has
been fulfilled after the accepted completed contribution. It is a
work-history/project coordination fact only. It does not create or alter wage,
payment, inventory, production output, material, permit, technology, social,
population, branch, or generic task truth.

## Fixed Contract

| Field | Rule |
| --- | --- |
| capability / outcome | `capability:organization-production-work-order-fulfillment@1` / `outcome:organization-production-work-order-fulfilled@1` |
| owner | existing `OrganizationAuthority` (`actor_gameplay.organization_domain`) |
| source | exactly one committed `gameplay.organization.production_work_contribution_accepted` event from the INF-4V row; its `source_evidence_event_id`, `schedule_event_id`, facility, project, recipient, assignment and work-order pins must remain valid |
| target stream / event | `gameplay:organization:{organization_ref}` / `gameplay.organization.work_order_fulfilled@1` |
| privacy | `organization:summary`; no widening beyond the Organization schedule scope |
| predicate / policy | `predicate:organization-work-contribution-accepted@1`; `policy:organization-production-work-order-fulfillment@1` |
| subject | fixed organization, project, facility, recipient, assignment and work-order refs derived from the accepted source |
| idempotency | owner-derived `organization:production-work-order-fulfillment:{accepted_event_id}:{accepted_revision}:v1` |
| receipt / replay | append-derived `GameplayEventStore.append_batch()` receipt; existing Organization projector and full/checkpoint-tail replay |
| event payload | accepted event id/revision, source evidence id/revision, schedule id/revision, organization/project/facility/recipient/assignment/work-order refs, `prior_status=accepted`, `next_status=fulfilled`, fixed policy and descriptor pins |
| lifecycle | v1 terminal; no re-open, cancel, reversal, compensation, retry-as-new, payment, wage, output, material, fanout or cross-owner batch |

## Zero-Write Rules

Reject before append for unknown/missing/private/non-INF-4V source, multiple or
ambiguous accepted events, changed source payload, stale source or target head,
wrong organization/project/facility/assignment/work-order binding, missing
acceptance status, duplicate or changed duplicate, caller-selected authority
coordinates, and any payload that introduces payment, wage, output, inventory,
material, social, population, branch, or generic task semantics. Exact replay
returns the original Organization receipt; changed intent under the same key is
zero-write.

## Conflict Matrix

This is a new Organization-owned terminal work-history fact, not a duplicate of
INF-4V acceptance, existing `work_order_recorded`, Economy wage accrual, or
branch promotion. It reuses the existing Organization stream and owner-local
replay boundary; no new owner, registry, router, coordinator, or writer is
introduced.
