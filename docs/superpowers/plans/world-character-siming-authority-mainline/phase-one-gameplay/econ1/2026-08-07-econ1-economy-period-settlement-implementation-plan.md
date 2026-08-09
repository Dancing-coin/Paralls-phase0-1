# Econ-1 Economy And Business Period Settlement Implementation Plan

> Backfill 2026-08-09: `implemented-and-verified` for fixed-quote purchase/sale and three-period
> close. Bakery now uses instance authority methods; legacy static helpers are compatibility
> forwarding shims only. Dynamic market/order-book behavior remains out of scope.

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** 在现有 account、fixed-offer、debt、contract 和 ownership 原语上实现面包店第一版固定报价采购、销售、税费、工资/租金/许可义务和三期日结。

**Architecture:** Economy owns account/journal/quote/posting/hold/tax/wage/rent/license obligations. CustomerDemandAggregate 和 public competitor profiles 是只读输入，不是 NPC canonical state；动态市场、订单簿、拍卖和宏观价格不进入本计划。

**Tech Stack:** Python/Pydantic, `economy_runtime.py`, `fixed_offer_purchase.py`, debt/contract/ownership runtimes, Inventory/Organization/Government adapters, pytest, Harness。

---

## Acceptance Criteria

1. fixed quote 具有 validity、quantity_limit、public_digest；过期或耗尽 quote 在付款/库存前拒绝。
2. purchase、sale、tax posting 使用明确 owner 和 pinned policy/revision；失败零写入。
3. BusinessPeriod close 计算 revenue/cost/payroll/rent/tax/license/debt/inventory value/reputation projection，并可重复回放。
4. zero-payroll 与 existing-CharacterRecord payroll 两条路径可区分；不生成员工 NPC。
5. overdue wage/rent/license/tax/debt 能以 payment、renegotiation、pause、debt 或新 period 事实恢复。
6. profile 证明没有 dynamic market/order book/NPC ecosystem 语义。

## Implementation Steps

### Task 1: Add quote, posting, period and obligation models

**Files:**
- Create: `backend/app/gameplay/econ1_economy_runtime.py`
- Create: `backend/tests/test_econ1_economy_models.py`
- Modify: `backend/app/gameplay/economy_runtime.py`

- [x] **Step 1: Write tests** for `MarketQuote`, `PurchasePosting`, `SalePosting`, `BusinessPeriod`, `EconomicObligation`, strict public/private fields and fixed-market-only configuration.
- [x] **Step 2: Implement** models and projection calculators; reject private account/inventory/belief data in public quote/demand inputs.
- [x] **Step 3: Run** `python -m pytest backend/tests/test_econ1_economy_models.py -q`; expected PASS.

### Task 2: Implement purchase and sale settlement

**Files:**
- Modify: `backend/app/gameplay/econ1_economy_runtime.py`
- Modify: `backend/app/gameplay/fixed_offer_purchase.py`
- Modify: `backend/app/gameplay/inventory_runtime.py`
- Modify: `backend/app/gameplay/ownership_runtime.py`
- Create: `backend/tests/test_econ1_purchase_sale.py`

- [x] **Step 1: Add tests** for supplier quote hold/posting, lot receipt, sale demand acceptance, inventory consumption, ownership transfer, tax refs, quote expiry, quantity exhaustion, funds and custody mismatch.
- [x] **Step 2: Implement** typed adapters that ask account/inventory/ownership owners for accepted proposals, then build one atomic batch per posting boundary.
- [x] **Step 3: Run** `python -m pytest backend/tests/test_econ1_purchase_sale.py -q`; expected PASS.

### Task 3: Implement period close and recovery obligations

**Files:**
- Modify: `backend/app/gameplay/econ1_economy_runtime.py`
- Modify: `backend/app/gameplay/debt_runtime.py`
- Modify: `backend/app/gameplay/contract_runtime.py`
- Create: `backend/tests/test_econ1_period_close.py`

- [x] **Step 1: Write tests** for three periods, zero payroll, existing-character payroll, rent/license/tax/debt due, duplicate close and revision conflict.
- [x] **Step 2: Implement** deterministic close projection and append-only obligations; recovery commands create new payment/renegotiation/pause/debt/new-period facts.
- [x] **Step 3: Run** `python -m pytest backend/tests/test_econ1_period_close.py -q`; expected PASS.

### Task 4: Add profile, replay and market-boundary evidence

**Files:**
- Create: `scripts/verification/verify_econ1_economy_period.py`
- Create: `.harness/profiles/econ1-economy-period-settlement.json`
- Modify: `docs/harness.md`
- Modify: `docs/superpowers/specs/world-character-siming-authority-mainline/phase-one-gameplay/econ1/2026-08-07-econ1-economy-period-settlement-design.md`

- [x] **Step 1: Verify** three-period full/checkpoint-tail replay, fixed quote limits, zero-write failures and obligation recovery.
- [x] **Step 2: Emit** an explicit report that no order book, auction, dynamic price discovery or NPC state was created.
- [x] **Step 3: Run** `python scripts/verification/harness.py --profile econ1-economy-period-settlement`; expected PASS.

## Risks And Mitigations

- **Risk:** public demand/profile becomes private competitor simulation. **Mitigation:** validate projection classification and reject private fields at input boundary.
- **Risk:** tax/wage/rent posting duplicates account truth. **Mitigation:** Economy alone creates journal/obligation events; other domains receive typed projections.
- **Risk:** period close hides partial commits. **Mitigation:** split posting boundaries, require expected revisions and compare event counts on failure.

## Verification Steps

1. `python -m pytest backend/tests/test_econ1_economy_models.py backend/tests/test_econ1_purchase_sale.py backend/tests/test_econ1_period_close.py -q`
2. `python scripts/verification/harness.py --profile econ1-economy-period-settlement`
3. `python scripts/verification/harness.py --profile gameplay-economy-authority`
4. `python scripts/verification/harness.py --profile gameplay-ownership-authority`
