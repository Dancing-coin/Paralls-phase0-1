# SGC Siming Group World Formalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Admit and verify narrow Siming/group-world verticals without adding a generic authority or a second runtime.

**Architecture:** Five contract-gated packages reuse the immutable catalog, one append spine, derived graph, existing continuity runtime, and scoped presentation projections. Each package stops at an audited blocked disposition unless its exact owner/capability contract is approved.

**Tech Stack:** Python, Pydantic models, existing GameplayEventStore/outbox/replay, pytest, repository Harness, Godot local presentation.

**Spec:** `docs/superpowers/specs/world-character-siming-authority-mainline/siming-group-world-formalization/2026-08-17-sgc-siming-group-world-formalization-program-design.md`

**Package plans:** SGC-1 `01-sgc-1-governed-siming-capability-plan.md`, SGC-2
`02-sgc-2-derived-cognitive-graph-plan.md`, SGC-3
`03-sgc-3-population-fidelity-continuity-plan.md`, SGC-4
`04-sgc-4-presentation-view-plan.md`, and SGC-5
`05-sgc-5-performance-replay-evidence-plan.md`.

## Global Constraints

- No new truth owner, generic writer/router/coordinator/registry, or second runtime/store/bus/clock/scheduler.
- Reuse `GameplayCommandEnvelope -> SettlementPlan -> GameplayEventStore.append_batch() -> outbox/replay -> scoped projection` for every admitted write.
- An unapproved owner/capability row is zero-write and is recorded as `owner-contract blocked`.
- Every admitted vertical needs focused RED tests and an independent Harness selector covering success, zero-write rejection, privacy, revision, idempotency, receipt, full replay and checkpoint-tail replay.

---

### Task 1: SGC package gates and dependency order

**Status:** `draft decomposition`

The package plans are the execution authority for their own task lists. Execute
them in this order: SGC-1 capability admission -> SGC-2 graph bridge -> SGC-3
fidelity handoff -> SGC-4 presentation projection -> SGC-5 performance
evidence. SGC-1 may stop at owner-contract blocked; SGC-2 and SGC-3 require
their own source/owner prerequisites; SGC-5 cannot start until one SGC-1..4
vertical is complete. The remainder of this file is a compact cross-package
map; do not use it instead of the package plan.

### Task 2: SGC-1 catalog-bound Siming capability admission

**Status:** `blocked pending one selected existing-owner row with a complete contract`

**Files:**
- Modify: `backend/app/gameplay/governed_contract_catalog.py`
- Modify: `backend/app/services/siming_intervention_guardrails.py`
- Modify: `backend/app/services/siming_audit_writer.py`
- Test: `backend/tests/test_siming_governed_capability_contract.py`
- Harness: `scripts/verification/harness.py` and `docs/harness.md`

**Interfaces:** Consumes a fixed `contract_ref` and scoped source vector. Produces either a typed, owner-local intent candidate or a zero-write audited refusal; it never produces an owner-selected fragment.

- [ ] Write failing tests for unknown catalog ref, changed capability version, widened privacy scope, stale source revision and exact duplicate; assert `append_batch()` is never called for all five rejections.
- [ ] Select one existing owner operation whose event, receipt, privacy, replay and compensation contract is already approved; record its `contract_ref`, owner principal, fixed stream/event family and idempotency shape in the relevant INF audit.
- [ ] Add exactly one immutable catalog entry and one guardrail adapter that resolves the owner-controlled operation before candidate conversion; do not add `register`, `append` or caller-selected routing APIs.
- [ ] Run the focused test file, then add a named Harness selector proving success, all zero-write rejections, scoped receipt and full/checkpoint-tail replay.
- [ ] Update the matching INF plan, completion audit and continuation checkpoint with either verified evidence or `owner-contract blocked`.

### Task 3: SGC-2 scoped graph correction and memory bridge

**Status:** `blocked pending an approved scoped authority-event reader`

**Files:**
- Modify: `backend/app/models/siming_heavenly_graph.py`
- Modify: `backend/app/services/in_memory_heavenly_graph.py`
- Modify: `backend/app/character_agent/mind/graph_projection.py`
- Test: `backend/tests/test_siming_scoped_graph_correction.py`

**Interfaces:** Consumes a permitted scoped event/projection and query tuple `(principal, scope, valid_at, recorded_at)`. Produces a derived graph result keyed by source vector, scope digest and policy revision.

- [ ] Write failing tests for privacy-redacted read, source compensation, policy revision change, checkpoint invalidation and an already-consumed character summary remaining subjective.
- [ ] Define only derived-node/relation fields required by the spec; append superseding/retracted/redacted derivations instead of mutating fact history.
- [ ] Add a single fixed projection consumer and a read-only character summary adapter; reject an unlisted event family or widened reader scope before graph write.
- [ ] Run focused tests and a named graph Harness selector for correction, redaction, full replay and checkpoint-tail equivalence.

### Task 4: SGC-3 cadence-pinned fidelity handoff

**Status:** `blocked pending one existing committed world-mode/cadence source and one admitted owner-bound consumer`

**Files:**
- Modify: `backend/app/population_continuity/batch.py`
- Modify: `backend/app/population_continuity/activation.py`
- Modify: `backend/app/population_continuity/models.py`
- Test: `backend/tests/test_sgc_population_fidelity_handoff.py`

**Interfaces:** Consumes fixed world-mode/cadence refs and revisions, source vector, seed, selector revision and budget. Produces no-op/requeue, an activation candidate, a discardable presentation seed, or an existing owner-bound intent.

- [ ] Write failing tests for missing/stale/private cadence, deterministic cohort ordering, no private memory in prewarm, lock conflict, requeue and no append for presentation-only output.
- [ ] Reuse the existing activation lock and population models; add only pinned fields and deterministic selection data required for replay.
- [ ] Wire one existing owner-bound consumer after its catalog admission; do not write population/social truth or introduce a clock/scheduler.
- [ ] Run focused tests and a named Harness selector proving handoff, privacy, idempotency, receipt and full/checkpoint-tail replay.

### Task 5: SGC-4 scoped PresentationView vertical

**Status:** `blocked pending one approved owner event family and published asset manifest`

**Files:**
- Modify: `backend/app/world_runtime/projection.py`
- Modify: `backend/app/gameplay/godot_mirror_projection.py`
- Modify: `backend/app/contracts/l1/presentation_command.py`
- Test: `backend/tests/test_sgc_presentation_view_contract.py`

**Interfaces:** Consumes a scoped owner projection, manifest revision and mapping revision. Produces a read-only `PresentationView` semantic digest plus renderer-local fallback guidance.

- [ ] Write failing tests for private source, layer identity leakage, below-threshold crowd output, changed manifest/mapping revision, missing asset fallback and no world append from renderer feedback.
- [ ] Add semantic layer metadata (`source_ref`, visibility, redaction, identity policy) and separate manifest-bound digest calculation from device-local LOD.
- [ ] Implement one owner-event-to-view projection and one Godot local fallback path; route observations only as existing evidence candidates.
- [ ] Run focused tests and a named Harness selector covering privacy, fallback, zero-write feedback, full replay and checkpoint-tail replay.

### Task 6: SGC-5 reproducible performance evidence

**Status:** `blocked until Tasks 1-4 yield one complete vertical`

**Files:**
- Create: `backend/tests/test_sgc_performance_profiles.py`
- Modify: `scripts/verification/harness.py`
- Modify: `docs/harness.md`
- Modify: `docs/superpowers/specs/world-character-siming-authority-mainline/siming-group-world-formalization/2026-08-17-sgc-siming-group-world-formalization-program-design.md`

**Interfaces:** Consumes synthetic data version/size, environment label, pinned vectors/revisions, seed, budget and repeat count. Produces a profile report with median/high-percentile measurements and an auditable load-shedding disposition.

- [ ] Write failing tests that reject missing environment/data/seed fields and assert an over-threshold profile cannot erase receipts, relax privacy or synthesize a settlement.
- [ ] Add `population-batch-baseline`, `activation-handoff`, `presentation-tail-replay` and `privacy-load-shed` selectors with the five required measurements and fixed synthetic inputs.
- [ ] Define per-selector regression thresholds from recorded local baselines; on breach report failure or an existing no-op/requeue/LOD disposition, never silent data loss.
- [ ] Run each selector independently, record environment limits, then run the applicable focused pytest and `git diff --check` before updating the verification record.

## Completion Rule

Do not mark this program implemented merely because the documents exist. Each
task becomes `implemented narrow vertical` only after its approved row, focused
tests, independent Harness report, replay/privacy evidence, formal spec/plan,
package README and completion audit are synchronized. Any remaining package
without a complete owner contract remains `owner-contract blocked` or
`unimplemented`.
