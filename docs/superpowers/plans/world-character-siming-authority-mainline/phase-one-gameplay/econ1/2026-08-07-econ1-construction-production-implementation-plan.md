# Econ-1 Construction And Production Implementation Plan

> Backfill 2026-08-09: `implemented-and-verified` for the bounded owner profile. The profile records
> facility acquisition, inventory reservation references and an explicit maintenance obligation;
> P1D adds the committed facility/output Godot mirror proof.

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** 为 `bakery-single-owner` 增加最小建造/生产 authority，拥有 plot、facility、blueprint、recipe 和 run 进度，同时保留 Inventory、Skill、Economy 和 Organization 的事实 owner。

**Architecture:** Construction/Production 只保存自己的 aggregate 和 reservation references；材料/工具 custody 由 Inventory，劳动资格由 Skill，工资由 Economy/Organization，finish 由显式 ScheduledObligation command 驱动。所有完成/失败通过现有 atomic event batches 落账。

**Tech Stack:** Python/Pydantic, `inventory_runtime.py`, `skill_action_gate.py`, `settlement_plan.py`, event store, pytest, Harness。

---

## Acceptance Criteria

1. 一个 plot 可以经过 ownership/permit/zoning 验证后构建 bakery facility。
2. 一个 recipe 能 reserve、consume/release 正确 material/tool/facility slot，并以 typed mapping 将 output 交给 Inventory。
3. 生产完成、重复完成、过期 reservation、slot conflict 和 stale revision 都是可重放的确定结果。
4. maintenance/condition 只创建 explicit obligation，不增加隐藏 scheduler。
5. Godot 只收到 committed facility/output projection，不成为 facility truth owner。

## Implementation Steps

### Task 1: Add domain models and failing owner-boundary tests

**Files:**
- Create: `backend/app/gameplay/construction_production_runtime.py`
- Create: `backend/tests/test_construction_production_runtime.py`
- Modify: `backend/app/gameplay/models.py`

- [x] **Step 1: Write tests** for `Plot`, `Blueprint`, `Facility`, `Recipe`, `ConstructionJob`, `ProductionRun`, strict revision fields and forbidden account/inventory/body fields.
- [x] **Step 2: Implement** strict domain models, package event types and read projections; only references cross-domain resources.
- [x] **Step 3: Run** `python -m pytest backend/tests/test_construction_production_runtime.py -q`; expected PASS.

### Task 2: Implement reservation-backed start commands

**Files:**
- Modify: `backend/app/gameplay/construction_production_runtime.py`
- Modify: `backend/app/gameplay/inventory_runtime.py`
- Modify: `backend/app/gameplay/skill_action_gate.py`
- Create: `backend/tests/test_construction_production_start.py`

- [x] **Step 1: Add tests** for zoning/permit/ownership validation, material/tool/slot reservations, skill insufficiency and duplicate starts.
- [x] **Step 2: Implement** a start mapper that requests typed reservations from each owner, stores only reservation refs, and atomically appends the run-start event only after all preconditions pass.
- [x] **Step 3: Run** `python -m pytest backend/tests/test_construction_production_start.py -q`; expected PASS.

### Task 3: Implement finish, loss and maintenance obligations

**Files:**
- Modify: `backend/app/gameplay/construction_production_runtime.py`
- Modify: `backend/app/world_runtime/scheduling.py`
- Create: `backend/tests/test_construction_production_finish.py`

- [x] **Step 1: Write tests** for finish idempotency, reservation expiry, revision conflict, output mapping, explicit loss/rework/release and maintenance creation.
- [x] **Step 2: Implement** a scheduled finish command that revalidates pinned revisions, consumes/releases reservations, emits facility/output evidence and maps inventory receipt via its authority.
- [x] **Step 3: Run** `python -m pytest backend/tests/test_construction_production_finish.py -q`; expected PASS.

### Task 4: Add projection, replay and Harness evidence

**Files:**
- Modify: `backend/app/gameplay/godot_mirror_projection.py`
- Create: `scripts/verification/verify_econ1_construction_production.py`
- Create: `.harness/profiles/econ1-construction-production.json`
- Modify: `docs/harness.md`

- [x] **Step 1: Add** scope-filtered facility/output projections and full/checkpoint-tail replay assertions.
- [x] **Step 2: Add** profile evidence for start, finish, duplicate, conflict, maintenance and forbidden direct cross-domain writes.
- [x] **Step 3: Run** `python scripts/verification/harness.py --profile econ1-construction-production`; expected PASS.

## Risks And Mitigations

- **Risk:** run completion mutates inventory directly. **Mitigation:** tests require Inventory-generated custody/output events in the same accepted batch.
- **Risk:** in-memory timer silently completes work. **Mitigation:** finish accepts explicit tick/obligation input and duplicate delivery is tested.
- **Risk:** facility becomes a balance or payroll owner. **Mitigation:** model validation rejects those fields and owner-diff report is required.

## Verification Steps

1. `python -m pytest backend/tests/test_construction_production_runtime.py backend/tests/test_construction_production_start.py backend/tests/test_construction_production_finish.py -q`
2. `python scripts/verification/harness.py --profile econ1-construction-production`
3. `python scripts/verification/harness.py --profile phase1b-contract-verification`
