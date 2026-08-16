# INF-3G Weather-Front Construction Consumer Edge

Status: `implemented and independently verified; one exact Construction consumer edge`

INF-3G adds exactly one registered Ecology-to-Construction consumer edge. Ecology
may propose an opaque admission from an existing project-scoped
`gameplay.ecology.weather_front.propagated` event. Only the existing
`ConstructionProductionAuthority` may append the existing
`gameplay.construction_production.maintenance_obligation_created` event on an
existing facility stream.

| Boundary | Contract |
| --- | --- |
| Source owner | `authority:ecology` |
| Source event | `gameplay.ecology.weather_front.propagated` |
| Target owner | `authority:construction` |
| Target stream | `gameplay:construction_production:{facility_ref}` |
| Target event | `gameplay.construction_production.maintenance_obligation_created` |
| Edge | `ecology-weather:front-to-construction-maintenance:v1` |
| Scope | `project` only |
| Write path | authority -> command/admission -> one `append_batch()` -> outbox/replay |

The command is a closed schema containing source event identity/revision,
source ecology stream head, target facility identity, region, weather and tick.
Construction rejects missing/forged admission, stale source or target revision,
source privacy violations, mismatched facility/run, changed duplicate and
unsupported edge before any append. Exact duplicates replay. The proposal is
not a generic consumer registry or cross-domain settlement coordinator.

Completion requires focused success, zero-write rejection, idempotency,
revision, privacy and full/checkpoint-tail replay evidence plus predecessor
INF-3A..3F and continuation-gate evidence.
