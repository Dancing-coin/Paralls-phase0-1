# Information Checkpoint + Tail Replay Evidence

## Scope

- A baseline: `99c7be5f5b290e82f4f2f4d70ea0ac40d7499851` from `origin/thread-a/ownership-bond-followup-20261121`, fetched on 2026-11-27.
- B branch: `thread-b/information-replay-20261127`.
- Conclusion level: runtime tests verified for Information durable checkpoint/tail behavior; full backend regression is not clean.
- Production changes are limited to writing the already-supported top-level `GameplayEvent.event_time` on Information knowledge events. The persisted event type and payload schema are unchanged.

## Behavior Verified

`backend/tests/test_information_replay_checkpoint.py` exercises the Information report publisher, SocialDelivery and L5 knowledge update on `DurableGameplayEventStore`.

- The checkpoint contains the recipient-private report event and SocialDelivery event, with their per-stream projection state and event IDs.
- The post-checkpoint tail contains the recipient-private Information knowledge event, including top-level `event_time=16`.
- Report, delivery and knowledge transactions retain their respective Information/SocialDelivery idempotency principals. The knowledge transaction pins the delivery and report stream revisions.
- The durable store is closed and reopened. Its saved checkpoint, events, transaction ownership and revisions remain available.
- Full replay and checkpoint-plus-tail replay after reopen have identical state, source revision vector, applied event IDs and projection hash.
- Removing the report event from a durable snapshot or changing its event ID while retaining the transaction references causes snapshot restoration to raise `GameplayEventStoreSnapshotError`.

## Commands and Results

Environment was Python `3.12.2`; `app.__file__` resolved to `F:\codex-temp\paralls-v2-thread-b-information-replay-20261127\backend\app\__init__.py`. `PYTHONPATH` pointed to that worktree's `backend`. `TEMP`, `TMP`, `TMPDIR`, pytest basetemp and logs were on F:.

The first focused run exposed that the L5-generated knowledge event had `event_time=None`. After the Information writer fix, the command below returned `24 passed, 6 warnings in 3.14s`, exit code 0.

```powershell
& 'D:\Temp\paralls-g0-py312\Scripts\python.exe' -B -m pytest -q -p no:cacheprovider --basetemp <F-drive-temp> `
  backend/tests/test_information_replay_checkpoint.py `
  backend/tests/test_siege_information_runtime.py `
  backend/tests/test_information_production_wiring.py
```

Raw logs are in `F:\paralls-verification\thread-b\information-replay-20261127-a99c7b\pytest-information-replay-final.log` and `pytest-information-replay-green.log`. The first red result is in `pytest-information-replay.log`.

The Information selection now contains 26 nodes, including the checkpoint-tail test. `compare_selection.py` returned `selected=26 problems=0 improvements=0`; raw output is `F:\paralls-verification\thread-b\information-replay-20261127-a99c7b\selection-information-26.log`. This evidence does not claim a full five-group G5 pass.

## Full Backend Regression

The explicit backend test command completed with `10,769 passed, 22 failed, 2 skipped, 2 xfailed, 227 warnings` in `1519.86s`, exit code 1. The raw log is `F:\paralls-verification\thread-b\information-replay-20261127-a99c7b\pytest-backend-full.log`.

The 22 failing nodes were rerun on the unchanged A parent `99c7be5f`. Seventeen failed there too: the missing `tokenizers` dependency, `test_cold_ready`, fourteen nested population harness evidence cases, and `test_recovery_owner_probe_measures_original_startup_before_full_oracle`.

The other five nodes passed on the parent and also passed when rerun individually on the current worktree: Task45 Godot probe, mixed soak, mixed verification, multi-game capacity and Task8 Godot registry probe. Their failures occurred only in the full-suite run context and are not attributed to this Information change. Parent comparison output is in `pytest-parent-failed-nodes.log` and `pytest-parent-five-differences.log`; current isolated reruns are in `pytest-current-five-differences.log`.

The full suite is not a pass. No full five-group selection comparison was performed in this unit.

## U1-U11 Status

| Item | Status | Evidence or remaining gap |
|---|---|---|
| U1 Owner declaration | Partial | Existing `Information` runtime and owner registration are used; this unit adds no full Owner declaration. |
| U2 FactType declaration | Existing partial | Existing county siege Information pack is unchanged. |
| U3 Event schema and P-3 | Existing verified | This change adds no event type or schema. |
| U4 Shared Owner mechanism | Partial | Durable store and existing Information writer are exercised; no OwnerCommitBuilder migration. |
| U5 R1/R2/R3 | Partial | Durable reopen, checkpoint-tail equality and corrupted snapshot rejection are covered. Broader Information-specific replay variants remain untested. |
| U6 Readers and downstream tests | Partial | Gateway/L5 path is exercised through production runtime wiring; no complete dynamic reader inventory is claimed. |
| U7 Visibility and read boundary | Partial | Report, delivery and knowledge remain recipient-private in the tested path. `read_as` is not implemented or verified here. |
| U8 Rule pack and Resolver | Existing partial | Existing rule pack is used by prior production-wiring tests; declarative Information Resolver is not added. |
| U9 Probe and baseline comparison | Partial | Focused runtime tests pass. Full backend regression is non-clean as above. |
| U10 Evidence | Complete for this unit | This evidence and raw logs identify scope and limitations. |
| U11 Unit selection | Updated | `docs/verification/selection/siege_information.json` now includes the checkpoint-tail test. |

## Not Covered

This proves Information event persistence and replay in the tested production-wired path. It does not prove `read_as`, the complete visibility model, production Gate values, live Unreal input, or a complete siege flow.
