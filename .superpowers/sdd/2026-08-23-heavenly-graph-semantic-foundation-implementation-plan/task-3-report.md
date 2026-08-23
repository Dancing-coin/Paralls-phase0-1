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
   queries and deterministic `query_subgraph` traversal.
4. GREEN run: focused semantic query suite passed for both InMemory and SQLite:
   `30 passed, 1 warning`.

## Implementation

- `CausalPathQuery` now follows only registered causal relation types
  (`caused_by`, `enabled_by`, `prevented_by`) through the existing bounded
  subgraph API. Node, relation, depth, and path bounds surface `truncated`.
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

## Concerns / Deferred

- The result model exposes the deterministic union of causal paths rather
  than individual path rows; `max_paths` is enforced as a disclosed bound.
- Query-specific grouping and semantic execution remain graph-foundation
  behavior only. Consumer integration is intentionally deferred to later
  phases.
