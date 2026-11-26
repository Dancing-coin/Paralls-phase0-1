# M2-4 Projection Incremental Verification

Date: 2026-11-23

## Scope and ruling

The migration plan defines M2-4 as projection cursoring, continuous interval validation, failure without partial installation, and equal reconstruction digest when no checkpoint is available. The current `GameplayProjectionReplay` and `GameplayProjectionStartup` implement this correctness path. No production code change was needed for this verification unit.

Ruling: M2-4 covers replay correctness. The performance proposal to cache projector state in a `ProjectionCheckpointer` is not part of this implementation. The read-only Architecture v2 shared Owner document records benchmark evidence against that proposal and replaces it with `StoreReadSnapshot`, tracked separately as M3-2. Treating M2-4 as both contracts would reintroduce the rejected cache design. The cost if this interpretation is wrong is that the plan may expect a separate performance change under M2-4, which should be resolved against M3-2 before implementation.

## Existing behavior and tests

| Requirement | Existing implementation | Evidence |
|---|---|---|
| Cursor and incremental tail | Checkpoints store `last_global_sequence` and `source_revision_vector`; startup reads events after the selected checkpoint sequence. | `backend/app/gameplay/replay.py`; `backend/app/gameplay/projection_startup.py` |
| Continuous relevant event interval | Replay requires each stream revision to equal its prior revision plus one. A gap returns `stream_revision_gap`. | `GameplayProjectionReplay._replay`; `test_stream_revision_gap_blocks_replay_with_typed_failure` |
| No partial installation on failure | A failed replay result has no projected state; startup leaves read/write readiness false, and the store rejects a subsequent append with `projection_not_ready`. | `GameplayProjectionStartup.bootstrap`; `test_failed_startup_keeps_writes_closed_and_returns_typed_rejection` |
| Checkpoint-free reconstruction | With no compatible checkpoint, startup performs full replay. A checkpoint plus tail produces the same projection hash as full replay. | `test_startup_ignores_invalid_or_incompatible_checkpoints_and_full_replays`; `test_full_replay_and_checkpoint_plus_tail_replay_have_identical_projection_hashes` |

The store exposes checkpoint save/list APIs but no checkpoint deletion API. The required digest property is verified through the no-valid-checkpoint full-replay path and the checkpoint-plus-tail comparison; this run did not physically delete a persisted checkpoint.

## Verification environment

- Worktree: `F:\codex-temp\paralls-v2-thread-a-bond-20261121`
- Code HEAD: `022f1772429fa95d1969d82de984568880da3a83`
- Python: 3.12.2 from `D:\Temp\paralls-g0-py312\Scripts\python.exe`
- `PYTHONPATH`: `F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend`
- `app.__file__`: `F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend\app\__init__.py`
- SQLite: 3.43.1
- Output directory: `F:\paralls-verification\thread-a\m2-4-replay-20261123-001\`

Command and result:

```text
& 'D:\Temp\paralls-g0-py312\Scripts\python.exe' -m pytest -q --basetemp 'F:\paralls-verification\thread-a\m2-4-replay-20261123-001\pytest-tmp' --junitxml='F:\paralls-verification\thread-a\m2-4-replay-20261123-001\junit.xml' backend/tests/test_gameplay_event_replay.py backend/tests/test_gameplay_projection_startup.py
15 passed, 2 warnings in 0.41s
```

The warnings are Starlette/httpx deprecations. Raw console and JUnit are retained in the output directory above. This was a focused mechanism run; no new full-suite run was performed for this verification-only unit.

## Current-tip revalidation, 2026-11-27

At A tip `74a291c4`, the same replay/startup command returned **15 passed, 2 warnings** with Python 3.12.2, the A-worktree `PYTHONPATH`, and explicit F-drive pytest basetemp.

Command:

```text
D:\Temp\paralls-g0-py312\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp F:\paralls-verification\thread-a\m2-4-current-tip-20261127-01\basetemp --junitxml F:\paralls-verification\thread-a\m2-4-current-tip-20261127-01\junit.xml backend/tests/test_gameplay_event_replay.py backend/tests/test_gameplay_projection_startup.py
```

Raw JUnit and temporary data are retained under `F:\paralls-verification\thread-a\m2-4-current-tip-20261127-01\`. No code changed in this revalidation. The current-tip full backend suite was not rerun, and M2-4 remains pending integration gate.

## DoD mapping

This is a shared projection mechanism audit, not a domain migration. U1, U2, U3, U4, U5, U6, U7, U8, and U11 are not applicable to this unit. U9 is verified for the two focused replay/startup test files at the stated depth. U10 is documented here with raw output retained externally.

The source implementation and tests are in shared, unassigned gameplay replay files and were not modified. M2-4 is recorded for project gate review based on the existing implementation and fresh focused tests; this does not claim Architecture v2 completion.
