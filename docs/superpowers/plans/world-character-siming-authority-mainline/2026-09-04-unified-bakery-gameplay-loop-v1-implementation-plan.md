# Unified Bakery Gameplay Loop v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the existing bakery reference composition a deterministic, replayable three-period playable loop across the existing authorities.

**Architecture:** Extend the existing `BakeryReferenceScenario` and its owner services; do not create a bakery truth owner or second runtime. Every new event is descriptor-bound and appended through the existing store.

**Tech Stack:** Python, Pydantic, existing GameplayEventStore, pytest, Harness, Godot read-only mirror.

**Spec:** `docs/superpowers/specs/world-character-siming-authority-mainline/2026-09-04-unified-bakery-gameplay-loop-v1-design.md`

## Global Constraints

- Preserve existing owner boundaries and `GameplayCommandEnvelope -> SettlementPlan -> GameplayEventStore.append_batch()`.
- No generic writer/router/coordinator, second runtime/store/bus/clock/scheduler, or caller-selected authority coordinates.
- Population remains signal-only; no shadow NPC/account/inventory state.
- Existing narrow rows and package revisions remain read-only compatible.
- All new facts retain package/content/declaration/descriptor/active-set/policy/source revision pins.

### Task 1: Deterministic three-period backend loop

**Files:**
- Modify: `backend/app/gameplay/bakery_reference_runtime.py`
- Test: `backend/tests/test_unified_bakery_gameplay_loop.py`

- [ ] Add a failing test that `BakeryReferenceScenario.default().run_three_periods(store=GameplayEventStore())` commits three distinct period refs and owner receipts.
- [ ] Run the focused test and observe the failure.
- [ ] Implement deterministic period identity, committed period-open/close evidence and existing-owner composition without bypassing authorities.
- [ ] Add failure-injection assertions for material, funds, skill and permit validation with zero-write.
- [ ] Run focused tests and preserve the existing bakery reference tests.

### Task 2: Failure/recovery and cross-owner acceptance

**Files:**
- Modify: `backend/app/gameplay/bakery_reference_runtime.py`, existing owner modules only where required
- Test: `backend/tests/test_unified_bakery_failure_recovery.py`

- [ ] Add RED tests for one production failure, explicit recovery, and source-pinned Inventory/Economy/Organization/Government handoffs.
- [ ] Implement only fixed recipes: purchase/custody, production/output, sale, wage/tax, survival and period close.
- [ ] Verify duplicate, stale revision, expired permit and changed-idempotency zero-write.
- [ ] Run focused cross-owner tests.

### Task 3: Read-only Godot projection and Harness

**Files:**
- Modify: `backend/app/gameplay/bakery_mirror_source.py`
- Create: `.harness/profiles/unified-bakery-gameplay-loop-v1.json`, `scripts/verification/verify_unified_bakery_gameplay_loop.py`
- Test: `backend/tests/test_unified_bakery_mirror.py`

- [ ] Add RED tests for committed-only three-period mirror and rejection rollback.
- [ ] Implement the mirror from committed events only; expose period, facility, inventory, sale, permit and failure/recovery summaries.
- [ ] Add Harness profile and verification script.
- [ ] Run focused Harness and Godot headless/desktop smoke when available.

### Task 4: Replay, documentation and release gate

**Files:**
- Modify: OGS/Construction/Economy/Inventory/INF README and completion audit files
- Test: `backend/tests/test_unified_bakery_replay.py`

- [ ] Add RED tests for full vs checkpoint-tail replay equality across all three periods.
- [ ] Implement replay checkpoint serialization and tamper rejection using existing event-store facilities.
- [ ] Synchronize mainline README, plan README, completion audit, remaining-scope and checkpoint without marking August INF A-D complete.
- [ ] Run `python -m pytest -q`, focused Harness, docs Harness, compileall and diff check.
- [ ] Commit each completed task with Lore trailers, then push `main`.
