# INF-1W Closed State Lifecycle Adapter Matrix

Status: `implemented and verified bounded matrix closure; not INF-1 completion`

Date: `2026-08-15`

## Problem

`EffectLifecycleEvaluator` has generic pure semantics for stack policy,
expiry, dispel and transform. The current authority surface, however, reaches
those semantics through owner-specific branches. The existing finite contract
reader proves only row admission; it is not an executable lifecycle matrix.

INF-1W will close that gap without adding an owner or a generic writer. It
will make a closed, immutable adapter matrix select only an existing owner
adapter after the semantic proposal has passed the corresponding contract row.

## Fixed Owner Boundary

| owner adapter | existing canonical stream | admitted lifecycle operations | write boundary |
| --- | --- | --- | --- |
| `SurvivalAuthority` | `gameplay:survival:{actor_ref}` | current matrix admission: apply for cold/overheated/dehydrated/fatigued; other existing actions remain owner-local pending per-operation migration | existing Survival command/fragment -> one append |
| `ConstructionProductionAuthority` | `gameplay:construction_production:{facility_ref}` | maintenance apply, scheduled expiry, maintenance dispel/cancel | existing Construction command/fragment -> one append |
| `EcologyHazardAuthority` | `gameplay:ecology:{region_ref}` | no semantic adapter admitted | existing owner-local frost path only |
| `EconomyAuthority` | `gameplay:economy:wage:{worker_ref}` | no semantic adapter admitted | existing owner-local wage path only |

The executable matrix is code-owned and immutable and initially contains only
the existing Survival and Construction adapters. Its first implemented
operation is `apply`; expiry/dispel/transform/cancel stay on their existing
owner-local entrypoints until separately migrated. A proposal cannot supply an adapter,
owner, stream, event type, visibility, revision vector or receipt. An operator
not listed for the selected existing owner row returns a structured rejection
before `GameplayEventStore.append_batch()`.

## Dispatch Protocol

```text
semantic proposal / MetaRule owner-authorized fragment
  -> immutable StateOwnerContract + LifecycleOwnerContract lookup
  -> fixed existing-owner lifecycle adapter validates its own source/revision
  -> owner GameplayCommandEnvelope / SettlementPlan
  -> GameplayEventStore.append_batch()
  -> owner outbox, scoped projection and append-derived receipt
```

The shared matrix performs admission and pure decision selection only. It may
not call an owner callback, append a batch, construct arbitrary events, or
turn a selector result into world truth.

## Selector Boundary

The package extends the closed selector vocabulary only with typed predicates
over already pinned semantic snapshot fields: tag inclusion, property equality,
numeric range and registered state presence. `all(...)`, `any(...)` and
`not(...)` compose those predicates with bounded depth. Free expressions,
scripts, reflection, arbitrary attribute traversal and proposal-supplied
function references remain invalid input.

## Acceptance Conditions

1. Formal matrix names each adapter, stream pattern, fixed operations,
   scope, revision/idempotency rule and replay/receipt reader.
2. Focused RED tests independently prove every admitted operation, unsupported
   operation zero write, forged adapter/stream/event rejection, duplicate,
   revision conflict, privacy and full/checkpoint-tail replay.
3. Each adapter submits only through its existing authority append path.
4. Dedicated Harness selectors correspond one-to-one with the asserted
   capabilities; no aggregate pytest result stands in for several claims.

## Explicit Blockers

`RegisteredStateOwnerRoute` currently names only the Survival and Construction
semantic adapters. Ecology frost has no `SemanticSettlementAuthority` proposal
adapter: its existing `apply_crop_state()` contract requires a pinned
`hazard_ref -> crop_ref -> region_ref` source relation and the Ecology
principal/source, neither of which exists on `SemanticEffectCommand`. Economy
wage has no state proposal contract. Neither may be
included in execution, tests or completion claims until a separate formal
owner/stream/event/projection/receipt/replay contract exists.

## Non-goals

- Caller-open owner, state, effect, event-family or adapter registration.
- New state truth, generic state events, second runtime/store/bus/clock or
  scheduler.
- Construction repair/transform/payment semantics, Ecology semantic dispatch,
  generic Economy effects, SOC/GAME/P6/P7.
