# INF-2C Economy Wage Obligation Implementation Plan

Status: `implemented and verified 2026-08-14; one Economy owner lifecycle row only`

1. [x] Lock the one Economy owner/stream/event/privacy/revision map above and
   add focused failing tests for open, due settlement, duplicate, stale
   revision, invalid scope, terminal zero-write, and checkpoint-tail replay.
2. [x] Add Economy's envelope-backed open event and owner settlement fragment;
   use only the existing `SettlementPlan`, coordinator, and event store.
3. [x] Register the row in the existing lifecycle reader and verify a caller
   `SimulationClock` selects it without creating a scheduler.
4. [x] Add an independent Harness profile with one pytest assertion per
   capability; synchronize the August guide, formal dependency record and
   plan only once fresh evidence is green.
5. [x] Run predecessor Harness, focused tests, docs, diff check, and full
   pytest.
