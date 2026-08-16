# INF-1H Registered State Owner Dispatch Design

Status: `implemented and verified as a closed adapter route; broader INF-1 remains incomplete`

## Scope

INF-1H adds one proposal-only entrypoint that resolves an already registered
state/effect row and delegates to its existing domain owner. It does not create
a generic writer, a new event store, or a caller-selected owner.

| Concern | Contract |
| --- | --- |
| Proposer | existing `authority:semantic` |
| Registered rows | the three existing Survival scheduled rows plus the verified Construction maintenance row |
| Dispatch | closed registry route to `SurvivalAuthority` or `ConstructionProductionAuthority` only |
| Write path | owner-built `GameplayCommandEnvelope` -> `SettlementPlan`/existing owner plan -> `GameplayEventStore.append_batch()` |
| Scope | `project` only |
| Rejection | unknown row, mismatched pair/owner/stream/privacy, stale semantic vector, revision conflict, and unsupported lifecycle are zero-write |

The route is a deterministic read of registered policy data. It may not accept
caller-selected adapter names, stream patterns, event families, or projection
scope. The selected owner remains responsible for state resolution, obligation
creation, event construction, idempotency and projection.

Both the dispatch entrypoint and the public owner helpers enforce the exact
closed semantic source vector (`{"semantic": 1}`) before an envelope is built.
This prevents a direct helper caller from bypassing the outer route fence with
a self-consistent stale snapshot.

## Non-goals

This does not admit unregistered state/effect rows, generic expression
execution, a new scheduler/clock, cross-stream atomic receipts, new owner
domains, or broad lifecycle completion. The registry remains closed over the
four already named rows; broader owner coverage remains incomplete.

## Evidence required

Focused tests and an independent Harness profile must separately prove Survival
dispatch, Construction dispatch, unknown-row zero-write, mismatched route
zero-write, duplicate/revision/privacy behavior, and full/checkpoint-tail replay
through the underlying owner projections. The report must state that the route
is only a closed adapter registry, not a generic domain writer.
