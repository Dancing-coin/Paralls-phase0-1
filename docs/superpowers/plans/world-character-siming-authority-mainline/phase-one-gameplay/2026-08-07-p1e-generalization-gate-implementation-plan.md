# P1E Generalization Gate Implementation Plan

> Backfill 2026-08-09: `implemented-and-verified`. The selected profile-backed sample composes
> existing OwnershipAuthority, EconomyAuthorityService and DebtAuthorityService facts. Fresh
> checkpoint-tail, scope-filtered replay and zero-write failure-matrix evidence are green.

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** 以一个与面包店结构不同的 debt/contract/ownership interaction 样板，证明 P1A/P1B contract 没有被 frost farm 或 Econ-1 字段污染。

**Architecture:** 本计划选择 `ownership-contract-debt` 作为第二样板：一个已存在 CharacterRecord 申请带抵押物的租赁/债务合同，经过 ownership custody、contract terms、debt obligation 和 permission projection 结算。它复用现有 authorities，不创建金融市场、NPC 债权人或新 runtime。

**Tech Stack:** Existing ownership/economy/debt/contract/credential authorities, shared contract adapters, pytest, schema/owner/replay reports, Harness。

---

## Selected Sample

正式选择 P1E candidate `contract/debt/ownership-heavy interaction`，具体 fixture 为
`ownership-contract-debt`：申请人以现有 ownership right 作为抵押，创建固定条款 contract，
成功时生成 debt obligation，失败时验证权限、抵押 custody、revision、重复和零写入。样板
不生成新 CharacterRecord，不包含动态利率、市场发现或人口模拟。

## Acceptance Criteria

1. Bakery、Frost Farm、Ownership-Contract-Debt 三者的 core schema、command envelope、action/fact、reservation、replay、permission diff 无样板字段渗入。
2. `ownership-contract-debt` 成功、permission denied、missing custody、stale revision、duplicate 和 term conflict 都有可重放 zero-write evidence。
3. 三种样板均通过 full/checkpoint-tail replay、projection rebuild、revision pin 和 package fail-closed checks。
4. owner matrix 显示新 contract/debt/ownership package 只增加自己的 schema/authority/projection/package。
5. 通过后只能声称“第一阶段通用契约通过泛化门禁”，不得声称 dynamic market、Population Simulation 或 Creator Control Plane 已完成。

## Implementation Steps

### Task 1: Lock the second-sample fixture and comparison schema

**Files:**
- Create: `backend/app/gameplay/ownership_contract_debt_sample.py`
- Create: `backend/tests/test_ownership_contract_debt_sample.py`
- Modify: `docs/superpowers/specs/world-character-siming-authority-mainline/phase-one-gameplay/2026-08-07-p1e-generalization-gate-design.md`

- [x] **Step 1: Write tests** for applicant CharacterRecord requirement, fixed contract terms, collateral ownership/custody, debt obligation and forbidden NPC/market fields.
- [x] **Step 2: Implement** a fixture adapter that consumes existing ownership/economy/debt/contract projections and emits typed proposals only.
- [x] **Step 3: Run** `python -m pytest backend/tests/test_ownership_contract_debt_sample.py -q`; expected PASS.

### Task 2: Implement cross-sample schema and owner comparison

**Files:**
- Create: `scripts/verification/phase1e_comparison.py`
- Create: `scripts/verification/tests/test_phase1e_comparison.py`

- [x] **Step 1: Add tests** that fail when a sample-only field appears in identity/semantic/settlement/time core or when a domain writes another owner's aggregate.
- [x] **Step 2: Implement** deterministic schema diff, owner diff, package dependency diff and action/fact boundary report for Frost Farm, Bakery and Ownership-Contract-Debt.
- [x] **Step 3: Run** `python -m pytest scripts/verification/tests/test_phase1e_comparison.py -q`; expected PASS.

### Task 3: Add cross-sample replay, permission and profile evidence

**Files:**
- Create: `scripts/verification/verify_phase1e_generalization.py`
- Create: `scripts/verification/tests/test_verify_phase1e_generalization.py`
- Create: `.harness/profiles/phase1e-generalization-gate.json`
- Modify: `docs/harness.md`

- [x] **Step 1: Verify** the same contract fixture suite against the selected second sample and compare replay hashes, revision pins, reservation lifecycle and scope-filtered projections.
- [x] **Step 2: Require** P1B, P1C and P1D predecessor reports; fail closed when any predecessor evidence is absent or non-green.
- [x] **Step 3: Emit** schema diff, owner diff, sample extension inventory, failure matrix and explicit deferred-domain claims.
- [x] **Step 4: Run** `python scripts/verification/harness.py --profile phase1e-generalization-gate`; PASS on 2026-08-09.

## Risks And Mitigations

- **Risk:** debt fixture silently becomes a finance system. **Mitigation:** fixed terms and existing debt primitive only; no pricing engine or market state.
- **Risk:** comparison report compares implementation details instead of contracts. **Mitigation:** compare typed schemas, owner matrix, evidence and replay digests, not module names alone.
- **Risk:** P1E green result is overclaimed. **Mitigation:** report includes an explicit non-claim section for dynamic market, full commercial society, Population Simulation and Creator Control Plane.

## Verification Steps

1. `python -m pytest backend/tests/test_ownership_contract_debt_sample.py scripts/verification/tests/test_phase1e_comparison.py scripts/verification/tests/test_verify_phase1e_generalization.py -q`
2. `python scripts/verification/harness.py --profile phase1e-generalization-gate`
3. `python scripts/verification/harness.py --profile phase1d-econ1-bakery`
4. `python scripts/verification/harness.py --profile docs`

## Spec Coverage Review

Task 1 selects and implements the required structurally different candidate; Task 2 covers all
comparison rows; Task 3 covers every P1E acceptance artifact and predecessor gate. No new store,
bus, runtime, scheduler, shadow NPC or sample-local interpreter is introduced.
