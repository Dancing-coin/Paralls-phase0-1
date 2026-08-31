# INF-4V Production Work-Contribution Acceptance Implementation Plan

Status: `implemented and verified narrow vertical; generic work acceptance remains blocked`

**Goal:** Add one Organization-owned acceptance fact for a completed Production
contribution when a committed organization schedule explicitly authorizes access.

## Ordered Tasks

### Task 1: RED source/admission tests

- [x] Add a committed schedule with `organization:summary` access and a
  Construction `work_completion_evidence_recorded` source.
- [x] Assert exact source/schedule binding, fixed event payload, and
  organization-summary privacy.
- [x] Assert missing/private/stale/multiple/mismatched source or schedule,
  interval mismatch, duplicate, changed duplicate, and revision conflict are
  zero-write.
- [x] Run the focused file and observe failure because the row-specific intent
  and method are absent.

### Task 2: Existing Organization owner implementation

- [x] Add strict row-specific intent and owner-derived idempotency key.
- [x] Verify source evidence, schedule access proof, effective interval, and
  current Organization stream head before append.
- [x] Append exactly one fixed `production_work_contribution_accepted@1` event
  through `GameplayCommandEnvelope -> SettlementPlan -> append_batch()`.
- [x] Add the Organization projector/replay branch and owner-local receipt.

### Task 3: Immutable catalog admission

- [x] Add only the exact descriptor/catalog row for INF-4V; no generic consumer
  or registry path.
- [x] Assert catalog owner, stream, event family, privacy, receipt and replay
  pins in focused regression tests.

### Task 4: Independent evidence

- [x] Add an independent Harness profile and verifier script.
- [x] Verify success, zero-write, privacy, source/schedule revisions,
  idempotency, append receipt, full replay, and checkpoint-tail replay.
- [x] Run focused INF tests, full pytest, docs checks, and continuation gate.

### Task 5: Documentation closeout

- [x] Update INF-4 README, mainline audit, remaining-scope matrix, blocker
  taxonomy, owner-operation matrix, and continuation checkpoint.
- [x] Mark only INF-4V `implemented narrow vertical`; keep generic branch,
  population, social, wage, and payment classes separately bounded.
