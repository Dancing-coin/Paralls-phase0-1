# Task 7 Report: Adapter Parity And Graph Consistency Audits

## Scope

Implemented only Task 7 of the Heavenly Graph semantic foundation plan. No
CharacterAgentRuntime, SimingRuntime, story policy, resource policy, LLM, or
Godot files were changed.

## Delivered

- Added read-only `HeavenlyGraphConsistencyAudit` and immutable
  `HeavenlyGraphConsistencyReport`/error models.
- Audits effective-independent historical records for orphan relations,
  revision-chain breaks, invalid provenance, scope violations, unsupported
  node/relation semantic types, and broken correction links.
- Added stable error IDs and deterministic ordering:
  `HG-AUDIT-ORPHAN-RELATION`, `HG-AUDIT-REVISION-CHAIN`,
  `HG-AUDIT-PROVENANCE`, `HG-AUDIT-SCOPE`, `HG-AUDIT-SEMANTIC-TYPE`, and
  `HG-AUDIT-CORRECTION-LINK`.
- Added visibility-safe redaction. A reader without the entity's visibility
  scope receives the invariant category but no entity reference or payload.
- Exposed `audit_consistency(...)` on the graph port and both adapters; SQLite
  serializes the audit under its read/write lock.
- Added adapter-agnostic clean-history contracts and a direct InMemory/SQLite
  semantic query + audit parity test.
- Added test-only private bypass fixtures for each invalid invariant; normal
  adapter admission remains unchanged.

## Fix Round 1

- Relation endpoint audits now resolve source and target revisions at the
  relation's `validity.valid_from` and `recorded_at` coordinates, including
  retraction/redaction semantics.
- Correction audits now require the predecessor's original
  `provenance.source_ref` in `correction_target_source_ref`, and require every
  correction source ref in both typed provenance lineage/evidence and semantic
  source-event linkage.
- Policy-revision mismatches are treated as inaccessible for audit payloads,
  matching semantic reader redaction behavior.
- Added bitemporal endpoint, forged correction-link, and stale-policy
  redaction regressions across both InMemory and SQLite adapters.
- Added a malformed-predecessor provenance regression; missing predecessor
  provenance now yields stable provenance/correction audit errors instead of
  raising during the read-only audit.
- Added a forged correction primary-source regression; the correction's typed
  `provenance.source_ref` must retain the predecessor's primary source in
  addition to the explicit target-source attribute.

## Verification

```text
python -m pytest -q backend/tests/heavenly_graph_contract.py backend/tests/test_sqlite_heavenly_graph_contract.py backend/tests/test_heavenly_graph_semantics.py backend/tests/test_heavenly_graph_semantic_queries.py backend/tests/test_heavenly_graph_branch_lifecycle.py backend/tests/test_heavenly_graph_consistency.py
240 passed, 1 warning

python -m compileall -q backend/app
passed

git diff --check
passed
```

The warning is the repository's existing Starlette/httpx deprecation warning
from `backend/tests/conftest.py`.

## Commit

`test: enforce semantic graph adapter parity and audits`
