# INF-3Y Hazard Propagation Consumer Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement exactly one registered canonical frost -> construction owner edge with deterministic, replayable zero-write failure.

**Architecture:** Ecology emits a proposal from INF-3X truth; each consumer independently validates and builds its fragment through the existing settlement spine. The edge catalog has no generic consumer authority.

**Tech Stack:** Python, semantic authority, existing domain fragment builders, event/replay projections, pytest, Harness.

---

### Task 1: Gate source and target owners

**Files:** Update INF-3Y design/plan; create `backend/tests/test_infra_hazard_propagation.py` after INF-3X admission succeeds.

- [x] Name the ecology source authority/stream and exactly one consumer builder/stream/event row: `ecology-hazard:frost-to-construction-finish:v1` reads project-visible canonical `hazard.recorded` + `crop.recorded` from `gameplay:ecology:{region_ref}`; `ConstructionProductionAuthority` accepts a new canonical command, selects one existing due run, and owns the existing `run_finished` fragment on `gameplay:construction_production:{facility_ref}`. The semantic crop-source command remains INF-3R and is not adapted.
- [x] Write failing tests for disabled/unknown edge, missing source revision, target privacy mismatch and direct consumer invocation; prove zero writes.
- [ ] Keep the current frost/crop evidence separate from the blocked proposed
  frost-to-production row; do not describe either as an enabled consumer edge
  or generalize it into market/body/social/population coverage.

### Task 2: Implement immutable edge evaluation

**Files:** Modify the named ecology authority and semantic proposal code; modify focused test.

- [x] Add the sole frozen proposal/catalog row `ecology-hazard:frost-to-construction-finish:v1` with canonical hazard/crop source event vector, causal refs, scope and idempotency. It has one deterministic target selected by the consumer; threshold/attenuation/fanout/cycle expansion is not admitted for this row.
- [x] Test the disabled/unknown edge and exact source-vector fences without append side effects. Multiple targets and fanout remain unsupported rather than inferred.
- [x] The consumer builds its named existing `ConstructionProductionAuthority.build_due_finish_fragment`; no consumer fragment means zero-write rejection.

### Task 3: Settle immediate and delayed rows

**Files:** Modify the named consumer authority and existing coordinator only as necessary; modify focused test.

- [x] Route the immediate fragment through the single existing append batch and prove consumer decline leaves all heads unchanged.
- [x] Delayed rows remain unsupported: this row has no INF-2X consumer-owned canonical-hazard obligation event family.
- [x] Test duplicate, source revision conflict, event-derived retired source rejection, visibility redaction and retry/compensation zero-write gating. Cancellation has no canonical-hazard row and remains unsupported.

### Task 4: Replay and evidence

**Files:** Modify causal/scoped readers as needed; create `.harness/profiles/infra-hazard-propagation.json`; create verifier/report.

- [x] Prove full/checkpoint-tail reproduction for the one enabled edge, consumer event, source ancestry and redacted projection. Schema version 1 needs no upcaster.
- [x] Create ten separate Harness assertions for the enabled row and each failure/replay/privacy case.
- [ ] Run full pytest, `git diff --check`, then update August/spec/plan/report with the enabled edge list and the exact registered-admission identity fence.
