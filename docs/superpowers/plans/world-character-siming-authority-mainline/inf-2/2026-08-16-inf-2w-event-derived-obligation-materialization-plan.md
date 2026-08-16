# INF-2W Event-Derived Obligation Materialization Plan

Status: `implemented and verified as a bounded read-only materialization slice; broader INF-2 remains incomplete`

1. [x] Add RED tests for two existing owners, bounded due conversion,
   checkpoint-tail equivalence, privacy and zero-write behavior.
2. [x] Preserve opening-event provenance and current registered stream revision
   in the existing lifecycle projection.
3. [x] Materialize deterministic `ScheduledObligation` inputs without append,
   clock advancement, owner selection, or receipt creation.
4. [x] Add independent Harness assertions and sync the INF-2 status records.

The slice remains a read-only input bridge. It does not close arbitrary policy
registration, generic retry/compensation, or cross-domain business settlement.
