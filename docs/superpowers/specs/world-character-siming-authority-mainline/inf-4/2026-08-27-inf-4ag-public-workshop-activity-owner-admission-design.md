# INF-4AG Public Workshop Activity Owner-Admission Contract

Status: `implemented and verified narrow vertical; generic activity/attendance remains blocked`

## Exact Row

```text
committed authority-only Contract
  gameplay.contract.record_fulfilled@1
  for service:industrial-facility-public-workshop-session@1
-> existing OrganizationAuthority (the fixed provider organization)
-> one project-scoped public_workshop_activity_recorded@1 fact
```

This row closes the product feedback loop for the already implemented public
workshop service. It records that one named organization activity completed at
one facility/project. It does not create a social relationship, attendance
roster, population/NPC fact, reputation, payment, material, inventory,
production output, permit, technology, weather, maintenance, or generic
activity writer.

## Fixed Contract

| Field | Rule |
| --- | --- |
| capability/outcome | `capability:organization-public-workshop-activity@1` / `outcome:organization-public-workshop-activity-recorded@1` |
| owner | existing `OrganizationAuthority` (`actor_gameplay.organization_domain`) |
| source | exact authority-only `gameplay.contract.record_fulfilled` for the fixed public-workshop terms, with its `record_created` source, provider organization, facility_ref and project_ref pins |
| predicate | `predicate:contract-public-workshop-session-fulfilled@1`; exactly one fulfilled Contract record and one matching `service_completion_recorded` event |
| subject | `slot:facility-project@1`; facility_ref and project_ref are copied from the Contract source, never caller-selected |
| target stream/event | `gameplay:organization:{provider_ref}` / `gameplay.organization.public_workshop_activity_recorded@1` |
| privacy | `project`; outbox payload contains activity/facility/project/status only |
| idempotency | authority-derived `organization:public-workshop-activity:{contract_id}:{fulfilled_revision}:{organization_head}:v1` |
| receipt/replay | `GameplayEventStore.append_batch()` append-derived receipt; Organization activity reader must match full/checkpoint-tail replay |
| lifecycle | v1 terminal `completed`; no reopen, cancellation, compensation, reversal, retry-as-new or fanout |

The provider organization is fixed by the Contract's party vector and must be
`organization:municipal-assessment-office`; the receiver is retained only as
opaque source context and is not a second target. Payment settlement is not a
prerequisite and is never re-emitted by this row.

## Zero-Write Rules

Unknown/missing/private source, wrong terms, unfulfilled or multiple Contract
records, missing service completion event, provider mismatch, facility/project
binding conflict, stale Contract or Organization head, duplicate or changed
duplicate, catalog/descriptor mismatch, caller-selected owner/stream/event/
privacy/receipt, and any attempt to add social, population, attendance,
payment, material, inventory, permit, technology, weather, maintenance,
compensation or fanout semantics reject before append. Exact duplicates replay
the original Organization receipt.

## Conflict Matrix

`INF-2AG` owns the service/economic facts; `INF-4AG` owns only the provider
organization's project-scoped activity record. It is disjoint from INF-4V/W
work-history/fulfillment, INF-4Y capability reads, and all social/population
truth. No new owner, generic router, registry, coordinator, writer, settlement
authority or second runtime is introduced.
