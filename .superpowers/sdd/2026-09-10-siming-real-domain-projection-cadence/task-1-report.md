# Task 1 Report

## Outcome

Implemented the read-only `assemble_committed_population_projections(...)` seam.
It reads committed `GameplayEventStore` events, reuses the existing Production,
Inventory, public Social, and redacted Tax source functions, rejects private,
malformed, stale, and cadence-unpinned rows, deduplicates refs, and returns
deterministically sorted projections.

The assembler contains no Owner, Character Core, event-store append, scheduler,
or package activation call.

## Verification

- `python -m pytest -q backend/tests/test_siming_population_store_projection_assembler.py backend/tests/test_siming_population_production_owner_vertical.py backend/tests/test_siming_population_inventory_vertical.py backend/tests/test_siming_population_social_signal_vertical.py backend/tests/test_siming_population_tax_pressure.py`
  - 22 passed
- `git diff --check`
  - passed

## Commit

`汇编已提交领域群体投影`

## Attention

This task validates the read-only projection assembly seam only. Authorized
cadence publication and real Siming dispatch remain later tasks in the plan.

## Review Fixes

- Source stream refs now use the committed event `stream_id` when present and
  reject mismatched payload stream claims; legacy AuthorityEvent fixtures with
  no stream id retain their declared source ref.
- Public cadence assembly admits only public event visibility, so project and
  organization-summary facts cannot be upcast into the public read set.
- Duplicate projection refs fail closed: every candidate sharing a ref is
  dropped instead of first-wins selection.

Review regression coverage raised the focused suite to 25 passed.

The committed marker is now fail-closed: it may be absent or exactly boolean
`True`; string and numeric values such as `"false"` and `0` are rejected.
The focused suite is 26 passed after this regression coverage.
