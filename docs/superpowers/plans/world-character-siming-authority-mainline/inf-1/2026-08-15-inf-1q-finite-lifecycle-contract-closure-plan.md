# INF-1Q Finite Lifecycle Contract Closure Plan

Status: `completed and verified`

Date: `2026-08-15`

1. [x] Add RED focused tests for the exact six immutable lifecycle contracts,
   admitted actions, and unknown-contract/action rejection.
2. [x] Add a read-only closed lifecycle contract model in `semantic_registry.py`.
   Derive the existing five state contracts through it and encode the already
   admitted wage obligation contract. Do not add registration.
3. [x] Make existing semantic route/action admission read the closed contract where
   it already validates a registered row; owner append code remains owner-local.
4. [x] Add a dedicated Harness profile whose selectors are separate assertions for
   matrix shape, action admission, each owner fence, zero-write, privacy and
   replay.
5. [x] Synchronize the INF-1 tree, root scope/plan, August analysis, harness docs,
   and evidence report. Run focused tests, predecessor Harnesses, docs check,
   `git diff --check`, and full pytest.

## Stop Conditions

Stop with zero runtime changes if any contract would require a new owner,
stream, event family, projection, receipt, or replay reader. In particular,
do not route Ecology frost through generic semantic settlement.
