# Stateful Patch Data Migration Plan

Status: `first-typed-resource-slice-implemented-and-mirror-projected; broader-migration-planned`

## Purpose

Deliver data-transform stateful Patch upgrade/rollback only after the runtime can
identify historical definitions, invoke an explicit trusted domain migrator, and
replay the resulting new facts without changing historical events.

This plan follows the migration constraints in:

- `2026-07-23-persistence-replay-migration-and-hot-reload-design.md`
- `2026-07-23-state-group-registry-and-runtime-facade-design.md`
- `2026-07-23-gameplay-patch-rule-ir-and-capabilities-design.md`

## Current Baseline

Implemented: immutable Patch manifests, event-ledger active-set lifecycle,
explicit-actor state-group enable/disable, and compatible same-definition
`identity_rebind` upgrade/rollback.

`identity_rebind` preserves an existing state-group record and changes only its
source Patch-set revision. It is not a data migration. The present
`StateGroupRegistry` now retains definitions by group ID plus exact definition
version and refuses implicit selection where multiple versions exist. The
generic state-group layer still has no owned domain payload or generic
domain-write API.

The first data-transform slice is also implemented: registered
`core.resources` definitions may upgrade through the trusted,
manifest-declared `resource.bounds.clamp_maximum.v1` migrator. It is a typed
maximum-reduction policy only: reservations reject, loss is explicit in an
append-only resource event, and the domain event/state-group version transition
/Patch cutover commit together. It intentionally supports only upgrade; its
loss policy means rollback is typed-rejected before write.

The same committed resource-migration batch carries an explicit
`godot_mirror` refresh hint. A no-outbox transaction is observed only after
commit by the existing dispatcher; an explicit backend mirror source rebuilds
the typed resource projection and the presentation consumer receives only its
filtered snapshot. Migration descriptors, authority payloads, and direct
world-state writes never cross into Godot.

## Non-Negotiable Constraints

- Upcasters change reader interpretation only; data migration appends new
  authority events and never rewrites historical event bytes.
- Godot, Rule IR, a Patch manifest, and a generic state-group façade cannot
  supply arbitrary migration code or write a domain stream.
- Each domain owns its projection data and migration adapter. The Patch
  lifecycle coordinates an already validated batch; it does not invent a
  cross-domain mutation API.
- Every migrated actor/domain batch pins old/new Patch set, registry, world
  config, definition, schema, and migrator code revisions.
- Upgrade requires shadow replay and compatibility evidence before cutover.
  Rollback requires an old reader for post-upgrade history or a forward fix.

## Required Design And Implementation Sequence

1. **Implemented:** replace the single-version state-group lookup with an immutable
   group-ID-plus-definition-version registry. Historical projectors must resolve
   the exact definition recorded by an event; active assembly must receive its
   explicit version selection rather than silently choosing a latest version.
2. **Partially implemented:** add a manifest-declared migration descriptor for a named trusted backend
   migrator: source/target group definition versions, input/output event-schema
   identities, code digest, required domain streams, migration digest, and
   declared compensation/rollback compatibility.
3. **Partially implemented:** create domain-owned pure migration planners. Each planner reads only pinned
   authoritative projections and emits typed event specifications for its own
   streams. It must have no Godot, network, filesystem, service-locator, or
   generic Patch-store write interface.
4. **Partially implemented:** add a Patch lifecycle coordinator that validates every per-actor domain plan
   before one cross-stream `append_batch`. It must atomically append migration
   facts, source-revision transition, Patch lifecycle event, and active-set
   cutover; any rejected plan produces zero events and no registry mutation.
5. **Partially implemented:** the resource slice runs pre-cutover shadow full
   and checkpoint-plus-tail comparison, and the Gameplay replay profile proves
   the migrated Phase 3 façade has the same checksum through full and
   checkpoint-plus-tail rebuild. Future domain migrations still need their own
   target-projector comparison policy and fixtures.
6. **Partially implemented:** add explicit rollback compatibility gates. Do not permit rollback merely
   because an older manifest exists; require reader/upcaster continuity for all
   retained post-upgrade events and an inverse migration or declared forward
   recovery path.

## First Candidate Slice

The first data-transform slice targets the existing resource domain with a typed
projection and an owned authority service. It does not use an opaque `dict`
payload or generic `state_group.data_migrated` event. The domain-specific
resource spec amendment now names its invariant, loss policy, migrator code
digest, old/new event schemas, and forward-fix-only rollback strategy. The
remaining work is the broader cross-domain/general case.

## Evidence Gate

The implementation phase is not complete until all of the following are
proved by focused harness evidence:

- historical old-definition replay and target-definition replay are deterministic;
- a bad/missing migrator, schema, digest, actor context, stream revision, or
  compensation plan leaves every stream and Patch registry unchanged;
- successful migration is one atomic multi-stream batch and is idempotent;
- shadow replay and checkpoint-plus-tail meet the declared comparison policy;
- rollback is either proved compatible or explicitly rejected with a typed
  diagnostic; and
- Godot receives only a post-commit presentation projection, never migration
  instructions or authority payloads.

For the first resource slice, the focused `gameplay-patch-runtime` profile
emits separate evidence rows for lifecycle control, migration replay and
zero-write rejection, post-commit filtered Godot projection, and Rule IR
capability boundaries. Those rows do not claim the broader deferred migration
program.

## Explicitly Deferred

- arbitrary third-party migration code;
- generic state-group projection-data mutation;
- implicit active-actor discovery;
- automatic compensation inference;
- multi-Patch replacement; and
- production durable handler-artifact distribution.
