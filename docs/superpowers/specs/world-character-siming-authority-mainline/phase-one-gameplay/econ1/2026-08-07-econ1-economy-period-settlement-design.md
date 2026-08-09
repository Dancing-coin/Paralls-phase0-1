# Econ-1 Economy And Business Period Settlement Design

Status: `approved; matching plan authorized by user on 2026-08-07`

Date: `2026-08-07`

## Purpose And Boundary

定义面包店第一版的经济闭环：固定报价、采购、销售、账户分录、税费、工资/租金/许可
义务和经营日结。它扩展现有 account、fixed-offer、debt、contract 和 ownership 原语，
不实现动态市场、订单簿、拍卖或宏观价格模型。

## Models

```text
MarketQuote
  quote_ref, issuer_ref, item_ref, side, unit_price, quantity_limit,
  valid_from_tick, valid_until_tick, policy_revision, public_digest

Purchase / Sale Posting
  posting_ref, buyer_ref, seller_ref, item_ref, quantity, amount,
  quote_ref, tax_refs, inventory_refs, ownership_refs, revision

BusinessPeriod
  period_ref, opening_tick, closing_tick, revenue, cost, payroll,
  rent, tax, license_fee, debt_due, inventory_value, reputation_delta,
  result, revision

EconomicObligation
  obligation_ref, holder_ref, kind, amount, due_tick, source_refs, status
```

## First-Phase Market Shape

- suppliers are fixed quote sources with validity, quantity limit and delivery rule;
- customers are `CustomerDemandAggregate` by item, period, price/quality band and time window;
- competitors are public parameterized profiles, not NPC owners or employees;
- prices may use cost, stock coverage, aggregate demand, quality, tax and competitor profile;
- sales only consume an unexpired quote and available inventory;
- private account, inventory, budget and belief data never become public market input。

## Settlement Flows

```text
purchase: quote -> account hold/posting -> inventory lot receipt -> ownership/custody
sale: demand aggregate -> quote -> inventory consumption -> account posting -> tax assessment
period close: revenue/cost -> payroll/rent/license/tax/debt obligations -> result projection
```

Payroll may be zero in `bakery-single-owner`. Real employee payroll requires an existing
CharacterRecord and a separate typed employment/organization contract; it does not activate
NPC population state.

## Failure And Recovery

- insufficient funds or expired quote;
- quantity/custody mismatch;
- tax policy unavailable or permit invalid;
- posting revision conflict or duplicate idempotency key;
- overdue wage/rent/license/tax/debt obligation。

Failure is zero-write for the rejected batch. Recovery appends payment, renegotiation, pause,
debt or new-period facts; it never edits historical postings.

## Acceptance

- at least three business periods can be replayed from a new bakery;
- purchase, inventory receipt, production sale and tax posting are atomic per owning batch;
- fixed quote expiry and quantity limits are enforced;
- period close produces deterministic revenue/cost/obligation result;
- zero-payroll and existing-agent payroll paths are separately observable;
- no dynamic market or NPC ecosystem claim is made。
