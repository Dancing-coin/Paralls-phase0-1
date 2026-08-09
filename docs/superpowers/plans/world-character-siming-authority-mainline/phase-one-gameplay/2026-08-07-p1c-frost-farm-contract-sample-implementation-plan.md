# P1C Frost Farm Contract Sample Implementation Plan

> Backfill 2026-08-09: `implemented-and-verified`. Fresh `phase1c-frost-farm` profile and its
> predecessor evidence pass; this remains a bounded frost contract sample, not a weather or
> population runtime.

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** 实现一个不扩张通用 schema 的霜冻农田 contract sample，验证环境 effect、crop resistance、状态转换、可选 Survival projection 和 replay。

**Architecture:** 新增一个有界 Frost Farm domain package；环境 fact 继续来自 world/ESM 路径，农田和作物由 package authority 拥有，角色后果只通过独立 typed proposal 进入 Survival owner。没有天气 runtime、生态模拟或市场系统。

**Tech Stack:** Python/Pydantic, existing Gameplay event store, world/ESM fact projection, state-group and mirror projections, pytest, Harness。

---

## Requirements Summary

- 固定一个 jurisdiction、farm plot、crop、environment frost fact 和 resistance profile。
- 事件必须包含 command/correlation/causation、pinned revisions、evidence refs、privacy scope。
- 覆盖命中、抗性减损、完全拒绝、target missing、permission、stale revision、duplicate 和 replay。
- Survival disabled 时不得产生需求衰减、资源消费或身体惩罚。

## Acceptance Criteria

1. frost effect 对同一 pinned input 得到相同 resistance/result digest。
2. `farm.crop_frost_evaluated` 和 `farm.crop_state_changed` 只能由 Frost Farm owner 映射并原子追加。
3. 失败场景前后 event count、stream head、inventory/body projection 均不变化。
4. Survival enabled/disabled 两种配置均可重放；disabled 配置没有隐藏 obligation。
5. actor、creator-debug、public、Godot projections 按 scope 过滤，P1B/P1A profile 继续通过。
6. `phase1c-frost-farm` Harness profile 产出 fresh JSON/MD/NDJSON evidence。

## Implementation Steps

### Task 1: Define the V0 package records and failing tests

**Files:**
- Create: `backend/app/gameplay/frost_farm_runtime.py`
- Create: `backend/tests/test_frost_farm_runtime.py`
- Modify: `backend/app/gameplay/models.py`

- [x] **Step 1: Write tests** for `FarmPlot`, `CropState`, `EnvironmentFact`, `FrostEffectInput`, `ResistanceProfile`, strict package schema and owner boundaries.
- [x] **Step 2: Implement** records and read-only package projections; keep farm-only fields out of `EntityRecord` core fields.
- [x] **Step 3: Run** `python -m pytest backend/tests/test_frost_farm_runtime.py -q`; expected FAIL before implementation, then PASS.

### Task 2: Implement effect evaluation and authority settlement

**Files:**
- Modify: `backend/app/gameplay/frost_farm_runtime.py`
- Modify: `backend/app/gameplay/settlement_plan.py`
- Modify: `backend/app/world_runtime/fact_registry.py`
- Create: `backend/tests/test_frost_farm_settlement.py`

- [x] **Step 1: Add failing tests** for full hit, resistance reduction, full resistance rejection, missing target, permission denial, stale revision and duplicate command.
- [x] **Step 2: Implement** environment reference resolution, P1A semantic snapshot lookup, deterministic resistance trace and typed proposals.
- [x] **Step 3: Map** accepted crop changes to one atomic batch; if Survival is enabled, emit a separate proposal owned by the Survival adapter instead of writing character state in the farm batch.
- [x] **Step 4: Run** `python -m pytest backend/tests/test_frost_farm_settlement.py backend/tests/test_gameplay_event_store_contract.py -q`; expected PASS.

### Task 3: Add projections, replay and Godot mirror evidence

**Files:**
- Modify: `backend/app/gameplay/frost_farm_runtime.py`
- Modify: `backend/app/gameplay/replay.py`
- Modify: `backend/app/gameplay/godot_mirror_projection.py`
- Create: `backend/tests/test_frost_farm_replay_and_projection.py`

- [x] **Step 1: Add** crop result, actor projection, creator-debug trace, public projection and Godot committed-result mirror views with explicit missing reasons.
- [x] **Step 2: Add** full replay/checkpoint-tail hash assertions and verify no projection rebuild writes event history.
- [x] **Step 3: Run** `python -m pytest backend/tests/test_frost_farm_replay_and_projection.py -q`; expected PASS.

### Task 4: Register the V0 package and Harness profile

**Files:**
- Create: `backend/app/gameplay/frost_farm_package.py`
- Create: `scripts/verification/verify_phase1c_frost_farm.py`
- Create: `scripts/verification/tests/test_verify_phase1c_frost_farm.py`
- Create: `.harness/profiles/phase1c-frost-farm.json`
- Modify: `docs/harness.md`
- Modify: `docs/superpowers/specs/world-character-siming-authority-mainline/phase-one-gameplay/2026-08-07-p1c-frost-farm-contract-sample-design.md`

- [x] **Step 1: Register** the package manifest with declared schemas, dependencies, capabilities, migration refs and `content_digest`.
- [x] **Step 2: Verify** P1B predecessor, scenario outcomes, replay hashes, projection scope and disabled Survival evidence.
- [x] **Step 3: Run** `python scripts/verification/harness.py --profile phase1c-frost-farm`; expected PASS.

## Risks And Mitigations

- **Risk:** frost package becomes a hidden weather engine. **Mitigation:** accept only explicit EnvironmentFact input and reject unregistered scheduler callbacks.
- **Risk:** farm authority writes role/body/economy state. **Mitigation:** owner matrix tests inspect event targets and reject cross-owner payloads.
- **Risk:** V0 fields leak into core schema. **Mitigation:** package manifest schema-diff report fails on core field additions.

## Verification Steps

1. `python -m pytest backend/tests/test_frost_farm_runtime.py backend/tests/test_frost_farm_settlement.py backend/tests/test_frost_farm_replay_and_projection.py -q`
2. `python scripts/verification/harness.py --profile phase1c-frost-farm`
3. `python scripts/verification/harness.py --profile phase1b-contract-verification`
4. `python scripts/verification/harness.py --profile docs`

## Spec Coverage Review

Tasks 1-3 cover records, settlement, evidence, projections and replay; Task 4 covers package
registration and Harness acceptance. Agriculture, ecology, dynamic market and population simulation
remain excluded as required by P1C.
