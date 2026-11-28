# M3-3 Contract fulfillment replay audit

## Finding

`ContractAuthorityService.fulfill_public_milling_session_by_policy` accepts a corrupt durable replay receipt. At `backend/app/gameplay/contract_runtime.py:835-839`, it requires two event IDs but only loads and validates the first event before returning `duplicate_replayed`. The second event reference is not checked on this path.

## Reproduction

- A worktree commit: `5709368f1bf24b69289ced61d9a3e0a0547fad5a`.
- Python: `3.12.2`; `app.__file__` resolved under this A worktree; SQLite `3.43.1`.
- The replay receipt's second committed event ID was changed to `event:missing:second` after the successful commit.
- Retrying returned `committed=True` and `idempotency_status=duplicate_replayed`; the missing event ID remained in the receipt. The store contained 9 events.
- Raw output: `F:/paralls-verification/thread-a/m3-3-contract-r2-static-repro-20261128-01/repro.log`.

## Scope and disposition

`contract_runtime.py` and its domain tests are B-owned per `docs/v2-coordination/BOUNDARIES.md`. A did not modify them. B should validate the full durable transaction and both ordered event references before returning a replay, with an integrity rejection that performs no writes. The adjacent `fulfill_facility_commissioning_review` path reads both committed event references and checks their event types, so this finding is specific to the public-milling fulfillment replay branch.

No tests were run in this audit. M3-3 remains in progress until the owning thread addresses the finding and verifies its domain path.
