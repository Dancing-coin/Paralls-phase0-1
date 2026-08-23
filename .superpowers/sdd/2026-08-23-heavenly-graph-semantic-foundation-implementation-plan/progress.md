# SDD ledger — plan: docs/superpowers/plans/current-project-intelligence-upgrade/2026-08-23-heavenly-graph-semantic-foundation-implementation-plan.md

## Preflight

Base: 09d9d07
Scope: graph foundation only; role and Siming runtime consumers excluded.

| Task | Shared files/interfaces | Preflight ruling |
| --- | --- | --- |
| 1 -> 2 | `siming_heavenly_graph.py`; semantic metadata consumed by query context | Task 1 defines stable metadata/context types before Task 2 query contracts. |
| 1 -> 3 | semantic registry used by adapters/query facade | Task 3 may only consume Task 1 registry; no duplicate vocabularies. |
| 2 -> 3 | `HeavenlyGraphQueryResult`; `query_semantic` | Task 2 owns query API/result shape; Task 3 implements domain query behavior. |
| 3 -> 4 | effective version/provenance selection | Task 4 appends correction records using Task 3 query semantics. |
| 4 -> 6 | revision vectors/checkpoint metadata | Task 6 extends Task 4 revision metadata without changing correction history semantics. |
| 5 -> 6 | branch source vectors and checkpoint scope | Task 5 owns branch lifecycle; Task 6 hashes branch metadata in replay digest. |
| 6 -> 7 | replay digest and adapter parity | Task 7 audits the finalized effective/historical graph surface. |
| 7 -> 8 | consistency report and focused contracts | Task 8 invokes only graph contracts; no consumer runtime. |

## Task self-consistency

| Task | Files vs interfaces | Ruling |
| --- | --- | --- |
| 1 | model/registry files and semantic tests match declared types | proceed |
| 2 | query models, Port method, facade test match | proceed |
| 3 | query facade and both adapters match bounded query requirements | proceed |
| 4 | correction API and revision tests match append-only requirement | proceed |
| 5 | branch request APIs and branch tests match lifecycle requirement | proceed |
| 6 | checkpoint/replay fields and contract tests match | proceed |
| 7 | audit service and adapter parity tests match | proceed |
| 8 | verifier/profile/docs/test files match graph-only scope | proceed |

Ruling: execute Task 1 first; later tasks must preserve the explicit non-goal boundary.

## Execution

Task 1: dispatched to `/root/graph_task1` from base `09d9d07`; brief: `task-1-brief.md`.

Task 1: fix round 1/5 (admission wired; legacy fallback too broad; review rejected; commits 2aac065..2324ce7).
Task 1: fix round 2/5 (explicit legacy mappings; full-suite regression repaired; review approved; commit a8576a1).
Task 1: complete (commits 2aac065..a8576a1, review clean).
Task 2: fix round 1/5 (visibility ordering, semantic filter window, canonical principal; review found truncation accounting gap).
Task 2: fix round 1/5 resolved in commit 456fd4a; scoped re-review approved.
Task 2: complete (commits 631e888..456fd4a, review clean).
Task 3: review rejected; fix round 1 required for implicit Perspective scope, candidate-window truncation propagation, causal max_paths output bound, and bounded causal adapter reads.
Task 3: fix round 1 scoped re-review rejected; max_paths must cap complete paths, and all-noncausal relation filters must return no causal edges.
Task 3: fix round 2 re-review found unbounded pending-path work queue; fix round 3 must add deterministic traversal budget and final evidence commit.
Task 3: fix round 3 committed as 2e04ef3/0b5da4c; scoped re-review approved.
Task 3: final re-review found bounded BFS can return an empty union despite reachable complete paths; Task 3 remains open until traversal prioritizes a complete path under budget.
Task 3: fix round 4 committed as 47a4c95/9813dc1; scoped re-review approved.
Task 3: complete (commits 09ddb14..9813dc1, review clean).
Task 4: review rejected; fix scope-level revision streams, strict correction metadata/source checks, typed provenance preservation, and SQLite rollback atomicity before advancing.
Task 4: fix commits 4d06114/017615f/2e1841c; scoped re-review approved.
Task 4: complete (commits d2ed863..2e1841c, review clean).
Task 5: review rejected; normalize fork diff equality, filter lifecycle markers by reader context, enforce branch-scope/terminal write admission, and repair lifecycle time/admit audit details.
Task 5: admit audit marker exists, but target copied stream vector remains zero; fix target node/relation stream counters and assert marker/vector coherence.
Task 5: final audit fix commits 15cd129/88ed64c; scoped re-review approved.
Task 5: complete (commits 56ed04b..88ed64c, review clean).
Task 6: review rejected; replay must retain non-effective revision-chain predecessors and reject retroactive tail timestamps before equivalence can be claimed.
Task 6: fix round 1 preserves full frontier but lacks SQLite restart replay parity; add persisted frontier/recovery regression before completion.
Task 6: fix commits fc05521/a5447f8/33db117; scoped re-review approved.
Task 6: complete (commits 68f4e64..33db117, review clean).
Task 7: review rejected; add temporal endpoint audit, typed correction source preservation checks, and policy-aware redaction.
Task 7: fix round 1 rejected; guard malformed predecessor provenance and verify correction primary typed source_ref retention.
Task 6: fix round 1 adds historical replay frontiers, strict checkpoint tail recorded-time admission, and dual-adapter regressions; focused graph suites green; awaiting scoped re-review.
Task 6: fix round 2 recovers legacy SQLite checkpoints with missing replay frontiers from durable recorded-time source history; file-backed future/retracted restart parity and immutability regressions pass.
Task 5: final audit fix sets copied target stream counters before target admission marker construction and pins its source/vector to the actual admitted source. Dual-adapter regression and affected graph suite pass; awaiting scoped re-review.
Task 5: fix round 1 committed as 273d672/d488c9c; branch suite 51 passed and affected graph suites 192 passed; awaiting scoped re-review.
Task 5 fix round still needs coordinate fidelity: fork must honor `fork_valid_at`/`fork_recorded_at` while propagating close state and markers; do not accept current-snapshot substitution without a regression.
Task 5 fix round 2: lifecycle markers now obey reader `recorded_at`; all explicit semantic `branch:` scopes require a registered fork, while the pre-semantic `policy:legacy` contract path remains compatible. Focused and affected graph suites green; awaiting scoped re-review.
Task 3: fix round 4 completed; deterministic DFS now returns a complete path under the bounded work budget, with focused and affected graph suites green. Awaiting scoped re-review.
Task 4: fix round 1 committed as 4d06114/017615f; scope stream counters, strict correction admission, typed provenance lineage, SQLite rollback atomicity, focused and affected graph suites green. Awaiting scoped re-review.
Task 7: scoped re-review of e000689 found typed correction provenance source_ref was still not compared with its predecessor. Fix round 2/5 is active; add a dual-adapter regression and compare the primary typed source_ref as well as the retained target attribute.
Task 7: fix round 2/5 complete (typed primary correction provenance addressed; scoped re-review approved; commit 14a1fd9).
Task 8: initial review rejected; fix round 1/5 must exercise all required proofs against SQLite, include the full Task 7 graph contract suite, make report evidence deterministic after temporary DB cleanup, and make helper evaluation fail closed on focused pytest status.
Task 8: fix round 1/5 complete (all proofs dual-adapter, six-suite gate, stable evidence, fail-closed helper; scoped re-review approved; commit 6596da2).
Final review: request changes; fix wave 1 must address five P1 graph defects: SQLite write/checkpoint rollback atomicity, canonical-owner/provenance admission, relation endpoint visibility closure, branch lifecycle recorded-time/vector fidelity, and full revision-chain-preserving fork/admit. Also address bounded branch diff and cross-namespace relation admission if possible; residual privacy vector leakage requires explicit triage.
