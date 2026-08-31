# INF-1AL Mill-Reinforced Public-Use Owner-Admission Contract

Status: `implemented narrow vertical; generic facility availability remains blocked`

## Exact Row

```text
committed project-visible Construction facility_operationally_verified@1
  for a current active facility whose kind is mill_reinforced
+ exactly one committed v2 mill -> mill_reinforced transformation provenance
  and its facility/project binding
-> existing ConstructionProductionAuthority
-> one facility_public_use_enabled@1 fact
```

The row records only Construction-owned `public_use_status=enabled` and the
next facility revision. It does not create or modify production output,
inventory, material, payment, permit, technology, weather, maintenance,
social, population, or lifecycle facts.

## Fixed Contract

| Field | Rule |
| --- | --- |
| capability / outcome | `capability:construction-facility-mill-reinforced-public-use-enable@1` / `outcome:construction-facility-mill-reinforced-public-use-enabled@1` |
| descriptor / catalog | `descriptor:construction-facility-mill-reinforced-public-use-enable@1`; `inf:construction-facility-mill-reinforced-public-use@1`, kind `lifecycle` |
| owner | existing `ConstructionProductionAuthority` (`actor_gameplay.construction_production_domain`) |
| source | one committed project-visible `facility_operationally_verified@1` for the same facility, plus exactly one earlier frozen v2 `mill -> mill_reinforced` transform event |
| eligibility / predicate | `construction:facility-operationally-verified@1` with row-specific `predicate:construction-facility-mill-reinforced-operationally-verified@1`; current facility kind `mill_reinforced`, lifecycle `active`, and v2 content/declaration/descriptor/policy pins must match exactly |
| target stream / event | `gameplay:construction_production:{facility_ref}` / existing `gameplay.construction_production.facility_public_use_enabled@1` family, partitioned by row ref |
| privacy / subject | project-scoped; committed `facility_ref` and `project_ref=facility.plot_ref` are fixed; caller selects neither |
| idempotency | `construction:facility-mill-reinforced-public-use:{verification_event_id}:{verification_revision}:{facility_revision}:{stream_head}:v1` |
| receipt / replay | append-derived `GameplayEventStore.append_batch()` receipt; existing Construction projector full/checkpoint-tail replay |
| fixed payload | facility/project refs, `facility_kind=mill_reinforced`, verification and reinforcement event ids/revisions, source run refs, prior/next facility revision, expected stream head, row policy/descriptor/catalog pins |
| lifecycle | v1 terminal; no disable, re-enable, reversal, downgrade, retry-as-new, compensation, fanout or cross-domain effect |

## Zero-Write Rules

Unknown or private verification, missing or multiple reinforcement provenance,
wrong v2 digest/declaration/policy, wrong facility kind, non-active or missing
facility, missing run verification, binding conflict, stale source/facility/
stream revision, enabled public-use status, catalog/descriptor mismatch,
duplicate or changed duplicate, and caller-selected owner/stream/event/privacy/
revision/receipt all reject before append. An oven request belongs only to
INF-1AJ; this row does not widen that operation or create generic
`facility_kind -> public_use` behavior.

## Conflict Matrix Result

Disposition: `existing_row_extension`. INF-1AJ owns the disjoint oven source
partition; INF-1AL owns the fixed mill-reinforced source partition while using
the same Construction-owned public-use fact semantics. INF-1AG v2 is read-only
source evidence and is not modified or re-frozen.

## Evidence

The focused `INF-1AL` suite and independent
`inf1al-mill-reinforced-public-use` Harness verify success, zero-write,
privacy, revision, idempotency, append receipt, and full/checkpoint-tail
replay. No generic public-use endpoint or second runtime is added.
