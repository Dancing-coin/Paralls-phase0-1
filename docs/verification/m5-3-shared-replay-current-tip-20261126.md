# M5-3 Shared Replay Current-Tip Attempt

## Baseline

| Item | Value |
|---|---|
| Worktree | `F:\codex-temp\paralls-v2-thread-a-bond-20261121` |
| Branch | `thread-a/ownership-bond-followup-20261121` |
| Commit | `bd02be3cbf3949742113c2e79d5216a7c23c20d1` |
| Python | `D:\Temp\paralls-g0-py312\Scripts\python.exe`, 3.12.2 |
| `app.__file__` | `F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend\app\__init__.py` |
| SQLite | 3.43.1 |
| Selection | Frozen shared-replay, 990 nodes |
| Git status before run | Clean |

## Attempt

Command:

```text
D:\Temp\paralls-g0-py312\Scripts\python.exe docs\verification\absorb-main-3bf3418e\compare_selection.py --repo F:\codex-temp\paralls-v2-thread-a-bond-20261121 --selection docs\verification\absorb-main-3bf3418e\shared-replay.json --output F:\paralls-verification\thread-a\m5-3-shared-replay-exact-tip-20261126-02\shared-replay
```

The process environment set `PYTHONPATH` to the A worktree `backend` and `TEMP`/`TMP` to `F:\paralls-verification\thread-a\m5-3-shared-replay-exact-tip-20261126-02\temp`. The PATH included the existing F-drive PowerShell shim directory `F:\paralls-verification\thread-a\m1-2-holdings-gates-20261125-02\env`. Before execution, `netstat -ano -p tcp | findstr /C:":8000"` returned no matching endpoint.

Ten of 25 batches completed (400 nodes). Batch 0010 logged five passing tests before pausing at `tests/test_embodied_interaction_session_runner.py::test_profile_repeated_in_one_run_receives_fresh_events[isolated-storage]`. The attempt was interrupted after the batch failed to progress. The compare script produced no aggregate `selected/problems/improvements` result. Therefore the 990-node comparison is incomplete and has no pass result.

Raw output is under `F:\paralls-verification\thread-a\m5-3-shared-replay-exact-tip-20261126-02\shared-replay\`. The corresponding temporary root is `F:\paralls-verification\thread-a\m5-3-shared-replay-exact-tip-20261126-02\temp\`. The runner was this turn's process and was interrupted; no external process was stopped. A post-run port check found no listener on 8000. Full backend regression was not run.

## Conclusion

| Area | Level |
|---|---|
| Python/worktree import | Verified |
| Frozen shared-replay selection | Incomplete; no aggregate comparison |
| Full backend regression | Not run |
