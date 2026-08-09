# Econ-1 Survival Profile Implementation Plan

> Backfill 2026-08-09: `implemented-and-verified` for disabled/narrative/lightweight/simulation
> policy and explicit tick/consumption proposal evidence. Population Simulation and hidden ticks
> remain excluded.

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** 将单一食物需求实现为可按 project/world/character-group 启停的 Survival state group，并证明 `disabled`、`narrative`、`lightweight`、`simulation` 四种模式不会混淆角色心智与 canonical 身体/消费事实。

**Architecture:** Survival 提出 need、consumption 和 labor-availability proposal；Inventory、Economy、Ownership、Body 仍各自提交真相。`NeedTensionEngine` 只保持角色心智提示，不能成为 Survival Authority；tick 由明确 command/obligation 传入。

**Tech Stack:** Python/Pydantic, resource/body/status/effective-stats runtimes, inventory/economy/ownership authorities, state-group lifecycle, pytest, Harness。

---

## Acceptance Criteria

1. 四个模式的 profile/revision 和 projection 明确；`disabled` 无 tick、消费、penalty、obligation，`narrative` 无资源消费。
2. `lightweight` 与 `simulation` 对相同 tick/idempotency input 重复执行不重复衰减。
3. 食物短缺、source 不可用、权限不足、stale revision 有结构化失败且不移动 inventory/资金。
4. consumption 只在 Inventory/Economy/Ownership 接受 reservation 后才改变 NeedState/Body projection。
5. replay 可重建 need/body/labor projection，P1D 能在 survival-disabled 和 survival-enabled 周期中运行。

## Implementation Steps

### Task 1: Add Survival models and mode tests

**Files:**
- Create: `backend/app/gameplay/survival_runtime.py`
- Create: `backend/tests/test_survival_runtime.py`
- Modify: `backend/app/gameplay/state_group_lifecycle_authority.py`

- [x] **Step 1: Write tests** for `NeedDefinition`, `NeedState`, `ConsumptionPlan`, `SurvivalPolicy`, all four modes, revision pinning and explicit missing reasons.
- [x] **Step 2: Implement** strict models and state-group registration; reject invalid mode transitions and preserve historical events.
- [x] **Step 3: Run** `python -m pytest backend/tests/test_survival_runtime.py -q`; expected PASS.

### Task 2: Implement explicit tick and consumption proposals

**Files:**
- Modify: `backend/app/gameplay/survival_runtime.py`
- Modify: `backend/app/gameplay/resource_body_runtime.py`
- Modify: `backend/app/gameplay/effective_stats.py`
- Create: `backend/tests/test_survival_tick_and_consumption.py`

- [x] **Step 1: Add tests** for disabled/narrative non-consumption, lightweight/simulation idempotent decay, thresholds, food shortage and pinned revision conflict.
- [x] **Step 2: Implement** explicit tick handling that yields a typed ConsumptionPlan/effect proposal rather than directly mutating item or account state.
- [x] **Step 3: Apply** accepted consumption/body consequence only after the owning external authorities return accepted reservation/settlement references.
- [x] **Step 4: Run** `python -m pytest backend/tests/test_survival_tick_and_consumption.py -q`; expected PASS.

### Task 3: Integrate inventory, economy, ownership and labor availability

**Files:**
- Modify: `backend/app/gameplay/inventory_runtime.py`
- Modify: `backend/app/gameplay/economy_runtime.py`
- Modify: `backend/app/gameplay/ownership_runtime.py`
- Modify: `backend/app/gameplay/skill_action_gate.py`
- Create: `backend/tests/test_survival_cross_domain_settlement.py`

- [x] **Step 1: Add tests** for in-custody food, quoted food purchase, unavailable use-right, payment failure and labor availability projections.
- [x] **Step 2: Implement** typed reservation/result adapters and reject any direct Survival inventory/account mutation.
- [x] **Step 3: Run** `python -m pytest backend/tests/test_survival_cross_domain_settlement.py -q`; expected PASS.

### Task 4: Add replay, profile and Harness gates

**Files:**
- Modify: `backend/app/gameplay/replay.py`
- Create: `scripts/verification/verify_econ1_survival_profile.py`
- Create: `.harness/profiles/econ1-survival-profile.json`
- Modify: `docs/harness.md`

- [x] **Step 1: Add** full/checkpoint-tail replay checks for all modes and a failure assertion for any disabled hidden write.
- [x] **Step 2: Add** Bakery profile bridge fixtures for survival-disabled and survival-enabled period execution.
- [x] **Step 3: Run** `python scripts/verification/harness.py --profile econ1-survival-profile`; expected PASS.

## Risks And Mitigations

- **Risk:** current cognitive NeedTension is treated as economic/body truth. **Mitigation:** require separate state-group streams and projection-only mind summaries.
- **Risk:** mode changes rewrite history. **Mitigation:** mode changes create new ruleset revisions and pinned sessions finish under their start revision.
- **Risk:** Survival reads private actor state through generic query. **Mitigation:** use scope-filtered authority inputs and redacted reports.

## Verification Steps

1. `python -m pytest backend/tests/test_survival_runtime.py backend/tests/test_survival_tick_and_consumption.py backend/tests/test_survival_cross_domain_settlement.py -q`
2. `python scripts/verification/harness.py --profile econ1-survival-profile`
3. `python scripts/verification/harness.py --profile gameplay-resource-body`
4. `python scripts/verification/harness.py --profile gameplay-state-groups`
