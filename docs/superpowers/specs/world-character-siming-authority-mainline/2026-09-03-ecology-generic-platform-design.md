# General Ecology Platform Design

Status: `implemented-and-verified`

## Architecture

Ecology is the canonical owner of regions, fixed local cells, environmental
state, resources, crops, wild species/community state, food-web edges, hazards
and regional period-close projections. Character/Population owns human
population facts; Survival, Construction/Production, Inventory, Economy,
Organization and Government own their target facts.

The spatial model is a region graph plus deterministic local grid. The temporal
model is an explicit `region + period` close, optionally requested by the
existing `WorldModeProfile` cadence. No Ecology scheduler, second clock,
router, coordinator, registry or generic writer is introduced.

## Content Contract

Ecology packages reuse `GameplayPatchManifest v3` / `platform_schema_version
2.0`. Strict frozen typed content covers Region, Cell, EnvironmentPolicy,
Resource, Crop, Species, FoodWebEdge, Hazard, RecoveryPolicy,
ConsumerEdgeDefinition and PopulationSignalDefinition. References include
namespace and revision; arrays are author-ordered and are never silently
sorted. Numeric values use integers, basis points or fixed-point values.

The adapter derives declaration/content digests and compares caller claims;
missing, malformed, conflicting or mismatched claims zero-write. Authority
coordinates, arbitrary code, scripts, caller proof and arbitrary event vectors
are forbidden in content.

## Deterministic Evolution

Each close reads one immutable input snapshot and evaluates in this order:

```text
region topology -> cells/soil -> temperature/moisture/contamination
-> resource regeneration/depletion -> crop growth/health
-> species biomass/carrying capacity -> food-web edges
-> hazard trigger/decay/recovery -> period-close projection
```

Only one close for a region/period is admitted. All source, policy, package,
descriptor, active-set and revision pins are persisted. Duplicate exact closes
replay the prior result; changed duplicates, stale/private/missing evidence,
policy mismatch, graph cycle, budget overflow or partial input fail closed.

## Hazards And Consumers

The initial typed hazard vocabulary is `frost`, `drought`, `rain`, `flood`,
`fire`, `pollution` and `disease`. Each has explicit trigger, severity,
duration, decay and recovery policy. Recovery never deletes history or implies
compensation.

Ecology emits source admissions/proposals only. Each Survival,
Construction/Production, Inventory, Economy, Organization and Government edge
has an immutable descriptor, exact target event/stream/privacy, predicate,
precompiled recipe and owner fragment. The target owner revalidates Ecology
source pins and writes its own fact. Population signals are public observations
only and cannot create accounts, inventory, payments or human population facts.

## Compatibility And Evidence

Existing frost/drought/rain/weather-front rows remain read-only compatibility
baselines. New content is additive; old digests and readers are not recomputed.
Every subsystem requires RED-to-green focused tests, an independent Harness,
privacy/revision/idempotency/receipt checks, tamper rejection and full plus
checkpoint-tail replay before its rollout gate opens. Completion does not alter
August INF A-D, which remains `not complete`.
