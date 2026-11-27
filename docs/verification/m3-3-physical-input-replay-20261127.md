# M3-3 signed physical-input replay validation

## Change

Implementation commit: `81e047e0d150732ec068854cd6924be3c084c54f`.

Signed siege physical-input receipts now pass through shared `replay_duplicate` validation before returning an existing result. The caller's expected v1 or v2 event type, command ID, transaction ID, event stream, and exact signed payload are checked. The duplicate check remains before v2 Presence source freshness validation, preserving retries after source heads advance. No event types or payload semantics changed.

## TDD

- Added `test_physical_input_retry_rejects_incomplete_receipt_without_writing` before the implementation.
- Red result: an empty committed-event list was treated as `siege_input_receipt_conflict` rather than a replay-integrity failure.
- Green result: the retry returns `siege_input_replay_event_count_mismatch` without changing the store snapshot.
- Red output: `F:/paralls-verification/thread-a/m3-3-physical-input-red-20261127-01/red.log`.

## Verification

Environment: Python 3.12.2 from `D:\Temp\paralls-g0-py312\Scripts\python.exe`, SQLite 3.43.1, `PYTHONPATH=F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend`, and `app.__file__` resolved to `F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend\app\__init__.py`.

| Check | Result |
|---|---|
| Physical-input, Facility, Presence, and M6-5 siege runtime focused files | `77 passed, 6 warnings` |
| New M3-3 selection | `selected=1 problems=0 improvements=0` |
| M6-5 impact-gate selection | `selected=26 problems=0 improvements=0` |
| Frozen Ownership / Modifier / Equipment / Inventory / shared-replay | `24/0/0`, `12/0/0`, `87/0/0`, `56/0/0`, `990/0/0`; total `1,169` selected nodes with zero differences |
| Full backend suite | Not run |

Focused raw output: `F:/paralls-verification/thread-a/m3-3-physical-input-focused-20261127-01/`. Selection output: `F:/paralls-verification/thread-a/m3-3-physical-input-selections-20261127-01/`.

## Limits

This covers signed evidence receipt replay only. It does not cover Facility or Presence consumer replay, other direct/custom paths, or the full backend suite. M3-3 remains in progress. Production Gate values remain unconfigured pending an authoritative deployment profile.
