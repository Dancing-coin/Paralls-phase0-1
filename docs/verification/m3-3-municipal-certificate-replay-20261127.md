# M3-3 municipal certificate replay validation

## Change

Implementation commit: `7ba82daf` (`feat-ownership-validate-municipal-certificate-replay`).

The municipal drought assessment certificate writer now routes retries through the shared `replay_duplicate` helper. The expected digest is generated from the same complete `GameplayCommandEnvelope` used to construct the settlement batch. The helper validates the stored transaction, command and transaction identity, event count and event references before returning a duplicate receipt. Failures are returned through the path's existing rejected-result shape.

The retry check still occurs before current contract and stream revision checks, preserving exact retry behavior after the original commit advances those streams. Invalid or unavailable advisory references for a reused key continue to return `idempotency_key_reused`.

## TDD

- Added `test_certificate_duplicate_rejects_incomplete_committed_event_receipt` before the implementation.
- Red result: the old path returned `idempotency_key_reused`; expected `ownership_replay_event_count_mismatch`. The test also checks that no transaction or event is appended.
- Green result after routing through `replay_duplicate`: the specific replay error is returned and the durable transaction/event counts remain unchanged.

## Verification

- Python: 3.12.2 from `D:\Temp\paralls-g0-py312\Scripts\python.exe`.
- `PYTHONPATH`: `F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend`; `app.__file__` resolved to `F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend\app\__init__.py`.
- SQLite: 3.43.1.
- Focused municipal certificate, Government acknowledgment, and shared helper tests: `18 passed, 2 warnings`.
- New registered selection: `selected=1 problems=0 improvements=0`.
- Frozen selections: Ownership `24/0/0`, Modifier `12/0/0`, Equipment `87/0/0`, Inventory `56/0/0`, shared-replay `990/0/0` (`selected/problems/improvements`). Total: 1,169 selected, zero differences.
- Full backend suite was not run.

The final focused output is `F:\paralls-verification\thread-a\m3-3-municipal-final-20261127-01\pytest.log`; the red test output is `F:\paralls-verification\thread-a\m3-3-municipal-r2-20261127-01\red.log`. The M3-3 selection output is `F:\paralls-verification\thread-a\m3-3-municipal-cert-final-selection-20261127-01\`. Frozen selection logs are under `F:\paralls-verification\thread-a\m3-3-municipal-frozen-20261127-01\`.

## Status

This closes the identified A-owned municipal certificate retry path against the shared R2 receipt validator. M3-3 remains in progress because repository-wide paths outside the A-owned migrated set have not all been inventoried and validated. This increment does not claim global R2 completion or a full backend regression pass.
