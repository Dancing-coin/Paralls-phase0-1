# M3-3 Organization membership replay validation

## Change

`OrganizationAuthority.record_admitted_platform_organization_membership` now routes duplicate receipts through the shared `replay_duplicate` validator. The existing domain error `ogs_organization_membership_idempotency_reused` is preserved for a missing transaction, and the rejection performs no additional event writes.

The regression test corrupts the durable append result's transaction reference after the original commit, retries the exact command, and asserts a rejection plus an unchanged event history. No event schema, persisted payload, storage-core code, or command contract changed.

## Verification

- Base A commit: `60d206d46ff03a239d9d46a4d20ccb2527b33b9e`.
- Code commit: `f1f6b30b`.
- Python: `3.12.2`, `F:\codex-temp\thread-a-python312\Scripts\python.exe`.
- `PYTHONPATH`: `F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend`; `app.__file__` resolved inside this A worktree. SQLite: `3.43.1`.
- Focused Organization descriptor/platform and Morale refold tests: `25 passed, 3 warnings`.
- Registered Organization membership selection: `selected=1 problems=0 improvements=0`.
- Frozen selections: ownership `24/0/0`, modifier `12/0/0`, equipment `87/0/0`, inventory `56/0/0`, shared-replay `990/0/0`. Total: 1,169 selected nodes, zero problems or improvements.
- Full backend suite: `10,836 passed, 5 failed, 2 skipped, 2 xfailed, 227 warnings`, exit code 1. All five failed node IDs and failure classes reproduced on clean parent `60d206d4` in a targeted run (`5 failed`). They are unchanged baseline/environment failures, not introduced by this unit.

Raw logs and comparison outputs are under `F:\paralls-verification\thread-a\organization-membership-replay-20261128-01\` through `-04\`. The first two attempts stopped before pytest because the output directory was absent and then because two guessed test paths did not exist; the corrected focused run used the checked-in test files. Full-suite raw output is `-03\pytest-full.log`; parent comparison is `-04\pytest-parent.log`.

## Status

This closes the Organization admitted-membership custom replay path against durable transaction corruption. M3-3 remains in progress because other Owner and custom replay paths still require inventory and validation. Full backend regression is not reported as passing.
