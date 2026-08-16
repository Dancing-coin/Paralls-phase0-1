# INF-2Q Owner-Only Obligation Commit Spine

Status: `implemented and verified; this is a bounded ownership repair, not August INF-2 closure`

Date: `2026-08-15`

## Scope

INF-2Q closes the remaining ownership defect in the fixed obligation rows. The
`ObligationSettlementCoordinator` remains a read-only validator/planner and
replay/receipt reader. It may build a validated `AtomicEventBatch`, but it may
not call `GameplayEventStore.append_batch()` or otherwise commit world truth.

The existing authorities retain commit ownership:

| lifecycle family | commit owner | canonical stream/event family | receipt boundary |
| --- | --- | --- | --- |
| construction due/maintenance | `ConstructionProductionAuthority` | existing construction facility stream | owner append result |
| Survival state expiry | `SurvivalAuthority` | existing survival actor stream | owner append result |
| Ecology frost crop expiry | `EcologyHazardAuthority` | existing ecology region stream | owner append result |
| Economy wage lifecycle | `EconomyAuthority` | existing wage stream | owner append result |
| Economy scheduled transfer | `EconomyAuthorityService` | existing economy ledger stream | owner append result |

The coordinator returns a validated `ObligationSettlementPlan` only. It has no
callback parameter and no execution API that can accept a raw store append
function. The caller must hand `owner_commit_batch` to the already selected
authority's `commit_obligation_batch()` method; that owner invokes the one
canonical `GameplayEventStore.append_batch()` path. The coordinator never
selects an owner, stream, event family, receipt store, scheduler, or clock.

## Invariants

1. Validation, idempotency digest construction, source/revision/privacy checks,
   bounded retry/cancel/expire/compensation and lifecycle replay remain
   unchanged.
2. Every successful write has one existing owner, one owner-built plan, one
   event-store append, append-derived outbox/projection and append-derived
   receipt.
3. Direct coordinator calls, callback-shaped arguments, unknown registrations,
   forged fragments and stale revisions produce zero writes.
4. Full replay and checkpoint-tail replay are equivalent for each migrated
   owner row; authority-scoped receipts do not leak through project views.

## Non-goals

This package does not add caller-open policy registration, generic payment,
arbitrary cross-domain business settlement, a new owner, or a second runtime,
store, bus, clock or scheduler. Those remain blocked until an existing owner
contract supplies the complete stream/event/projection/receipt mapping.
