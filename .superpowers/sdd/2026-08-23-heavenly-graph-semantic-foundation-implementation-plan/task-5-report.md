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
- Admission rechecks the immutable fork source vector against the current source
  scope, so a branch cannot be admitted after its source has advanced.
- Fix round 1 normalizes branch-independent diff payloads, filters lifecycle
  markers by reader policy and recorded time, rejects unknown/terminal branch
  writes, propagates closure state through descendants, preserves coordinate-
  bounded fork snapshots, and guards lifecycle-internal marker writes.

## Verification

```text
python -m pytest -q backend/tests/test_heavenly_graph_branch_lifecycle.py
51 passed, 1 warning

python -m pytest -q backend/tests/test_heavenly_graph_branch_lifecycle.py backend/tests/test_heavenly_graph_semantics.py backend/tests/test_heavenly_graph_semantic_queries.py backend/tests/test_sqlite_heavenly_graph_contract.py
192 passed, 1 warning

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

## Fix Round 1

- Normalized branch-independent payloads before classifying changed diff records,
  so a pristine fork has no semantic diff.
- Restricted lifecycle markers to authority readers with a matching policy and
  recorded-time window; public or historical readers receive no future internal
  marker metadata.
- Enforced explicit branch admission for semantic writes, rejected terminal
  branch writes and terminal-source forks, while retaining the narrow
  `policy:legacy` compatibility path required by the pre-existing storage
  contract fixtures.
- Propagated append-only close marker history through fork and admission,
  removed dangling close relations from admitted snapshots, and reject both node
  resurrection and relations targeting permanently closed nodes.
- Replaced lifecycle's fixed `valid_at=10` behavior with the requested fork
  coordinates and source effective snapshot; close markers derive their
  coordinates from the target record.
- Admission now appends an explicit audit marker to the admitted target as
  well as the source branch, preserving source scope and source revision
  vector provenance on both sides of the transition.

## Fix Round 2

- Target admission markers now reference the immediately admitted source branch
  and its current revision vector; the source-side marker retains the original
  fork source/vector audit provenance.
- The target node and relation stream counters are initialized from copied
  records before its admission marker is constructed, so its marker revision
  vector is consistent with the admitted snapshot.
- Added parametrized InMemory/SQLite regression coverage for source/vector
  coherence and target stream counts.

Verification after the fix:

```text
python -m pytest -q backend/tests/test_heavenly_graph_branch_lifecycle.py
53 passed, 1 warning

python -m pytest -q backend/tests/heavenly_graph_contract.py backend/tests/test_sqlite_heavenly_graph_contract.py backend/tests/test_heavenly_graph_semantics.py backend/tests/test_heavenly_graph_semantic_queries.py backend/tests/test_heavenly_graph_branch_lifecycle.py
194 passed, 1 warning

python -m pytest -q backend/tests/test_heavenly_graph_branch_lifecycle.py backend/tests/test_heavenly_graph_semantics.py backend/tests/test_heavenly_graph_semantic_queries.py backend/tests/test_sqlite_heavenly_graph_contract.py backend/tests/test_character_graph_memory_store.py backend/tests/test_character_graph_memory_routing.py
210 passed, 2 warnings
```
