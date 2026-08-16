# INF-4X Household And Organization Source Projection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend existing social and organization owners to supply verified scoped schedule inputs without creating new truth owners.

**Admission status:** `implemented bounded as of 2026-08-13`. User authorization
approved the owner extension contract; only the existing SocialFactAuthority
and OrganizationAuthority were extended. No new truth owner or store was added.

**Architecture:** A named existing source authority publishes revisioned readers; the planner freezes their output and emits only existing owner intents. Branches copy, but cannot promote, scoped inputs.

**Tech Stack:** Python, `population_continuity`, social scoped views, existing event/replay infrastructure, pytest, Harness.

---

### Task 1: Lock the admitted source owners

**Files:** Modify `backend/app/gameplay/p5/social_knowledge.py`; modify `backend/app/gameplay/organization_government_runtime.py`; create `backend/tests/test_infra_household_org_source_projection.py`; update INF-4X design.

- [x] Extend the two existing authorities with canonical owner events, revisioned scoped readers and privacy labels on their existing streams.
- [x] Write failing tests for missing provenance/vector/recipient scope and prove planner/event store remain untouched.
- [x] Tests prove the existing owners, rather than planner state, source the read vectors.

### Task 2: Publish and freeze source projections

**Files:** Modify named source projection modules and `backend/app/population_continuity`; modify focused test.

- [x] Add immutable schedule inputs carrying stable refs, time windows, source vectors, observation time, owner principal, scope and digest.
- [x] Test actor/other-recipient filtering, effective windows, forged provenance/digest rejection, source correction as a new event, stale vector and digest pinning.
- [x] Ensure planner does not infer membership/kinship/obligations or persist source truth.

### Task 3: Produce and settle plans safely

**Files:** Modify `population_continuity` planner/activation code and applicable existing target owner tests.

- [x] Pin mode, seed, source vectors and deterministic digests in planner output for existing owners only.
- [x] Test duplicate, source revision conflict, recipient scope denial and owner-only append with zero production writes as appropriate.
- [x] Existing branch preview remains isolated; no production promotion path was added.

### Task 4: Replay and evidence

**Files:** Modify readers/replay adapters as needed; create `.harness/profiles/infra-household-org-source-projection.json`; create verifier/report.

- [x] Prove full/checkpoint-tail production equality and source correction replay.
- [x] Add distinct Harness assertions for source provenance, privacy, zero-write scope, duplicate, revisions and replay.
- [x] Run full pytest and final diff check after documentation synchronization (`2640 passed`; `git diff --check`).

Evidence: `.harness/verification/infra-household-org-source-projection-report.json`.
