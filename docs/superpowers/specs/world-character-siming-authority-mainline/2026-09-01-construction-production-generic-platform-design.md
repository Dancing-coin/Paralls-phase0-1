# Generic Construction/Production Platform Design

Status: `implemented and verified; August INF A-D remains not complete`

This design extends the existing bounded Construction/Production slice into an
owner-bound, content-generic platform. `ConstructionProductionAuthority`
remains the sole owner of plots, facilities, construction jobs, production
runs, quality evidence and facility lifecycle facts. Inventory, Skill,
Organization, Economy and Government retain their own facts and write paths.

## Contract Boundary

Content is carried by existing `GameplayPatchManifest` v2 typed definitions.
Authoring produces Canonical JSON draft input; one adapter derives normalized
bytes and declaration/content digests before immutable candidate/active
admission. No new manifest schema, owner, router, writer, coordinator,
settlement authority, runtime, store, bus, clock or scheduler is introduced.

Existing narrow package revisions, descriptors, event payloads and readers are
read-only compatibility partitions. New content uses a new immutable package
revision. A running job/run keeps the package, content, declaration,
descriptor, policy and source revision pins captured at start.

## State And Data

The compatibility models remain `Plot`, `Blueprint`, `Facility`,
`ConstructionJob`, `Recipe` and `ProductionRun`. Facility main state remains
`active | decommissioned`; construction and maintenance states remain Job and
maintenance projections. Typed content adds component trees, grid footprints,
discrete orientations, capabilities, reservation requirements, batch size,
quality/capacity/wear policy and explicit failure policy.

Grid footprint and orientation are authoritative. Local visual offsets and
procedural mesh details never affect occupancy, digest, conflict or replay.
Each run is one owner fact. `batch_size` is package-declared; multi-run
combined receipts and fanout are not supported.

## Data Flow

```text
draft -> canonical export -> review artifact -> explicit freeze
      -> immutable candidate -> exact-one active binding
      -> owner-bound intent -> GameplayCommandEnvelope
      -> SettlementPlan -> GameplayEventStore.append_batch()
      -> owner projection + full/checkpoint-tail replay
```

Construction writes completion, quantity, quality and provenance evidence.
Inventory independently creates custody from committed evidence. Failure is
explicitly `release`, `loss`, `rework` or `terminal`; missing policy is
zero-write. Reservation refs are issued by existing owners and are stored with
revision pins, not re-owned by Construction.

## Verification And Rollout

The staged gates are: (1) content/schema/admission, (2) Construction owner
runtime, (3) cross-owner reservation and Inventory handoff, and (4)
procedural Godot editor/view. Each gate has focused tests, a Harness profile,
replay/privacy evidence and a rollback condition. Three immutable test
packages (bakery, mill, kiln), three recipes and two component combinations
prove content genericity. Godot uses built-in PrimitiveMesh and state overlays;
backend mirror remains authoritative.

The first implementation checkpoint provides strict typed-content loading from
immutable package definitions, deterministic grid occupancy, and explicit
recipe policy pins retained through ProductionRun replay snapshots as pure
headless behavior. It does not yet claim Construction job events, generalized
production finish, cross-owner handoff, or Godot editor delivery.

The first Plot/Blueprint/Job runtime slice now emits plot-scoped
`construction_job_started@1` and terminal `construction_job_completed@1`
events with deterministic occupancy, owner-derived idempotency and replay
equivalence. It is intentionally a compatibility owner primitive; package-
bound placement admission, permit/zoning evidence and facility materialization
remain later gates.

The procedural view assets are now present as an external-art-free Node2D
editor scene/script. Static checks plus Godot 4.6.3 headless and desktop smoke
startup confirm it only previews grid occupancy, applies backend projections and
clears rejected speculative state.

The recipe content contract now distinguishes legacy `schema:recipe@1` from
`schema:construction-recipe@1`: only the latter requires explicit batch,
quality, wear and failure policy pins. Existing legacy content remains byte-
compatible and read-only.

The approved platform scope is implemented and verified through backend replay,
three immutable packages, and the procedural editor runtime probe. August INF
narrow rows remain `implemented narrow vertical` where independently verified;
this platform work does not mark August INF A-D complete.
