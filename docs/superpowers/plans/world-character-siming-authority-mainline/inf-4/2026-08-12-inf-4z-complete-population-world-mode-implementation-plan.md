# INF-4Z Complete Population World-Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend population planning across game, simulation and preview modes while preserving one identity, one production truth path and isolated branches.

**Architecture:** `PopulationPlanner` consumes only admitted scoped inputs and emits existing owner commands. Production uses canonical append/replay; branches use a fixed-base non-production buffer that cannot promote events.

**Tech Stack:** Python, `population_continuity`, existing activation/replay/event store, pytest, Harness.

---

### Admission gate: bounded row admitted; general package remains gated

Predecessor Harness profiles were rerun on 2026-08-13 and passed:
`infra-continuation-gate`, `infra-obligation-lifecycle`,
`infra-household-org-source-projection`, `infra-population-world-mode`, and
`infra-population-branch-preview`. That evidence does not admit INF-4Z
production writes. The historical `ContinuityMergeAuthority` generic writer
selected streams and event types from free-form planner payloads and wrote with
`population.authority`; it is now retired as a zero-write compatibility API and
its unreachable append implementation is removed. No existing domain authority/fragment/receipt mapping
is named for the `work` example or any other INF-4Z intent kind.
`OrganizationAuthority.AttendanceEvidence` is only a local validator today,
not an event-derived completed-evidence stream/projection. For
`production-completed`, the existing issuer is the Production owner, but its
canonical `run_finished` event has no actor/assignment/work-order linkage.
`EconomyAuthority.build_commerce_wage_accrual_fragment` also accepts opaque
evidence refs without their source stream/revision/privacy pins. These partial
objects do not compose into an admissible `work` row. The admitted
rows are `supply -> OrganizationAuthority.build_commerce_commitment_fragment`
and `inspection -> GovernmentAuthority.build_commercial_inspection_fragment`;
its focused evidence is `infra-population-world-mode-complete`.

Do not add another intent mapping or modify the generic merge path until an
admission amendment supplies a bounded mapping for the new intent:
target owner principal, `GameplayCommandEnvelope` validation, `SettlementPlan`
or owner fragment builder, canonical stream/event family, revision vector,
privacy-scoped projection, and canonical owner receipt. It must also name the
fixed-base checkpoint reader/upcaster and encoded tail boundary. Unknown,
missing, changed, or capability inputs must remain zero-production-write. This
is a formal design blocker, not permission to make `population.authority` a
truth owner. `work` remains an explicit zero-write case. The INF-4Z Harness
independently asserts `legacy_population_merge_zero_write`, so historical P3C
generic-merge compatibility cannot be mistaken for a production path. The admitted generic
`inspection` row must attach its own committed Government scoped-projection
outbox entry: topic `world.government.inspection.scoped_projection`, audience
exactly equal to `PopulationWorldPlan.report_scope`, and redacted payload
limited to `inspection_ref`, `organization_ref`, `jurisdiction_ref`, and
`passed`. `evidence_ref` and planner/source payloads must not cross that
boundary.

---

### Task 1: Lock prerequisites and frozen plan contract

**Files:** Modify `backend/app/population_continuity/models.py`; create `backend/tests/test_infra_population_world_mode_complete.py`; update INF-4Z design.

- [x] Require INF-2X lifecycle evidence and admitted INF-4X source contracts; reject missing/unsupported sources before planning. Generic capability input remains rejected; the separately approved INF-4Y `supply` edge uses its own frozen source contract.
- [x] Add immutable `PopulationWorldPlan` and fixed-base branch request models with checkpoint/tail boundary, active revisions, source vectors, seed, budget, locks and report scope.
- [x] Independently assert shuffled candidate determinism, altered fixed-base and
  calibration digests, and unknown profile rejection without production writes.
  Reverified 2026-08-13 by `infra-population-branch-preview` with ten separate
  assertions; focused INF-4Z tests and the 2717-test full suite also passed.
- [x] INF-4Z-A now asserts authoritative calibration admission through the
  separately documented `ReferenceDataAuthority` contract: frozen permitted
  dataset view, owner/forged/revoked/stale/privacy zero-write and replay are
  independently proved by `infra-reference-data-license-admission`.

### Task 2: Implement caller-selected mode batching

**Files:** Modify `backend/app/population_continuity/batch.py` and `activation.py`; modify focused test.

- [x] Implement game/simulation/preview cadence as pure caller-selected policy with stable ordering and bounded work; assert it cannot advance `SimulationClock` itself. `preview` is explicitly zero-write at the production merge boundary and is consumed only by the isolated branch authority.
- [x] Test each admitted mode's budget, source scope, activation-lock pending zero-write, duplicate idempotency replay, revision conflict zero-write, privacy-scope zero-write and owner decline through existing owner fragments. Generic defer/requeue remains blocked for unadmitted mappings.
- [x] Retire the historical P3C `PopulationBatchPlan` generic merge: delete its
  unreachable free-form append writer and independently assert
  `legacy_population_merge_zero_write` for caller-selected stream/event data.
- [x] Add a distinct generic inspection outbox/privacy assertion: one committed Government
  outbox entry, exact report audience, no `evidence_ref`, and replay equivalence.
- [x] Do not introduce persistent aggregate, household, organization, social or NPC truth.

### Task 3: Fix branch replay boundary

**Files:** Modify `backend/app/population_continuity/branch_preview.py`; modify focused test.

- [x] Pin branch replay to a production checkpoint plus tail boundary and all source/ruleset/policy digests.
- [x] Test repeatable fixed-base branch replay, source/calibration digest pinning, tail boundary mismatch and production isolation. Broader actor/creator report filtering and branch discard lifecycle remain bounded follow-up.
- [x] Keep production correction/compensation in target owner paths; branches cannot merge/promote.

### Task 4: Production replay and independent evidence

**Files:** Modify existing replay adapters as needed; create `.harness/profiles/infra-population-world-mode-complete.json`; create verifier/report.

- [x] Prove fixed-base branch equality and bounded production owner mapping with independent Harness assertions.
- [x] Add distinct bounded assertions for game/simulation/preview cadence, preview-production zero-write, duplicate, revision, privacy, activation-lock pending, fixed-base branch and tail-boundary behavior. Future owner mappings, generic defer/requeue and full population completion remain blocked; current report is bounded, not complete.
- [x] Re-run focused tests, profiles, full pytest, `git diff --check`; synchronize exact proven sources and remaining unsupported inputs in August/spec/plan/report. INF-4Z-A reference-data evidence remains in its dedicated package report.
