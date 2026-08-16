# INF-1AC Weather-front Survival Cold Owner Row

Status: `implemented and independently verified`

Verification: `backend/tests/test_infra_weather_front_survival_cold.py` and
the `infra-weather-front-survival-cold` Harness independently prove all named
success, zero-write, revision, idempotency, privacy and replay boundaries.

## Purpose

INF-4AC supplies the previously missing, event-derived active profile-to-region
projection. INF-1AC consumes that projection for exactly one existing Survival
row. It admits a project-visible committed `weather:frost` weather-front event
for one active profile assigned to that front's target region, then lets the
existing `SurvivalAuthority` append its existing cold state and expiry events.

## Fixed Contract

| Field | Value |
| --- | --- |
| source evidence owner | existing `EcologyHazardAuthority` / `authority:ecology` |
| source event | project-visible `gameplay.ecology.weather_front.propagated` with `weather_ref == "weather:frost"` |
| target evidence owner | existing `ProfileActivationAuthority` / `world_runtime.activation_authority` |
| target evidence event | project-visible `population.activation.region_assigned` for the same active `profile_ref` and `target_region_ref` |
| write owner | existing `SurvivalAuthority` / `actor_gameplay.survival_domain` |
| target stream | existing `gameplay:survival:{profile_ref}` |
| target events | existing `gameplay.survival.state_applied`, `gameplay.survival.obligation_opened` |
| effect/state | fixed `effect:cold_exposure -> state:cold` |
| expiry | existing `policy:survival_state_expiry@1`, due at weather-front tick plus one |
| privacy | project only; scoped Survival outbox and projection only |
| receipt/replay | one resulting `GameplayEventStore.append_batch()` result; existing `SurvivalProjector` and checkpoint-tail replay |

## Admission

Before its owner fragment is built, Survival must verify all of the following:

- command principal is the existing Survival owner, source is `authority:ecology`,
  actor and payload profile are identical, and the requested event family/scope
  is the fixed row;
- the weather event exists on its canonical Ecology stream, is project-visible,
  has the exact event type, target region and `weather:frost` value;
- the region assignment exists on `population:{world_ref}`, is project-visible,
  names the same active profile and target region, and the profile remains
  active in that world;
- the command pins the Survival write head plus both Ecology and population
  read heads; and
- the governed catalog admits only this owner, stream, existing event family
  and project projection scope.

Missing, private, forged or region-mismatched evidence; inactive profiles;
wrong weather/effect/state/owner/stream/scope; stale source or target revisions;
and changed idempotency reuse must reject before `append_batch()` with zero
writes. Ecology only supplies committed evidence and never writes Survival.

## Non-goals

This does not introduce a generic weather mapping, a generic ecology consumer
registry, a new Survival stream/event family, a scheduler, or a population/NPC/
social truth owner. Other weather values, profiles, state rows, fanout, retry,
compensation and consumer outcomes remain unsupported until separately admitted.
