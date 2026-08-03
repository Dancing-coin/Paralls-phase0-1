# Siming Durable Heavenly Graph Phase 1.1-7 Program Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver durable Siming six-domain memory, `char_b` private five-pool graph memory, graph-backed story convergence, resource-aware staging, online-LLM bridge proposals, and a real Authority-to-Godot acceptance loop.

**Architecture:** Execute seven dependency-gated phase plans in order. The graph is canonical memory, SQLite is the runtime adapter, and `SimingRuntime.tick(...)` remains the only decision owner; state trees, summaries, read models, and checkpoints are projections rather than alternate story truth.

**Tech Stack:** Python `>=3.11`, Pydantic v2, standard-library `sqlite3`, pytest, existing FastAPI/System L6 runtime, existing Godot 4 project, existing Harness Engineering.

## Global Constraints

- Source design: `docs/superpowers/specs/current-project-intelligence-upgrade/2026-08-03-current-project-siming-durable-heavenly-graph-phase2-7-integration-design.md`.
- Delivery order is Phase 1.1, 2, 3, 4, 5, 6, then 7; a failed dedicated profile blocks dependent phases.
- `SimingRuntime.tick(...)` is the only Siming decision path and each correlation ID has at most one selected decision and one dispatch family.
- Graph memory is canonical; compression changes only the active subgraph and never deletes long-term memory.
- World/ESM/L1 results remain authority; the graph records confirmed outcomes but cannot manufacture them.
- `char_b` is the only initial graph-backed heavy actor; `char_a` remains on `CharacterAgentMemoryStore`.
- Siming reads actor-private memory through a read-only gateway and never writes actor memory.
- LLM output is proposal-only and cannot write graph state, activate nodes, publish catalysts, or alter actor memory.
- Phase 7 acceptance requires a real online LLM call and real Godot runtime evidence; fake/disabled providers cannot satisfy it.
- Reuse current `MainDemo.tscn`, `char_b`, `char_c`, `obj_letter`, `env_lamp`, dialogue/voice path, camera, and realization keys; add no art.
- Add no external graph database, vector database, full-text engine, distributed graph, or deletion-based forgetting.
- Preserve unrelated working-tree changes, especially `docs/架构/整体架构.md`.

---

## Dependency Order

| Gate | Plan | Entry condition | Exit proof |
| --- | --- | --- | --- |
| 1 | `2026-08-03-phase1-1-durable-graph-hardening-implementation-plan.md` | Existing in-memory foundation passes | In-memory and SQLite shared contract, restart recovery, bounded traversal |
| 2 | `2026-08-03-phase2-siming-six-domain-memory-implementation-plan.md` | Gate 1 passes | Six-domain writes and deterministic context rebuild |
| 3 | `2026-08-03-phase3-actor-five-pool-graph-memory-implementation-plan.md` | Gate 2 passes | `char_b` graph-backed five-pool recall and cross-actor isolation |
| 4 | `2026-08-03-phase4-storyline-obligation-attractor-implementation-plan.md` | Gate 3 passes | Permanent node closure, obligation transform, attractor reachability |
| 5 | `2026-08-03-phase5-resource-capability-staging-implementation-plan.md` | Gate 4 passes | Existing-resource scoring and truthful staging lifecycle |
| 6 | `2026-08-03-phase6-adaptive-bridge-implementation-plan.md` | Gate 5 passes | Typed, deterministic bridge validation and no resurrection |
| 7 | `2026-08-03-phase7-full-runtime-integration-implementation-plan.md` | Gate 6 passes and live prerequisites exist | Online LLM + backend + SQLite + Authority + Godot archived evidence |

### Task 1: Execute Phase 1.1 Through Phase 3 Memory Gates

**Files:**
- Follow: `docs/superpowers/plans/current-project-intelligence-upgrade/2026-08-03-phase1-1-durable-graph-hardening-implementation-plan.md`
- Follow: `docs/superpowers/plans/current-project-intelligence-upgrade/2026-08-03-phase2-siming-six-domain-memory-implementation-plan.md`
- Follow: `docs/superpowers/plans/current-project-intelligence-upgrade/2026-08-03-phase3-actor-five-pool-graph-memory-implementation-plan.md`

**Interfaces:**
- Consumes: existing `HeavenlyGraphPort`, `InMemoryHeavenlyGraphAdapter`, `CharacterAgentRuntime`, and `CharacterMemoryRecordBundle`.
- Produces: durable scoped graph storage, `SimingHeavenlyMemoryService`, `SimingContextCompiler`, `CharacterGraphMemoryStore`, and `ActorMemoryReadGateway`.

- [ ] **Step 1: Complete Phase 1.1 and run its gate**

Run: `python scripts/verification/harness.py --profile siming-heavenly-graph-foundation`

Expected: PASS with namespace/owner isolation, deterministic bounded traversal, SQLite contract parity, and restart recovery evidence.

- [ ] **Step 2: Complete Phase 2 and run its gate**

Run: `python scripts/verification/harness.py --profile siming-six-domain-memory`

Expected: PASS with all six domains present and an identical compiled context after deleting cached projections.

- [ ] **Step 3: Complete Phase 3 and run its gate**

Run: `python scripts/verification/harness.py --profile siming-actor-memory-read`

Expected: PASS with `char_b` Event/Observation persistence, `char_a` light-store compatibility, restart recall, and zero private-memory leakage.

### Task 2: Execute Phase 4 Through Phase 6 Narrative Gates

**Files:**
- Follow: `docs/superpowers/plans/current-project-intelligence-upgrade/2026-08-03-phase4-storyline-obligation-attractor-implementation-plan.md`
- Follow: `docs/superpowers/plans/current-project-intelligence-upgrade/2026-08-03-phase5-resource-capability-staging-implementation-plan.md`
- Follow: `docs/superpowers/plans/current-project-intelligence-upgrade/2026-08-03-phase6-adaptive-bridge-implementation-plan.md`

**Interfaces:**
- Consumes: durable six-domain graph, actor read gateway, authored/runtime story split, and existing resource/skill contracts.
- Produces: terminal story outcomes, obligation transformations, reachable attractors, staging records, and validated bridge nodes.

- [ ] **Step 1: Complete Phase 4 and run its gate**

Run: `python scripts/verification/harness.py --profile siming-story-runtime`

Expected: PASS with N3 divergence resolution, terminal N4 closure, N5 unreachable state, and O2-to-O6 transformation.

- [ ] **Step 2: Complete Phase 5 and run its gate**

Run: `python scripts/verification/harness.py --profile siming-resource-staging`

Expected: PASS proving resource scores never bypass facts/autonomy and staging failure never resolves a node or obligation.

- [ ] **Step 3: Complete Phase 6 and run its gate**

Run: `python scripts/verification/harness.py --profile siming-adaptive-bridge`

Expected: PASS proving `private_confrontation` requires `char_b` observation, open O6, executable resources, and a new runtime node ID.

### Task 3: Execute Phase 7 and Archive Full Runtime Proof

**Files:**
- Follow: `docs/superpowers/plans/current-project-intelligence-upgrade/2026-08-03-phase7-full-runtime-integration-implementation-plan.md`
- Verify: `.harness/verification/`

**Interfaces:**
- Consumes: all prior phase contracts plus configured online Siming LLM route and `GODOT_EXE`.
- Produces: one graph-backed runtime decision chain and matching archived Harness/Godot evidence.

- [ ] **Step 1: Run Phase 7 preflight**

Run: `python scripts/verification/verify_siming_heavenly_runtime.py --preflight`

Expected: PASS only when SQLite path, `GODOT_EXE`, `SIMING_LLM_MODE=http`, live route, model, and API key are available without printing secrets.

- [ ] **Step 2: Run the live dedicated profile**

Run: `python scripts/verification/harness.py --profile siming-heavenly-runtime`

Expected: PASS with before/after screenshots, online request audit, graph transaction refs, single dispatch correlation, and restart-restored `char_b` memory.

- [ ] **Step 3: Run mainline and broad regression gates**

Run: `python scripts/verification/harness.py --profile mainline-unified-runtime`

Expected: PASS.

Run: `python scripts/verification/harness.py --profile all`

Expected: PASS with a matching archived manifest/report `run_id` and `suite_id`; hosted `ci-non-godot` is not a substitute for this local proof.

- [ ] **Step 4: Commit the complete program**

```powershell
git add backend scripts scenes project.godot .harness/profiles docs/harness.md docs/INDEX.md docs/superpowers/plans/current-project-intelligence-upgrade
git commit -m "feat: integrate durable Siming heavenly graph runtime"
```
