# Generic Construction/Production Platform Implementation Plan

Status: `implemented and verified; August INF A-D remains not complete`

## Order

1. Implement and test typed content validation and canonical package binding.
2. Extend Plot/Blueprint/ConstructionJob with grid occupancy and deterministic
   construction lifecycle while preserving old events/readers.
3. Extend Facility lifecycle/maintenance projections with explicit policies.
4. Extend Recipe/ProductionRun with batch, quality, capacity, wear and failure
   evidence, using existing owner reservations.
5. Add concurrency and revision fences for owner-issued reservations and slots.
6. Add failure recovery and Construction-to-Inventory evidence handoff.
7. Add focused Harness profiles and full/checkpoint-tail replay assertions.
8. Add procedural Godot draft editor and read-only monitor after headless gates.

Current checkpoint: typed Blueprint, Facility, Recipe, Failure and Quality
content, deterministic grid occupancy, exact Blueprint descriptor activation,
package-bound Job provenance, reservation evidence validation with optional
source-event pins, append-level reservation revision pins, and output
certification provenance are implemented. The focused Construction/Production
suite and both dedicated Harness profiles are green. Package-bound placement
permit evidence persistence/replay, optional zoning evidence validation and
malformed-permit rejection are implemented; Blueprint component-tree occupancy
and certification-to-custody source provenance are now carried and validated
in Inventory full/checkpoint-tail replay. Zoning completeness, full
lifecycle policy coverage, cross-owner
reservation projection integration, complete output custody handoff, and
Godot headless and desktop smoke verification are now green. Generic lifecycle
active-run conflict remains enforced before append and covered by focused tests.
Facility content materialization now preserves the declared facility definition
identity for downstream recipe fences.

The independent `construction-job-runtime` Harness profile is green (`3
passed`), and the new plot-job event schemas are source-controlled and
idempotently registered (`2` schema registrations). Its events are plot-scoped
owner primitives and are not a replacement
for package-bound placement admission or the later facility materialization
contract.

The latest repository-wide regression is `4138 passed`; compileall and
`git diff --check` are green. The new mill package is a test-only immutable
content instance used to prove a third facility family member; it does not
modify or supersede any August frozen package.

The current focused Construction/Production band is `97 passed`; the latest
repository-wide regression after the Blueprint provenance, reservation,
output-policy, permit-evidence, lifecycle active-run, replay-integrity,
custody-lineage, reservation-lifecycle, unbound-evidence, failure-policy
revision, explicit failure-lifecycle, reservation-source mapping and Job
reservation replay, Job completion provenance and ConstructionJob terminal-
failure, pure-start lifecycle and projection-checkpoint gates are green; the
latest full backend baseline is `4138 passed`.

The first procedural authoring/view asset is implemented as an internal,
external-art-free Node2D scene with a read-only typed-draft exporter. Its asset
contract test passes (`1` test); the editor does not compute digests, activate
bindings or choose authority coordinates.
The asset now also mirrors backend facility/Job/run status dictionaries and a
read-only replay timeline while clearing speculative state on every sync or
rejection.
Godot 4.6.3 headless and desktop smoke scene verification is green through the
dedicated `procedural-construction-editor-runtime` Harness profile.

Output handoff now enforces committed quantity and optional quality policy
compatibility before Construction certification, and a third kiln output-
certification package is available for the three-facility genericity gate.

The three-facility certification gate is now exercised end-to-end: bakery,
mill and kiln immutable packages resolve through the same
`production_output_certification@1` owner-bound adapter, and each passes full
and checkpoint-tail replay. The generic-content Harness runs both the content
and certification suites.

The output handoff gate now also covers kiln custody through the existing
Inventory adapter and immutable destination mapping; bakery, mill and kiln each
have full/checkpoint-tail custody evidence.

Latest output-certification/custody focused verification is `15 passed`; the
latest full backend regression is `4386 passed`.

The certification family focused suite is `14 passed`; the latest full backend
regression is `4388 passed`.

## Gates

Every step must have RED-to-green tests, no mutation before validation,
append-derived receipts, owner-derived idempotency, privacy/revision fences,
and a rollback point. Old narrow rows must continue to replay unchanged.

## Acceptance

Three immutable test packages cover bakery, mill and kiln; at least three
recipes and two component combinations pass success, conflict, failure,
tamper, duplicate, privacy and replay checks. Completion requires all four
gates and a desktop Godot run; unavailable external art is not a blocker.
The failure-policy resolver, owner-issued reservation requirement validation,
facility condition/slot-capacity checks, and Construction output quantity/
quality evidence are now covered by RED-to-green tests. Construction still
does not write Inventory custody directly.

The latest Plot/Blueprint/Job and production-evidence focused band is green
(`71 passed` across the current failure/output and Construction/Production
focused suite). Both
dedicated Harness profiles remain green. The procedural editor asset check is
also green; Godot 4.6.3 headless and desktop smoke scene startup is green.

Economy reservation lifecycle integration now rejects a Construction start
whose owner-issued `gameplay.economy.budget_reserved` source has already been
consumed by `gameplay.economy.public_project_budget_consumed`; replay applies
the same fail-closed rule. This closes the active-hold gate without adding a
scheduler, coordinator, or new owner. Focused Construction/Production
verification after this gate is `84 passed`.

Failure replay integrity now also requires `run_failed@1` to retain project
privacy, the run's facility/recipe stream identity, and a source revision
vector whose facility and pre-append stream-head pins match the committed run.
Tampered identity, privacy, or revision vectors fail closed before projection
mutation.

Failure events now additionally retain the started ProductionRun's reservation
refs/evidence and replay verifies exact lineage equality. This closes the
failure-side owner reservation handoff without cancelling or re-owning another
owner's reservation.

Maintenance-obligation events now carry facility/project, facility-revision,
maintenance-policy and pre-append stream-head pins whenever the owner can
resolve the facility; replay validates the additive pins while preserving old
no-pin readers.

Maintenance obligation idempotency now compares run, obligation, causation and
correlation identity; changed duplicate keys fail closed without a second event.

Maintenance replay now validates a non-empty obligation reference and returns
the stable domain conflict code for malformed payloads.

Latest focused Construction/Production verification is `81 passed`; latest
full backend regression is `4390 passed`.

The maintenance obligation event schema is source-controlled and registered
through the existing `EventSchemaRegistry`.

Latest focused Construction/Production plus procedural verification is
`99 passed`; latest full backend regression is `4384 passed`.

Reservation requirements now use exact-set admission: undeclared refs or
evidence keys are rejected before append, keeping package-declared owner
reservation boundaries deterministic.

ProductionRun `run_started` replay now applies the same canonical reservation
ordering and exact evidence-key checks, preserving append/replay equivalence.

ConstructionJob replay now rejects malformed or non-canonical occupied cells
without filtering, preserving deterministic placement provenance.

ProductionRun start replay now validates project privacy and exact facility
stream/source pins when a materialized Facility exists; legacy source-less
run-start events remain compatible.

ConstructionJob start replay now validates project privacy and canonical plot
stream identity before accepting occupancy state.

ConstructionJob completion/failure replay now enforces the same plot-stream and
project-privacy source fence.
Existing identity-conflict classification remains reserved for plot/blueprint
payload mismatches.

The Job terminal source gate is covered by focused replay tests and the
construction-production Harness; no new authority or event family is added.

ProductionRun finish replay now enforces project privacy, exact facility stream
and facility/project identity pins.

ProductionRun finish replay also enforces positive-integer output quantity and
`[0,1]` output quality bounds.

Facility acquisition replay now enforces project privacy, canonical facility
stream and non-empty facility/plot identity while preserving legacy event shape.

Facility transform replay now enforces project privacy, canonical facility
stream and project binding before applying a transition.

Declared transform acquisition pins are now resolved against the committed
acquisition event during replay; missing or mismatched sources fail closed.
Checkpoint-tail replay uses the persisted acquisition identity only when the
source event is outside the tail, preserving full-replay strictness.

Facility repair replay now enforces project privacy, canonical facility stream
and project binding before applying condition/revision changes.

Repair replay validates condition bounds and strict facility revision
increment, rejecting malformed or stale payloads before mutation.

Maintenance-state application replay now enforces project privacy, canonical
facility stream and project binding for materialized facilities.

Malformed maintenance-state refs/counts/magnitudes/revisions now fail closed
with a stable domain error before projection mutation.

Facility decommission replay now enforces project privacy, canonical facility
stream and project binding before applying terminal lifecycle state.

Decommission replay resolves acquisition provenance for all rows and requires
reinforcement provenance only for the exact v3 mill-decommission content row,
preserving generic lifecycle compatibility.

Failure admission now enforces `failed_tick >= started_tick`; pre-start failure
attempts fail closed before any event is appended.

Failure replay applies the same `failed_tick >= started_tick` chronology fence.

The owner-bound `production_output_certified@1` event schema is now explicitly
registered in the existing EventSchemaRegistry.

The Inventory-owned `production_output_received@1` handoff event is now
explicitly registered in the same registry, completing the event-schema
evidence for both sides of this handoff.

Core Construction facility/run lifecycle events now have explicit,
idempotent registrations in the existing registry as well.

An aggregate `register_construction_production_event_schemas()` helper now
installs the complete opt-in Construction/Production schema bundle
idempotently, including the Inventory custody handoff event.

The bundle now also includes facility repair and maintenance-state event
variants used by the existing lifecycle owner paths.

Full repository verification on 2026-09-02 reached `4383 passed` after the
catalog snapshot and explicit failure-policy fixture were reconciled. Godot
runtime remains unavailable because no Godot executable is installed; the
generic platform therefore remains staged, not complete.

Current focused Construction/Production plus procedural asset verification is
`129 passed`; the latest full backend baseline is `4419 passed`. The
procedural editor executable gate is still unavailable because no Godot binary
is installed in this environment.
