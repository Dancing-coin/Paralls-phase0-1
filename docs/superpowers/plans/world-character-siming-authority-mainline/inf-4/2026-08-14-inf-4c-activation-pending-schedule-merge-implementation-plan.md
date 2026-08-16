# INF-4C Activation Pending Schedule Merge Implementation Plan

Status: `implemented and checkpoint-verified; one released schedule_gated_supply row only`

1. [x] Add RED tests for released activation pending -> existing Organization
   supply merge and forged/stale zero-write rejection.
2. [x] Add a deterministic full-plan digest and admit only the named pending
   payload on the existing activation stream.
3. [x] Rebuild pending/release state from activation events, with scoped view,
   idempotency and checkpoint-tail replay checks.
4. [x] Revalidate released pending pins before calling the existing
   Organization fragment; retain the normal source/revision/privacy gates.
5. [x] Register `infra-activation-pending-schedule-merge` with one independent
   focused pytest assertion per capability and record its report.

No generic pending queue, new population owner, obligation coordinator binding,
second clock/store/scheduler, branch promotion, or civilization system is in
scope.
