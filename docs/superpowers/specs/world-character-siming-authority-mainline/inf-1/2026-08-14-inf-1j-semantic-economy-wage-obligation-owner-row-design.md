# INF-1J Semantic Economy Wage Obligation Owner Row

Status: `implemented and verified as one closed third-owner semantic obligation row; broader INF-1 remains incomplete`

## Scope

INF-1J admits exactly one semantic effect proposal to an existing third-domain
owner:

| Effect | Target | Owner | Stream | Open event | Projection |
| --- | --- | --- | --- | --- | --- |
| `effect:wage_accrual_due` | `character:{worker_ref}` | `EconomyAuthority` | `gameplay:economy:wage:{worker_ref}` | `gameplay.economy.wage_obligation_opened` | project |

The proposal carries the existing wage owner inputs: `accrual_ref`,
`organization_ref`, immutable work-evidence references, positive minor amount,
due tick and policy revision. `EconomyAuthority` remains the only writer and
derives the existing replayable `ScheduledObligation` lifecycle from its open
event.

## Boundaries

- only `authority:semantic`, `project` scope and source revision vector
  `{"semantic": 1}` are admitted;
- the route fixes owner, stream pattern, event type and adapter; callers cannot
  select them;
- snapshot target, expected digest and target worker must agree;
- unregistered effects, malformed wage fields, wrong owner/stream/privacy,
  stale vector and stale revision are zero-write;
- `SemanticSettlementAuthority` delegates to `EconomyAuthority`; only that
  owner builds its `GameplayCommandEnvelope` / `SettlementPlan` and calls the
  existing `GameplayEventStore.append_batch()` path.

## Non-goals

No payment, account balance, generic wage policy, generic effect routing,
cross-stream atomic receipt, scheduler, clock, store, or new Economy truth is
admitted. This is one third-owner semantic row, not completion of a generic
cross-owner matrix.

## Required evidence

Focused tests and an independent Harness profile must separately prove success,
unknown-effect zero write, route/privacy/vector zero write, idempotency,
revision conflict, lifecycle full/checkpoint-tail replay and project-only
outbox scope.

Fresh evidence is recorded by
`.harness/verification/infra-semantic-economy-wage-obligation-report.json`.
