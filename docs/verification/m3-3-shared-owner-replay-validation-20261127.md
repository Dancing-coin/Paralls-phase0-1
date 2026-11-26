# M3-3 shared Owner replay receipt validation

## Scope

Code commit: `78fa4548` (`feat-owner-replay-validation`).

The shared `replay_duplicate` path previously returned the durable idempotency result without resolving its `committed_event_ids` or checking the related transaction. Credential had a local R2 check, while the other callers did not. This increment moves the common transaction, event-count, event-resolution, event-identity, sequence-range, and resulting-revision checks to the A-owned shared Owner base. Credential retains its legacy/current event-type contract through the helper's optional expected event types.

Production `OwnerCommitBuilder`, store schemas, event names, payloads, and event semantics are unchanged. Errors preserve caller-specific replay error codes.

## TDD evidence

Python 3.12.2, `PYTHONPATH` pointed at this A worktree's `backend`, and the `app` import check resolved to:

```text
F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend\app\__init__.py
```

Three new Ownership retry tests were first run against the previous helper implementation:

```text
test_owner_duplicate_rejects_unresolvable_committed_event_id: FAILED, DID NOT RAISE
test_owner_duplicate_rejects_committed_event_count_mismatch: FAILED, DID NOT RAISE
test_owner_duplicate_rejects_missing_transaction: FAILED, DID NOT RAISE
```

After the implementation, the same three tests passed as part of the focused run.

## Verification

All outputs are retained on F under `F:/paralls-verification/thread-a/`.

| Check | Result |
|---|---|
| A shared mechanism and primary domain tests: `test_owner_runtime_base.py`, `test_owner_commit_builder.py`, `test_ownership_runtime.py`, `test_ownership_bond_lifecycle.py`, `test_pool_runtime.py`, `test_holdings_runtime.py`, `test_credential_runtime.py`, `test_credential_replay_integrity.py`, `test_credential_reference_rebuild.py`, `test_credential_reference_chain.py`, `test_credential_v2_land_right_revision_vector.py` | `112 passed, 2 warnings` |
| Other shared-helper callers: Debt, Contract, Gift, Fixed Offer, Package Migration, Production Package Registry, Adventure Basic scenario 4 / LandRight, and Ownership-Contract-Debt sample | `87 passed, 6 warnings` |
| New registered M3-3 selection | `selected=9 problems=0 improvements=0` |
| Frozen Ownership | `selected=24 problems=0 improvements=0` |
| Frozen Modifier | `selected=12 problems=0 improvements=0` |
| Frozen Equipment | `selected=87 problems=0 improvements=0` |
| Frozen Inventory | `selected=56 problems=0 improvements=0` |
| Frozen shared-replay | `selected=990 problems=0 improvements=0` |

Focused raw output: `F:/paralls-verification/thread-a/m3-3-r2-current-20261127-01/` and `F:/paralls-verification/thread-a/m3-3-r2-callers-20261127-01/`. Selection comparisons and raw batch logs: `F:/paralls-verification/thread-a/m3-3-r2-selection-20261127-01/` and `F:/paralls-verification/thread-a/m3-3-r2-frozen-20261127-01/`.

The registered selection was rerun on exact code tip `78fa4548`: `selected=9 problems=0 improvements=0`. Raw output: `F:/paralls-verification/thread-a/m3-3-r2-exact-tip-20261127-01/`.

## Compatibility and limitations

- Exact retries continue to return the original durable receipt with `duplicate_replayed` and do not append events.
- Credential's v1-to-v2 legacy retry path and all three Credential commands are covered by `test_credential_replay_integrity.py`.
- Invalid receipts are rejected before a new append. The new Ownership corruption tests assert the committed event stream is unchanged.
- This increment validates shared-helper callers. Replay implementations that do not call `replay_duplicate` remain outside this increment and require separate M3-3 inventory.
- Full backend suite was not run for this increment. Current known A-tip full-suite evidence remains `10,761 passed, 5 failed, 2 skipped, 2 xfailed, 227 warnings`, exit 1, from H-A-129.

## U status

This is a shared mechanism increment, not an Owner/domain migration. It provides current focused R2 evidence and a permanently registered selection. It does not claim completion of M3-3 or any domain's U1-U11.
