# INF-1Q Finite Lifecycle Contract Closure

Status: `verified bounded closure`

Date: `2026-08-15`

## Decision

INF-1Q consolidates only the lifecycle metadata already admitted by earlier
INF-1 verticals into one immutable reader. It does not add a state, effect,
owner, stream, event family, scheduler, or writer.

The closed reader contains exactly these existing contracts:

| Contract | Existing owner | Existing stream | Scope |
| --- | --- | --- | --- |
| cold, dehydrated, overheated state lifecycles | `SurvivalAuthority` | `gameplay:survival:{actor_ref}` | project |
| maintenance state lifecycle | `ConstructionProductionAuthority` | `gameplay:construction_production:{facility_ref}` | project |
| frosted crop-state lifecycle | `EcologyHazardAuthority` | `gameplay:ecology:{region_ref}` | project |
| wage-accrual obligation lifecycle | `EconomyAuthority` | `gameplay:economy:wage:{worker_ref}` | project |

Each entry fixes its existing event family, terminal operations, outbox topic,
revision-vector rule, idempotency strategy, and named replay reader. The
Survival dispel/recovery and Construction maintenance-dispel actions remain
action metadata attached to their existing state contracts. They are not new
effect rows.

## Authority Boundary

The reader is admission data only. Existing owner authorities retain fragment
construction and the sole formal write path:

`owner -> GameplayCommandEnvelope / SettlementPlan -> GameplayEventStore.append_batch() -> outbox/replay -> scoped projection`.

It exposes no registration method and no caller-selected owner, stream, event,
projection, or action. Unknown rows, action mismatches, and malformed contract
metadata are rejected before append. Ecology frost remains owner-local and is
not added to `settle_registered_state()`.

## Acceptance Evidence

Focused tests and the package Harness must independently prove immutable
six-contract shape, owner/action admission, unknown-row zero-write, per-owner
revision/privacy/idempotency fences, and the existing full/checkpoint-tail
replay readers. Existing row Harnesses remain the proof of domain semantics.

The 2026-08-15 package report records twelve independent passing selectors in
`.harness/verification/infra-finite-lifecycle-contract-closure-report.json`.

## Non-goals

- New effect/state rows or caller-open registration.
- Generic lifecycle dispatch, generic actions, or an additional writer.
- Construction repair/transform/payment semantics.
- Ecology semantic dispatch beyond the existing frost owner-local path.
- SOC, GAME, P6, or P7 work.
