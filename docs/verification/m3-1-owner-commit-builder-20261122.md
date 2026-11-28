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

## Current-tip revalidation, 2026-11-27 follow-up

At A tip `caa062aadc6726687a6f220bd3e450334e457629`, the focused command returned **23 passed, 2 warnings**. Python was `3.12.2`, SQLite `3.43.1`, and `app.__file__` resolved to the current A worktree backend.

| Selection | Current-tip result | Raw output |
|---|---|---|
| ownership, 24 nodes | `selected=24 problems=0 improvements=0` | `F:\paralls-verification\thread-a\m3-1-current-tip-20261127-03\ownership\` |
| shared-replay, 990 nodes | `selected=990 problems=0 improvements=0` | `F:\paralls-verification\thread-a\m3-1-current-tip-20261127-03\shared-replay\` |

Focused output is `F:\paralls-verification\thread-a\m3-1-current-tip-20261127-03\focused.log`; environment output is in `environment.log`. Pytest temporary files and selection outputs used the new F-drive run directory. Full backend suite was not run. M3-1 remains `待门禁`.

## Current-tip revalidation, 2026-11-28

At A tip `a1be4c259b766f1fe416fbce415fa1c7b723b30b`, the focused OwnerCommitBuilder, Ownership, and Credential tests returned **23 passed, 2 warnings**. Python was `3.12.2`, SQLite `3.43.1`, and `app.__file__` resolved to the A worktree backend.

| Selection | Current-tip result | Raw output |
|---|---|---|
| ownership, 24 nodes | `selected=24 problems=0 improvements=0` | `F:\paralls-verification\thread-a\m3-1-current-tip-20261128-01\ownership\`; summary `ownership.log` |
| shared-replay, 990 nodes | `selected=990 problems=0 improvements=0` | `F:\paralls-verification\thread-a\m3-1-current-tip-20261128-01\shared-replay\`; summary `shared-replay.log` |

Focused command: `F:\codex-temp\thread-a-python312\Scripts\python.exe -B -m pytest -q -p no:cacheprovider --basetemp F:\paralls-verification\thread-a\m3-1-current-tip-20261128-01\pytest-temp backend/tests/test_owner_commit_builder.py backend/tests/test_ownership_runtime.py backend/tests/test_credential_runtime.py`. Full output: `F:\paralls-verification\thread-a\m3-1-current-tip-20261128-01\focused.log`. Full backend suite was not run. This revalidates the shared mechanism at the current tip; M3-1 remains `待门禁`.

## Current-tip revalidation, 2026-11-28 follow-up

At A tip `4cf42fa33be54c4d0f5432bcc19cced35a0f6e04`, static call-site inspection found `OwnerCommitBuilder` used by Ownership (`ownership_runtime.py`), Credential (`credential_runtime.py`), Holdings (`holdings_runtime.py`), and Pool (`pool_runtime.py`). Package migration remains a platform-control event path and uses its existing atomic batch builder. No code changed in this revalidation.

Environment: Python `3.12.2` at `F:\codex-temp\thread-a-python312\Scripts\python.exe`; `app.__file__` resolved to `F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend\app\__init__.py`; SQLite `3.43.1`. Environment output: `F:\paralls-verification\thread-a\m3-1-four-owner-current-20261128-01\environment.log`.

Focused command:

```powershell
F:\codex-temp\thread-a-python312\Scripts\python.exe -B -m pytest -q -p no:cacheprovider --basetemp F:\paralls-verification\thread-a\m3-1-four-owner-current-20261128-01\pytest-temp backend/tests/test_owner_commit_builder.py backend/tests/test_ownership_runtime.py backend/tests/test_credential_runtime.py backend/tests/test_holdings_runtime.py backend/tests/test_pool_runtime.py
```

Result: `63 passed, 2 warnings`, exit 0. Full output: `F:\paralls-verification\thread-a\m3-1-four-owner-current-20261128-01\focused.log`.

All 58 registered selections and the frozen five selections were run serially through `docs/verification/absorb-main-3bf3418e/compare_selection.py`: 63 invocations returned exit 0, each with `problems=0 improvements=0`. Frozen selection counts were Ownership 24, modifier 12, equipment 87, inventory 56, and shared-replay 990, totaling 1,169. Per-selection raw outputs and logs are under `F:\paralls-verification\thread-a\m3-1-four-owner-current-20261128-01\selection-runs\` and `selection-logs\`; exact summaries are in `selection-summary.txt`.

The full backend suite was not run. U4 is revalidated at current tip across four A-owned consumers; U1 remains static, U2/U5/U8 remain outside this shared-mechanism unit, U3/U6 are not applicable because no event schema or persisted event changed, U7 remains static, and U9/U10 have fresh evidence. M3-1 remains `待门禁`; this evidence does not establish completion of Architecture v2 or any Owner migration.

P-1 scan of the staged documentation additions checked assignment-shaped secrets, AWS access keys, GitHub tokens, JWTs, and private-key headers: `patterns-scanned=5 credential-pattern-hits=0`. Raw output: `F:\paralls-verification\thread-a\m3-1-four-owner-current-20261128-01\p1-scan.log`.

## Current A-tip revalidation, 2026-11-28 follow-up

At documentation HEAD `e62ce9d825f4fd1f317c0165203b9b61c3ab34d5`, the backend and packs source tree matches code commit `8bdf01dc4539b3f67898a9c4276fa941be90bdda`; the intervening commit changes only verification and coordination documentation. The M3-1 focused result above remains `63 passed, 2 warnings` at `4cf42fa3`; this follow-up revalidates regression selections against the current source tree.

Python `3.12.2` at `F:/codex-temp/thread-a-python312/Scripts/python.exe`, `PYTHONPATH` points to the A worktree backend, `app.__file__` resolves under that worktree, and SQLite is `3.43.1`. All 59 registered selections and the frozen five selections were run serially with `docs/verification/absorb-main-3bf3418e/compare_selection.py`: 64 invocations, 1,575 summed selected nodes including overlap, every invocation exited 0 with `problems=0 improvements=0`. The frozen groups selected 24/12/87/56/990 nodes, totaling 1,169 including overlap. Raw outputs and per-group logs are under `F:/paralls-verification/thread-a/m3-1-current-tip-a5e32538/`; `summary.txt` records every result.

The exact source tree's full backend result is recorded separately in `docs/verification/m1-1-bond-slices-20261122.md` for code commit `8bdf01dc`: `10,837 passed, 5 failed, 2 skipped, 2 xfailed, 227 warnings`, exit 1. The five failed nodes were reproduced on code parent `dbaae2c7` in targeted comparisons. This is a merge-state full-suite result, not an M3-1 slice result or a green full-suite claim.

P-1 scanned the four changed repository documents across five credential-pattern families: `patterns-scanned=5 credential-pattern-hits=0`. Raw output: `F:/paralls-verification/thread-a/m3-1-current-tip-a5e32538/p1-scan.log`.

M3-1 remains `待门禁`. U4 shared-builder adoption is verified across Ownership, Credential, Holdings, and Pool. U1 is static; U2, U5, and U8 are outside this shared-mechanism unit; U3 and U6 are not applicable because no event schema or persisted event changed; U7 is static. No M3-1 completion or Architecture v2 completion is claimed.
