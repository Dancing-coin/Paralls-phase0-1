# INF-3V Weather Rain To Survival Hydration Owner-Admission Contract

Status: `implemented and verified narrow vertical; generic weather consumer remains blocked`

## Exact Row

```text
committed project-visible gameplay.ecology.weather_front.propagated@1
  weather_ref = weather:rain
  + committed active profile-to-region assignment
-> existing SurvivalAuthority
-> state:hydrated@1 + scheduled obligation
```

Rain provides one bounded hydration state for the assigned character. The row
uses the existing Survival state lifecycle and changes no need, inventory,
water resource, weather truth, social fact, payment, material, production,
population, or generic consumer registry.

## Fixed Contract

| Field | Rule |
| --- | --- |
| capability / outcome | `capability:weather-front-survival-hydration@1` / `outcome:weather-front-survival-hydration@1` |
| source owner / evidence | existing `EcologyHazardAuthority`; exact project-visible `gameplay.ecology.weather_front.propagated` with `weather_ref=weather:rain`, source/target region and event revision pinned |
| assignment evidence | existing active `population.activation.region_assigned` for the same profile and target region, project-visible and revision pinned |
| target owner | existing `SurvivalAuthority` (`actor_gameplay.survival_domain`) |
| target stream / vector | `gameplay:survival:{profile_ref}`; exactly `state_applied` then `obligation_opened` |
| state / effect | fixed `state:hydrated`, `effect:hydration`, refresh stack policy, limit 1, scheduled expiry at source tick + 1 |
| privacy | project-scoped; no authority-only or public widening |
| predicate / policy | `predicate:ecology-weather-front-rain@1`; `policy:weather-front-survival-hydration@1` |
| idempotency | `weather-front-hydration:{weather_event_id}:{profile_ref}:v1`, derived from source and bound profile |
| receipt / replay | append-derived Survival receipt; existing Survival full/checkpoint-tail replay |
| lifecycle | existing Survival expiry closes the state; no compensation, fanout, retry-as-new, reversal, or cross-owner batch |

## Zero-Write Rules

Unknown/missing/private/wrong-weather source, inactive or mismatched region
assignment, stale Ecology/population/Survival revisions, duplicate or changed
duplicate, existing hydration state, wrong target stream, caller-selected
profile/source/owner/event/privacy/revision, and any `drought_process_advanced`
substitution reject before append. Exact duplicate returns the original
Survival receipt.

## Conflict Matrix

Disposition: `new` existing-owner Ecology -> Survival extension. It is distinct
from drought dehydration, frost cold, heat overheated, and existing Ecology
process rows because source weather, state/effect, policy, and idempotency are
fixed to rain/hydration. No new owner, router, registry, fanout, or generic
consumer is introduced.
