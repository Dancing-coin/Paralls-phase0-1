# Session projection policy check

The existing WebSocket session projection pull selected the next event from a
session stream and projected allowlisted fields without checking the committed
event's visibility policy. A real WebSocket regression reproduced disclosure
of an `authority_only` event's `reason_code` when it followed a valid session
event. The route now denies an event unless its committed policy is
`session_public_safe` and its type belongs to the session event family. A bus
event is selected only when its type and committed payload agree with the
stored event; otherwise the existing stored-event projection is used.

The focused test covers denied policy and unrelated event type, both with and
without bus delivery. Existing public session projection and probe behavior
still passes. This is a narrow check at an existing route: it does not bind a
principal, enforce room scope, derive known time or establish the safety of
every field in a bus projection. The probe and pull remain available without
a session binding. Other raw EventStore consumers remain outside this check.
Do not treat this as acceptance of general `read_as` or the G2 visibility
contract. The synthetic performance gate and D6 remain open.

Windows 11, Python 3.12.2: the authority-only regression failed before the
change; the focused session file reported 11 passed and 6 warnings.

```powershell
& 'D:/Temp/paralls-g0-py312/Scripts/python.exe' -m pytest backend/tests/test_embodied_interaction_session.py -q
& 'D:/Temp/paralls-g0-py312/Scripts/python.exe' docs/verification/g0-939c6746/run_baseline.py --repo . --output D:/Temp/paralls-g2-session-policy-baseline-20261110 --freeze
```

Full G0-range comparison: 10,027 nodes, 9,984 passed, 39 failed, 2 skipped,
2 xfailed, no collection errors. All 9,937 approved G0 nodes and 10,023
preceding nodes retained their setup/call/teardown outcomes; four new nodes
passed. The 39 failure node/phase/type signatures and stacks match the prior
run after normalizing pytest temporary-directory numbers and AnyIO
cancel-scope IDs. Python, OS, dependency and package hashes and pytest
environment match; source, HEAD and status were stable during the run. The
[archive](g2-session-projection-policy-evidence.zip) contains the frozen
manifest, environment, invocation, node list, JUnit, results and failures.

Rollback: revert this commit. There is no data migration; rollback restores
the ability to project fields from non-public events in a session stream.
D2-D10 and B3 client acceptance remain open.
