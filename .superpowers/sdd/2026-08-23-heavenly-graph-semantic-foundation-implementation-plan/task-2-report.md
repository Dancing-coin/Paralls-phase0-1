# Task 2 Report: Scoped Heavenly Graph Semantic Queries

## Scope

Implemented only the Heavenly Graph semantic read foundation. No CharacterAgentRuntime, SimingRuntime, story orchestration, resource scoring, LLM, Godot, or external graph dependency was changed.

## TDD Evidence

1. Added `backend/tests/test_heavenly_graph_semantic_queries.py` before production implementation.
2. RED run: `python -m pytest -q backend/tests/test_heavenly_graph_semantic_queries.py` failed during collection because `NodeLookupQuery` and the semantic facade did not exist.
3. GREEN run: the focused suite passes for both in-memory and SQLite adapters: `10 passed, 1 warning`.

## Implementation

- Added explicit `GraphReaderContext`-backed typed query models: `NodeLookupQuery`, `RelationLookupQuery`, `CausalPathQuery`, `PerspectiveQuery`, `ConflictSetQuery`, `BehaviorTurnQuery`, and `SourceImpactQuery`.
- Added immutable `HeavenlyGraphQueryResult` with nodes, relations, selected refs, revision vector, policy revision, scope digest, truncation, and incomplete reason.
- Added `HeavenlyGraphPort.query_semantic(...)` and adapter-backed `query_semantic` on the in-memory adapter (inherited by SQLite).
- Added `HeavenlyGraphSemanticQueryFacade` plus aliases/function helper for discoverability.
- Semantic reads call existing bounded low-level node/relation queries, preserve low-level signatures, filter proposals by default, enforce visibility/actor ownership, and fail closed with `visibility_denied`, `stale_read_set`, or `graph_unavailable`.
- Causal/domain traversal query types are intentionally typed and bounded but left for Task 3 domain behavior.

## Verification

- `python -m pytest -q backend/tests/test_heavenly_graph_semantic_queries.py backend/tests/heavenly_graph_contract.py backend/tests/test_sqlite_heavenly_graph_contract.py backend/tests/test_heavenly_graph_semantics.py`
  - `69 passed, 1 warning`
- `python -m compileall -q` on all changed production modules: passed.
- `git diff --check`: passed.

Controller follow-up:

- Preserved the filtered candidate count before slicing so ordinary results exceeding the requested limit also report `truncated=true`; added a regression test for this case.
- Final review-fix verification: focused `20 passed, 1 warning`; affected graph contracts `79 passed, 1 warning`; `git diff --check` passed.

## Concerns / Deferred

- Task 3 owns causal, conflict, perspective, behavior-turn, and source-impact domain execution.
- Runtime consumers remain intentionally unmodified.

## Review Fix Round 1

- Reordered semantic admission so visibility and exact actor ownership are checked before policy revision; inaccessible stale records now report only `visibility_denied`.
- Node source/record-kind filters now run against a bounded 1000-record candidate window before applying the requested result limit, with truncation surfaced when the window/result bound is reached.
- Replaced arbitrary principal suffix authorization with exact owner IDs or explicit `actor:` / `reader:` canonical forms; prefixes such as `attacker:` are denied.
- Added regression coverage for all three findings against both InMemory and SQLite adapters.

Review-fix verification:

- `python -m pytest -q backend/tests/test_heavenly_graph_semantic_queries.py`: `18 passed, 1 warning`.
- `python -m pytest -q backend/tests/test_heavenly_graph_semantic_queries.py backend/tests/heavenly_graph_contract.py backend/tests/test_sqlite_heavenly_graph_contract.py backend/tests/test_heavenly_graph_semantics.py`: `75 passed, 1 warning`.
- `git diff --check`: passed.
