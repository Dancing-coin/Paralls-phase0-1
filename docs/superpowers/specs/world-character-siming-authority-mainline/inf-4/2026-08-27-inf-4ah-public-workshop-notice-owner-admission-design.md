# INF-4AH Public Workshop Notice Owner-Admission Contract

Status: `implemented and verified; Goal active; August INF A-D not complete`

## Exact Row

```text
committed project-scoped Organization
  gameplay.organization.public_workshop_activity_recorded@1
  (activity_kind=public_workshop_session, status=completed)
-> existing GovernmentAuthority
-> one project-scoped public_workshop_notice_recorded@1 fact
```

This is the public-notice edge for the already completed public-workshop loop.
It records only that the fixed provider activity completed at one bound
facility/project. It does not expose Contract identifiers, payment/account
facts, participants, social relationships, reputation, population, materials,
inventory, production output, permit, technology, weather, maintenance, or a
generic notice/event writer.

## Fixed Contract

| Field | Rule |
| --- | --- |
| capability/outcome | `capability:government-public-workshop-notice@1` / `outcome:government-public-workshop-notice-recorded@1` |
| owner | existing `GovernmentAuthority` (`actor_gameplay.government_domain`) |
| source | exact project-visible `gameplay.organization.public_workshop_activity_recorded` for the fixed INF-4AG row; source activity stream revision and head are pinned |
| source predicate | `predicate:organization-public-workshop-activity-completed@1`; source provider is `organization:municipal-assessment-office`, activity kind/status are exact |
| subject binding | `slot:facility-project@1`; facility_ref/project_ref copied from activity, jurisdiction_ref copied from its committed acquisition event |
| target stream/event | `gameplay:government:public-notice:{jurisdiction_ref}` / `gameplay.government.public_workshop_notice_recorded@1` |
| privacy | project-scoped; public projection contains notice kind, status, organization, facility, project and jurisdiction only |
| idempotency | authority-derived `government:public-workshop-notice:{activity_event_id}:{activity_revision}:{government_head}:v1` |
| receipt/replay | append-derived `GameplayEventStore.append_batch()` receipt; `GovernmentAuthority.public_workshop_notice_view_for` full/checkpoint-tail replay |
| lifecycle | v1 terminal completed; no revoke, edit, retry-as-new, compensation, fanout or generic notification semantics |

The Government stream is a fixed row-specific public-notice projection stream,
not a generic notice registry. The source Contract and Economy events remain
authority-only and are never copied into the notice payload.

## Zero-Write Rules

Unknown/missing/private/stale activity, wrong provider/kind/status, missing or
ambiguous Contract provenance, facility/project/jurisdiction conflict, stale
Government head, unknown/unadmitted descriptor, duplicate or changed
duplicate, privacy conflict, caller-selected owner/stream/event/revision/
receipt, or any attempt to include Contract/payment/account/participant/social/
population fields rejects before append. Exact duplicates replay the original
Government receipt.

## Conflict Matrix

INF-4AG owns the provider activity fact. INF-4AH owns only the Government
notice projection. It is disjoint from drought advisory, inspection,
organization activity, SocialFactAuthority relationship/knowledge, and all
population/group truth. No new owner, router, registry, coordinator, writer,
settlement authority or second runtime is introduced.
