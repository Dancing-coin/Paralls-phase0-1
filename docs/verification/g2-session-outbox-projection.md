# Session pull outbox projection integrity

A real WebSocket regression showed that an in-process bus publisher could copy
a committed session event and substitute top-level projection fields, including
the cursor, while preserving the committed payload. The pull now accepts a bus
projection only when the full payload matches the committed event and its
deterministic, associated session outbox entry. A missing or mismatched outbox
uses the existing committed-event fallback. This protects against a forged bus
projection; it does not establish a remote attack path, principal binding,
room authorization, known time, or general G2 visibility enforcement.

Windows 11, Python 3.12.2. The regression failed before the fix with cursor
999999 instead of the committed sequence. The focused file passed 14 tests,
including valid, missing, and mismatched outbox cases and the existing public
projection workflow. These tests do not establish durable restart behavior
for this specific change.

```powershell
& 'D:/Temp/paralls-g0-py312/Scripts/python.exe' -m pytest backend/tests/test_embodied_interaction_session.py -q --disable-warnings
& 'D:/Temp/paralls-g0-py312/Scripts/python.exe' docs/verification/g0-939c6746/run_baseline.py --repo . --output D:/Temp/g2-session-outbox-projection-baseline --freeze
```

Full G0-range run: 10,030 nodes, 9,987 passed, 39 failed, 2 skipped and
2 xfailed; no collection errors. All 9,937 G0 and 10,027 prior nodes retain
their phase outcomes; the three new nodes pass. Failure signatures and stacks
match both runs after normalizing pytest temporary directory numbers and the
verified AnyIO cancel-scope identifier. Environment and dependency hashes
match the preceding run; source, HEAD and worktree status were stable while
running. The [archive](g2-session-outbox-projection-evidence.zip) includes
the frozen test inventory, results, failures, environment and comparison
script. The approved 39 failures remain unresolved.

Rollback: revert this commit. No data migration is involved; reverting restores
the possibility of selecting a bus projection whose top-level fields differ
from its persisted outbox. D2-D10, the synthetic performance gate and B3
client acceptance remain open.
