# M3-3 R2 replay path audit

- Snapshot: A branch `thread-a/ownership-bond-followup-20261121` at `ea3c727f6c86e06a9d1ac43ca8a685b43723493a`.
- Verification level: static only. No runtime behavior or tests were changed by this audit.
- Method: `rg` over `backend/app/gameplay` for `replay_duplicate`, `get_by_idempotency`, `get_idempotency_record`, and `duplicate_replayed`. Raw file lists are retained outside the repository under `F:\paralls-verification\thread-a\m3-3-r2-audit-20261127-runtime-files.txt` and `F:\paralls-verification\thread-a\m3-3-r2-audit-20261127-shared-files.txt`.

## A-owned paths

The A-owned migrated Owner paths inspected in this audit are `credential_runtime.py`, `ownership_runtime.py`, `land_right_runtime.py`, `holdings_runtime.py`, `pool_runtime.py`, and `package_migration_runtime.py`. Each imports and calls the shared `replay_duplicate` helper. `credential_reference_chain.py`, `adventure_basic_reference.py`, and `adventure_basic_closure.py` are read/rebuild consumers and do not have a command duplicate path to migrate.

The shared helper is also used by Contract, Debt, Fixed Offer, Gift and other runtime files outside A's current domain ownership. Those files are inventory evidence only. They were not modified because their ownership is outside this thread or explicitly unresolved by `BOUNDARIES.md`.

## Findings

1. The A-owned command paths have a common duplicate receipt validation entry point. The M3-3 code increment therefore covers the A-owned paths listed above at helper level.
2. The repository-wide search found many direct idempotency lookup and custom duplicate-receipt paths that do not call `replay_duplicate`. Several are in shared storage, B-owned domains, or other phase/runtime slices. Their presence prevents a global R2-complete claim.
3. `event_store.py`, `models.py`, `economy_runtime.py`, and `inventory_runtime.py` were inspected only by search and were not edited. Their contracts remain outside this audit's implementation scope.

## Conclusion

This audit provides static evidence for the next M3-3 work split. It does not promote M3-3 to complete, does not change any Owner/runtime contract, and does not establish replay correctness for the direct custom paths. A follow-up needs explicit file ownership and per-domain contracts before changing those paths.
