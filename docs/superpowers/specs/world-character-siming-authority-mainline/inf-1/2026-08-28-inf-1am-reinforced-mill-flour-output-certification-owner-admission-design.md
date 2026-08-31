# INF-1AM Reinforced Mill Flour Output Certification Owner-Admission Contract

Status: `implemented and verified narrow vertical; generic Construction output remains blocked`

## Exact Row

```text
committed project-visible facility_acquired(mill)
+ exact frozen package:industrial-facilities:v2 mill -> mill_reinforced transform
+ current project-visible active mill_reinforced facility
+ one completed run with recipe_ref=recipe:industrial-facilities:mill-flour@1
  and output_item=item:industrial-facilities:flour@1
-> existing ConstructionProductionAuthority
-> one project-visible flour-output-certified fact
```

The fact certifies only that this exact Construction run produced the fixed
typed flour output. It does not instantiate an item, grant custody, consume
input grain, settle a price, change a recipe, or create an Economy fact.

## Fixed Boundary

| Field | Fixed value |
| --- | --- |
| capability / outcome | `capability:construction-reinforced-mill-flour-output-certification@1` / `outcome:construction-reinforced-mill-flour-output-certified@1` |
| owner | `ConstructionProductionAuthority` |
| target stream / event | `gameplay:construction_production:{facility_ref}` / `gameplay.construction_production.mill_flour_output_certified@1` |
| privacy | project only; `project_ref` equals committed acquisition `plot_ref` |
| output partition | `recipe:industrial-facilities:mill-flour@1`, `item:industrial-facilities:flour@1`, quantity `10` |
| evidence | exact acquisition, frozen v2 reinforcement, run-started, run-finished, current facility revision and stream head |
| policy / descriptor / catalog | `policy:industrial-facilities:reinforced-mill-flour-output@1`, `descriptor:construction-reinforced-mill-flour-output-certification@1`, `inf:construction-reinforced-mill-flour-output-certification@1` |
| idempotency | authority-derived from the finished event id/revision, facility revision, target stream head, and policy revision |
| receipt / replay | `GameplayEventStore.append_batch()` receipt; existing Construction projector full and checkpoint-tail replay |
| lifecycle | terminal per exact completed run; duplicate replays, changed duplicate rejects; no reversal, retry-as-new, compensation, fanout, material, payment, or output delivery |

The conflict-matrix disposition is `new`. Earlier operational verification
certifies facility operability; public-use rows certify service availability;
this row certifies one immutable output partition and shares neither their
outcome nor their payload semantics.

## Zero Write

Unknown or private/stale acquisition, reinforcement, run-start, or run-finish;
wrong kind/lifecycle/recipe/output; missing or mismatched v2 pins; project or
facility binding conflict; revision conflict; duplicate certification; a
caller-selected quantity, item, stream, event, privacy, owner, receipt or
compensation request; and any attempt to use a non-fixed recipe/output all
reject before append.

## Downstream Boundary

INF-2AM may consume this certificate only through a separately admitted
Inventory custody row. This Construction event never creates Inventory or
Economy truth and cannot be used as a generic production-output API.
