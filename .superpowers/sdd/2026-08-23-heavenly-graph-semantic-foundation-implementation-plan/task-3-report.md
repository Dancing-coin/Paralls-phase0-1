# Task 3 Report: Causal, Conflict, Perspective, Turn, And Source-Impact Queries

## Scope

Implemented only semantic query execution for Heavenly Graph. The change does
not modify CharacterAgentRuntime, SimingRuntime.tick, story orchestration,
obligation transitions, resource scoring, online LLM, Godot, or external graph
dependencies.

## TDD Evidence

1. Added adapter-parametrized failing tests for causal paths, conflict sets,
   actor perspectives, behavior turns, and source impact.
2. RED run: `python -m pytest -q backend/tests/test_heavenly_graph_semantic_queries.py`
   produced 10 failures because the typed query branches were still an empty
   Task 2 shell (plus one intentionally incomplete fixture).
3. Implemented each semantic branch through the existing low-level adapter
   queries and deterministic bounded traversal.
4. GREEN run: focused semantic query suite passed for both InMemory and SQLite:
   `30 passed, 1 warning`.

## Implementation

- `CausalPathQuery` follows only registered causal relation types
  (`caused_by`, `enabled_by`, `prevented_by`) through bounded adapter reads.
  Node, relation, depth, and path bounds surface `truncated`.
- `ConflictSetQuery` selects concurrent claims by `subject_ref` and
  `property_key`, preserves all eligible claims, and returns connected
  `contradicts` relations without collapsing values.
- `PerspectiveQuery` reads actor view/memory projection nodes in an explicit
  actor-private scope, applies actor ownership and requested visibility scopes,
  and inherits the facade's fail-closed privacy filtering.
- `BehaviorTurnQuery` filters behavior-turn records by turn, correlation,
  actor, and stage, and includes bounded relations/nodes participating in that
  turn without implementing role behavior.
- `SourceImpactQuery` returns bounded derived nodes and relations whose source
  event/evidence/revision metadata references the requested source revision.
- Semantic predicate branches use a fixed adapter candidate window (1000) so
  post-query filters cannot hide an eligible record behind an early mismatch.
- SQLite now serializes semantic facade reads under its adapter lock, matching
  mutation and low-level query behavior.

## Verification

```text
python -m pytest -q backend/tests/test_heavenly_graph_semantic_queries.py \
  backend/tests/heavenly_graph_contract.py \
  backend/tests/test_sqlite_heavenly_graph_contract.py \
  backend/tests/test_heavenly_graph_semantics.py
89 passed, 1 warning

git diff --check
passed
```

## Review Fix Round 4

- Replaced budget-consuming sibling-first BFS with deterministic depth-first
  path selection so a reachable complete path is returned before alternate
  branches consume the traversal budget.
- Preserved the finite work-item budget and truncation behavior for unexplored
  siblings and additional seeds.
- Updated the high-branching InMemory/SQLite regression to require the first
  complete path while proving the expansion counter remains within budget.

Round-4 verification:

```text
python -m pytest -q backend/tests/test_heavenly_graph_semantic_queries.py \
  backend/tests/heavenly_graph_contract.py \
  backend/tests/test_sqlite_heavenly_graph_contract.py \
  backend/tests/test_heavenly_graph_semantics.py
107 passed, 1 warning

git diff --check
passed
```

## Concerns / Deferred

- The result model exposes the deterministic union of causal paths rather
  than individual path rows; `max_paths` is enforced as a disclosed bound.
- Query-specific grouping and semantic execution remain graph-foundation
  behavior only. Consumer integration is intentionally deferred to later
  phases.

## Review Fix Round 1

- Added explicit `HeavenlyGraphScope` construction for actor-private
  perspective queries when the caller supplies `actor_ref` without a scope.
- Preserved raw 1,000-record candidate-window saturation through all semantic
  node/relation branches, even when post-query predicates remove most records.
- Replaced causal `query_subgraph` delegation with bounded facade BFS using
  low-level node/relation limits. The deterministic path-union result caps
  selected relation edges at `min(relation_limit, max_paths)` and reports
  `truncated` when the path-equivalent bound is reached.
- Restricted relation endpoint source-impact matching to `derived_from`; other
  relation types require explicit source event/evidence/provenance metadata.

Review-fix regression coverage includes both adapters for implicit actor
scope, candidate-window saturation, causal `max_paths`, no `query_subgraph`
delegation, and source-impact relation semantics.

Review-fix verification:

```text
python -m pytest -q backend/tests/test_heavenly_graph_semantic_queries.py
40 passed, 1 warning

python -m pytest -q backend/tests/test_heavenly_graph_semantic_queries.py \
  backend/tests/heavenly_graph_contract.py \
  backend/tests/test_sqlite_heavenly_graph_contract.py \
  backend/tests/test_heavenly_graph_semantics.py
99 passed, 1 warning

git diff --check
passed
```

## Review Fix Round 2

- Causal execution now enumerates complete simple paths breadth-first within
  the requested depth. The result remains a deterministic node/relation union,
  but `max_paths` limits complete paths independently from `node_limit` and
  `relation_limit`; a selected path keeps all of its edges until those output
  limits are reached.
- An explicit `relation_types` list containing no registered causal relation
  types now returns an empty causal result. It is never converted into an
  unrestricted relation query.
- Added adapter-parametrized regressions for a three-edge path with
  `max_paths=1` and an explicit non-causal relation filter.

Round-2 verification:

```text
python -m pytest -q backend/tests/test_heavenly_graph_semantic_queries.py
45 passed, 1 warning

python -m pytest -q backend/tests/test_heavenly_graph_semantic_queries.py \
  backend/tests/heavenly_graph_contract.py \
  backend/tests/test_sqlite_heavenly_graph_contract.py \
  backend/tests/test_heavenly_graph_semantics.py
105 passed, 1 warning

git diff --check
passed
```

## Review Fix Round 3

- Added a deterministic causal work-item budget derived from
  `max_paths * (max_depth + 1)` and `node_limit + relation_limit`, capped by
  the semantic adapter candidate window.
- Causal BFS now uses a deque and enforces the budget both when admitting seed
  and child path prefixes and when processing pending prefixes. Queue and
  traversal exhaustion always set `truncated=true`; no unbounded branch fan-out
  can accumulate before a terminal path is found.
- Added an InMemory/SQLite-parametrized 64-way, depth-eight regression with a
  traversal expansion counter. The query admits no more than the nine work
  items derived from its limits and discloses truncation.

Round-3 verification:

```text
python -m pytest -q backend/tests/test_heavenly_graph_semantic_queries.py
48 passed, 1 warning

python -m pytest -q backend/tests/test_heavenly_graph_semantic_queries.py \
  backend/tests/heavenly_graph_contract.py \
  backend/tests/test_sqlite_heavenly_graph_contract.py \
  backend/tests/test_heavenly_graph_semantics.py
107 passed, 1 warning

git diff --check
passed
```

## Review Fix Round 4

- Replaced bounded causal BFS queue expansion with deterministic depth-first
  path priority. High fan-out siblings no longer consume the entire work
  budget before a reachable terminal path can be completed.
- Preserved the derived path-prefix work budget, complete-path `max_paths`
  semantics, node/relation output bounds, simple-path cycle guard, and
  truncation disclosure for unexplored alternatives or budget exhaustion.
- Updated the adapter-parametrized high-branching regression to require one
  complete valid root-to-terminal path while asserting bounded expansion and
  `truncated=true` for the unexplored sibling branches.

Round-4 verification:

```text
python -m pytest -q backend/tests/test_heavenly_graph_semantic_queries.py
48 passed, 1 warning

python -m pytest -q backend/tests/test_heavenly_graph_semantic_queries.py \
  backend/tests/heavenly_graph_contract.py \
  backend/tests/test_sqlite_heavenly_graph_contract.py \
  backend/tests/test_heavenly_graph_semantics.py
107 passed, 1 warning

git diff --check
passed
```
