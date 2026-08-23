# Task 6 Report: Checkpoint Digest And Replay Equivalence

Status: implemented

## Scope

- Extended `HeavenlyGraphCheckpointRef` with schema version, source revision
  vector, policy revision, scope digest, and replay digest.
- Added `HeavenlyGraphPort.replay_from_checkpoint(...)`.
- Implemented non-mutating checkpoint-plus-tail replay in the InMemory adapter;
  SQLite delegates through the same implementation under its write lock.
- Kept source history and the stored checkpoint immutable.

## Digest contract

Replay digests are deterministic SHA-256 values over the canonical JSON form
of the schema version, scope, scope digest, source revision vector, policy
revision, and sorted node/relation payloads. Scope revisions are pinned to the
checkpoint's recorded coordinate when the checkpoint is created.

## Verification

```text
python -m pytest -q backend/tests/heavenly_graph_contract.py backend/tests/test_sqlite_heavenly_graph_contract.py
41 passed, 1 warning

python -m pytest -q backend/tests/test_heavenly_graph_semantics.py backend/tests/test_heavenly_graph_semantic_queries.py backend/tests/test_heavenly_graph_branch_lifecycle.py
158 passed, 1 warning

python -m compileall -q backend/app/models/siming_heavenly_graph.py backend/app/services/in_memory_heavenly_graph.py backend/app/services/sqlite_heavenly_graph.py
passed

git diff --check
passed
```

The warning is the existing Starlette/httpx deprecation warning from the test
conftest. No CharacterAgentRuntime or Siming runtime code was changed.

## Fix Round 2: SQLite restart parity

SQLite restart now recovers a missing replay frontier from the durable source
revision tables at the checkpoint's recorded coordinate. This handles database
payloads written before `replay_nodes`/`replay_relations` existed without
silently treating Pydantic's empty defaults as a complete history. Recovery is
read-model only; source rows and the stored checkpoint payload remain
immutable.

Added file-backed regressions for future-valid and retracted predecessor
chains. Each closes and reopens SQLite, verifies the recovered replay
frontier, admits a valid revision-3 tail, and compares effective nodes,
relations, and replay digest with a full-history checkpoint.

Verification:

```text
python -m pytest -q backend/tests/test_sqlite_heavenly_graph_contract.py
46 passed, 1 warning

python -m pytest -q backend/tests/heavenly_graph_contract.py backend/tests/test_sqlite_heavenly_graph_contract.py backend/tests/test_heavenly_graph_semantics.py backend/tests/test_heavenly_graph_semantic_queries.py backend/tests/test_heavenly_graph_branch_lifecycle.py
204 passed, 1 warning

python -m compileall -q backend/app/models/siming_heavenly_graph.py backend/app/services/in_memory_heavenly_graph.py backend/app/services/sqlite_heavenly_graph.py
passed

git diff --check
passed
```

## Fix Round 1

Review identified that an effective checkpoint view alone cannot seed a later
revision: a predecessor may already be recorded but not yet valid at the
checkpoint's valid coordinate, or may be a retraction/redaction and therefore
be absent from the effective view. `HeavenlyGraphSnapshot` now keeps the
effective `nodes`/`relations` separate from `replay_nodes`/`replay_relations`,
which contain every admitted revision at the checkpoint recorded coordinate.
Replay seeds its temporary adapter from that historical frontier without
mutating source history. Tail entities recorded before the checkpoint's
recorded coordinate are rejected with `HeavenlyGraphRevisionConflict`.

Added adapter-parametrized regressions for:

- future-valid revision 2 followed by revision 3 admission after replay;
- retracted revision predecessor followed by a new revision;
- retroactive tail rejection;
- non-mutating checkpoint/source history.

Verification:

```text
python -m pytest -q backend/tests/heavenly_graph_contract.py backend/tests/test_sqlite_heavenly_graph_contract.py
44 passed, 1 warning

python -m pytest -q backend/tests/heavenly_graph_contract.py backend/tests/test_sqlite_heavenly_graph_contract.py backend/tests/test_heavenly_graph_semantics.py backend/tests/test_heavenly_graph_semantic_queries.py backend/tests/test_heavenly_graph_branch_lifecycle.py
202 passed, 1 warning

git diff --check
passed
```
