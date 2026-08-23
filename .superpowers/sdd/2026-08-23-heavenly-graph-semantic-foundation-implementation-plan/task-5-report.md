# Task 5 Report: Heavenly Graph Branch Lifecycle

## Status

Implemented and verified. Commit: `feat: add Heavenly Graph branch lifecycle`.

## Implemented

- Added typed `GraphBranchForkRequest`, `GraphBranchDiffQuery`,
  `GraphBranchLifecycleRequest`, lifecycle markers, diff limits, and diff result
  models.
- Added `fork_branch`, `diff_branches`, and `lifecycle_branch` to the graph port.
- Added InMemory and SQLite parity for branch snapshot fork, deterministic node
  and relation diff, close-node markers, discard, and explicit admission.
- Fork copies the effective source snapshot into a distinct scope and validates
  the source revision vector before any mutation.
- Branch-only writes are rejected for scopes that have not been explicitly
  forked. Production scope remains unchanged by branch writes.
- Closing a node appends an immutable close marker and hides the original node;
  later writes for that node are rejected, so the instance cannot resurrect.
- Discard hides the branch from normal graph queries while retaining its
  in-memory/SQLite audit marker and historical records.
- SQLite persists branch status, branch revision, and marker history in the
  `graph_branch_state` table and restores them on reopen.
- Admission requires an explicit target branch and rejects terminal branches or
  target collisions.

## Verification

```text
python -m pytest -q backend/tests/test_heavenly_graph_branch_lifecycle.py
12 passed, 1 warning

python -m pytest -q backend/tests/test_heavenly_graph_branch_lifecycle.py backend/tests/test_heavenly_graph_semantics.py backend/tests/test_heavenly_graph_semantic_queries.py backend/tests/test_sqlite_heavenly_graph_contract.py
153 passed, 1 warning

python -m compileall -q backend/app/models/siming_heavenly_graph.py backend/app/services/siming_heavenly_graph_port.py backend/app/services/in_memory_heavenly_graph.py backend/app/services/sqlite_heavenly_graph.py
passed

git diff --check
passed
```

## Scope boundary

No CharacterAgentRuntime, SimingRuntime, story/business transition, resource
scoring, LLM, Godot, or external graph/database behavior was changed.

## Concerns / Deferred

- Branch admission is a graph-foundation copy into an explicitly named branch;
  no domain consumer is automatically switched to the admitted branch.
- Lifecycle markers are retained in the graph adapter audit state and are not
  exposed as ordinary branch-marker nodes in normal node queries.
- Checkpoint replay digest and consistency audit remain Tasks 6 and 7.
