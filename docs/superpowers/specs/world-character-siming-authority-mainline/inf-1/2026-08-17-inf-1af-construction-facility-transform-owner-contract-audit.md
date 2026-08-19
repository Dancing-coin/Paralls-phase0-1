# INF-1AF Construction Facility Transform Owner-Contract Audit

Status: `implemented narrow vertical for the separately approved bakery-reinforcement contract; generic transform remains owner-contract blocked`

## Exact Row

This audit considers one next bounded INF-1 row only:
`Construction facility transform action`. It is not a request for generic
Construction actions, repair variants, payment, material consumption, service
completion, or an action router.

## Existing Authority Evidence

At the time of this audit, `ConstructionProductionAuthority` was the legitimate existing owner of
`gameplay:construction_production:{facility_ref}`. Its committed projector
recognizes facility acquisition, maintenance lifecycle events, and INF-1AE's
fixed `facility_repaired` / `facility_repair_compensated` pair. The projected
`Facility` fact has `facility_ref`, `plot_ref`, `facility_kind`, `condition`,
and `revision`. The verified repair contract changes condition only.

No current Construction owner contract supplies all fields needed for a
facility transform:

| Required transform contract field | Current evidence | Disposition |
| --- | --- | --- |
| admitted business source and permitted actor | no generic committed transform source fact or typed action intent | missing for the generic class |
| target facility-kind truth and projection semantics | the fixed INF-1AF `bakery -> bakery_reinforced` event/projector transition exists; no general kind transition exists | missing for the generic class |
| event family and static catalog contract | the fixed INF-1AF catalog row exists; no generic transform row exists | missing for the generic class |
| source/target revision and idempotency rule | INF-1AF pins one source/current facility stream; no general transform rule exists | missing for the generic class |
| scoped outbox, append receipt, full/tail replay | INF-1AF has independent evidence; repair-only evidence cannot be reinterpreted as generic transform evidence | missing for the generic class |
| terminal, reversal, or compensation semantics | INF-1AF is terminal; repair compensation restores condition only and cannot become generic transform reversal | missing for the generic class |

The three resumed existing-owner discovery audits remain terminal evidence for
the old broad discovery lane. This row does not repeat that search: it tests
the already-known Construction owner against the exact transform contract and
finds the contract incomplete.

## Decision

The generic `INF-1AF` transform class remains `owner-contract blocked`.
The separately approved `bakery -> bakery_reinforced` contract is the one
implemented narrow vertical. Preserve zero-write for every other transform
request. No new Construction owner was created.

No caller may select a target stream, event family, replacement facility kind,
privacy scope, receipt rule, or compensation rule. `SettlementPlan` cannot
fill those gaps, and the immutable governed catalog cannot be used as a
runtime registration mechanism.

## Unblock Condition

Each further generic-class member may resume only after a row-specific approved
contract names one exact transform source, fixed target kind, Construction
event vector, owner revision rules, authority/project privacy, idempotency
shape, append-derived receipt, full/checkpoint-tail replay, and
terminal/reversal semantics. INF-1AF is one such approved vertical; it does
not unblock another facility-action row.

## Transition To Owner-Admission Design

The terminal existing-owner audit is durable evidence, not a failed
implementation attempt. The approved federation mechanism permits the attached
row-specific [bakery reinforcement design](2026-08-17-inf-1af-bakery-reinforcement-owner-admission-design.md)
and [plan](../../../../plans/world-character-siming-authority-mainline/inf-1/2026-08-17-inf-1af-bakery-reinforcement-owner-admission-plan.md).
They extend the existing Construction owner only and define one fixed
`bakery -> bakery_reinforced` capability. Following explicit approval, the
runtime/catalog/projector, focused tests, and independent Harness were added
for that exact capability only. This does not authorize generic transforms,
payment/material truth, or a second Construction owner.
