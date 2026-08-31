# Gameplay Patch Rule IR And Capabilities Plan

Status: `minimum-governed-runtime-and-lifecycle-slice-implemented; broader-lifecycle-planned`

## Dependencies

Contracts/events, state groups, and at least the resource/body minimal slice.

## 2026-08-02 Implementation Status

Implemented and backend-test verified: immutable digest-checked trusted
manifests, batch-atomic candidate registration, patch dependency/cycle/schema
collision rejection, explicit active-set composition, deterministic
proposal-only trigger evaluation, bounded conditions/proposals/capability
calls, deterministic side-effect-free capability registration, and atomic JSON
snapshot recovery of candidates plus recomputed active-set identity. The runtime
has no Godot write interface; Rule evaluation remains proposal-only and failure
there occurs before any settlement.

The initial control-plane authority slice is also implemented and backend-test
verified: candidate installation appends an authority-only audit event; complete
active-set enable/disable appends lifecycle events in one Gameplay event batch
before changing the in-memory registry. Commands require a matching authority
principal, canonical command digest, and pinned registry/active-set revisions.
The first patch-owned state-group lifecycle slice is also implemented:
an explicit trusted actor-context set, pinned to the target patch-set revision,
is planned without writes and then committed with the Patch active-set cutover
in one batch. Enable materializes groups; disable is pinned to their current
source revision and rejects shared ownership. Both reject missing/duplicate/
mismatched actor contexts or policy expansion before any write. Disable changes
only lifecycle state; domain-effect revocation and compensation remain planned.

Rule-only same-patch revision upgrade/rollback is also implemented. A narrow
stateful same-patch identity-rebind path now also supports one-for-one valid
version-direction cutover when both manifests keep the same state groups and
the target declares a digest-pinned unchanged-definition migration for every
group. It records per-actor `gameplay.state_group.rebound`, the lifecycle event,
and active-set cutover atomically.

One deliberately narrow data-transform upgrade is now implemented and
backend-test verified: `core.resources` may move from one registered resource
definition version to a lower maximum through the manifest-declared
`resource_bounds_clamp` migrator. The trusted resource planner rebuilds the
pinned authority projection, rejects reservations, applies the explicit clamp
and loss amount in `gameplay.resource.bounds_migrated`, then the coordinator
commits that domain fact, `gameplay.state_group.migrated`, Patch upgrade and
active-set cutover in one batch. Historical state-group/resource definitions
are version-addressable; replay resolves the version named by the event. This
is forward-fix-only: rollback of this potentially lossy migration rejects
before append. Multi-patch replacement, other data transforms, compensation,
and generic state-group writes remain rejected.

The corresponding lifecycle replay fixture is implemented: a read-only
projector rebuilds installed candidate identities and the active set from
committed control-plane events, rejecting digest/order/revision mismatches.

The first proposal-to-settlement mapping is also implemented: an evaluated
`resource.consume` proposal is revalidated against the actor's current resource
projection and commits its resource adjustment plus
`gameplay.patch.rule_settled` in one atomic batch. The adapter rejects every
other effect type before append; it does not make Rule IR a generic domain-write
surface.

Not yet implemented: database-backed registry, complete typed Rule IR,
capability handler-artifact persistence and code-digest loading, general
authority settlement conversion beyond `resource.consume`, state-group
domain-effect revocation, grant/modifier lifecycle effects, data-transform
stateful migration beyond the bounded resource-bounds clamp, cross-version
reader/rollback compatibility, privacy views, or live delivery.

## 2026-08-27 Shared Persistence Integrity Closure

The common event-store recovery seam is hardened and verified. Snapshot loading
rejects mismatches between the event ledger and embedded transaction batches,
append results, idempotency indexes, or outbox references before the restored
store becomes usable. Focused RED-to-green coverage is in
`backend/tests/test_gameplay_event_store_persistence.py` and remains within
the existing event-store regression band. Batch ordering and contiguous global
event sequence checks also preserve deterministic full/checkpoint-tail replay.
This does not broaden patch capabilities or add a persistence surface.

## Work

1. Extend the implemented immutable manifest/runtime core with group
   definitions, complete schema/event registration, migrations, bindings, and
   verification metadata.
2. Extend the implemented deterministic trigger/equality-condition core with
   the full typed Rule IR, reservations, modifier policy, and settlement-facing
   proposal validation beyond the implemented `resource.consume` slice.
3. Persist trusted handler artifacts and code identities; retain the
   implemented proposal-only/no-store/no-Godot boundary and JSON candidate
   snapshot recovery.
4. Extend the implemented in-memory lifecycle slice with durable control-plane
   records, state-group domain-effect revocation, other patch-owned lifecycle effects,
   additional typed data-transform migrations and replay fixtures.

## Exit Criteria

Invalid, circular, unauthorized, timed-out, or malformed patch behavior cannot
partially activate or mutate authoritative domain state.
