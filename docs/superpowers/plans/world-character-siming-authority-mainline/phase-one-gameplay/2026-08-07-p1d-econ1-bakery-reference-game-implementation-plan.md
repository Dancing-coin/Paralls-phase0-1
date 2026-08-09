# P1D Econ-1 Bakery Reference Game Implementation Plan

> Backfill 2026-08-09: `implemented-and-verified`. Three periods, facility acquisition,
> instance-authority settlement, reservation lifecycle, full/checkpoint-tail replay, profile-backed
> employee assignment, failure/recovery matrix, and a Godot headless committed facility/output mirror
> probe are all fresh-green in `phase1d-econ1-bakery`.

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** 组合现有技能、资源、背包、产权、账户、固定报价、债务/合同与 Econ-1 四个子域，完成 `bakery-single-owner` 三个可回放经营周期。

**Architecture:** P1D 是 reference-game composition package，不是新的万能 business authority。Construction/Production、Survival、Economy、Organization/Government 各自拥有 canonical facts；P1D 只编排 typed commands、period projection 和前置 profile，最终仍使用现有 authority settlement。

**Tech Stack:** Python/Pydantic, existing Gameplay authorities and projections, pytest, Harness profile, optional Godot committed mirror.

---

## Requirements Summary

- 一个 owner CharacterRecord、一个 bakery Organization、一个 facility、一个 jurisdiction。
- 三个 item、一个 recipe、一个固定 supplier quote、聚合 customer demand、两个公开 competitor profiles。
- 一个 permit、一个 tax policy、一个 inspection；员工只能引用已存在 CharacterRecord。
- 覆盖 acquisition、permit、purchase、receipt、production、inventory output、sale、tax、obligations、period close、survival on/off。
- 明确记录 population simulation 尚未实现，不物化 NPC canonical state。

## Acceptance Criteria

1. 新 bakery 能连续完成至少三个 business periods，且每期收入、成本、税费、义务和结果可重放。
2. Purchase、lot receipt、production output、sale、tax posting 各自有 owning authority，跨域失败无部分提交。
3. Survival disabled/enabled、zero-employee/existing-CharacterRecord employee 两条路径均可观测。
4. material shortage、skill failure、capacity、funds、quote expiry、permit、facility、overdue obligation、stale revision、duplicate 都有结构化结果。
5. P1B、P1C 及四个 Econ-1 子域 Harness profiles 作为 predecessor 全部通过。
6. 任何测试或 runtime 文件不得创建 `NpcState`、Population Simulation Authority 或动态市场订单簿。

## Implementation Steps

### Task 1: Lock the reference-game scenario and owner matrix

**Files:**
- Create: `backend/app/gameplay/bakery_reference_runtime.py`
- Create: `backend/tests/test_bakery_reference_runtime.py`
- Modify: `docs/superpowers/specs/world-character-siming-authority-mainline/phase-one-gameplay/2026-08-07-p1d-econ1-bakery-reference-game-design.md`

- [x] **Step 1: Write failing tests** for the exact `bakery-single-owner` configuration, owner matrix, NPC prohibition, and three-period command sequence.
- [x] **Step 2: Implement** a scenario configuration and read-only period composition facade; it may submit typed commands but may not own account, inventory, facility or body state.
- [x] **Step 3: Run** `python -m pytest backend/tests/test_bakery_reference_runtime.py -q`; expected PASS after the composition contract is present.

### Task 2: Integrate the four Econ-1 domain packages

**Files:**
- Modify: `backend/app/gameplay/bakery_reference_runtime.py`
- Modify: `backend/app/gameplay/settlement_plan.py`
- Create: `backend/tests/test_bakery_domain_integration.py`

- [x] **Step 1: Add tests** for facility acquisition, permit activation, fixed quote purchase, recipe run, inventory output, aggregate demand sale, tax posting and period close.
- [x] **Step 2: Implement** the dependency order: Government permit -> Economy quote/hold -> Inventory receipt -> Construction/Production run -> Inventory output -> Economy sale/tax -> Organization period close -> Survival projection.
- [x] **Step 3: Verify** every event target belongs to the declared owner and every cross-domain input carries pinned revisions, causation and idempotency.
- [x] **Step 4: Run** `python -m pytest backend/tests/test_bakery_domain_integration.py -q`; expected PASS.

### Task 3: Add recovery and employee-path evidence

**Files:**
- Modify: `backend/app/gameplay/bakery_reference_runtime.py`
- Create: `backend/tests/test_bakery_failure_recovery.py`

- [x] **Step 1: Write tests** for shortage, qualification, capacity, funds, quote expiry, permit expiry, unavailable facility, overdue obligations and survival shortage.
- [x] **Step 2: Implement** bounded recovery proof: failed writes leave the ledger unchanged, and a corrected operation can proceed on that ledger; overdue obligations block period close until resolved.
- [x] **Step 3: Add** zero-employee and existing-CharacterRecord employee fixtures; reject synthetic actor IDs and hidden NPC state.
- [x] **Step 4: Run** `python -m pytest backend/tests/test_bakery_failure_recovery.py -q`; expected PASS.

### Task 4: Add vertical replay, mirror and Harness closure

**Files:**
- Create: `scripts/verification/verify_phase1d_bakery.py`
- Create: `scripts/verification/tests/test_verify_phase1d_bakery.py`
- Create: `.harness/profiles/phase1d-econ1-bakery.json`
- Modify: `docs/harness.md`
- Modify: `docs/superpowers/specs/world-character-siming-authority-mainline/phase-one-gameplay/2026-08-07-p1d-econ1-bakery-reference-game-design.md`

- [x] **Step 1: Verify** three-period online/full/checkpoint-tail replay and projection/mirror rebuild hashes.
- [x] **Step 2: Verify** predecessor profiles and all four Econ-1 domain reports before declaring the vertical green.
- [x] **Step 3: Emit** scenario timeline, owner diff, failure matrix, revision pins and population-simulation exclusion evidence.
- [x] **Step 4: Run** `python scripts/verification/harness.py --profile phase1d-econ1-bakery --godot-exe D:\godot\Godot_v4.6.3-stable_win64.exe`; PASS on 2026-08-09.

## Risks And Mitigations

- **Risk:** P1D becomes a hidden coordinator. **Mitigation:** keep composition facade stateless and require domain-owned commands/events.
- **Risk:** aggregate demand is mistaken for customer NPC simulation. **Mitigation:** type it as public demand projection and assert no CharacterRecord creation.
- **Risk:** period close becomes one unrecoverable mega-transaction. **Mitigation:** use obligations and append-only period facts with explicit recovery commands.

## Verification Steps

1. `python -m pytest backend/tests/test_bakery_reference_runtime.py backend/tests/test_bakery_domain_integration.py backend/tests/test_bakery_failure_recovery.py -q`
2. `python scripts/verification/harness.py --profile phase1d-econ1-bakery`
3. `python scripts/verification/harness.py --profile phase1c-frost-farm`
4. `python scripts/verification/harness.py --profile docs`

## Spec Coverage Review

Tasks 1-3 cover runtime configuration, full loop, owner matrix, failure/recovery and employee
paths. Task 4 covers replay, mirror, Harness and population-simulation boundary. Domain truth is
implemented only in the four subordinate plans.
