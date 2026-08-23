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
Task 3: fix round 4 completed; deterministic DFS now returns a complete path under the bounded work budget, with focused and affected graph suites green. Awaiting scoped re-review.
Task 4: fix round 1 committed as 4d06114/017615f; scope stream counters, strict correction admission, typed provenance lineage, SQLite rollback atomicity, focused and affected graph suites green. Awaiting scoped re-review.
