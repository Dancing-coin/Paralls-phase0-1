# Behavior Turn Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立共享 typed behavior turn（行为回合）协议，并让 `CharacterAgentRuntime` 通过 Heavenly Graph 记录、查询一条完整且可审计的八阶段行为链。

**Architecture:** `BehaviorTurnRecorder` 只把 owner 已产生的阶段结果转成图谱 projection/proposal；它不推进阶段、不拥有角色决策或 Authority truth。角色运行时仍拥有 L1-L4 行为语义，Heavenly Graph 通过现有 port 原子追加 turn anchor、stage nodes 与 `part_of_turn` relations。

**Tech Stack:** Python 3.12、Pydantic v2、pytest、Heavenly Graph port/SQLite adapter、repository Harness。

**Spec:** GitHub Issue `Dancing-coin/Paralls-phase0-1#2`

## Global Constraints

- `CharacterAgentRuntime` 保留角色认知、意图和执行语义所有权。
- `SimingRuntime.tick(...)` 继续是唯一司命决策入口；本计划不改其决策链。
- 不新增 generic coordinator、generic writer、第二 runtime/store/bus 或第二 truth owner。
- 八阶段固定为 `context`、`interpretation`、`goal`、`intent`、`execution`、`settlement`、`evaluation`、`policy`。
- 失败与 Authority rejection 必须保留为 attempted chain，不得伪造 committed fact。
- 新英文术语首次出现时提供中文释义；提交信息优先使用中文。

---

### Task 1: Typed Behavior Turn Contract And Recorder

**Files:**
- Create: `backend/app/models/behavior_turn.py`
- Create: `backend/app/services/behavior_turn_recorder.py`
- Test: `backend/tests/test_behavior_turn_recorder.py`

**Interfaces:**
- Consumes: `HeavenlyGraphPort.write_batch(batch: HeavenlyGraphWriteBatch) -> HeavenlyGraphWriteResult`
- Produces: `BehaviorTurnStage`, `BehaviorTurnStageRecord`, `BehaviorTurnRecordRequest`, `BehaviorTurnRecorder.record(request)`

- [x] **Step 1: Write failing contract and end-to-end recorder tests**

  Test a complete eight-stage actor-private turn, required provenance/context fields, `part_of_turn` relations, idempotent replay, and rejected settlement retained as projection rather than fact.

- [x] **Step 2: Run the focused test and verify RED**

  Run: `python -m pytest backend/tests/test_behavior_turn_recorder.py -v`

  Expected: collection fails because `app.models.behavior_turn` and `BehaviorTurnRecorder` do not exist.

- [x] **Step 3: Implement the minimal typed contract and recorder**

  `BehaviorTurnRecordRequest` owns one scope, turn identity and ordered non-empty stages. The recorder validates the fixed stage order, creates one `behavior_turn` anchor plus one stage node per supplied stage, links every stage with `part_of_turn`, and emits one graph batch using the caller-provided idempotency key.

- [x] **Step 4: Run focused tests and verify GREEN**

  Run: `python -m pytest backend/tests/test_behavior_turn_recorder.py -v`

- [x] **Step 5: Run existing graph semantic contracts**

  Run: `python -m pytest backend/tests/test_heavenly_graph_semantic_queries.py backend/tests/test_sqlite_heavenly_graph_contract.py -v`

- [x] **Step 6: Commit the contract**

  Commit only Task 1 files with: `实现统一行为回合图谱记录协议`

### Task 2: Character Runtime Eight-Stage Projection

**Files:**
- Modify: `backend/app/character_agent/runtime/runtime_loop.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_character_agent_runtime_memory_integration.py`
- Test: `backend/tests/test_behavior_turn_recorder.py`

**Interfaces:**
- Consumes: `BehaviorTurnRecorder.record(request)` from Task 1
- Produces: optional `behavior_turn_recorder` injection on `CharacterAgentRuntime` and one recorded turn for an accepted or rejected character action

- [x] **Step 1: Write a failing character runtime integration test**

  Inject a real in-memory graph recorder, ingest one deterministic perceived event, query by actor/correlation, and assert the eight ordered stages exist with actor-private visibility. Add a rejected/zero-write scenario that still records settlement, evaluation and policy without a committed fact.

- [x] **Step 2: Run the focused test and verify RED**

  Run the two new test node ids with `python -m pytest ... -v`; expected failure is the missing recorder injection/runtime write.

- [x] **Step 3: Add the narrow runtime hook**

  Build the request only after existing L1-L4/settlement/evaluation data exists. Preserve existing return values and event publication. The hook may observe existing typed results but must not decide, dispatch, normalize Authority truth, or swallow graph errors silently.

- [x] **Step 4: Wire the existing application composition root**

  Construct one recorder from the existing SQLite Heavenly Graph instance and inject it into `CharacterAgentRuntime`; do not create another graph adapter.

- [x] **Step 5: Run focused and character integration suites**

  Run: `python -m pytest backend/tests/test_behavior_turn_recorder.py backend/tests/test_character_agent_runtime_memory_integration.py backend/tests/test_character_agent_runtime.py -v`

- [x] **Step 6: Commit the runtime integration**

  Commit only Task 2 files with: `接入角色八阶段行为回合图谱链`

### Task 3: Behavior Turn Harness And Documentation Gate

**Files:**
- Create: `.harness/profiles/behavior-turn-runtime.json`
- Create: `scripts/verification/verify_behavior_turn_runtime.py`
- Create: `scripts/verification/tests/test_behavior_turn_runtime_verify.py`
- Modify: `scripts/verification/tests/test_harness_registry.py`
- Modify: `docs/harness.md`
- Modify: `docs/INDEX.md`

**Interfaces:**
- Consumes: externally queryable behavior-turn runtime from Tasks 1-2
- Produces: `behavior-turn-runtime` Harness profile and JSON/Markdown evidence

- [x] **Step 1: Write failing Harness registry and verifier tests**

  Assert profile discovery, isolated selection, evidence paths, eight-stage trace, rejected-turn evidence, actor-private scope and replay status.

- [x] **Step 2: Run Harness tests and verify RED**

  Run: `python -m pytest scripts/verification/tests/test_behavior_turn_runtime_verify.py scripts/verification/tests/test_harness_registry.py -v`

- [x] **Step 3: Implement the narrow profile and verifier**

  Follow existing Heavenly Graph verifier report structure. The verifier must execute real backend tests and emit trace-backed JSON/Markdown; it must not infer completion from source inspection.

- [x] **Step 4: Register and document the profile**

  Add it to the all-profile registry and document that it proves the character behavior-turn vertical only, not character restart continuity, Siming integration, Authority six-domain closure or live Godot closure.

- [x] **Step 5: Run profile and docs gates**

  Run: `python scripts/verification/harness.py --profile behavior-turn-runtime`

  Run: `python scripts/verification/harness.py --profile docs`

- [x] **Step 6: Commit Harness coverage**

  Commit only Task 3 files with: `新增行为回合运行时验证门禁`

### Task 4: Slice Verification And Review

**Files:**
- Modify only files required by review findings.

**Interfaces:**
- Consumes: Tasks 1-3 commits
- Produces: reviewed, fully verified first vertical slice for Issue #2

- [x] **Step 1: Run compilation and focused verification**

  Run: `python -m compileall backend/app backend/tests scripts/verification`

  Run: `python scripts/verification/harness.py --profile behavior-turn-runtime`

- [x] **Step 2: Run the full backend suite**

  Run: `python -m pytest -v`

- [x] **Step 3: Run the broad Harness**

  Note: the implementation slice and its dedicated profile passed. The broad
  run was blocked by the existing `character-agent-execution` Godot probe
  missing its execution markers; this is recorded as an external verification
  blocker, not converted into a passing claim.

  Run: `python scripts/verification/harness.py --profile all`

- [x] **Step 4: Review from the pre-slice commit**

  Use `/code-review` against the fixed pre-slice commit and Issue #2. Resolve all correctness/spec blockers and rerun affected verification.

- [x] **Step 5: Commit review repairs**

  Commit only repair files with: `修复行为回合运行时评审问题`

## Follow-On Plans

After this slice is green and reviewed, create separate implementation plans for:

1. character continuity recovery;
2. Siming behavior-turn and graph-state closure;
3. six owner-specific Authority graph projection verticals plus their aggregate gate;
4. online LLM + Authority + Godot + SQLite restart live closure.

Each follow-on plan consumes the Task 1 typed protocol and must remain independently testable.
