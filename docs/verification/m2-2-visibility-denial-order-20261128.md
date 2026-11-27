# M2-2 visibility denial ordering

## Scope

- Code commit: `95a56461b7502f9c9d681c9c8429c3c6575d51ed`.
- `GameplayReadAs` now checks unsupported delay/distortion metadata and `secret`/`debug_only` classes before dispatching to a domain reader. A FactType without a reader therefore receives the contract-specific visibility error rather than `read_as_fact_type_reader_unavailable`.
- This increment does not add a reader, resolve principal membership, or make non-Information facts queryable.

## Test-driven evidence

- RED: the new non-Information secret FactType assertion failed with actual `read_as_fact_type_reader_unavailable`, expected `read_as_visibility_forbidden`. Raw output: `F:/paralls-verification/thread-a/m2-2-read-as-metadata-order-20261128-07/red.log`.
- GREEN: `python -B -m pytest -q -p no:cacheprovider backend/tests/test_siege_information_runtime.py backend/tests/test_information_replay_checkpoint.py backend/tests/test_websocket_connection_context.py` returned `32 passed, 6 warnings`, exit 0. Python `3.12.2`, SQLite `3.43.1`, and `app.__file__` under the A worktree were verified. Raw output: `F:/paralls-verification/thread-a/m2-2-read-as-metadata-order-20261128-08/focused.log`.

## Regression evidence

- All 47 registered selections returned exit 0 with `problems=0 improvements=0`. The updated `m2-2-information-read-as` selection contains the regression node. Raw logs: `F:/paralls-verification/thread-a/m2-2-read-as-metadata-order-20261128-03/`.
- Exact-code-commit rerun of the updated M2-2 selection returned `selected=3 problems=0 improvements=0`. Raw output: `F:/paralls-verification/thread-a/m2-2-read-as-metadata-order-20261128-10/selection.log`.
- Frozen selections returned ownership `24/0/0`, modifier `12/0/0`, equipment `87/0/0`, inventory `56/0/0`, and shared-replay `990/0/0` for `selected/problems/improvements`. The five groups contain 1,169 selected nodes, including overlap. Raw logs: the same selection output directory.
- Full A-tip backend run returned `10,813 passed, 6 failed, 2 skipped, 2 xfailed, 227 warnings` in `2130.69s`, exit 1. The six failed node IDs were rerun at parent `f709f82eb041affad7e99f39e5e33c3f479ba914`, where the exact same six nodes failed. Current and parent raw logs: `F:/paralls-verification/thread-a/m2-2-read-as-metadata-order-20261128-05/full.log` and `F:/paralls-verification/thread-a/m2-2-read-as-metadata-order-20261128-06/parent-failures.log`.
- The six failures are the missing optional `tokenizers` package, the character shared-pool wake test, Task45 and Task8 Godot type resolution, the known `test_cold_ready` resource-bounds assertion, and recovery measurement failing because inherited `GIT_CONFIG_VALUE_0` is missing. Matching parent failures mean this increment added no failure among the current full-run failures. The full suite is not green.
- All output and pytest temporary paths were on F:. The Godot executable and one subprocess interpreter reside on D:, but the subprocess Python was verified as `3.12.2`; no test output or temporary path was directed to D:.
- P-1 complete branch-addition scan against `origin/thread-a/ownership-bond-followup-20261121` returned zero hits across all five credential-pattern families. Raw output: `F:/paralls-verification/thread-a/m2-2-read-as-metadata-order-20261128-11/p1-scan.log`.

## Remaining M2-2 gaps

- Runtime selector qualification for `faction`, `role`, `self`, `group_of`, `owner_of`, and `holder_of` is not implemented generally. The available Organization role assignments do not establish the credential authority role's historical effective interval, and Organization membership/delegation does not establish faction membership.
- `resolve_event_fact_type` rejects legacy domain stream IDs. Their historical event-to-FactType attribution remains unresolved.
- The only production readers in `GameplayReadAs` remain the two recipient-private Information FactTypes. FactType-wide visibility filtering, known-time policy/model execution, and U7 remain incomplete. M2-2 remains blocked.

## Conclusion

- This increment is verified for cross-FactType visibility-denial ordering and regression selections.
- Generic `read_as`, historical principal qualification, and U7 are not complete. No Architecture v2 or M2-2 completion claim is made.
