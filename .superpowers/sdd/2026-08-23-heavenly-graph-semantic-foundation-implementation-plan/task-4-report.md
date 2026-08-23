# Task 4 Report: Append-Only Correction, Retraction, And Stale Reads

## Scope

Implemented only Heavenly Graph correction semantics. No CharacterAgentRuntime,
SimingRuntime, story/business policy, resource scoring, LLM, Godot, or external
graph dependency was changed.

## TDD Evidence

The new correction tests were written before the implementation and initially
failed during collection because `GraphCorrectionRequest` was absent. The
implementation then passed the adapter-parametrized correction suite for both
InMemory and SQLite.

## Implemented Contracts

- `GraphCorrectionRequest` supports node/relation targets, target revision,
  `corrected`/`retracted`/`redacted` lifecycle, source refs, semantic metadata,
  optional target scope, and expected revision vector.
- `HeavenlyGraphPort.correct(...)` is part of the graph port.
- `HeavenlyGraphRevisionConflict` now carries expected/current revision vectors
  and affected record refs.
- Corrections append revision `N+1` with `supersedes_revision=N`; original
  records remain untouched and queryable at their historical recorded time.
- Retraction and redaction derivations are excluded from the default effective
  view while historical reads still return the pre-correction record.
- Source linkage, target identity, scope, policy revision, visibility and record
  kind are validated before constructing a correction batch.
- Expected vectors support explicit read-set dimensions; stale vectors fail
  before any write and report affected refs.
- Correction idempotency is request-payload based. Exact retries replay; changed
  payloads under the same correction identity raise an idempotency conflict.
- SQLite serializes correction and persistence under its adapter lock and
  restart tests verify history and idempotency durability.

## Verification

```text
python -m pytest -q backend/tests/test_heavenly_graph_semantics.py
42 passed, 1 warning

python -m pytest -q backend/tests/test_heavenly_graph_semantics.py \
  backend/tests/test_heavenly_graph_semantic_queries.py \
  backend/tests/heavenly_graph_contract.py \
  backend/tests/test_sqlite_heavenly_graph_contract.py
127 passed, 1 warning

git diff --check
passed
```

## Concerns / Deferred

- The correction API remains a graph-foundation primitive; domain owners still
  decide whether a correction is authoritative.
- Full branch lifecycle, checkpoint replay digest, consistency audit and focused
  harness profile remain Tasks 5-8.
