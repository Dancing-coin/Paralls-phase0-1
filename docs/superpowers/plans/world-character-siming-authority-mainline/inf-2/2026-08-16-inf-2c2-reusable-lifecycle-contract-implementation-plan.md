# INF-2C2 Reusable Lifecycle Contract Implementation Plan

Status: `implemented and focused-verified`

1. Add RED tests for the closed terminal-operation lookup, explicit canonical
   registry factory, legacy empty-registration zero-write fence and replay
   equivalence.
2. Add `ObligationLifecycleRegistration.event_type_for()` and route lifecycle
   admission checks through it without changing event families.
3. Add `ObligationSettlementCoordinator.from_closed_registry()` while
   preserving the legacy empty constructor behavior.
4. Run the reusable lifecycle, existing Survival/Economy lifecycle and
   registration-admission suites.
5. Record independent Harness checks and update the INF audit/status indexes.

Completion condition: two existing owner families use the same closed
registration/projection contract; unknown and forged rows remain zero-write;
full and checkpoint-tail event-derived replay are equivalent; no second writer,
store, scheduler or truth owner is introduced.
