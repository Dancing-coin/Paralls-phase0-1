# M3-3 morale refold replay validation

## Change

Implementation commits: `11fd1754` and `2d0ef9c6`.

The casualty-driven Morale refold now validates an existing receipt through the shared `replay_duplicate` helper before returning it. The stored Pool digest is retained for retry lookup because historical roster and life-state reads can legitimately move after the original refold. The helper still validates the durable transaction, command and transaction identity, event count, event references, event type, sequence range and resulting revisions. The previous local receipt-shape checker was removed.

## TDD

- Added `test_morale_duplicate_rejects_incomplete_committed_event_receipt` before the implementation.
- Red result: the old path returned `morale_idempotency_key_reused` for an incomplete committed-event receipt.
- Green result: the helper returns `morale_replay_event_count_mismatch` without appending transactions or events.

## Verification

- Python: 3.12.2 from `D:\Temp\paralls-g0-py312\Scripts\python.exe`.
- `PYTHONPATH`: `F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend`.
- Focused Morale, Pool, and shared helper tests: `27 passed, 2 warnings`.
- New registered selection: `selected=1 problems=0 improvements=0`.
- Frozen selections at the implementation tip: Ownership `24/0/0`, Modifier `12/0/0`, Equipment `87/0/0`, Inventory `56/0/0`, shared-replay `990/0/0` (`selected/problems/improvements`). Total: 1,169 selected, zero differences.
- Full backend suite was not run.

Raw outputs are under `F:\paralls-verification\thread-a\m3-3-morale-r2-20261127-01\` and `F:\paralls-verification\thread-a\m3-3-morale-frozen-20261127-01\`.

## Status

This closes the identified A-owned Morale refold retry path against the shared R2 receipt validator. M3-3 remains in progress because repository-wide direct/custom replay paths are not fully audited.
