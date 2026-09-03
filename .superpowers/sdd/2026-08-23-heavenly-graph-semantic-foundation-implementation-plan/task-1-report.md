# Task 1 Report: Semantic Metadata And Registries

## Scope

- Added typed `GraphRecordKind`, `GraphVisibilityScope`, and derivation vocabularies.
- Added frozen Pydantic `GraphRevisionVector`, `GraphSemanticMetadata`, and `GraphReaderContext` models.
- Added typed `semantic_metadata` fields to `HeavenlyGraphNode` and `HeavenlyGraphRelation`, with compatibility defaults for existing graph writers.
- Added deterministic node and relation registries with explicit namespace, record-kind, visibility, and actor-private owner validation.
- Added focused tests for invalid semantic values, reader context completeness, actor-private ownership, unknown node types, namespace admission, cross-namespace relation restrictions, and fact/proposal classification.

## TDD Evidence

### Red

Command:

```text
python -m pytest -q backend/tests/test_heavenly_graph_semantics.py
```

Result: collection failed because `GraphReaderContext` and the other semantic types were not yet defined in `siming_heavenly_graph.py`.

### Green

Command:

```text
python -m pytest -q backend/tests/test_heavenly_graph_semantics.py
```

Result: `9 passed, 1 warning`.

Compatibility checks:

```text
python -m pytest -q backend/tests/test_siming_heavenly_graph_models.py backend/tests/test_sqlite_heavenly_graph_contract.py
```

Result: `45 passed, 1 warning`.

`git diff --check` passed.

## Boundary Notes

This task only establishes models and validation registries. Adapter admission, semantic query filtering, correction lifecycle, and runtime integration remain for later tasks. No CharacterAgentRuntime or SimingRuntime behavior was changed.

## Review Fix: Adapter Write Admission

Review found that the initial registry work was not invoked by adapter writes. The shared `InMemoryHeavenlyGraphAdapter.write_batch(...)` path now validates node and relation semantics before computing idempotency state or mutating storage. `SQLiteHeavenlyGraphAdapter` inherits this path while holding its write lock, so both adapters enforce the same admission rule.

Legacy records that retain the compatibility `policy:legacy` metadata are constrained to the existing known graph type families; arbitrary unknown legacy names are still rejected. Explicit semantic metadata always uses the frozen registry rules.

### Fix-round Red

Command:

```text
python -m pytest -q backend/tests/test_heavenly_graph_semantics.py
```

Result before admission wiring: `4 failed, 9 passed, 1 warning`; both adapters accepted unknown node types and invalid namespace/scope combinations.

### Fix-round Green

Commands:

```text
python -m pytest -q backend/tests/test_heavenly_graph_semantics.py backend/tests/test_siming_heavenly_graph_models.py backend/tests/test_sqlite_heavenly_graph_contract.py
git diff --check
```

Result: `62 passed, 1 warning`; whitespace check passed. Focused tests now cover InMemory and SQLite rejection of unknown semantic node types, unknown semantic relation types, invalid namespace, and invalid visibility scope before idempotency persistence.

Fix commit: `5ec861f fix: enforce Heavenly Graph semantic write admission`.

## Review Fix Round 2: Explicit Legacy Admission

The first compatibility fallback caught every registry `ValueError`, which both admitted invalid legacy combinations and rejected existing story writer types. The fallback now uses explicit rules for `authored_story_blueprint`, `runtime_story_node`, `story_authority_outcome`, `narrative_obligation`, `narrative_attractor`, adaptive bridge audits, historical `memory:`/`projection:` names, actor memory names, and `world_fact`. Each rule checks namespace, record kind, visibility, and actor ownership; legacy relation names have the same explicit checks.

Added adapter tests for invalid legacy node namespace/visibility and invalid legacy relation namespace. No runtime consumer behavior was changed.

### Round 2 Evidence

```text
python -m pytest -q backend/tests/test_heavenly_graph_semantics.py backend/tests/test_siming_heavenly_graph_models.py backend/tests/test_sqlite_heavenly_graph_contract.py backend/tests/test_siming_story_graph_runtime.py backend/tests/test_siming_story_obligation_runtime.py backend/tests/test_siming_story_node_staging.py backend/tests/test_siming_adaptive_bridge.py backend/tests/test_siming_heavenly_runtime_composition.py backend/tests/test_character_graph_memory_store.py
```

Result: `137 passed, 2 warnings`.

```text
python -m pytest -q
```

Result: `3885 passed, 7 warnings in 80.03s`.
