# INF Reusable Contract Substrate Implementation Plan

Status: `INF-C1 through INF-C5 implemented and independently verified; further broad owner-row expansion remains contract-gated`

## Sequence

1. **Baseline and contract inventory.** Re-run the INF continuation gate,
   focused state/obligation/ecology/branch profiles and the checkpoint-tail
   suites. Record one matrix mapping every admitted owner row to stream,
   event family, scope, revision, idempotency, receipt and replay reader.
2. **INF-C1: typed state-transition proposal.** Add focused RED tests first
   for `add/replace/refresh/reject`, stack limit, scheduled expiry, dispel and
   transform. Evolve the existing pure evaluator output into one typed plan;
   wire exactly two existing owner adapters without adding an owner router or
   writer. Prove a third/unregistered owner is zero-write.
3. **INF-C2: lifecycle contract normalization.** Make the closed obligation
   registration the shared source of terminal-operation admission and
   event-derived opening provenance. Reuse it for at least one state-expiry
   owner and one Economy obligation; preserve owner-built terminal fragments.
   Prove bounded due, retry/cancel/expire/compensate admission and
   full/checkpoint-tail equivalence.
4. **INF-C3: append-derived settlement recipe.** Normalize fragment-plan
   validation and receipt construction for one single-owner and one existing
   multi-owner batch. The coordinator remains planner-only and no generic
   caller-selected settlement is admitted. Prove one append result, duplicate,
   stale revision, owner/scope rejection and receipt privacy.
5. [x] **INF-C4: ecology consumer contract adapter.** Extract the common finite
   source/target admission checks from the existing Construction, Organization
   and Economy rows while retaining each target's fragment builder. Prove the
   adapter can be reused by at least two target owners and rejects a forged or
   unregistered consumer with zero writes.
6. [x] **INF-C5: deterministic branch replay contract.** Normalize fixed base
   revision, calibration digest, input ordering and projection digest into a
   branch replay reader. It is consumed by the existing isolated branch path
   and the fixed Organization supply admission, with production promotion still
   owner-specific and zero-write for unknown input. Evidence:
   `infra-fixed-base-branch-replay-contract`.
7. **Resume domain expansion only after C1-C5 evidence.** Add the next owner
   row only by filling the owner-contract matrix and creating RED tests. Do
   not claim that a reusable planner grants permission to register a new owner,
   policy, event family or promotion.

## Acceptance Criteria

- No new runtime, store, bus, clock, scheduler or truth owner.
- Every reusable layer is pure/read-only until an existing owner commits a
  `GameplayEventStore.append_batch()` batch.
- Each C-package has its own focused tests, Harness profile/report, formal
  spec/plan entry, August status update and `git diff --check` evidence.
- Full `python -m pytest -q` and required replay/continuation evidence pass
  at the end of each package.

## Research References

- https://github.com/pyeventsourcing/eventsourcing/tree/9.6
- https://github.com/temporalio/sdk-python
- https://github.com/renew-engine/renew
- https://github.com/oskardudycz/EventSourcing.NetCore

These are pattern references only. No dependency may be added without a
separate approval and compatibility review.
