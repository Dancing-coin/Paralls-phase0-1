# INF Governed Authority Contract Catalog Design

Status: `implemented and verified; extended 2026-08-16`

## Purpose

The verified INF rows are real but distributed across independent authority
implementations. This package establishes one immutable, read-only catalog of
the existing cross-INF contracts. It is an admission boundary, not a runtime,
registry writer, scheduler, event store, bus, or coordinator.

## Contract model

Each entry is source-controlled and names: its `contract_ref`, existing sole
writer, permitted stream pattern, event family, projection privacy, receipt
source, replay reader, and allowed command surface. A caller cannot register,
edit, select, or combine an entry. `require_contract()` rejects unknown or
kind-mismatched references before an authority reaches `append_batch()`.

The initial catalog contains only already-real rows:

| Contract | Existing writer | Purpose |
| --- | --- | --- |
| `inf:state-lifecycle@1` | Survival, Construction, Ecology, Economy | references the closed lifecycle matrix; it is not a generic effect router |
| `inf:government-inspection-policy@1` | `GovernmentAuthority` | fixed inspection policy register/revoke |
| `inf:government-inspection-promotion@1` | `GovernmentAuthority` | fixed durable passed-inspection revalidation to the existing production inspection row |
| `inf:simple-debt-settlement@1` | `DebtAuthorityService` | fixed debt issue/repayment settlement |
| `inf:weather-front-organization-supply@1` | `OrganizationAuthority` | fixed Ecology evidence to Organization commitment edge |
| `inf:weather-front-organization-supply-fanout@1` | `OrganizationAuthority` | fixed Ecology evidence to two exact existing Organization commitments in one owner batch |
| `inf:organization-supply-promotion@1` | `OrganizationAuthority` | fixed branch scenario revalidation to production commitment |
| `inf:organization-operating-window@1` | `OrganizationAuthority` | fixed organization window open/close/due lifecycle |
| `inf:economy-wage-payment@1` | `EconomyAuthority` | fixed paid-wage and account debit/credit batch |
| `inf:weather-front-construction-maintenance@1` | `ConstructionProductionAuthority` | fixed one/two-facility weather-front maintenance rows |
| `inf:weather-front-economy-quote@1` | `EconomyAuthorityService` | fixed weather-front source-pinned quote row |

## Enforcement

Each participating owner resolves its own fixed reference immediately before
constructing a formal envelope/plan. The catalog validates only immutable
metadata; the owner still validates domain inputs, revision, privacy,
idempotency and source evidence, then is the only code that may append.

`BranchPreviewAuthority` remains evidence-only. Promotion is a fresh,
revision-pinned Organization authority operation, never a branch writeback.
The existing Government passed-inspection promotion is equivalently
revision-pinned and must validate `inf:government-inspection-promotion@1`
before it builds a fragment. Its dedicated proof is
`infra-government-promotion-owner-contract-catalog`; neither row supplies a
generic promotion API.
Government policy is registered only by Government; debt settlement remains
Debt-owned; Ecology may only provide the already-admitted opaque evidence.
The two payroll rows are separately rechecked by
`infra-payroll-owner-contract-catalog`; the existing Organization and Economy
authorities validate their own row immediately before the existing append path.
INF-3L separately records and enforces the Construction, Organization and
Economy weather-front rows; it does not make new consumers eligible.

## Non-goals and remaining blockers

This does not make arbitrary policy registration, arbitrary cross-domain
atomic settlement, arbitrary ecology fanout, arbitrary promotion, or complete
population simulation valid. A future expansion must add one source-controlled
entry with its owner/stream/event/projection/receipt/replay evidence and an
independent Harness assertion. Population/NPC/social truth ownership remains
absent and complete group simulation remains deferred.
