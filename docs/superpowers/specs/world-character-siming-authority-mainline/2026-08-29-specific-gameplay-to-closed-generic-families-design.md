# Specific Gameplay To Closed Generic Families Design

Status: `execution-active; full closed-family refactoring program`

Date: `2026-08-29`

## Goal

Convert all currently identified repeated, content-specific gameplay rows into
a complete set of closed, owner-bound gameplay families. This is a full
refactoring program, not a recipe-only feature. Each family reuses the existing
event, authority, admission and replay spine while packages provide only
explicitly typed content slots. Existing bakery, mill, flour, weather, project
and social rows remain immutable regression baselines.

The program is complete only when every family listed below has a strict
content schema, immutable owner descriptor, deterministic binding and
selection, owner-bound execution adapter (or an evidence-backed blocker),
focused tests, independent Harness, and migration/replay evidence.

This design does not claim that the current narrow rows are already generic.
It defines the work required to make selected families reusable without
introducing a generic writer, router, runtime registry, second store, or new
truth owner.

## Why Closed Families

The current system has a strong generic *execution substrate* but finite
business contracts. `GameplayEventStore`, `SettlementPlan`, replay,
immutable package admission, and the governed catalog can safely execute a
new row only when the owner, source evidence, event vector, privacy, revision,
receipt, idempotency and lifecycle are already fixed.

An unbounded generic operation would have to let content or callers choose one
or more of those coordinates. That would make package data an authority,
permit arbitrary facts, weaken replay determinism, and reintroduce the exact
owner-conflict and privacy failures the INF contracts prevent. A closed family
therefore supplies a finite vocabulary and fixed descriptor boundary, while
allowing unbounded content instances *inside* that vocabulary. New vocabulary,
new owners, or new cross-domain recipes remain separate admissions.

## Current Specificity Inventory

| Existing slice | Content currently fixed in code or row | Proposed closed family |
| --- | --- | --- |
| Bakery production | bakery, flour, bread, fixed recipe and duration | `recipe_production@1` |
| Bakery, oven and mill reinforcement | concrete source and target facility kinds | `facility_identity_upgrade@1` |
| Mill decommission | mill_reinforced, active -> decommissioned | `facility_lifecycle_transition@1` |
| Mill flour certification | one recipe, one item, quantity 10 | `production_output_certification@1` |
| Flour custody | provider, container and item are fixed | `production_output_custody@1` |
| Flour purchase and public services | fixed parties, accounts, currency and policy | `declared_exchange@1` and `fixed_service_exchange@1` |
| Project budget | one public-project commitment lifecycle | `bounded_project_budget@1` |
| Grain harvest and receipt | wheat/grain and fixed holder/container mapping | `harvest_to_custody@1` |
| Weather consumers | finite weather-to-owner state mappings | `owner_bound_environment_consumer@1` |
| Organization acceptance and social acknowledgment | one source fact and one owner-local marker | `domain_acceptance_marker@1` and `private_follow_on@1` |

The family names above are design vocabulary only. They are not catalog rows,
manifest values, runtime identifiers, or implementation authorization.

## Layered Architecture

### 1. Content Plane

An immutable package supplies only descriptor-approved slots:

```text
facility_definition_ref
recipe_definition_ref
input_item_definition_refs
output_item_definition_refs
quantity_and_unit
duration_policy_ref
eligibility_reference
policy_revision_ref
```

Every definition has a schema, namespace, revision and digest. Typed content
does not contain owner, stream, event, receipt, privacy, compensation,
account, or arbitrary code fields. Empty arrays are allowed only where the
family contract explicitly says the array is semantically empty.

### 2. Descriptor Plane

The immutable `OwnerOperationDescriptor` fixes:

- existing owner and operation family;
- accepted intent schema;
- source event/projection and exact revision fence;
- target stream and event family/vector;
- privacy scope;
- authority-derived idempotency key;
- append-derived receipt reader;
- full and checkpoint-tail replay readers;
- terminal, reversal and compensation semantics;
- allowed predicate and recipe families.

Package declarations may fill only named, typed, bounded content slots. The
caller cannot select any descriptor-owned coordinate.

### 3. Evidence Plane

Predicates read only owner-derived committed facts. The minimum vocabulary is
`exact_event_kind_at_revision`, `projection_subject_matches`,
`projection_value_equals`, `source_revision_is_current`,
`privacy_scope_allows`, `idempotency_key_is_new`, and
`package_slot_satisfies_bound`. Unknown, private, stale, malformed or
ambiguous evidence is a typed failure before append.

### 4. Execution Plane

The existing owner builds the fixed fragment and submits it through:

```text
GameplayCommandEnvelope
  -> SettlementPlan
  -> GameplayEventStore.append_batch()
  -> outbox / scoped projection / replay
```

The family layer never appends, creates receipts, discovers owners, or merges
arbitrary event vectors.

## Family Contracts

### A. `recipe_production@1`

One committed facility and one owner-authorized recipe produce one completed
run. Construction owns facility and run truth. Inventory may consume inputs or
receive output only through a separate, explicitly admitted owner recipe.

Package slots: facility definition, recipe definition, input/output item
definitions, quantity, unit, duration and qualification references.

Fixed boundaries: Construction stream for the facility, owner event family for
run start/finish, project privacy, source and stream-head pins, owner-derived
run idempotency, append-derived receipt, full/tail replay, and row-specific
terminal semantics.

Non-goals: arbitrary recipes, caller-selected containers, implicit inventory
transfers, payment, wages, market pricing, or generic production output.

Example content instance (not admitted by this design):

```text
site = bakery
recipe = flour -> bread
```

### B. `facility_identity_upgrade@1`

One existing Construction facility identity changes to one package-declared
target identity. Construction alone owns the facility revision and kind.

Package slots: source and target definition references, typed definitions,
policy reference and owner-derived eligibility references.

Fixed boundaries: facility stream, `facility_transformed@1` or a separately
fixed event family, project privacy, source/current revision fence, one-shot
idempotency and terminal/no-compensation unless a descriptor explicitly
admits correction.

`bakery -> bakery_reinforced`, `oven -> kiln`, and `mill -> mill_reinforced`
remain disjoint historical partitions. They are not silently migrated into
this family.

### C. `production_output_certification@1` and `production_output_custody@1`

Certification remains a Construction fact derived from a completed run.
Custody remains an Inventory fact derived from the certified output. The two
owners keep separate receipts and replay readers. A package may declare a
recipe/output identity only when the corresponding Inventory item definition,
holder/container rule and privacy scope are already admitted.

### D. `declared_exchange@1` and `fixed_service_exchange@1`

Economy owns debit, credit and exchange events; Contract, Inventory or
Ownership provide source evidence only. A package may declare a typed service
or item exchange, but the descriptor fixes party derivation, accounts,
currency, price policy, lifecycle and compensation. This family cannot become
an arbitrary payment or transfer API.

### E. `harvest_to_custody@1` and `owner_bound_environment_consumer@1`

Ecology owns harvest/weather facts; Inventory or Survival owns the admitted
consumer fact. Each edge has a fixed source event, target owner, subject
binding, privacy, revision, idempotency, receipt and replay contract. A
process event cannot substitute for an admitted weather-front source.

## Migration And Compatibility

1. Existing narrow rows remain readable and replayable forever under their
   original descriptor, package, event and reader pins.
2. No in-place rename of a row, event family, package revision or digest is
   allowed.
3. A family introduction is additive. An existing row may be represented by
   a new family only through an explicit migration contract that proves
   equivalent source pins, payload meaning, privacy, lifecycle and replay
   digest; otherwise it remains a historical row.
4. Existing callers continue using their existing row-specific methods. A new
   family entry point cannot reinterpret old commands or accept omitted slots.
5. Descriptor, predicate, recipe, package and active-set revisions are pinned
   in every admission artifact and event provenance record.
6. Unknown family revision, missing definition, changed digest, incompatible
   reader or stale source is zero-write. There is no compatibility fallback.

## Conflict And Selection Rules

The existing owner-operation conflict matrix is mandatory before family
admission. A candidate is rejected when it collides on fact, owner, event
meaning, privacy, receipt, replay, lifecycle or package pins. Selection is
exact-one over typed intent and immutable declarations; zero or multiple
matches are zero-write. Canonical sorting is for audit output only and never a
priority or load-order tie-breaker.

## Verification Boundary

Each family requires its own focused RED-to-green tests and independent
Harness. At minimum, evidence covers success, unknown content, missing or
private source, stale revision, duplicate and changed duplicate, binding
conflict, append receipt, privacy projection, full replay, checkpoint-tail
replay and terminal behavior. Cross-owner families additionally prove
separate owner receipts and rejection of arbitrary event vectors.

The existing bakery, mill, flour purchase, grain custody and weather rows are
regression fixtures for these tests, not permission to generalize them.

## Full Refactoring Scope

The complete target contains these family workstreams:

1. `recipe_production@1`: facility plus declared recipe -> Construction run;
2. `facility_identity_upgrade@1`: one fixed facility identity upgrade;
3. `facility_lifecycle_transition@1`: owner-defined lifecycle transition;
4. `production_output_certification@1`: completed run -> owner certification;
5. `production_output_custody@1`: certified/completed output -> Inventory custody;
6. `declared_exchange@1` and `fixed_service_exchange@1`: fixed item/service
   exchange with Economy/Contract owners;
7. `bounded_project_budget@1`: fixed project budget lifecycle;
8. `harvest_to_custody@1`: Ecology harvest -> Inventory custody;
9. `owner_bound_environment_consumer@1`: finite environment -> target owner;
10. `domain_acceptance_marker@1` and `private_follow_on@1`: owner-local
    acceptance and actor-private follow-on facts.

Existing exact rows are compatibility partitions and regression fixtures. They
are not silently renamed; migration requires explicit replay-compatible proof.

## Product Decision

Implementation starts with `recipe_production@1` because it captures the
highest-value repeated pattern, but the approved objective is the full family
set above. Production, facility/lifecycle, certification/custody,
exchange/project, ecology, and owner-local follow-on families all remain in
scope. They stay separate because their truth owners and lifecycle semantics
differ.

The custody follow-on is currently evidence-blocked, not implementation-ready:
the committed Construction completion event lacks output quantity, no approved
source-to-Inventory holder mapping exists, and Inventory does not guarantee one
eligible destination container. The family must remain zero-write until those
literal facts and pins are committed; it cannot infer them from facility owner,
fixtures, or the caller.

This sequencing gives content authors useful extension without pretending that
all future world facts share one operation. The framework is extensible by
adding content instances inside approved families, and by adding a separately
admitted family when the product requires a new semantic boundary.

## 2026-08-29 Task 3 Admission Result

The first family now has one immutable Construction descriptor and governed
catalog row. The descriptor fixes the owner, accepted intent schema, committed
facility source, facility stream/revision fence, run event vector, project
privacy, owner-derived idempotency, append-derived receipt, full and
checkpoint-tail readers, terminal/no-reversal/no-compensation semantics, and
the finite recipe package-slot vocabulary. Activation resolves each package
binding request to exactly one descriptor and validates the typed
`RecipeProductionContent` before changing the active set. Package content may
provide multiple distinct recipe bindings, but duplicate binding references,
unknown or ambiguous descriptors, mismatched predicates/effects, malformed
content, stale snapshots, or digest conflicts fail closed before mutation.

This is an admission and content contract only. The existing Construction
production adapter now consumes that binding for one fixed start-run path. It
derives the Construction stream and idempotency key, rereads committed
project-visible facility acquisition, delegates to the existing
`settle_start_run()` append path, and records package/declaration/descriptor
provenance in the run snapshot. Finish, Inventory custody, and all existing
narrow rows remain separate paths; August INF A-D remains `not complete`.

## 2026-08-29 Full-Refactoring Matrix Admission

The declarative closed-family matrix now covers all twelve required family
names with immutable content-model, owner, contract, descriptor, stream, event,
privacy, predicate, effect and package-slot pins. `recipe_production@1`,
`facility_identity_upgrade@1`, `facility_lifecycle_transition@1`,
`production_output_certification@1`, `declared_exchange@1`,
`fixed_service_exchange@1`, and `bounded_project_budget@1` now have bounded
execution adapters and focused narrow-row verification at this checkpoint.
Existing narrow Construction, Economy, Ecology, Contract, Organization and
Social rows are retained as compatibility evidence and are not silently
renamed or widened into generic writers. These adapters are not content-generic
completion evidence: they must each admit two distinct content instances with
family-specific source proof, digest, lifecycle and replay validation before
their status can become `generic_implemented`. `production_output_custody@1`
is explicitly blocked and has
no writer until committed quantity, source-to-holder mapping and unique
destination-container evidence are admitted. The independent family Harness
records this split and keeps August INF A-D `not complete`.

Family capabilities also pass through the existing registry activation gate:
their generated immutable descriptor is resolved exactly once, typed content
is validated before active-set mutation, and a family with an evidence-backed
blocker is rejected with a typed zero-write error. This remains admission
metadata and validation, not a runtime-writable family registry.

## 2026-08-30 Facility Lifecycle Generic Promotion

`facility_lifecycle_transition@1` is now generic over two separately committed
immutable content instances: `mill_reinforced` and `bakery_reinforced`, both
declaring the typed `active -> decommissioned` transition. Both packages bind
to the same read-only `ConstructionProductionAuthority.settle_facility_lifecycle_transition`
adapter, fixed Construction owner, facility stream, project privacy, terminal
`facility_decommissioned` event, append-derived receipt, and full/checkpoint-tail
replay reader.

The family descriptor uses the existing generic
`predicate:construction-facility-acquired@1` source predicate. The historical
v3 mill decommission row and INF-1AF bakery reinforcement row remain unchanged
compatibility partitions; this promotion does not create a generic transform,
reactivation, compensation, or caller-selected lifecycle target.

## Explicit Non-Goals

- no generic `facility_kind -> facility_kind` transform;
- no generic production writer or recipe interpreter;
- no caller-selected owner, stream, event, account, currency, privacy or
  receipt;
- no runtime-writable registry, router, coordinator or second runtime;
- no automatic migration of existing rows;
- no claim that August INF A-D is complete.
