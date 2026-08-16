# INF-3X Regional Ecology Truth And Lifecycle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the existing `EcologyHazardAuthority` with replayable regional ecology records without a second ecology store.

**Architecture:** The owner must publish event-derived region/resource/crop/hazard projections through the canonical event store; `EcologyHazardAuthority` remains a semantic settlement consumer, not an implicit record database.

**2026-08-13 execution gate:** Admitted after formalizing the existing-store
contract: `EcologyHazardAuthority` owns only
`gameplay:ecology:{region_ref}` and the ten explicit record/retire event rows.
The semantic crop stream and frost-to-construction proposal remain separate
predecessors, not substitutes for this contract.

**2026-08-13 continuation gate:** `infra-continuation-gate` must be green
before moving to INF-3Y. It independently asserts this canonical owner/stream/
event map and records that consumer-edge admission is still empty.

**Tech Stack:** Python, existing gameplay event/replay/projection infrastructure, pytest, Harness.

---

### Task 1: Lock the admitted owner/event map

**Files:** Modify `backend/app/gameplay/ecology_runtime.py`; create `backend/tests/test_infra_regional_ecology_truth.py`; update INF-3X design.

- [x] Treat `EcologyHazardAuthority` as the sole record owner and define its ecology stream/event map, scoped readers and fragment interface. The admitted matrix is in the paired formal spec; it uses the existing store and forbids a second truth store or projection write path.
- [x] Write failing owner-map tests that reject region/record revision, unknown record, unsupported record kind, privacy and bundle overwrite before append.
- [x] Prove all implemented writes use the existing `GameplayEventStore` path; no direct record mutation occurs.

### Task 2: Record/event lifecycle

**Files:** Modify the named owner module and its existing projections; modify focused test.

- [x] Add frozen versioned canonical region/environment/resource/crop/hazard recorded/retired events with stable identities and causal refs.
- [x] Test valid record/retire transitions, stale revision, duplicate, privacy and event-count-preserving rejection.
- [ ] Add scheduled regeneration/growth only as an INF-2X registered owner fragment; blocked by design because ecology has no registered INF-2X lifecycle policy. Reads remain non-mutating.

### Task 3: Scoped projections and recovery

**Files:** Modify owner projection/replay readers; modify focused test.

- [x] Implement authority/public projection filters and test protected causality/idempotency data never escapes public scope.
- [x] Add forward retirement events and prove full/checkpoint-tail equality. No schema migration/upcaster is required for schema version 1 rows.
- [x] Test idempotency, privacy and altered lifecycle bundle overwrite return zero-write structured results. Retry remains unsupported.

### Task 4: Harness and documentation

**Files:** Create `.harness/profiles/infra-regional-ecology-truth.json`; create verifier/report; update August/spec/plan.

- [x] Create `infra-regional-ecology-truth` with a distinct Harness assertion per canonical recorded/retired row and boundary capability.
- [x] Run focused tests, profile, `python -m pytest -q`, and `git diff --check`; update August analysis, formal specs/plans, Harness documentation and evidence with exact propagation gaps.
