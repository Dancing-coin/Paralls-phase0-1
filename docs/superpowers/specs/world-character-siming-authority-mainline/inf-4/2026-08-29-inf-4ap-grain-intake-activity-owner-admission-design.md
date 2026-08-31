# INF-4AP Grain Intake Activity Owner-Admission Contract

Status: `implemented and verified narrow vertical`

## Exact Row

```text
one committed project-visible
gameplay.inventory.grain_harvest_received@1
  holder=organization:district-milling-cooperative
  container=container:district-milling-cooperative:grain-intake
  item=grain:wheat@1 quantity=10
-> existing OrganizationAuthority
-> one project-visible gameplay.organization.grain_intake_recorded@1
```

The row records only the fixed organization's intake of one grain lot. It does
not move or duplicate Inventory custody, start or finish production, settle
money, create a market, or create attendance, social, population or group
truth.

## Fixed Contract

| Field | Value |
| --- | --- |
| capability / outcome | `capability:organization-grain-intake@1` / `outcome:organization-grain-intake-recorded@1` |
| owner / stream / event | `OrganizationAuthority` / `gameplay:organization:organization:district-milling-cooperative` / `gameplay.organization.grain_intake_recorded@1` |
| predicate / effect | `predicate:inventory-grain-harvest-custody@1` / `effect:organization-grain-intake-recorded@1` |
| privacy | project; project and plot are copied only from the committed Inventory source |
| idempotency | owner-derived source event id/revision plus target stream revision |
| receipt / replay | `GameplayEventStore.append_batch()` receipt; `grain_intake_view_for()` full/checkpoint-tail reader |
| lifecycle | terminal once per source custody event; duplicate replay only; no reversal, retry-as-new or compensation |

## Zero-Write

Unknown, private, stale, wrong-owner, wrong-container, wrong-item, wrong
quantity, binding-conflict, duplicate, changed duplicate, revision-conflict,
caller-selected stream/event/privacy/owner, and any payment/production/social
extension reject before append.

The source Inventory event remains the only custody truth. This is one fixed
Organization record and not a generic activity or intake API.
