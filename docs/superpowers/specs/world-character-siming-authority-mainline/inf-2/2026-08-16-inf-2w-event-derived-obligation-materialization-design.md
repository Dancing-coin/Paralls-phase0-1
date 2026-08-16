# INF-2W Event-Derived Obligation Materialization

Status: `implemented and verified as a bounded read-only materialization slice; broader INF-2 remains incomplete`

## Contract

`ObligationLifecycleProjection` already rebuilds registered open/retry/terminal
records from the existing event store. INF-2W adds a read-only conversion from
those records to `ScheduledObligation` inputs. Opening-event provenance,
policy, stream, visibility, deterministic idempotency, and the current scoped
revision are derived from the projection; the conversion never appends,
advances a clock, selects an owner, or creates a receipt.

| Field | Fixed boundary |
| --- | --- |
| owner | existing registered owner only |
| source | committed registered opening/retry events |
| projection | existing `ObligationLifecycleProjection` |
| output | `ScheduledObligation` proposal/input only |
| privacy | registration visibility is preserved |
| revision | projection source revision vector |
| replay | full and checkpoint-tail lifecycle reconstruction |
| write path | owner fragment -> existing `GameplayEventStore.append_batch()` only after downstream owner admission |

## Evidence

Focused tests are in
`backend/tests/test_infra_event_derived_scheduled_obligation_materialization.py`.
The independent Harness profile is
`infra-event-derived-obligation-materialization`.

## Non-goals

This does not register policies, run a scheduler, create a settlement writer,
choose a target owner, perform arbitrary cross-domain settlement, or replace
the existing owner fragment/append/outbox/replay spine. Caller-open policy
registration and unsupported owner rows remain zero-write.
