# INF-1AD Weather-front Survival Overheated Owner Row

Status: `implemented and independently verified as one exact existing-owner source edge; generic INF-1 remains incomplete`

INF-1AD adds one explicit Ecology evidence edge to the existing Survival owner.
It does not add a Survival owner, stream, event family, scheduler, or truth
store. The admitted input is a committed project-visible Ecology weather-front
event with `weather_ref == "weather:heat"`, paired with the existing
project-scoped activation region assignment for one active profile.

| Field | Contract |
| --- | --- |
| source event | `gameplay.ecology.weather_front.propagated` on `gameplay:ecology:{source_region_ref}` |
| source value | `weather:heat` |
| target prerequisite | committed `population.activation.region_assigned` with active profile and matching target region |
| owner | existing `actor_gameplay.survival_domain` / `SurvivalAuthority` |
| target stream | `gameplay:survival:{profile_ref}` |
| effect/state | `effect:heat_exposure -> state:overheated` |
| event family | existing `gameplay.survival.state_applied`, `gameplay.survival.obligation_opened` |
| projection/privacy | existing project-scoped Survival outbox and projector |
| revision fence | survival expected revision plus Ecology source and population assignment read revisions |
| receipt | only the existing Survival `AppendBatchResult`; source writes keep independent receipts |

The Survival authority validates the source event, assignment evidence, active
profile lifecycle, privacy, source/target revisions and the immutable governed
catalog row before constructing its existing state/obligation events. All
rejections occur before `GameplayEventStore.append_batch()`. Duplicate commands
replay by the existing Survival idempotency key and changed duplicates remain
zero-write.

This package is intentionally one finite source edge. It does not register
caller-selected weather mappings, add a generic consumer registry, widen the
effect/state matrix, or implement fanout, retry, compensation, group truth or
any new owner.

Evidence: `.harness/verification/infra-weather-front-survival-overheated-report.json`.
