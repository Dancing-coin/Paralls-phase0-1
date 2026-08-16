# INF-2R Payroll Owner-Contract Catalog Design

Status: `implemented and independently verified; broader INF-2 remains incomplete`

## Purpose

INF-2P already proves one real payroll and operating-window vertical slice,
but an isolated proof is not a reusable INF admission boundary. INF-2R records
its two existing owner writes in the immutable governed contract catalog and
makes each affected authority validate its own row before it constructs an
envelope, plan, fragment, or append batch.

This is not a generic payroll policy, cross-domain coordinator, scheduler, or
second receipt store. The catalog remains source-controlled and read-only.

## Owner Contract Matrix

| Contract | Sole append owner | Streams and event family | Scope / replay / receipt |
| --- | --- | --- | --- |
| `inf:organization-operating-window@1` | `OrganizationAuthority` | `gameplay:organization:window:{window_ref}`; `operating_window_opened`, `operating_window_closed`, `operating_window_due_recorded` | fixed project/authority-only Organization outbox categories; `_operating_window_state` replay reader; one `append_batch()` result |
| `inf:economy-wage-payment@1` | `EconomyAuthority` | `gameplay:economy:wage:{worker_ref}` plus `gameplay:economy`; `wage_paid`, `account_debited`, `account_credited` | actor-scoped wage plus authority-only account outbox; `EconomyProjector`; one multi-stream `append_batch()` result |

`mixed` is catalog metadata only. It describes the already existing fixed
project/authority-only categories on the window batch and actor/authority
categories on the Economy wage-payment batch; it does not permit a caller to
invent a visibility policy.

## Admission And Failure Semantics

Each owner calls `GovernedAuthorityContractCatalog.require_operation()` with
its immutable contract reference, principal, stream IDs, event types and fixed
visibility category immediately before generating the existing formal batch.
An unknown, owner-, stream-, event-, or scope-mismatched row is rejected before
`GameplayEventStore.append_batch()`. No caller can register, edit, compose, or
select a catalog row.

The organization window row preserves its existing project/authority-only
visibility validation. The Economy payment row preserves account currency,
funds, revision, idempotency, and actor/authority outbox rules. Both retain
their existing append-derived receipts and full/checkpoint-tail replay paths.

## Non-goals

- caller-open policy registration;
- arbitrary payroll rules, account reservation, or business settlement;
- a generic effect/state matrix or ecology consumer registry;
- population, NPC, social truth, branch promotion, SOC-1, GAME-1, P6, or P7.

INF-2R makes future expansion explicit: each new row requires a named existing
owner, stream, event family, scoped projection, revision/idempotency rule,
append-derived receipt, replay reader, focused RED test, and independent
Harness assertion before source control may admit it.
