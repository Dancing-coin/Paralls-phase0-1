# INF-4C Activation Pending Schedule Merge Design

Status: `implemented and checkpoint-verified; one released schedule_gated_supply row only`

## Scope

This package replaces INF-4A's former fail-closed-only activation-lock result
for one explicitly named row. `ProfileActivationAuthority` owns activation
admission state only, on the existing `population:{world_ref}` stream. It does
not own population, household, organization, social, obligation, or schedule
truth.

The only admitted pending payload is:

```text
kind = schedule_gated_supply
plan_digest = sha256 of the complete PopulationWorldPlan
```

All other payloads are `pending_change_kind_unsupported` with zero writes.

## Event and merge contract

`record_pending()` appends `population.activation.pending_recorded` through the
existing `GameplayEventStore.append_batch()` path. The event pins profile,
world, lock, change ref, kind, plan digest, and privacy scope. `release_lock()`
derives pending refs from that event stream and appends the existing
`population.activation.released` event. The pending projection is rebuilt from
those events, so it does not depend on a process-local queue.

`ContinuityMergeAuthority.merge_released_schedule_gated_supply()` reads only
that event-derived projection. It requires a released matching pending row,
the exact plan digest, profile/world/lock alignment, and the lock pin already
present in the plan. Only after those checks does it remove the specific lock
from an in-memory plan copy and call the existing
`merge_schedule_gated_supply()` path. That path revalidates frozen social,
household and organization sources and calls only
`OrganizationAuthority.build_commerce_commitment_fragment()`.

The two owner writes remain separate existing authority commits:

```text
ProfileActivationAuthority -> population activation event -> append/outbox/replay
released event-derived admission -> ContinuityMergeAuthority -> OrganizationAuthority fragment
-> one Organization append/outbox/replay/scoped projection
```

No generic pending executor, second scheduler/store/clock, branch promotion,
or generic population writer is added.

## Privacy, revision, idempotency and replay

Pending rows are visible only to their recorded privacy scope or
`authority:activation`; public callers receive no row. Pending record commands
are idempotent on the activation authority principal and the pending change
ref. The lock's held revision guards intent freshness, while the current
activation stream head is the append revision. Release requires its exact
stream revision. The target Organization fragment still owns target revision,
idempotency, receipt, outbox, and scoped projection. Full and checkpoint-tail
replay are asserted separately.

## Completion and non-goals

`infra-activation-pending-schedule-merge` independently asserts event-derived
pending/release, unsupported zero-write, duplicate idempotency, privacy,
checkpoint-tail replay, released owner-fragment merge, and forged/stale
zero-write. This supersedes only the INF-4A statement that every activation
lock must remain fail-closed. It does not complete generic activation pending
merge, ScheduledObligation activation integration, branch-domain consequences,
branch promotion, civilization diffusion, or full group simulation.
