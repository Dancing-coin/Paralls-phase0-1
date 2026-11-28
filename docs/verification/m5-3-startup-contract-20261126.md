# M5-3 Startup Contract Exact-Tip Evidence

## Baseline

| Item | Value |
|---|---|
| Worktree | `F:\codex-temp\paralls-v2-thread-a-bond-20261121` |
| Branch | `thread-a/ownership-bond-followup-20261121` |
| Commit | `45480fb2` |
| Python | `D:\Temp\paralls-g0-py312\Scripts\python.exe`, 3.12.2 |
| PYTHONPATH | `F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend` |
| SQLite | Not separately printed in this run; the existing environment records SQLite 3.43.1 |
| Integration | Not modified |

## Verified

The targeted command ran with `PYTHONPATH` set to the current worktree and a new F-drive basetemp:

```text
D:\Temp\paralls-g0-py312\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp=F:\paralls-verification\thread-a\m5-3-startup-contract-20261126-01\pytest-temp backend\tests\test_package_migration_runtime.py backend\tests\test_gameplay_event_schema_registry.py backend\tests\test_m6_5_siege_runtime.py
```

Raw output: `F:\paralls-verification\thread-a\m5-3-startup-contract-20261126-01\pytest.log`.

Result: `71 passed, 6 warnings, exit 0`.

| Selection | Result | Raw output |
|---|---|---|
| M5-3 registration | `selected=22 problems=0 improvements=0` | `F:\paralls-verification\thread-a\m5-3-startup-contract-20261126-01\m5-3\` |
| Ownership | `selected=24 problems=0 improvements=0` | `F:\paralls-verification\thread-a\m5-3-startup-contract-20261126-01\ownership\` |

The targeted tests cover real county siege package directories, complete deployment manifest loading, partial-manifest rejection, trusted content-hash rejection, world-pinned M6-5 consumer construction, and the compatibility path when deployment settings are absent.

## Incomplete

The frozen shared-replay selection was started with the same exact-tip worktree and output root. Batches 0000 through 0009 completed and batch 0010 stopped at the previously observed PowerShell listener lookup stall. The runner was interrupted after no aggregate output for about four minutes. The raw partial output remains under:

`F:\paralls-verification\thread-a\m5-3-startup-contract-20261126-01\shared-replay\`

Shared-replay is **not verified** for this commit. No external process was stopped.

## Production boundary

This evidence verifies the deployment contract and startup archive assembly in code. It does not verify a production manifest source, production Gate values, a production server startup, cross-language hash canonicalization, or UE transport. Full backend regression and a complete siege playthrough were not run.

## Conclusion

## Current A-tip revalidation, 2026-11-27

At A tip `e09bcf1a`, the focused package migration, EventSchema registry, and M6-5 siege runtime command returned **74 passed, 6 warnings** with Python 3.12.2, the A-worktree `PYTHONPATH`, and explicit F-drive pytest basetemp.

| Selection | Current-tip result | Raw output |
|---|---|---|
| M5-3 package migration, 23 nodes | `selected=23 problems=0 improvements=0` | `F:\paralls-verification\thread-a\m5-3-current-tip-20261127-01\m5-3\` |
| Ownership, 24 nodes | `selected=24 problems=0 improvements=0` | `F:\paralls-verification\thread-a\m5-3-current-tip-20261127-01\ownership\` |
| shared-replay, 990 nodes | `selected=990 problems=0 improvements=0` | `F:\paralls-verification\thread-a\m5-3-current-tip-20261127-01\shared-replay\` |

The current selection file contains 23 nodes. This current-tip result supersedes the older 22-node registration count above for this selection. Production manifest trust source, cross-language hash canonicalization, production Gate values, deployment target, UE transport, and complete siege execution remain unverified. The current-tip full backend suite was not rerun.

| Area | Level |
|---|---|
| Deployment contract validation | Verified |
| M6-5 archive consumer assembly | Verified by targeted tests |
| M5-3 frozen registration selection | Verified |
| Ownership selection | Verified |
| Shared-replay 990 selection | Not verified |
| Production deployment and UE runtime | Not verified |

## Current A-tip revalidation, 2026-11-28

The tested code state is A commit `4cf42fa33be54c4d0f5432bcc19cced35a0f6e04`; the subsequent `d24c303e` commit changes documentation only. Python is `3.12.2` at `F:\codex-temp\thread-a-python312\Scripts\python.exe`, `app.__file__` resolves under this A worktree, and SQLite is `3.43.1`. Environment output: `F:\paralls-verification\thread-a\m5-3-current-tip-recheck-20261128-01\environment.log`.

The focused package migration, EventSchema registry, M6-5 runtime startup, and RulePack validator tests returned `213 passed, 6 warnings`, exit 0. Full output: `F:\paralls-verification\thread-a\m5-3-current-tip-recheck-20261128-01\focused.log`.

At the same code state, the M5-3 registered selection returned `selected=23 problems=0 improvements=0`; frozen Ownership and shared-replay returned `24/0/0` and `990/0/0`. Those comparisons are retained with the M3-1 current-tip sweep at `F:\paralls-verification\thread-a\m3-1-four-owner-current-20261128-01\selection-runs\m5-3-package-migration\`, `...\selection-runs\frozen-ownership\`, and `...\selection-runs\frozen-shared-replay\`.

This is local code verification only. The external trusted manifest source, target-world deployment binding and invocation path, production Gate profile, cross-language canonical hash contract, production startup, and UE transport remain unverified. The approved `pack.migrated` classification remains an L4 platform control-plane event; no gameplay Owner was added. M5-3/M5 remain in progress, and the full backend suite was not run.

P-1 scan of the staged documentation additions found zero hits across five credential-pattern families. Raw output: `F:\paralls-verification\thread-a\m5-3-current-tip-recheck-20261128-01\p1-scan.log`.
