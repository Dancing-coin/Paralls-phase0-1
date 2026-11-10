# G2: Social delivery known-time boundary

- Source branch: `codex/g0-b3-ingress-20261109`
- Baseline source commit: `59084f369ec6c19672b91e26770b81d9e17ef510`
- Scope: record and enforce the recipient-domain known tick for committed social delivery events.
- Status: this bounded unit is verified; the G2 visibility, time and epoch gates remain open.

## Behavior

New social deliveries use `gameplay.social.delivery_recorded@2` and persist
`known_at_world_tick` from the validated domain clock at commit. The recipient
view omits the delivery before that tick and returns the tick with the row at
or after it. Invalid clock values reject before a write. Version 2 replay
requires a valid known tick. Legacy `@1` events remain readable for receipt and
replay compatibility but are not projected because they have no trustworthy
known-time evidence.

The change does not establish a session participant's identity, authenticate a
WebSocket binding, authorize a general session projection, or record actual
network presentation time. It is not a generic EventStore `read_as` filter and
does not implement `presented_time`, historical perception, non-field
disclosure, or the authority epoch fence. The approved session-projection
product rule and its remaining source gaps are recorded in
[`g2-visibility-budget/boundary-audit.md`](../g2-visibility-budget/boundary-audit.md).

## Verification

The focused regression command ran against the project's Python 3.12.2
environment on Windows 11:

```powershell
& 'D:/Temp/paralls-g0-py312/Scripts/python.exe' -m pytest -q --junitxml=D:/Temp/g2-social-known-time-targeted-20261110/junit.xml tests/test_p5_social_delivery.py tests/test_social_delivery_caller.py tests/test_world_replay_participants.py tests/test_world_replay_checkpoint_cut.py tests/test_world_replay_checkpoint_application.py tests/test_gameplay_event_schema_registry.py tests/test_modifier_runtime.py tests/test_equipment_runtime.py tests/test_resource_modifier_admission.py
```

Result: **135 passed, 7 warnings**. This set includes invalid and delayed
known-time cases, exact retry and changed payload, legacy-event behavior,
schema/replay checks, Decimal digest behavior, corrupt equipment receipts, and
bridge recovery on an exact duplicate.

The frozen full backend baseline ran at HEAD `59084f36` with Python 3.12.2,
Windows 11, the same dependency hashes as the prior G2 run, and no source or
worktree-status drift during execution. Its runner was invoked from the
repository root and executed pytest from `backend/`. Command:

```powershell
& 'D:/Temp/paralls-g0-py312/Scripts/python.exe' docs/verification/g0-939c6746/run_baseline.py --repo . --output D:/Temp/g2-social-known-time-baseline-20261110 --freeze
```

Results: **10,041 collected; 9,998
passed, 39 failed, 2 skipped, 2 xfailed; 0 collection errors**. Against the
G0 9,937-node run there were 104 additional nodes, all passed; all G0 nodes
remained present, with zero changed outcomes, added/removed failures, or
normalized failure-stack differences. Against the previous 10,034-node G2 run,
the 7 added nodes are this unit's tests and all passed; prior outcomes and
failure signatures were unchanged.

The unit-specific performance script measured a 4,096-event in-memory
recipient view against raw event reads in four alternating 60-sample runs:

| Sample | Raw p95 | Recipient view p95 | Ratio |
|---|---:|---:|---:|
| c | 21.930 ms | 22.056 ms | 1.006 |
| d | 18.726 ms | 19.657 ms | 1.050 |
| e | 22.665 ms | 24.478 ms | 1.080 |
| f | 22.298 ms | 23.636 ms | 1.060 |

These samples are within the current candidate bounds of 10% p95 overhead and
40 ms absolute p95 for this synthetic domain view. They do not close the G2
performance gate: earlier end-to-end and persistent-read samples exceeded the
candidate bounds, and this fixture does not include authenticated session
access, transport, real-world workload, or production storage contention.

## Evidence and rollback

- `full-run-10041.zip`: complete frozen run, including node inventory,
  environment, result and failure files, invocation and JUnit.
- `baseline-comparison.json`: exact G0 and prior-G2 node/failure comparison and
  environment stability.
- `performance-c.json` through `performance-f.json`: raw per-sample latency
  distributions.
- `targeted-tests.log` and `targeted-junit.xml`: focused regression output.
- Measurement commands (run from the repository root):

  ```powershell
  & 'D:/Temp/paralls-g0-py312/Scripts/python.exe' docs/verification/g2-visibility-budget/measure_social_delivery_known_time.py --repeats 60 --output docs/verification/g2-social-delivery-known-time/performance-e.json
  & 'D:/Temp/paralls-g0-py312/Scripts/python.exe' docs/verification/g2-visibility-budget/measure_social_delivery_known_time.py --repeats 60 --output docs/verification/g2-social-delivery-known-time/performance-f.json
  ```

This is one independently revertible unit. Revert the code-and-evidence commit
that introduced this report with `git revert <unit-commit>`; no migration or
data rewrite is required. Previously written `@1` events stay intact.
