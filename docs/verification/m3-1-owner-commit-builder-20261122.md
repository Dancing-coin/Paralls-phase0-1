# M3-1 OwnerCommitBuilder verification

Date: 2026-11-22

## Scope and implementation

`OwnerCommitBuilder` assembles only the common append-batch envelope. Ownership and Credential continue to supply their transaction IDs, idempotency key shape, payload digest, revision maps, event sequence, and `result_digest`. The builder does not compute or normalize domain values. Optional `read_stream_revisions` is copied only when the caller supplies it.

Production call sites migrated in this unit:

- `OwnershipAuthorityService._append` in `backend/app/gameplay/ownership_runtime.py`.
- Credential issue append in `backend/app/gameplay/credential_runtime.py`.

No event schema, persisted event payload, store implementation, or rejection path changed. The migration plan's M3-1 instruction to keep `result_digest`, revision naming, and idempotency-key shape caller-defined was followed. The older shared Owner base document describes the same non-unification constraint and says caller-specific result digests must remain intact.

## Verification environment

| Item | Value | Status |
|---|---|---|
| Worktree | `F:\codex-temp\paralls-v2-thread-a-bond-20261121` | verified |
| Branch / HEAD | `thread-a/ownership-bond-followup-20261121` / `7defd05b7d2b9f7b8038b8240901e6933076cd64` | verified before M3-1 commit |
| Python | 3.12.2, `D:\Temp\paralls-g0-py312\Scripts\python.exe` | verified |
| `app.__file__` | `F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend\app\__init__.py` | verified |
| SQLite | 3.43.1 | verified; frozen WAL checkpoint cases remain environment-unverified |
| Verification outputs | `F:\paralls-verification\thread-a\` | verified |

## Unit and frozen-selection tests

Command for the focused tests:

```powershell
& 'D:\Temp\paralls-g0-py312\Scripts\python.exe' -m pytest -q --basetemp <new F-drive directory> backend/tests/test_owner_commit_builder.py backend/tests/test_ownership_runtime.py backend/tests/test_credential_runtime.py
```

Result: **21 passed, 2 warnings**, exit code 0. The warnings are Starlette/httpx deprecations.

Frozen selections used `docs/verification/absorb-main-3bf3418e/compare_selection.py`:

| Selection | Result | Output |
|---|---|---|
| ownership, 24 nodes | `selected=24 problems=0 improvements=0`, exit 0 | `F:\paralls-verification\thread-a\m3-1-ownership-20261122-f2b6c311\` |
| shared-replay, 990 nodes | `selected=990 problems=0 improvements=0`, exit 0 | `F:\paralls-verification\thread-a\m3-1-shared-replay-20261122-6d1a9e57\` |

## Full-suite run and diagnosis

The G0 runner froze 10,446 collected tests at HEAD `7defd05b7d2b9f7b8038b8240901e6933076cd64`. With a short pytest temporary root on F drive, the full run exited 1 with **24 failed, 10,418 passed, 2 skipped, 2 xfailed, 239 warnings**. The 24 failed nodes are the existing M1-1 full-run failures. A comparison by `(node, phase, error type)` against `F:\paralls-verification\thread-a\m1-1-full-ae7d650e-de7850922c1140ae9b19a7483ab7281b\full\results.json` found `new_only=0 old_not_in_new=0`.

- Console: `F:\paralls-verification\thread-a\m3-1-full-shorttemp-20261122-7defd05b-58a2-console.log`
- Results, frozen test manifest, environment, and JUnit: `F:\paralls-verification\thread-a\m3-1-full-shorttemp-20261122-7defd05b-58a2\`
- Pytest temporary root: `F:\paralls-verification\thread-a\m3t\`

An earlier full run used a long pytest temporary root and reported 53 failures and 10,389 passes. All 29 extra failures passed in diagnostic reruns, 28 in a 107-test four-file run and one capacity test separately. The short-root full run then reproduced exactly the same 24 `(node, phase, error type)` failures as M1-1, confirming the earlier 29 were temporary-path artifacts. The earlier raw run is retained at `F:\paralls-verification\thread-a\m3-1-full-20261122-7defd05b-926214f97f6444a0b088f6effd24cf5a-console.log` and its output directory.

## U1-U10

| DoD | Status | Evidence or gap |
|---|---|---|
| U1 Owner declaration and classification | Static only | Existing Ownership and Credential ownership preserved; no classification decision made here. |
| U2 FactType declarations and deviations | Not done | M3-1 does not add Owner declarations or FactTypes. |
| U3 Event registration and P-3 | Not applicable | No event types changed. |
| U4 Shared mechanism adoption | Verified | Builder used by Ownership and Credential; focused behavior tests passed. |
| U5 R1/R2/R3 | Not done | Outside M3-1 scope. |
| U6 Reader list and event compatibility | Not applicable | No persisted event fields or schema changed. |
| U7 Subject-facing read classification | Static only | No read visibility behavior changed. |
| U8 Rule-pack completeness and Resolver registration | Not done | Outside M3-1 scope. |
| U9 Regression verification | Verified with baseline failures | Focused tests, two frozen selections, and full-suite comparison found no new failure. The full run retains 24 known failures and SQLite WAL environment gaps. |
| U10 Evidence | Verified | This record and retained raw outputs above. |

M3-1 is a shared-mechanism unit only. It does not establish completion of Architecture v2 or any Owner migration.

## Current-tip revalidation, 2026-11-26

At A tip `9cee2f25911dcc6221c43e89b9b42ace38ae3d06`, the focused command returned **23 passed, 2 warnings**. Python was 3.12.2 and `app.__file__` resolved to the current A worktree backend.

| Selection | Current-tip result | Raw output |
|---|---|---|
| ownership, 24 nodes | `selected=24 problems=0 improvements=0` | `F:\paralls-verification\thread-a\m3-1-current-tip-20261126-01\ownership\` |
| shared-replay, 990 nodes | `selected=990 problems=0 improvements=0` | `F:\paralls-verification\thread-a\m3-1-current-tip-20261126-01\shared-replay\` |

This is current-tip focused and frozen-selection evidence. The full backend suite was not rerun at this tip. M3-1 remains `待门禁`.

## Current-tip revalidation, 2026-11-27

At A tip `3978f4f9ecc02990e2be8d09681a3beaed40ad58`, the focused command returned **23 passed, 2 warnings**, using Python 3.12.2 and the A-worktree `PYTHONPATH`. The warnings are the existing Starlette/httpx deprecation warnings.

| Selection | Current-tip result | Raw output |
|---|---|---|
| ownership, 24 nodes | `selected=24 problems=0 improvements=0` | `F:\paralls-verification\thread-a\m3-1-current-tip-20261127-02\ownership\` |
| shared-replay, 990 nodes | `selected=990 problems=0 improvements=0` | `F:\paralls-verification\thread-a\m3-1-current-tip-20261127-02\shared-replay\` |

The full backend suite was not rerun for this M3-1 check. The latest recorded A-tip full suite remains `10,761 passed, 5 failed, 2 skipped, 2 xfailed, 227 warnings`, exit code 1, and is a merge-state result rather than slice evidence. M3-1 remains `待门禁`.
