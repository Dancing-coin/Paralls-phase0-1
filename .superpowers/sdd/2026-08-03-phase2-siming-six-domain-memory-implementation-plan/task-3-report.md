# Task 3 Report: Bounded Context and Disposable Projections

## Files Changed

- `backend/app/services/siming_context_compiler.py`
- `backend/app/services/siming_story_projection.py`
- `backend/tests/test_siming_context_compiler.py`
- `backend/tests/test_siming_story_projection.py`

## Key Decisions

- The compiler calls `query_subgraph` with sorted, de-duplicated seed IDs, `direction="both"`, `max_depth=4`, and the request temporal and limit bounds.
- Compiler input is sorted by graph node ID. Only `memory:*` nodes are parsed; their node ID and declared memory domain must match the validated entry, otherwise compilation rejects the data.
- Buckets and selected graph references are deterministic. The SHA-256 context hash uses compact, sorted-key JSON over the request, validated graph-derived entries, selected IDs, and truncation state.
- Projection remains a pure transformation: it has no graph port, writer, or memory-write surface. Its IDs and `NarrativeReadModel.derived_from_snapshot_ref` use `context_hash`; mirror and editable authority values use the existing runtime-state vocabulary.
- `debug_summary` accepts JSON values only.

## Verification

Command:

```powershell
python -m pytest backend/tests/test_siming_heavenly_memory_models.py backend/tests/test_siming_six_domain_memory.py backend/tests/test_siming_context_compiler.py backend/tests/test_siming_story_projection.py -q
```

Output: `9 passed, 1 warning in 0.97s`.

The warning is the pre-existing Starlette/httpx deprecation warning from `backend/tests/conftest.py`.

## Self-Review

- Fresh compilation with opposite graph-return order produces an identical context and hash.
- All six domains are bucketed, with entry ordering asserted.
- Temporal filtering is exercised through the real in-memory graph, and compilation does not delete the durable entry.
- Projection bundle fields, graph-basis reference, authority invariants, and JSON-only debug data are covered.
- No graph storage or port behavior, runtime integration, harness profile, or Phase 1 code was changed.

## Commit

This report is included in the focused Task 3 commit created after verification.

## Concerns

None. Godot runtime verification is not applicable to this backend-only task.
