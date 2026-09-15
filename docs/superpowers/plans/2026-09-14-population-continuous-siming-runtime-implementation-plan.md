# 持续群体模拟与司命运行时准入 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (or superpowers:subagent-driven-development) to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 在现有 12 人群体连续性、Siming、Owner 和 Character Core 边界上，补齐可重启的持续 cadence 推进、普通居民 B0 连续状态、真相优先的记忆对齐，以及正式 SGC 运行时准入证据。

**Architecture:** 复用 `SimulationClock`、`WorldContinuityRuntime`、现有 Authority Event Bus 和 `SimingRuntime.tick(...)`。新增一个只负责产生离散人口窗口的 driver，由应用生命周期启动；driver 不写世界真相，所有客观结果仍经 Siming 的已准入 capability 和 Domain Owner，角色记忆仍由 Character Core 写入。完整 Profile 角色继续走高保真认知，9 名 dormant actor 只推进有界的 B0 客观连续状态。

**Tech Stack:** Python 3、FastAPI、asyncio、Pydantic、SQLite GameplayEventStore/Heavenly Graph、pytest、Harness。

**Spec:**
- `docs/superpowers/specs/world-character-siming-authority-mainline/2026-08-29-siming-led-population-simulation-design.md`
- `docs/superpowers/specs/world-character-siming-authority-mainline/2026-09-01-siming-generalized-population-decision-surface-design.md`
- `docs/superpowers/specs/world-character-siming-authority-mainline/2026-09-07-siming-population-domain-owner-adaptation-design.md`
- `docs/superpowers/specs/world-character-siming-authority-mainline/siming-group-world-formalization/03-sgc-3-population-fidelity-continuity-contract.md`

## Global Constraints

- 居民规模固定为 `POPULATION_ACTOR_IDS` 的 12 人；不扩展到 54 人。
- `SimingRuntime.tick(...)` 是唯一司命决策和 dispatch 入口；不新增第二个事件总线、事件库或通用 writer。
- `SimulationClock` 只推进离散窗口；wall-clock 只负责唤醒 driver，不能直接改变世界真相。
- 已提交的 Owner/Character Core 事实优先于任何 projection、计划或角色旧记忆。
- 记忆核对只按需触发；司命直接纠正必须是显式、授权、限频的单次操作，禁止常驻全量扫描。
- 旧 cohort fixture 保留为测试/兼容路径；正式居民路径必须使用 source-controlled generic selector。
- 图谱继续作为 actor-private 长期记忆和审计投影，不承担群体调度、世界真相或跨角色私有记忆读取。
- Godot 运行时本计划只登记待验证项，不把静态或后端证据描述为 Godot 已完成。
- `docs/superpowers/` 文档只作为本地实施材料，提交代码时排除该目录。

---

### Task 1: 建立可重启的群体 cadence driver

**Files:**
- Create: `backend/app/world_runtime/population_driver.py`
- Modify: `backend/app/world_runtime/simulation_clock.py`（仅补充可测试的窗口计算 helper）
- Test: `backend/tests/test_population_runtime_driver.py`

**Interfaces:**
- `PopulationCadenceDriver.tick(target_tick: int) -> PopulationDriverTickResult`
- `PopulationCadenceDriver.run_forever(stop_event: asyncio.Event, sleep: Callable[[float], Awaitable[None]]) -> None`
- driver 构造参数：`world_runtime`、`publish_window: Callable[[PopulationCadenceInput], AuthorityEvent | None]`、`window_size`、`catch_up_limit`、`initial_tick`。
- `PopulationDriverTickResult` 返回 `published_cadence_ids`、`deferred_windows` 和 `rejected_windows`，不包含领域写入结果。

- [x] **Step 1: 写失败测试**

在测试文件中定义 `driver` fixture：用现有 `GameplayEventStore`、`WorldContinuityRuntime` 和 `_mode()` 构造世界运行时，用一个返回固定 `AuthorityEvent` 的 fake publisher 记录 cadence。

```python
def test_driver_publishes_each_due_window_once() -> None:
    first = driver.tick(7200)
    second = driver.tick(7200)
    assert first.published_cadence_ids == ("cadence:world:0", "cadence:world:3600")
    assert second.published_cadence_ids == ()
```

- [x] **Step 2: 运行 focused test，确认缺少 driver 合约而失败**

Run: `python -m pytest -q backend/tests/test_population_runtime_driver.py`

- [x] **Step 3: 实现最小 driver**

复用 `SimulationClock.advance()` 计算窗口；以已有 `population_cadence_event` 的 `cadence_id` 做幂等判断；每次 `tick()` 最多处理 `catch_up_limit` 个窗口，超出部分只返回 `deferred_windows`。driver 不调用 Owner、不写 Character Core、不执行 LLM。

- [x] **Step 4: 验证重启和异常语义**

增加测试：历史事件已存在时重建 driver 不重复发布；`target_tick < current_tick` 返回 `simulation_clock_cannot_rewind`；发布器返回 `None` 时记录 rejected 窗口而不推进已确认游标。

- [x] **Step 5: 运行并提交**

Run: `python -m pytest -q backend/tests/test_population_runtime_driver.py backend/tests/test_world_runtime_population_cadence.py`

```powershell
git add backend/app/world_runtime/population_driver.py backend/app/world_runtime/simulation_clock.py backend/tests/test_population_runtime_driver.py
git commit -m "增加可重启的群体节拍驱动"
```

### Task 2: 将 driver 接入应用生命周期

**Files:**
- Modify: `backend/app/main.py:208,477-830`（FastAPI 生命周期和 runtime 初始化）
- Test: `backend/tests/test_population_runtime_lifecycle.py`

**Interfaces:**
- `start_population_runtime() -> asyncio.Task | None`
- `stop_population_runtime() -> None`
- 复用现有 `publish_population_cadence_window(...)`，不复制发布授权校验。

- [x] **Step 1: 写生命周期测试**

```python
def test_runtime_lifecycle_starts_one_population_task_and_cancels_it() -> None:
    task = main.start_population_runtime()
    assert task is not None
    main.stop_population_runtime()
    assert task.cancelled() or task.done()
```

- [x] **Step 2: 接入 FastAPI startup/shutdown**

使用现有 `authority_event_bus`、`gameplay_event_store` 和 `WorldContinuityRuntime` 构造 driver。startup 只启动一个 task；shutdown 设置 `stop_event`、取消 task 并等待完成。测试环境可通过注入 fake sleep/clock 控制 tick，不启动真实无限循环。

- [x] **Step 3: 验证事件链**

测试应用启动后产生一个 `population_cadence_event`，事件进入现有 `SimingEventPipeline`，并且 Siming 仍通过 `tick()` 处理；重复 startup 不产生第二个 driver。

- [x] **Step 4: 回归验证并提交**

Run: `python -m pytest -q backend/tests/test_population_runtime_lifecycle.py backend/tests/test_siming_event_pipeline.py backend/tests/test_siming_population_authorized_cadence_publication.py`

```powershell
git add backend/app/main.py backend/tests/test_population_runtime_lifecycle.py
git commit -m "接入群体模拟应用生命周期"
```

### Task 3: 完成 12 人 B0 连续状态推进

**Files:**
- Modify: `backend/app/services/siming_population_capability.py`
- Modify: `backend/app/population_continuity/seed_planner.py`
- Modify: `backend/app/character_agent/services/character_continuity.py`（只补充 dormant continuity 的明确入口）
- Test: `backend/tests/test_population_continuity.py`
- Test: `backend/tests/test_siming_led_population_seed_continuity.py`

**Interfaces:**
- `PopulationSimulationCapability.run_default_decision_cycle(...)` 继续是 generic 居民入口。
- dormant actor 使用现有 `CharacterContinuityCommand`/`CharacterRuntimeContinuityPort`，不要求 `CharacterProfile` 或 L2/L3 cognition。
- 完整 Profile 角色仍由 `run_scheduled_background_cognition_ticks()` 处理高保真认知。

- [x] **Step 1: 写 12 人连续性失败测试**

测试 fixture 使用现有 `PopulationSimulationCapability`、`PopulationCadenceInput` 和 `PopulationReadSet`，并将 12 个 `POPULATION_ACTOR_IDS` 的 projection 放入同一个 read set。

```python
def test_twelve_residents_receive_b0_continuity_without_memory_claims() -> None:
    result = capability.run_default_decision_cycle(cadence, read_set)
    assert result.report.continuity_committed_count == 12
    assert all(not seed.memory_candidates for seed in result.seed_candidates)
```

- [x] **Step 2: 让 generic routine projection 覆盖 roster**

保持 `POPULATION_ACTOR_IDS` 为唯一名单；每名居民生成 `dynamic_state`、`presentation_seed` 和 continuity cursor。不得把 dormant actor 转换成伪造的完整 Profile。

- [x] **Step 3: 处理冲突和饥饿**

沿用现有 revision vector、`expected_character_revision` 和 `starvation_credit`。同一 actor revision 已变化时返回 `requeue`；预算不足时保留 deferred projection，下一个窗口按连续性优先级重新选择。

- [x] **Step 4: 保持记忆暴露边界**

只有 projection 带有 `exposure_evidence` 时才生成 `memory_candidates`；单纯 routine 状态更新不生成事件记忆、知识记忆或社交印象。

- [x] **Step 5: 运行 focused tests 并提交**

Run: `python -m pytest -q backend/tests/test_population_continuity.py backend/tests/test_siming_led_population_seed_continuity.py`

```powershell
git add backend/app/services/siming_population_capability.py backend/app/population_continuity/seed_planner.py backend/app/character_agent/services/character_continuity.py backend/tests/test_population_continuity.py backend/tests/test_siming_led_population_seed_continuity.py
git commit -m "补齐十二名居民的 B0 连续推进"
```

### Task 4: 增加真相优先的记忆对齐闸门

**Files:**
- Modify: `backend/app/character_agent/runtime/runtime_loop.py:1293-1385,1804-1865`
- Modify: `backend/app/character_agent/models/memory_consistency.py`（复用现有模型；仅在缺少策略字段时补充）
- Test: `backend/tests/test_character_agent_memory_consistency.py`

**Interfaces:**
- `run_memory_consistency_pass(actor_id: str, producer_ts: int) -> MemoryConsistencyResult`
- pass 只读取 actor 已知冲突；调用现有 `get_memory_verification_requests()` 或显式 `apply_memory_correction()`，不直接改写 memory store。

- [x] **Step 1: 写冲突矩阵测试**

覆盖以下固定情况：

1. World Truth 与角色记忆 predicate 相同但值不同：返回 `truth_wins`，不允许角色记忆覆盖真相。
2. 角色没有暴露证据：返回 `verification_required`，不生成记忆候选。
3. 相同 correction id 重放：返回 `idempotent_replay`。
4. 角色 revision 已变化：返回 `character_revision_conflict`。
5. 同一 actor 在限频窗口内再次扫描：返回 `rate_limited`。

- [x] **Step 2: 实现低频、按需检查**

仅在 actor 存在未解决冲突、角色具有严谨核对倾向，且距离上次检查超过策略间隔时运行；每轮限制 actor 数量。博闻强记角色使用更长的压缩/核对间隔，但不跳过事实校验。

- [x] **Step 3: 保留司命 edit 权限的显式边界**

`apply_memory_correction()` 必须要求授权 principal、source revision、actor revision 和 idempotency key；司命不能通过普通 cadence 或 background tick 隐式调用它。

- [x] **Step 4: 验证图谱边界并提交**

确认 correction 事件先写 actor-private timeline，再由 Heavenly Graph 投影；图谱查询只提供核对上下文，不成为世界真相来源。

Run: `python -m pytest -q backend/tests/test_character_agent_memory_consistency.py backend/tests/test_character_agent_runtime_memory_integration.py`

```powershell
git add backend/app/character_agent/runtime/runtime_loop.py backend/app/character_agent/models/memory_consistency.py backend/tests/test_character_agent_memory_consistency.py
git commit -m "增加真相优先的角色记忆对齐闸门"
```

### Task 5: 收紧 generic/fixture 路由并完成 SGC 准入证据

**Files:**
- Modify: `backend/app/services/siming_runtime.py:147-198`
- Modify: `backend/app/population_continuity/decision_surface.py`
- Modify: `docs/harness.md`
- Create: `.harness/profiles/population-continuous-runtime.json`
- Create: `.harness/profiles/siming-sgc-runtime-admission.json`
- Test: `backend/tests/test_siming_population_decision_routing.py`

**Interfaces:**
- generic selector 固定为 `selector:generic:population:v1`。
- fixture selector 固定为 `selector:cohort-bakery:v1`。
- 未知 selector、缺失 capability descriptor、owner receipt 过期时返回可审计 `population_requeue`，不执行 fallback。

- [x] **Step 1: 写路由隔离测试**

测试 fixture 提供已经注入 capability 的 `siming_runtime` 和 generic `population_cadence_event`，事件的 selector 固定为 `selector:generic:population:v1`。

```python
def test_generic_selector_cannot_fall_back_to_cohort_fixture() -> None:
    result = siming_runtime.tick([generic_population_input])
    assert result.audit_records[-1].reason != "cohort_fixture"
```

- [x] **Step 2: 明确正式路径**

generic cadence 只能进入 `run_decision_cycle()` 或 `run_default_decision_cycle()`；cohort fixture 只能由 fixture selector 进入 `run_cohort_cycle()`。移除依据 cadence id 前缀的隐式判断，改为显式 selector + capability catalog 校验。

- [x] **Step 3: 建立 Harness 验收条件**

`population-continuous-runtime` 必须证明：至少两个窗口、12 名 actor、幂等、断点恢复、deferred/requeue、Owner receipt、真相优先和无暴露记忆候选。`siming-sgc-runtime-admission` 必须证明：descriptor、Owner 映射、scope/revision、隐私、stale/duplicate/changed-duplicate 和 full/checkpoint-tail replay。

- [x] **Step 4: 标记 Godot 待验证**

Harness 报告明确记录 backend-only；没有 Godot 环境时状态为 `written_and_backend_verified; godot_unverified`，不得提升为完整 SGC runtime proof。

- [x] **Step 5: 运行验证并提交代码范围**

Run:

```powershell
python -m pytest -q backend/tests/test_siming_population_decision_routing.py backend/tests/test_siming_population_authorized_cadence_publication.py
python scripts/verification/harness.py --profile population-continuous-runtime
python scripts/verification/harness.py --profile siming-sgc-runtime-admission
git diff --check
```

```powershell
git add backend/app/services/siming_runtime.py backend/app/population_continuity/decision_surface.py backend/tests/test_siming_population_decision_routing.py .harness/profiles/population-continuous-runtime.json .harness/profiles/siming-sgc-runtime-admission.json docs/harness.md
git commit -m "完成群体模拟正式路由与 SGC 准入验证"
```

### Final verification

- [x] 运行全部群体和角色记忆 focused pytest。
- [x] 运行 `python scripts/verification/harness.py --profile population-continuous-runtime`。
- [x] 运行 `python scripts/verification/harness.py --profile siming-sgc-runtime-admission`。
- [x] 运行 `python scripts/verification/harness.py --profile all`；若仅因 Godot 环境缺失失败，记录为待环境验证，不修改后端完成结论。
- [x] 检查 `git diff --check`、提交文件列表和 `.harness/verification/` 证据；确认没有 54 人配置、第二事件总线、常驻记忆全扫描或 fixture fallback。

## 执行结果（2026-09-15）

- Task 1–5 已实现并独立复审；Task 4 早期延期决议已撤销，按需单 actor pass/限频已补齐，绝不由 cadence 隐式调用 edit。
- 实际日窗口覆盖12居民；停止/重启从第13窗口继续；world pause/resume不改变时间原点、不生成重叠窗口。
- 重启恢复保证限定同一进程的既有 Authority Event 历史；跨进程 cadence 持久化未证明，不宣称已支持。
- 启动契约升级v4，旧v3 SQLite审计记录保留，真实baseline库升级并再次启动验证通过。
- 两个命名 Harness 均重新运行、写入本轮JSON/Markdown/JUnit/日志；full_sgc_runtime_proof=false，Godot未验证。
- harness --profile all 已执行，文档/边界/漂移/后端协议/工程静态通过，停于缺少Godot executable，后续有环境再继续。
- 上述勾选表示步骤已执行；Godot的检查状态仍以报告godot_unverified为准。