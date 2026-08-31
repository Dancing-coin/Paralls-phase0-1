# INF-3AA Weather Rain To Water Resource Recovery Owner-Admission Contract

Status: `implemented and verified narrow vertical; generic Ecology consumer remains blocked`

## Exact Row

```text
committed project-visible gameplay.ecology.weather_front.propagated@1
  weather_ref = weather:rain
+ exactly one project-visible ResourceNode in target_region_ref
  substance_ref = substance:water
  quantity = 0..99
-> existing EcologyHazardAuthority
-> one project-visible gameplay.ecology.resource.recorded@1 recovery partition
```

The fixed policy adds `10` to the selected resource quantity and caps it at
`100`. It is a direct weather-front consequence, not seasonal regeneration,
drought correction, crop recovery, extraction, inventory material, or an
economy input.

## Ownership And Conflict Matrix

| Field | Fixed rule |
| --- | --- |
| capability / outcome | `capability:ecology-weather-rain-water-resource-recovery@1` / `outcome:ecology-weather-rain-water-resource-recovered@1` |
| fact claim | one `substance:water` ResourceNode quantity transition within one target region |
| source claim | exact committed project-visible rain front, source event revision, Ecology source/target stream heads, target region binding |
| owner | existing `EcologyHazardAuthority` only |
| target | `gameplay:ecology:{target_region_ref}` / existing `gameplay.ecology.resource.recorded@1`, partitioned by `row_ref=ecology:weather-rain-water-resource-recovery@1` |
| privacy | project; no authority-only/private/caller-selected substitute |
| policy | `policy:ecology-weather-rain-water-resource-recovery@1`, revision `1`, delta `10`, cap `100` |
| idempotency | owner-derived weather event id/revision + resource ref/revision + target stream head + policy revision |
| receipt / replay | `GameplayEventStore.append_batch()` receipt; Ecology regional full and checkpoint-tail replay |
| lifecycle | terminal once per weather/resource revision; exact duplicate replays, changed duplicate rejects; no reversal, retry-as-new, compensation, or fanout |

The row is `new`, not a duplicate. Seasonal regeneration is a separate
process-source partition; drought correction, crop recovery, and resource
extraction have different fact claims and source policies. It shares only the
existing Ecology owner, stream, and `resource.recorded` family under an exact
provenance partition.

## Fixed Payload

The event payload must carry `row_ref`, weather event id/revision, target
region, resource ref, prior/next resource revision and quantity, recovery
delta, cap, policy/predicate/descriptor/catalog pins, causal parent, and
authority-derived key. No caller may select the resource, amount, cap, owner,
stream, event, privacy, receipt, or lifecycle fragment.

## Zero-Write

Unknown/wrong/private/stale weather; non-rain source; source/target revision
conflict; zero or multiple eligible water resources; healthy/full resource;
wrong region/substance; authority-only/private resource source; duplicate/change mismatch; forged policy/predicate/
catalog provenance; caller-shaped authority coordinates; and fanout or
compensation requests all reject before append.

## Explicit Exclusions

This row does not create grain, crop harvest, Inventory custody, material,
payment, market price, service, facility condition, Survival state, social
fact, generic resource recovery, consumer registry, router, coordinator,
writer, or second runtime. `drought_process_advanced` is never source evidence.

The runtime locates the latest committed resource record for the selected node
and rejects it unless that source event is project-visible. The regional reader
repeats this check against the exact prior resource revision, so forged private
source provenance fails closed in both full and checkpoint-tail replay.
