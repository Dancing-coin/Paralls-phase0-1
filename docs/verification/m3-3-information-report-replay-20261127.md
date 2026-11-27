# M3-3 Information report replay validation

## Change

Implementation commit: `094669f1c3069e12ae03b8896c29afb86236013c`.

Information siege-report publication now checks an existing report receipt through shared `replay_duplicate` before validating report content or attempting the follow-on delivery. The existing report payload comparison remains in place, and retries still use the committed publication tick to recover delivery after the report's active window. No report event fields, visibility, or delivery behavior changed.

## TDD

- Added `test_information_report_retry_rejects_incomplete_receipt_without_writing` before the implementation.
- Red result: a receipt with an empty committed-event list returned `information_report_idempotency_key_reused` instead of identifying the incomplete receipt.
- Green result: the retry returns `information_report_replay_event_count_mismatch` without changing the store snapshot or attempting a new delivery.
- Red output: `F:/paralls-verification/thread-a/m3-3-information-report-red-20261127-01/red.log`.

## Verification

Environment: Python 3.12.2 from `D:\Temp\paralls-g0-py312\Scripts\python.exe`, SQLite 3.43.1, `PYTHONPATH=F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend`, and `app.__file__` resolved to `F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend\app\__init__.py`.

| Check | Result |
|---|---|
| Information report and M6-5 siege runtime focused tests | `51 passed, 6 warnings` |
| New M3-3 selection | `selected=1 problems=0 improvements=0` |
| Existing M6-5 Information report source selection | `selected=25 problems=0 improvements=0` |
| Frozen Ownership / Modifier / Equipment / Inventory / shared-replay | `24/0/0`, `12/0/0`, `87/0/0`, `56/0/0`, `990/0/0`; total `1,169` selected nodes with zero differences |
| Full backend suite | Not run |

Focused raw output: `F:/paralls-verification/thread-a/m3-3-information-report-focused-20261127-01/`. Selection output: `F:/paralls-verification/thread-a/m3-3-information-report-selections-20261127-01/`.

## Limits

This covers Information report publication only. Information knowledge-update and signed physical-input replay paths remain separate direct/custom paths. M3-3 remains in progress, and the full backend suite was not run. Production Gate values remain unconfigured pending an authoritative deployment profile.
