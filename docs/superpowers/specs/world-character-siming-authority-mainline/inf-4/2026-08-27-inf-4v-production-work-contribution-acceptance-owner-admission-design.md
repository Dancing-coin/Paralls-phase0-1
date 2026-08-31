# INF-4V Production Work-Contribution Acceptance Owner-Admission Contract

Status: `implemented and verified narrow vertical; generic work acceptance remains blocked`

## Product Loop

```text
committed Construction production-completed evidence
  + committed Organization schedule/work-order access proof
-> existing OrganizationAuthority
-> one Organization-owned production_work_contribution_accepted@1 fact
```

This row records that an organization accepted one completed contribution that
was already linked to its committed assignment and work order. It is useful for
organization-side work history and later public-project accounting, but it does
not create a wage, payment, production output, inventory, social relationship,
population, or branch-promotion fact.

## Fixed Contract

| Field | Rule |
| --- | --- |
| capability / outcome | `capability:organization-production-work-contribution-acceptance@1` / `outcome:organization-production-work-contribution-accepted@1` |
| owner | existing `OrganizationAuthority` (`actor_gameplay.organization_domain`) |
| source evidence | one committed `gameplay.construction_production.work_completion_evidence_recorded` event with `evidence_kind=production-completed`, `outcome=completed`, `verification_state=verified` |
| access proof | exactly one committed `gameplay.organization.work_order_recorded` event whose `visibility_scope=organization:summary`, `organization_ref`, `recipient_ref`, `assignment_ref`, and `work_order_ref` match the source; its effective interval must contain the source `observed_at` |
| target stream / event | `gameplay:organization:{organization_ref}` / `gameplay.organization.production_work_contribution_accepted@1` |
| privacy | `organization:summary`; the source actor-private evidence is never widened to public or another actor; the schedule event is the explicit organization access grant |
| policy / predicate | `policy:organization-production-work-contribution-acceptance@1`; `predicate:production-completed-evidence-bound-to-organization-schedule@1` |
| subject | fixed `organization_ref + recipient_ref + assignment_ref + work_order_ref + run_ref + facility_ref`; caller cannot replace any subject component |
| idempotency | owner-derived `organization:production-work-contribution:{organization_ref}:{source_event_id}:{source_revision}:{schedule_event_id}:{schedule_revision}:v1` |
| receipt / replay | `GameplayEventStore.append_batch()` append-derived receipt; existing Organization stream projector supports full and checkpoint-tail replay |
| lifecycle | v1 terminal acceptance; no reversal, retraction, compensation, retry-as-new, wage, payment, material, output, fanout, or cross-owner batch |

The target event retains the exact source and schedule event ids/revisions,
their stream heads, the contribution digest, and the fixed policy/descriptor
pins. It does not copy private source details into an outbox projection.

## Admission And Zero-Write

The verifier rereads both source and schedule streams before append and checks
the current Organization stream head. Unknown/missing source, source visibility
or evidence-kind mismatch, missing/private/non-summary schedule, zero or
multiple matching schedule records, assignment/work-order/recipient mismatch,
effective-interval mismatch, stale source or schedule revision, target stream
revision conflict, duplicate or changed duplicate, caller-selected owner/
stream/event/privacy/revision, and any payment/wage/output/material/social
field are rejected before mutation.

An exact duplicate returns the original owner-local receipt. Any changed intent
under the same derived key is zero-write. The source actor-private event remains
visible only through the existing actor/owner evidence rules; the accepted
record is organization-summary scoped and carries only the minimum bound
identifiers.

## Conflict-Matrix Decision

Disposition: `new` existing-row extension. Construction retains production
completion evidence; Economy retains wage truth; Organization owns the new
acceptance fact and its stream/replay/receipt. This is distinct from wage
accrual, role assignment, work-order recording, branch promotion, and social
relationship truth. No new owner, registry, router, coordinator, or generic
consumer is introduced.

## Implementation Gate

The row requires a strict Organization intent, an owner-bound verifier, one
fixed projector branch, an immutable catalog descriptor, focused RED-to-green
tests, an independent Harness, and full/checkpoint-tail replay evidence. The
existing generic schedule recorder remains unchanged; this row cannot be
invoked by caller-supplied proof or by a generic event type.
