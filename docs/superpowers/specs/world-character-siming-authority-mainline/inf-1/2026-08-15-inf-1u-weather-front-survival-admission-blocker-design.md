# INF-1U Weather-front Survival Admission Blocker Design

Status: `superseded for the exact weather:frost cold and weather:heat overheated rows; broader admission remains blocked`

Date: `2026-08-15`

Only two approved `weather-front -> Survival` effect/state lifecycle rows
exist in the INF-1 contract surface; all other weather-front inputs remain
blocked.

The only admitted Survival-owned lifecycle rows remain:

- `effect:cold_exposure -> state:cold`
- `effect:heat_exposure -> state:overheated`
- `effect:dehydration_exposure -> state:dehydrated`
- `effect:fatigue_exposure -> state:fatigued`

Those rows are closed to the existing `actor_gameplay.survival_domain` owner,
the existing `gameplay:survival:{actor_ref}` stream, the existing project-scoped
outbox, append-derived receipt, and the existing replay reader.

No other weather-front source contract names all of the required fields for a
Survival row:

| Concern | Status |
| --- | --- |
| Existing owner | INF-1AC/INF-1AD approve the existing Survival owner only for `weather:frost -> effect:cold_exposure -> state:cold` and `weather:heat -> effect:heat_exposure -> state:overheated`; all other rows remain blocked |
| Canonical source event family | INF-1AC/INF-1AD approve only project-visible `gameplay.ecology.weather_front.propagated ->` the existing Survival cold/overheated state/obligation events |
| Region-to-profile target mapping | INF-4AC now supplies the bounded existing-activation-owner, project-scoped committed Ecology `region_ref -> profile_ref` projection; dossier/client/household substitutes remain invalid |
| Stream pattern | INF-1AC/INF-1AD approve only existing `gameplay:survival:{profile_ref}` |
| Projection/privacy | INF-1AC/INF-1AD approve only existing project-scoped Survival projection/outbox |
| Receipt/replay reader | INF-1AC/INF-1AD use only the existing Survival append result and projector; other edges remain blocked |

## Required blocked behavior

1. The finite lifecycle contract matrix stays limited to the four existing
   Survival exposure rows.
2. A weather-front-shaped provenance input may not reuse the semantic Survival
   bridge by smuggling Ecology revisions into the semantic snapshot.
3. A weather-front-shaped provenance input may not reuse the existing Survival
   action route for `state_dispel` or fixed `state_transform_recovery`.
4. All such attempts remain zero-write before `GameplayEventStore.append_batch()`.
5. A future row must consume the INF-4AC projection with its pinned source
   revision and project scope; it may not infer a target from a profile dossier,
   Godot/client position, or household residence text.

## Evidence shape

The package is complete only when focused proof shows:

- the Survival lifecycle matrix still enumerates only the four existing rows;
- a weather-front-shaped apply attempt rejects before append; and
- a weather-front-shaped Survival action attempt rejects before append.

## Non-goals

- Adding a new Survival owner row.
- Adding any weather-front consumer edge beyond the two exact approved rows.
- Adding a new scheduler, store, bus, clock, or generic router.
- Reinterpreting Ecology proposal/evidence as direct Survival write authority.
