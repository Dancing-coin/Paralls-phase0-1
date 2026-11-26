# M5-3 Shared Replay After Listener Query Repair

## Baseline

| Item | Value |
|---|---|
| Worktree | `F:\codex-temp\paralls-v2-thread-a-bond-20261121` |
| Branch | `thread-a/ownership-bond-followup-20261121` |
| Commit | `4d366b9e7e7c9d542f15b1dba0ad9c7ffeb96aea` |
| Python | `D:\Temp\paralls-g0-py312\Scripts\python.exe`, 3.12.2 |
| `app.__file__` | `F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend\app\__init__.py` |
| SQLite | 3.43.1 |
| Git status at comparison start | Clean |
| Selection | Frozen shared-replay, 990 nodes |

## Change

The verification helper now reads TCP `LISTENING` rows from `netstat -ano -p tcp`, matches IPv4 and IPv6 local addresses by exact port, and bounds the query to five seconds. A failed query raises `listener_inspection_failed`; it no longer silently treats an inspection failure as an available port. The existing caller still reuses a healthy backend and rejects an unhealthy occupied port without terminating its process.

## Verification

The exact-commit command for `scripts/verification/tests/test_harness_processes.py` returned:

```text
15 passed in 4.59s
```

Raw output: `F:\paralls-verification\thread-a\m5-3-listener-inspection-exact-tip-20261126-01\pytest.log`.

The frozen comparison command was:

```text
D:\Temp\paralls-g0-py312\Scripts\python.exe docs\verification\absorb-main-3bf3418e\compare_selection.py --repo F:\codex-temp\paralls-v2-thread-a-bond-20261121 --selection docs\verification\absorb-main-3bf3418e\shared-replay.json --output F:\paralls-verification\thread-a\m5-3-shared-replay-netstat-20261126-01\shared-replay
```

Raw runner output:

```text
selected=990 problems=0 improvements=0
```

The batch-0010 log records both previously stalled WebSocket runner cases as passed. Batch environment records show HEAD and `head_after` equal to `4d366b9e7e7c9d542f15b1dba0ad9c7ffeb96aea`, clean starting status, and `source_unchanged=true`. Raw logs and per-batch results are under `F:\paralls-verification\thread-a\m5-3-shared-replay-netstat-20261126-01\shared-replay\`.

`PYTHONPATH`, `TEMP`, and `TMP` pointed to the A worktree backend and F-drive run directory. Port 8000 had no listener after the comparison. No external process was stopped. Full backend regression, production startup, and UE transport were not run.

## Conclusion

| Area | Level |
|---|---|
| Listener-query regression tests | Verified, 15 passed |
| Frozen shared-replay | Verified, 990 selected, 0 problems, 0 improvements |
| Full backend regression | Not run |
| Production deployment and UE transport | Not run |
