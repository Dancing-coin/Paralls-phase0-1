# Heavenly Graph Semantic Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the existing Heavenly Graph storage kernel into a typed, scope-aware, bi-temporal, correction-safe, branch-aware semantic graph foundation without changing CharacterAgentRuntime or SimingRuntime behavior.

**Architecture:** Extend the existing Pydantic graph models and `HeavenlyGraphPort`, then implement the same semantics in `InMemoryHeavenlyGraphAdapter` and `SQLiteHeavenlyGraphAdapter`. Semantic queries will require an explicit reader/query context and return bounded results with provenance, revision-vector, policy, scope, and truncation metadata. Consumer integration remains outside this plan.

**Tech Stack:** Python `>=3.11`, Pydantic v2, standard-library `sqlite3`, pytest, existing graph contract tests, existing Harness verification.

**Spec:** `docs/superpowers/specs/current-project-intelligence-upgrade/2026-08-23-heavenly-graph-semantic-foundation-design.md`

## Global Constraints

- Do not modify CharacterAgentRuntime L1/L2/L3/L4 behavior, prompt policy, role state persistence, or role policy engine.
- Do not modify `SimingRuntime.tick(...)`, story orchestration, obligation business transitions, resource scoring, online LLM, or Godot runtime.
- Canonical domain owners remain the only writers of domain facts; Heavenly Graph stores committed facts and governed projections, not world truth.
- `record_kind=proposal` must never be returned as a fact by default queries.
- All semantic queries require reader principal, allowed visibility scopes, world/session/branch, valid time, recorded time, and policy revision.
- All graph traversal is bounded and returns `truncated=true` when any limit is reached.
- Preserve `InMemoryHeavenlyGraphAdapter` for deterministic tests and `SQLiteHeavenlyGraphAdapter` for runtime persistence.
- Do not add an external graph database, vector database, full-text engine, or deletion-based forgetting.
- Preserve unrelated dirty worktree changes and never stage `.runtime/` or `backend/.runtime/` artifacts.

## File Map

- Modify: `backend/app/models/siming_heavenly_graph.py` for typed semantic metadata, query contexts, query results, revision vectors, branch operations, and checkpoint metadata.
- Modify: `backend/app/services/siming_heavenly_graph_port.py` for semantic query, branch, correction, and consistency interfaces.
- Modify: `backend/app/services/in_memory_heavenly_graph.py` for registry validation, scope filtering, correction lifecycle, revision vectors, branches, and deterministic query behavior.
- Modify: `backend/app/services/sqlite_heavenly_graph.py` for schema migration and durable persistence of the extended graph state.
- Create: `backend/app/services/heavenly_graph_semantics.py` for the node/relation registry, scope admission, metadata normalization, and shared validation helpers.
- Create: `backend/app/services/heavenly_graph_queries.py` for causal path, conflict set, behavior-turn, perspective, source-impact, and branch-diff query orchestration.
- Modify: `backend/tests/heavenly_graph_contract.py` with adapter-agnostic semantic contracts.
- Create: `backend/tests/test_heavenly_graph_semantics.py` for registry, metadata, query-context, and structured failure tests.
- Create: `backend/tests/test_heavenly_graph_semantic_queries.py` for causal, conflict, perspective, behavior-turn, source-impact, and branch-diff tests.
- Create: `backend/tests/test_heavenly_graph_branch_lifecycle.py` for fork, close, diff, discard, and production-isolation tests.
- Modify: `backend/tests/test_sqlite_heavenly_graph_contract.py` to run the new shared contracts against SQLite.
- Create: `scripts/verification/verify_heavenly_graph_semantic_foundation.py` for a backend-only graph foundation proof.
- Create: `.harness/profiles/heavenly-graph-semantic-foundation.json` for the focused profile.
- Modify: `docs/harness.md` and `docs/INDEX.md` to document the focused graph profile and its artifacts.

### Task 1: Freeze Semantic Metadata And Registries

**Files:**
- Modify: `backend/app/models/siming_heavenly_graph.py`
- Create: `backend/app/services/heavenly_graph_semantics.py`
- Test: `backend/tests/test_heavenly_graph_semantics.py`

**Interfaces:**
- Add `GraphRecordKind = Literal["fact", "projection", "proposal"]`.
- Add `GraphVisibilityScope = Literal["public", "actor_private", "siming_internal", "authority_only", "branch_only"]`.
- Add `GraphSemanticMetadata(record_kind, visibility_scope, derivation_kind, source_event_refs, source_revision_vector, policy_revision, scope_digest, redaction_reason)`.
- Add `GraphReaderContext(reader_principal, allowed_visibility_scopes, world_id, session_id, story_branch_id, valid_at, recorded_at, policy_revision)`.
- Add `GraphRevisionVector(node_revision, relation_revision, source_revision, policy_revision, branch_revision)`.
- Add `HeavenlyNodeTypeRegistry` and `HeavenlyRelationTypeRegistry` with explicit allowed namespaces, record kinds, and scope rules.
- Preserve existing `GraphProvenance` fields and add semantic metadata as a typed field, not an unvalidated `attributes` convention.

- [ ] **Step 1: Write failing model and registry tests**

Test invalid record kinds, invalid visibility scopes, missing reader fields, forbidden actor-private ownership, unknown node types, forbidden cross-namespace relations, and proposal/fact classification.

- [ ] **Step 2: Run the focused tests and verify expected failures**

Run: `python -m pytest -q backend/tests/test_heavenly_graph_semantics.py`

Expected: collection or assertion failures because the semantic types and registry do not exist.

- [ ] **Step 3: Implement the typed metadata and registry**

Use frozen Pydantic models, explicit literal vocabularies, and deterministic registry dictionaries. Reject unknown semantic types and invalid namespace/scope combinations before adapter writes.

- [ ] **Step 4: Run focused tests**

Run: `python -m pytest -q backend/tests/test_heavenly_graph_semantics.py`

Expected: all metadata and registry tests pass.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/models/siming_heavenly_graph.py backend/app/services/heavenly_graph_semantics.py backend/tests/test_heavenly_graph_semantics.py
git commit -m "feat: add Heavenly Graph semantic metadata registry"
```

### Task 2: Add Reader Context And Structured Query Results

**Files:**
- Modify: `backend/app/models/siming_heavenly_graph.py`
- Modify: `backend/app/services/siming_heavenly_graph_port.py`
- Create: `backend/app/services/heavenly_graph_queries.py`
- Test: `backend/tests/test_heavenly_graph_semantic_queries.py`

**Interfaces:**
- Add `NodeLookupQuery`, `RelationLookupQuery`, `CausalPathQuery`, `PerspectiveQuery`, `ConflictSetQuery`, `BehaviorTurnQuery`, and `SourceImpactQuery`.
- Add `HeavenlyGraphQueryResult(nodes, relations, selected_node_refs, selected_relation_refs, revision_vector, policy_revision, scope_digest, truncated, incomplete_reason)`.
- Add `HeavenlyGraphPort.query_semantic(query) -> HeavenlyGraphQueryResult`.
- Keep existing low-level `query_nodes`, `query_relations`, and `query_subgraph` signatures for compatibility tests.

- [ ] **Step 1: Write failing query-context and failure-contract tests**

Cover missing reader principal, missing scope, proposal exclusion, visibility denial without node-existence leakage, explicit valid/recorded time, and deterministic result metadata.

- [ ] **Step 2: Run the focused tests**

Run: `python -m pytest -q backend/tests/test_heavenly_graph_semantic_queries.py`

Expected: failures because semantic query models and the Port method are absent.

- [ ] **Step 3: Implement typed query models and query facade**

The facade must validate reader context, call existing bounded low-level queries, filter semantic metadata, and return `incomplete_reason` values such as `visibility_denied`, `stale_read_set`, and `graph_unavailable`.

- [ ] **Step 4: Run focused tests**

Run: `python -m pytest -q backend/tests/test_heavenly_graph_semantic_queries.py`

Expected: query context and structured failure tests pass.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/models/siming_heavenly_graph.py backend/app/services/siming_heavenly_graph_port.py backend/app/services/heavenly_graph_queries.py backend/tests/test_heavenly_graph_semantic_queries.py
git commit -m "feat: add scoped Heavenly Graph semantic queries"
```

### Task 3: Implement Causal, Conflict, Perspective, And Turn Queries

**Files:**
- Modify: `backend/app/services/heavenly_graph_queries.py`
- Modify: `backend/app/services/in_memory_heavenly_graph.py`
- Modify: `backend/app/services/sqlite_heavenly_graph.py`
- Test: `backend/tests/test_heavenly_graph_semantic_queries.py`

**Interfaces:**
- `CausalPathQuery` returns bounded paths following registered causal relation types.
- `ConflictSetQuery` groups concurrent claims by subject/property and preserves all revisions.
- `PerspectiveQuery` filters by reader principal and visibility scope.
- `BehaviorTurnQuery` returns nodes/relations grouped by `turn_id` or `correlation_id` without implementing role behavior.
- `SourceImpactQuery` returns all derived records that reference a source revision.

- [ ] **Step 1: Add failing causal/conflict/perspective/turn/source-impact tests**

Seed facts, projections, proposals, private views, contradictory claims, and behavior-turn references in both adapters. Assert deterministic ordering and bounded truncation.

- [ ] **Step 2: Run tests and confirm failures**

Run: `python -m pytest -q backend/tests/test_heavenly_graph_semantic_queries.py`

- [ ] **Step 3: Implement adapter-backed semantic query execution**

Use existing effective-version selection and relation traversal. Do not scan or return unbounded graph state from the semantic facade. Preserve `truncated=true` whenever node, relation, path, or depth limits are reached.

- [ ] **Step 4: Run tests**

Run: `python -m pytest -q backend/tests/test_heavenly_graph_semantic_queries.py`

Expected: all semantic query tests pass for InMemory and SQLite.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/services/heavenly_graph_queries.py backend/app/services/in_memory_heavenly_graph.py backend/app/services/sqlite_heavenly_graph.py backend/tests/test_heavenly_graph_semantic_queries.py
git commit -m "feat: support causal conflict perspective and turn queries"
```

### Task 4: Add Correction, Retraction, And Stale Revision Semantics

**Files:**
- Modify: `backend/app/models/siming_heavenly_graph.py`
- Modify: `backend/app/services/siming_heavenly_graph_port.py`
- Modify: `backend/app/services/heavenly_graph_semantics.py`
- Modify: `backend/app/services/in_memory_heavenly_graph.py`
- Modify: `backend/app/services/sqlite_heavenly_graph.py`
- Test: `backend/tests/test_heavenly_graph_semantics.py`

**Interfaces:**
- Add `GraphCorrectionRequest(target_kind, target_id, target_revision, correction_kind, source_refs, semantic_metadata, expected_revision_vector)`.
- Add `HeavenlyGraphPort.correct(request) -> HeavenlyGraphWriteResult`.
- Add `HeavenlyGraphRevisionConflict` payload fields for expected/current vectors and affected refs.
- Support `active -> superseded -> corrected/retracted/redacted` history without deleting the original record.

- [ ] **Step 1: Write failing correction and stale-read tests**

Assert correction appends a new revision, old history remains auditable, default current query excludes retracted records, conflict claims coexist, and stale expected vectors cause zero writes.

- [ ] **Step 2: Run focused tests**

Run: `python -m pytest -q backend/tests/test_heavenly_graph_semantics.py`

- [ ] **Step 3: Implement correction admission and revision-vector checks**

Validate immediate predecessor, target identity, source linkage, scope, policy revision, and expected vector before constructing the append-only correction batch.

- [ ] **Step 4: Run focused tests**

Run: `python -m pytest -q backend/tests/test_heavenly_graph_semantics.py`

Expected: correction, conflict, and stale-read tests pass.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/models/siming_heavenly_graph.py backend/app/services/siming_heavenly_graph_port.py backend/app/services/heavenly_graph_semantics.py backend/app/services/in_memory_heavenly_graph.py backend/app/services/sqlite_heavenly_graph.py backend/tests/test_heavenly_graph_semantics.py
git commit -m "feat: add append-only graph correction and stale reads"
```

### Task 5: Implement Branch Fork, Diff, Close, And Discard

**Files:**
- Modify: `backend/app/models/siming_heavenly_graph.py`
- Modify: `backend/app/services/siming_heavenly_graph_port.py`
- Modify: `backend/app/services/in_memory_heavenly_graph.py`
- Modify: `backend/app/services/sqlite_heavenly_graph.py`
- Create: `backend/tests/test_heavenly_graph_branch_lifecycle.py`

**Interfaces:**
- Add `GraphBranchForkRequest(source_scope, target_branch_id, fork_valid_at, fork_recorded_at, source_revision_vector)`.
- Add `GraphBranchDiffQuery(left_scope, right_scope, reader_context, limits)`.
- Add `GraphBranchLifecycleRequest(branch_scope, operation, expected_revision_vector)` where operation is `fork`, `close_node`, `discard`, or `admit`.
- Add `HeavenlyGraphPort.fork_branch`, `diff_branches`, and `lifecycle_branch`.

- [ ] **Step 1: Write failing branch tests**

Cover fork snapshot isolation, branch-only writes, diff output, permanent node close marker, discard visibility, production non-contamination, source-vector mismatch, and no branch resurrection.

- [ ] **Step 2: Run tests**

Run: `python -m pytest -q backend/tests/test_heavenly_graph_branch_lifecycle.py`

Expected: failures because the branch lifecycle API is absent.

- [ ] **Step 3: Implement branch lifecycle in both adapters**

Represent branch lifecycle as append-only markers and scoped graph records. `discard` must make branch records unavailable to production queries without deleting audit history. `admit` requires an explicit target branch and matching source vector.

- [ ] **Step 4: Run tests**

Run: `python -m pytest -q backend/tests/test_heavenly_graph_branch_lifecycle.py`

Expected: all branch tests pass for InMemory and SQLite.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/models/siming_heavenly_graph.py backend/app/services/siming_heavenly_graph_port.py backend/app/services/in_memory_heavenly_graph.py backend/app/services/sqlite_heavenly_graph.py backend/tests/test_heavenly_graph_branch_lifecycle.py
git commit -m "feat: add Heavenly Graph branch lifecycle"
```

### Task 6: Extend Checkpoint Digest And Replay Equivalence

**Files:**
- Modify: `backend/app/models/siming_heavenly_graph.py`
- Modify: `backend/app/services/in_memory_heavenly_graph.py`
- Modify: `backend/app/services/sqlite_heavenly_graph.py`
- Modify: `backend/tests/heavenly_graph_contract.py`
- Modify: `backend/tests/test_sqlite_heavenly_graph_contract.py`

**Interfaces:**
- Extend checkpoint metadata with schema version, source revision vector, policy revision, scope digest, and replay digest.
- Add `HeavenlyGraphPort.replay_from_checkpoint(checkpoint_ref, tail_batches) -> HeavenlyGraphSnapshot`.

- [ ] **Step 1: Write failing checkpoint/replay tests**

Create a checkpoint, append a correction and a branch-local tail, replay full history and checkpoint-plus-tail, and assert equivalent effective nodes, relations, metadata, and digest.

- [ ] **Step 2: Run the adapter contract tests**

Run: `python -m pytest -q backend/tests/test_sqlite_heavenly_graph_contract.py backend/tests/heavenly_graph_contract.py`

- [ ] **Step 3: Implement deterministic digest and replay**

Hash canonical sorted node/relation payloads plus scope, revisions, policy, and schema version. Never use checkpoint data as a replacement for source history.

- [ ] **Step 4: Run both adapter contracts**

Run: `python -m pytest -q backend/tests/test_sqlite_heavenly_graph_contract.py backend/tests/heavenly_graph_contract.py`

Expected: InMemory and SQLite produce equal replay digests.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/models/siming_heavenly_graph.py backend/app/services/in_memory_heavenly_graph.py backend/app/services/sqlite_heavenly_graph.py backend/tests/heavenly_graph_contract.py backend/tests/test_sqlite_heavenly_graph_contract.py
git commit -m "feat: make graph checkpoints replay-verifiable"
```

### Task 7: Enforce Adapter Parity And Graph Consistency Audits

**Files:**
- Modify: `backend/tests/heavenly_graph_contract.py`
- Modify: `backend/tests/test_sqlite_heavenly_graph_contract.py`
- Create: `backend/app/services/heavenly_graph_consistency.py`
- Create: `backend/tests/test_heavenly_graph_consistency.py`

**Interfaces:**
- Add `HeavenlyGraphConsistencyAudit(scope, reader_context) -> HeavenlyGraphConsistencyReport`.
- Report orphan relations, invalid revision chains, invalid provenance, scope violations, unsupported semantic types, and broken correction links.
- Make the same contract suite run against InMemory and SQLite adapters.

- [ ] **Step 1: Write failing consistency-audit tests**

Construct invalid fixtures only through test-only bypass helpers and assert each invariant is reported with stable error IDs while valid graphs report no errors.

- [ ] **Step 2: Run tests**

Run: `python -m pytest -q backend/tests/test_heavenly_graph_consistency.py`

- [ ] **Step 3: Implement the read-only consistency audit**

Audit effective and historical records without mutating the graph. Use deterministic ordering and redact inaccessible payload values while retaining error category.

- [ ] **Step 4: Run full graph contract tests**

Run: `python -m pytest -q backend/tests/heavenly_graph_contract.py backend/tests/test_sqlite_heavenly_graph_contract.py backend/tests/test_heavenly_graph_semantics.py backend/tests/test_heavenly_graph_semantic_queries.py backend/tests/test_heavenly_graph_branch_lifecycle.py backend/tests/test_heavenly_graph_consistency.py`

- [ ] **Step 5: Commit**

```powershell
git add backend/app/services/heavenly_graph_consistency.py backend/tests/test_heavenly_graph_consistency.py backend/tests/heavenly_graph_contract.py backend/tests/test_sqlite_heavenly_graph_contract.py
git commit -m "test: enforce semantic graph adapter parity and audits"
```

### Task 8: Add Focused Graph Foundation Verification And Documentation

**Files:**
- Create: `scripts/verification/verify_heavenly_graph_semantic_foundation.py`
- Create: `.harness/profiles/heavenly-graph-semantic-foundation.json`
- Modify: `docs/harness.md`
- Modify: `docs/INDEX.md`
- Test: `scripts/verification/tests/test_heavenly_graph_semantic_foundation_verify.py`

**Interfaces:**
- Verification script runs only graph foundation contracts and writes `.harness/verification/heavenly-graph-semantic-foundation-report.json` and `.md`.
- Profile has `requires_godot=false`, uses a verifier-owned temporary SQLite database, and never starts CharacterAgentRuntime or SimingRuntime.

- [ ] **Step 1: Write failing verifier tests**

Assert the profile manifest, report IDs, SQLite temporary database ownership, InMemory/SQLite parity, scope denial, correction, branch isolation, and replay digest checks.

- [ ] **Step 2: Run verifier tests**

Run: `python -m pytest -q scripts/verification/tests/test_heavenly_graph_semantic_foundation_verify.py`

- [ ] **Step 3: Implement the focused verifier and profile**

The verifier must fail closed on missing semantic metadata, unbounded results, scope leakage, stale writes, correction-chain breaks, branch contamination, or replay digest mismatch.

- [ ] **Step 4: Run focused verification**

Run: `python scripts/verification/harness.py --profile heavenly-graph-semantic-foundation`

Expected: profile exit code `0` and a report proving graph-only behavior; no role or Siming runtime markers are accepted as evidence.

- [ ] **Step 5: Run docs and complete graph test suite**

Run: `python scripts/verification/check_docs.py` and the Task 7 full graph contract command.

- [ ] **Step 6: Commit**

```powershell
git add scripts/verification/verify_heavenly_graph_semantic_foundation.py scripts/verification/tests/test_heavenly_graph_semantic_foundation_verify.py .harness/profiles/heavenly-graph-semantic-foundation.json docs/harness.md docs/INDEX.md
git commit -m "test: add Heavenly Graph semantic foundation gate"
```

## Completion Gate

Before claiming this plan complete, run:

```powershell
python -m pytest -q backend/tests/heavenly_graph_contract.py backend/tests/test_sqlite_heavenly_graph_contract.py backend/tests/test_heavenly_graph_semantics.py backend/tests/test_heavenly_graph_semantic_queries.py backend/tests/test_heavenly_graph_branch_lifecycle.py backend/tests/test_heavenly_graph_consistency.py
python scripts/verification/harness.py --profile heavenly-graph-semantic-foundation
python scripts/verification/check_docs.py
```

Do not run or claim role/司命 integration as part of this phase. The next phase may consume this graph foundation only after this completion gate passes and receives separate approval.
