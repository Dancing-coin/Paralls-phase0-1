# 群体模拟数据导向优化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在保留现有 Authority、Domain Owner、Character Core、Siming 和 Godot 职责边界的前提下，将群体模拟从“全历史读取、全量复制、逐角色对象处理”逐步改造成“当前态加增量投影、按到期集合推进、热字段批处理”的数据导向运行时，并用实测决定是否需要原生代码或 GPU。

**Architecture:** 继续使用现有 `SimulationClock`、`PopulationCadenceDriver`、`SimingRuntime.tick(...)`、`PopulationSimulationCapability`、Gameplay Event Store 和 Heavenly Graph 接口。数据导向实现只拥有其明确声明的 runtime 热字段或投影；世界真相仍由既有 Owner/Authority 提交，角色私有连续性仍由 Character Core 写入。五个阶段按依赖顺序推进，每阶段都必须保持固定种子、事件输入、版本检查、幂等和回放结果不变。

**Tech Stack:** Python 3.11+、FastAPI、asyncio、Pydantic、SQLite、pytest、现有 Harness；标准库优先，只有基准证明热循环不足时才评估 NumPy、C++ 或 GPU。

**Spec:**
- `docs/9月分析/2026-09-15-群体模拟开源参考与数据导向架构分析.md`
- `docs/superpowers/specs/world-character-siming-authority-mainline/2026-08-29-siming-led-population-simulation-design.md`
- `docs/superpowers/specs/world-character-siming-authority-mainline/2026-09-01-siming-generalized-population-decision-surface-design.md`
- `docs/superpowers/specs/world-character-siming-authority-mainline/2026-09-07-siming-population-domain-owner-adaptation-design.md`
- `docs/superpowers/specs/world-character-siming-authority-mainline/siming-group-world-formalization/03-sgc-3-population-fidelity-continuity-contract.md`

**Current verification status:** `backend_local_probe_only; godot_unverified`。本计划和相关研究证据没有 Godot editor/runtime 证明；其他会话继续工作时必须先读取本文件和 `.harness/verification/population-data-oriented-research/session-handoff.md`，完成 Godot 验证后才能更新状态。

## Global Constraints

- `SimingRuntime.tick(...)` 仍是唯一司命决策和 dispatch 入口；不新增第二个事件总线、事件库或仿真时钟。
- `SimulationClock` 只推进离散窗口；wall-clock 只唤醒 driver，不能直接改变世界真相。
- 任何数组或热表必须声明字段 owner；不得与现有 Owner、Character Core 各自修改同一权威值。
- Domain Owner 继续负责库存、资源、占用、支付和其他竞争写入；批量计算只能产生结构化意图或受版本保护的增量。
- 图谱继续是角色私有连续性和审计投影，不承担群体调度、世界真相或跨角色私有记忆读取。
- 普通居民的 B0 连续性不得伪造完整 `CharacterProfile`、私有知识、长期记忆或 Godot 角色实例。
- LLM、深度认知和异步结果必须检查输入版本、执行时刻、权限和幂等键；过期结果只能记录并丢弃或 requeue。
- 保留事件审计、恢复、因果、幂等和 scope/revision 校验；性能优化不得删除这些语义。
- 优化前后必须使用相同种子、cadence、输入事件和规则版本比较最终状态、Owner 结果、Character Core 结果和 replay hash。
- `docs/superpowers/` 仅作本地实施材料；代码提交时排除该目录及其变更。
- 现有无关的 XLSX、配置和工作树修改不得被重置、清理或纳入提交。
- 每阶段都需运行对应 focused pytest、Harness profile 和 `git diff --check`；未完成 Godot 验证不得宣称 Godot 完成。
- Godot 状态必须明确写为 `godot_unverified`，直到真实 editor/runtime 或 headless probe 产生新鲜证据；backend-only 证据不能提升该状态。
- task 是逻辑审查边界；实际提交优先按阶段合并/squash，提交消息以中文概括阶段目的。

## 已确认设计决策（2026-09-15）

- **B0 边界**：B0 只输出客观连续状态增量、`presentation_seed` 或 `deferred`；它不直接调用 Character Core 写入、不直接提交 Domain Owner intent。需要角色记忆、认知候选或领域结算时，必须经过已有的激活/B1/B2 授权路径，并保留 exposure、权限、版本和幂等校验。
- **恢复锚点**：事件追加成功是事实提交锚点；current state、checkpoint、projection 和热状态都必须能从已提交事件重建。禁止以缓存命中或未确认的 current state 推进提交游标。
- **游标分离**：`simulation_tick_cursor` 表示客观状态推进到的仿真 tick；`last_applied_global_sequence` 和 `source_revision_vector` 表示输入事实版本，三者不得互相替代。所有 B0 command/receipt 必须保留 `from_tick`、`to_tick` 和 source revisions。
- **数据布局门禁**：当前 `list[dict]` 热状态只能作为 seam 或基线，不得宣称为 SoA。只有在 1× 实时门槛未通过、并证明 Python 热循环占端到端预算主要部分后，才允许迁移为列式数组或原生/GPU kernel。
- **性能目标**：100、1,000、10,000 人三档均必须通过 1× 实时验收；10× 作为独立压测报告，不作为第一阶段上线门槛。1× 通过条件是连续窗口的 p95 端到端处理时间不超过该窗口墙钟预算的 80%，连续 30 个窗口 backlog 不增长，最大居民推进延迟不超过 1 个窗口。
- **规模前置**：1,000 和 10,000 人验收前必须提供 roster 初始化、continuity actor 注册、默认热字段、持久化恢复和 unsupported actor 的明确结果；不能用默认 12 人名单外推容量。

### 审查后新增硬门禁

- 阶段一不能只统计 SQL 行数；必须同时统计 `_snapshot_mutable_state()` 的复制条目、session/checkpoint 的序列化字节和重新打开数据库后的可见行，确认热路径没有全图复制。
- 阶段二必须从真实 `cadence -> authorized publisher -> store projection assembler` 链路读取 checkpoint tail；只测 `PopulationHotState.export_rows()` 或独立索引函数不能作为增量读取证据。
- 阶段三必须先完成 `CharacterContinuityCommand` 的 `from_tick/to_tick/simulation_tick_cursor` 协议迁移，并明确 B0 与 B1/B2 的输出类型；不能使用 `max(source_revision_vector)` 作为时间游标。
- 阶段四必须有生产接入、重启重建和字段 owner 证据；当前 `list[dict]` 只能作为 baseline seam。Owner 批量结算必须先定义 batch API、稳定排序、逐 actor receipt、局部失败和回滚边界。
- 阶段五的 backend gate 与 Godot gate 分离。没有 Godot editor/runtime/headless 证据时，任何表现实现都保持未提交，状态保持 `godot_unverified`。

## 文件与模块地图

| 区域 | 当前职责 | 计划中的最小变化 |
|---|---|---|
| `backend/app/gameplay/event_store.py` | Gameplay 权威事件、幂等、outbox、checkpoint | 增加可索引的序号读取；保持既有事件模型和返回类型 |
| `backend/app/services/sqlite_heavenly_graph.py` | Heavenly Graph SQLite adapter | 热路径按批增量写入；保留低频全量导出/恢复能力 |
| `backend/app/services/in_memory_heavenly_graph.py` | 图谱语义内存实现 | 作为契约基线，不引入第二套语义 |
| `backend/app/character_agent/runtime/runtime_loop.py` | Character Core 连续性与认知 | 分离当前态、追加时间线、检查点；保留角色权威 |
| `backend/app/character_agent/storage/` | 角色 session、memory、dynamic state、graph continuity | 只改写放大和索引，不把记忆搬进人口热表 |
| `backend/app/world_runtime/population_driver.py`、`simulation_clock.py` | cadence 窗口与重启 | 保留单一时钟，增加可观测 backlog/due 统计 |
| `backend/app/population_continuity/world.py`、`siming_contracts.py` | cadence、projection、read set | 支持当前态/增量投影和热状态输入 |
| `backend/app/services/siming_population_capability.py`、`population_continuity/decision_surface.py` | 候选评估、预算和 Owner/Character Core 适配 | 分离 B0 连续推进与昂贵候选预算；增加批处理适配 |
| `backend/app/services/authority_event_bus.py`、`siming_event_pipeline.py` | 事件分发和 Siming pipeline | 减少重复 materialization；不改 authority 路由边界 |
| `backend/tests/` | 契约、连续性、图谱、Harness 测试 | 每项优化先写回归测试和等价性测试 |
| `.harness/profiles/`、`.harness/verification/` | 验收 profile 与证据 | 增加阶段 profile 和基准原始结果 |
| Godot `scripts/`、`scenes/` | 本地表现与实例 | 最后一阶段按需评估远景批量表现，不迁移世界真相 |

## 现有基线与升级门槛

基线提交为 `9361c6f9df58b89c94b512f8dc3bc202888a2561`。局部探针结果保存在 `.harness/verification/population-data-oriented-research/results.json`：10,000 人构造投影约 60.839 ms，构造并哈希 ReadSet 约 83.329 ms，评估/过滤/选择约 133.110 ms；50,000 条合成历史构造一次 cadence 约 665.983 ms。SQLite 内存探针显示，已有 10,000 个节点时修改 1 个节点会执行 6 次 DELETE 和 10,001 次 `graph_nodes` INSERT。

这些数据只作为当前实现的局部基线，不是整局容量承诺。每阶段完成条件必须同时报告：p50/p95、峰值 RSS、对象分配或序列化字节、历史读取数量、投影数量、写入行数、backlog、最大居民推进延迟以及 replay/恢复结果。

## 五阶段完整实施规则

本文件描述的是五个**完整阶段**，不是把已经写过的代码标成“完成”。阶段只有在该阶段的全部任务、出口测试、证据产物和提交都完成后才算完成。任何只完成接口、测试或局部 profile 的状态都保持为“进行中”，不得替代阶段出口。

每个阶段都按同一条数据流实施：

```text
SimulationClock
  -> PopulationCadenceDriver
  -> PopulationCadenceInput
  -> immutable PopulationReadSet
  -> pure evaluation / B0 integration
  -> presentation_seed or deferred result (B0)
  -> authorized B1/B2 intent
  -> Domain Owner / Character Core (only after authorization)
  -> receipt + event append
  -> projection checkpoint / presentation seed
```

执行时必须为每个窗口保留以下五个标识，并把它们写入测试证据：`cadence_id`、`read_set_digest`、`source_revision_vector`、`actor_revision`、`idempotency_key`。任意一个标识缺失时，该窗口只能返回 `requeue` 或 `rejected`，不能产生部分投影。

阶段之间的硬依赖如下：阶段一先解决写入复制和恢复边界；阶段二才能可靠地使用 tail cursor；阶段三才能把连续推进与昂贵认知拆开；阶段四只能在阶段三的字段访问集合固定后做热表；阶段五只允许搬运纯计算，不能绕过前四阶段的 Owner 和 replay 语义。阶段出口未通过时，不得进入下一阶段，也不得用 GPU、线程池或 Godot 表现掩盖前一阶段的全历史读写。

---

## 阶段一：增量持久化与当前态分离

阶段目标：更新一个角色或一个图节点时，持久化工作量与本批变化接近；异常、重复提交和恢复语义与现有实现一致。

### Task 1：建立图谱写放大和回滚回归基线

**Files:**
- Modify: `backend/tests/test_sqlite_heavenly_graph_contract.py`
- Modify: `backend/tests/heavenly_graph_contract.py`（复用已有构造器）
- Create: `backend/tests/test_population_persistence_regression.py`
- Create: `.harness/profiles/population-data-oriented-persistence.json`

**Interfaces:**
- Consumes: `HeavenlyGraphPort.write_batch(...)`、`SQLiteHeavenlyGraphAdapter(':memory:')`、现有 `CharacterRuntimeContinuityPort`。
- Produces: 可重复的 SQL 语句计数、失败注入和语义等价断言；不改变生产接口。

- [ ] **Step 1: 写失败测试**

  记录 N=100、1,000、10,000 节点时更新一个节点的 SQL `DELETE`/`INSERT` 数量；注入 commit 失败，断言内存查询和 SQLite 查询均保持更新前状态；重复相同幂等键，断言 `replayed=True` 且不新增版本。

- [ ] **Step 2: 运行 focused test，确认当前行为被锁定**

  Run: `backend` 目录下 `python -m pytest -q tests/test_population_persistence_regression.py tests/test_sqlite_heavenly_graph_contract.py`

  Expected: 基线计数与当前实现一致；失败注入暴露所有必须保留的回滚语义。

- [ ] **Step 3: 建立基准产物**

  将 SQL 计数、节点查询结果、revision vector、replay hash 和环境信息写入 `.harness/verification/population-data-oriented-persistence/`。产物只用于验证，不成为运行时配置。

- [ ] **Step 4: 运行 Harness profile**

  Run: `python scripts/verification/harness.py --profile population-data-oriented-persistence`

- [ ] **Step 5: Commit**

  `git add backend/tests/test_sqlite_heavenly_graph_contract.py backend/tests/heavenly_graph_contract.py backend/tests/test_population_persistence_regression.py .harness/profiles/population-data-oriented-persistence.json`；提交信息：`增加群体持久化写放大基线`。

### Task 2：将 SQLite 图谱热路径改为增量事务

**Files:**
- Modify: `backend/app/services/sqlite_heavenly_graph.py:47-55,203-260`
- Modify: `backend/app/services/in_memory_heavenly_graph.py:463-530`（必要时暴露本批变更信息，保持语义不变）
- Test: `backend/tests/test_population_persistence_regression.py`
- Test: `backend/tests/test_sqlite_heavenly_graph_contract.py`

**Interfaces:**
- Consumes: 现有 `HeavenlyGraphWriteBatch`、幂等记录、scope stream revision 和 adapter rollback seam。
- Produces: `write_batch(...)` 的相同 `HeavenlyGraphWriteResult`；内部增加只写本批 entities/metadata 的实现，不向调用者暴露 SQLite 细节。

- [ ] **Step 1: 写增量写入失败测试**

  断言 N=10,000 时一次节点更新只写新节点版本及必要的幂等/stream revision 行；无关节点版本和关系不重新 INSERT。覆盖新增节点、revision 2、关系变更、幂等重放、revision conflict、commit 异常。

- [ ] **Step 2: 先实现普通 `write_batch` 增量 SQL**

  在成功的 SQLite 事务内写入本批 node/relation、幂等记录和 scope revision；删除旧版本只在语义明确要求时执行。不要为热路径调用全图 `_snapshot_mutable_state()` 或六表 DELETE。

- [ ] **Step 3: 保留失败恢复但限制复制范围**

  事务失败时使用 SQLite rollback，并恢复内存 adapter 的本批变更；低频 branch/correction/checkpoint 操作可暂时保留旧实现，但必须有明确回归测试和 profile 记录，不能让 continuity `write_batch` 走全量路径。

- [ ] **Step 4: 运行契约与性能测试**

  Run: `python -m pytest -q tests/test_population_persistence_regression.py tests/test_sqlite_heavenly_graph_contract.py tests/test_heavenly_graph_consistency.py`

  Expected: 语义契约全部通过；SQL 写入行数随本批变化增长，而不是随全图历史增长。

- [ ] **Step 5: Commit**

  提交信息：`将群体图谱写入改为增量事务`。

### Task 3：分离角色当前态、追加历史和检查点

**Files:**
- Modify: `backend/app/character_agent/runtime/runtime_loop.py:1561-1696,4362-4390`
- Modify: `backend/app/character_agent/storage/graph_continuity_store.py:53-122`
- Modify: `backend/app/character_agent/storage/session_store.py:20-100`
- Modify: `backend/app/character_agent/storage/memory_store.py:540-590`
- Test: `backend/tests/test_character_agent_runtime_memory_integration.py`
- Test: `backend/tests/test_character_graph_memory_store.py`

**Interfaces:**
- Consumes: `CharacterContinuityCommand`、`CharacterContinuityReceipt`、已有 `write_snapshot/read_snapshot` 和 session store。
- Produces: 相同 Character Core 对外查询；内部保存当前态引用、追加 timeline 和按 actor 索引的 receipt，检查点仍可完整恢复。

- [ ] **Step 1: 写等价性测试**

  对同一 actor 连续执行 K 次 routine continuity command；断言当前态、timeline、memory candidates、receipt、revision 和 graph read-back 与基线相同，并记录快照 payload 字节数随 K 的变化。

- [ ] **Step 2: 先拆出当前态和追加记录**

  当前态更新只写变化字段；timeline 继续追加单条事件；receipt 按 actor/idempotency key 读取。不得把长期记忆、对白或完整 profile 移入人口热表。

- [ ] **Step 3: 定义检查点边界**

  检查点保存角色恢复所需的状态游标、版本、待物化候选和必要历史引用；恢复后通过现有 `read_snapshot` 和 replay 验证。任何被裁剪的历史必须仍能通过事件或检查点恢复。

- [ ] **Step 4: 注入中断和重复恢复测试**

  覆盖写入中断、同一 source event 重放、进程重启、旧检查点加 tail、character revision conflict 和 memory scope 拒绝。

- [ ] **Step 5: Commit**

  提交信息：`拆分角色连续性当前态与历史快照`。

### 阶段一出口检查

- [ ] `python -m pytest -q backend/tests/test_population_persistence_regression.py backend/tests/test_sqlite_heavenly_graph_contract.py backend/tests/test_character_agent_runtime_memory_integration.py`
- [ ] `python scripts/verification/harness.py --profile population-data-oriented-persistence`
- [ ] 10,000 节点改单节点不再触发整表重写；同时确认内存快照复制量、session/checkpoint 序列化字节和实际落盘行数不随无关历史增长。断电/异常、幂等、scope、revision、full/tail replay 通过。
- [ ] 记录本阶段真实 SQL 行数、字节量、p95 和回滚结果；未通过则停止，不进入数组迁移。

## 阶段二：增量读取、索引和投影游标

阶段目标：固定人口增加历史后，窗口更新成本不再随全部历史线性增长；每个 projection/cadence 只处理自上次游标之后的有效事实。

### Task 4：为 Gameplay Event Store 建立序号和流索引读取

**Files:**
- Modify: `backend/app/gameplay/event_store.py:85-320`
- Modify: `backend/app/gameplay/dispatcher.py:100-150`
- Test: `backend/tests/test_gameplay_event_store_contract.py`
- Test: `backend/tests/test_gameplay_event_store_persistence.py`
- Test: `backend/tests/test_population_incremental_reads.py`

**Interfaces:**
- Consumes: 现有 `read_events(global_sequence_after=...)`、`read_stream(...)`、`get_stream_head(...)`。
- Produces: 保持现有返回类型，并让 after-sequence、stream revision 和 limit 访问复用索引；必要时新增内部私有索引，不新增事件存储系统。

- [ ] **Step 1: 写读取复杂度回归测试**

  合成 1,000、10,000、50,000 条历史，仅读取 tail；断言返回事件顺序、深拷贝隔离、limit、空 tail 和 missing stream 与现有契约一致，并统计扫描事件数。

- [ ] **Step 2: 实现增量索引维护**

  在 `append_batch` 成功时维护 global sequence 和 stream revision 到事件位置的索引；snapshot load 时重建索引。不要改变事件 ID、global sequence 或幂等语义。

- [ ] **Step 3: 让 dispatcher 复用 after-sequence**

  将 gap/resync 路径连接到索引读取；保留现有 gap detection 和恢复账本。

- [ ] **Step 4: 运行测试与基准**

  Run: `python -m pytest -q tests/test_population_incremental_reads.py tests/test_gameplay_event_store.py tests/test_gameplay_dispatcher.py`

- [ ] **Step 5: Commit**

  提交信息：`增加事件流增量读取索引`。

### Task 5：让 cadence、投影组装和 read set 复用增量游标

**Files:**
- Modify: `backend/app/population_continuity/world.py:111-190`
- Modify: `backend/app/main.py:1150-1365`
- Modify: `backend/app/population_continuity/store_projection_assembler.py:40-165`
- Modify: `backend/app/population_continuity/siming_contracts.py:1-155`
- Test: `backend/tests/test_world_runtime_population_cadence.py`
- Test: `backend/tests/test_population_incremental_reads.py`
- Test: `backend/tests/test_siming_population_authorized_cadence_publication.py`

**Interfaces:**
- Consumes: 已授权 `PopulationCadenceInput`、已有 `ProjectionCheckpoint`、事件序号索引。
- Produces: 相同 cadence/schema/revision 校验和 `PopulationReadSet`；同一窗口只构造一次 cadence，投影组装可从 checkpoint/tail 继续。

- [ ] **Step 1: 写重复读取失败测试**

  publisher、authorized cadence、projection assembler 在同一窗口共享一个 source snapshot；测试断言历史读取和 JSON 编码次数不重复，旧 full replay 结果与增量 tail 结果相同。

- [ ] **Step 2: 复用 cadence 实例和 source digest**

  driver 生成的 cadence 直接传给 publisher；禁止 publisher 再按相同窗口隐式构造第二份。source digest 仍覆盖授权要求的版本向量、scope 和规则版本。

- [ ] **Step 3: 为投影组装增加 checkpoint/tail 路径**

  从最后已应用序号读取 tail；只更新受影响的当前投影和候选索引。旧事件仍可通过显式 full replay 重建。

- [ ] **Step 4: 处理 stale、缺口和恢复**

  source revision 变化、scope 不匹配、checkpoint schema 不兼容、tail 缺口时返回现有 requeue/error，不使用未经验证的部分投影。

- [ ] **Step 5: Commit**

  提交信息：`复用群体窗口与增量投影游标`。

### Task 6：建立历史增长性能回归和证据 profile

**Files:**
- Modify: `.harness/profiles/population-data-oriented-persistence.json`
- Create: `.harness/profiles/population-data-oriented-incremental-read.json`
- Create: `scripts/verification/verify_population_data_oriented_incremental.py`
- Create: `backend/tests/test_population_incremental_benchmark.py`

**Interfaces:**
- Consumes: Task 4/5 的已有接口和 `.harness/verification/population-data-oriented-research/results.json` 基线。
- Produces: 固定数据集下的 p50/p95、历史扫描数、序列化字节、投影数量和 full/tail replay evidence。

- [ ] **Step 1: 写基准断言**

  对 54、100、1,000、10,000 人和短/长历史分别测 full 与 tail；测试只断言计量协议及行为等价，不写死机器时间阈值。

- [ ] **Step 2: 实现离线验证脚本**

  不导入 `app.main`、不启动 provider；记录 Python 版本、git head、输入 digest、p50/p95 和输出 hash。

- [ ] **Step 3: 运行 profile**

  Run: `python scripts/verification/harness.py --profile population-data-oriented-incremental-read`

- [ ] **Step 4: 审查复杂度证据**

  确认历史增加时 tail 路径的扫描/编码量不随全部历史增长；若仍增长，回到 Task 4/5，不开始 SoA。

- [ ] **Step 5: Commit**

  提交信息：`增加群体增量读取性能证据`。

### 阶段二出口检查

- [ ] `python -m pytest -q backend/tests/test_population_incremental_reads.py backend/tests/test_world_runtime_population_cadence.py backend/tests/test_siming_population_authorized_cadence_publication.py backend/tests/test_population_incremental_benchmark.py`
- [ ] `python scripts/verification/harness.py --profile population-data-oriented-incremental-read`
- [ ] full replay 与 checkpoint+tail replay hash 一致；stale、缺口和 scope 错误不会输出未授权投影。
- [ ] 记录重复 cadence 构造、全历史读、JSON 编码和投影组装次数；profile 必须调用真实 checkpoint+tail assembler，不能用 hot-state 全量导出后过滤代替。

## 阶段三：连续状态与深度认知分频

阶段目标：普通居民按经过的仿真时间和到期事件保持连续；昂贵规划、反思、LLM 只在需要时消耗预算，不再被“每轮最多选两个候选”阻塞或误认为完整生活模拟。

### Task 7：分离 B0 连续状态推进与昂贵候选选择

**Files:**
- Modify: `backend/app/services/siming_population_capability.py:149-491`
- Modify: `backend/app/population_continuity/decision_surface.py:242-365`
- Modify: `backend/app/population_continuity/seed_planner.py:23-145`
- Test: `backend/tests/test_population_continuity.py`
- Test: `backend/tests/test_siming_population_decision_planner.py`
- Test: `backend/tests/test_siming_led_population_seed_continuity.py`

**Interfaces:**
- Consumes: `PopulationCadenceInput`、`PopulationReadSet`、现有 `CharacterContinuityCommand` 和 Owner receipt。
- Produces: 一个只生成有界连续性增量、`presentation_seed` 或 `deferred` 结果的 B0 内部批处理路径，以及现有 `run_default_decision_cycle(...)` 的昂贵候选预算路径；只有 B1/B2 授权意图才经 Character Core/Owner 接口。

- [ ] **Step 1: 写分频失败测试**

  用 N=12、54、1,000 的固定窗口断言所有符合条件的 B0 actor 的 state cursor 推进到窗口末端；昂贵候选仍受现有 budget/max candidates 限制；无 exposure evidence 时不生成 memory candidates。

- [ ] **Step 2: 定义连续增量**

  连续增量只包含明确的数值/进度字段、source revision vector、时间区间和 idempotency key；不得在 B0 路径创建完整 profile、LLM 请求或长期记忆。

- [ ] **Step 3: 让 B0 结果保持无写权限，并接入授权升级**

  B0 批量计算只产生 `state_deltas`、`presentation_seed` 或 `deferred`；每个结果保留 `simulation_tick_cursor`、actor revision、source revision、scope、失败原因和 requeue。只有通过 activation/B1/B2 的结果才可生成 Owner-bound intent 或 Character Core command，不能把批量数组直接写进世界真相。

- [ ] **Step 4: 验证公平性和暂停恢复**

  覆盖 starvation credit、同一 actor revision conflict、pause/resume、catch-up、duplicate window 和 configured roster。

- [ ] **Step 5: Commit**

  提交信息：`分离居民连续推进与候选决策预算`。

### Task 8：建立到期索引和时间积分路径

**Files:**
- Modify: `backend/app/world_runtime/population_driver.py:35-145`
- Modify: `backend/app/world_runtime/simulation_clock.py:1-65`
- Modify: `backend/app/population_continuity/world.py:155-190`
- Create: `backend/tests/test_population_due_index.py`
- Test: `backend/tests/test_population_runtime_driver.py`
- Test: `backend/tests/test_population_continuous_runtime.py`

**Interfaces:**
- Consumes: 现有 `SimulationClock` 和唯一 cadence driver。
- Produces: driver 每个窗口返回 due/deferred/rejected 统计；内部使用标准库 `heapq` 或等价索引，不添加第二个时钟或后台 scheduler。

- [ ] **Step 1: 写到期顺序和跨窗口测试**

  同一 tick 多个 due item 按稳定 `(due_tick, actor_id, obligation_id)` 顺序；跨越多个窗口时一次积分到阈值，保留阈值事件和未处理 backlog。非 due actor 仍按 `from_tick/to_tick` 更新客观游标，due index 只控制昂贵或有阈值的工作。

- [ ] **Step 2: 实现最小到期索引**

  在 cadence/当前投影更新时维护下次到期索引；driver 只取不晚于窗口末端的项目。名单变更、取消、重复和恢复时重建或修正索引。

- [ ] **Step 3: 保持窗口幂等**

  due item 带 cadence/actor revision/idempotency key；发布失败不推进确认游标并重新挂回 due index，重复发布返回既有 receipt。`simulation_tick_cursor` 只有在事件追加成功后推进，不能使用 source revision 代替。

- [ ] **Step 4: 运行时间连续性测试**

  Run: `python -m pytest -q tests/test_population_due_index.py tests/test_population_runtime_driver.py tests/test_population_continuous_runtime.py`

- [ ] **Step 5: Commit**

  提交信息：`增加居民到期索引与时间积分`。

### Task 9：限制深度认知和 LLM 唤醒范围

**Files:**
- Modify: `backend/app/character_agent/runtime/runtime_loop.py:2046-2080,4635-4780`
- Modify: `backend/app/services/siming_population_capability.py`
- Test: `backend/tests/test_population_activation_policy.py`
- Test: `backend/tests/test_character_agent_runtime_memory_integration.py`
- Create: `backend/tests/test_population_cognition_budget.py`

**Interfaces:**
- Consumes: 现有 `run_scheduled_background_cognition_ticks(...)`、wake candidates、activation lock 和 cadence policy。
- Produces: 对 active/profile actor 的按需认知调用；B0 dormant actor 不经过 L2/L3/LLM，除非已有明确 activation grant。

- [ ] **Step 1: 写预算和过期结果测试**

  断言同一窗口深度认知调用数受预算限制；玩家接触、显著事件、计划失效可提升优先级；LLM 延迟返回在 actor revision 变化后被拒绝或 requeue。

- [ ] **Step 2: 收紧唤醒选择**

  复用既有 `RuntimeWakeUpCandidate` 和 population policy；不做常驻全量 memory consistency 扫描，不因镜头外就停止 B0 世界后果。

- [ ] **Step 3: 记录可观测预算**

  记录 active、quiet、B0、LLM queued/completed/expired、最大等待时间和 requeue 原因；诊断输出必须有界。

- [ ] **Step 4: 回归 Character Core 语义**

  Run: `python -m pytest -q tests/test_population_cognition_budget.py tests/test_character_agent_runtime_memory_integration.py tests/test_population_activation_policy.py`

- [ ] **Step 5: Commit**

  提交信息：`限制群体深度认知与模型唤醒预算`。

### 阶段三出口检查

- [ ] `python -m pytest -q backend/tests/test_population_continuity.py backend/tests/test_population_due_index.py backend/tests/test_population_cognition_budget.py backend/tests/test_population_continuous_runtime.py`
- [ ] `python scripts/verification/harness.py --profile population-continuous-runtime`
- [ ] 所有居民的 B0 cursor 连续推进，昂贵候选/LLM 预算独立；无暴露证据不生成 memory candidate。
- [ ] 暂停恢复、重复窗口、Owner receipt、actor revision conflict 和延迟结果均有证据。

## 阶段四：热状态 seam、布局门禁与批量提交

阶段目标：先用稳定 ID 映射的最小热状态 seam 验证字段访问集合；只有通过 1× 实时门禁且确认 Python 热循环为主要瓶颈时，才把同构字段迁移为列式数组或其他 SoA 布局。保留 Pydantic/协议作为外部 seam，保留 Owner 和 Character Core 作为写入权威。

### Task 10：建立人口热状态存储的最小 seam

**Files:**
- Create: `backend/app/population_continuity/hot_state.py`
- Modify: `backend/app/population_continuity/world.py:155-190`
- Modify: `backend/app/population_continuity/roster.py`
- Create: `backend/tests/test_population_hot_state.py`

**Interfaces:**
- Consumes: `PopulationRoster.actor_ids`、稳定 actor ID、当前投影和 cadence。
- Produces: `PopulationHotState` 的最小接口：`upsert(actor_id, values, revision) -> None`、`due_actor_ids(tick) -> tuple[str, ...]`、`read(actor_id) -> Mapping`、`apply_batch(...) -> tuple[...receipt...]`；内部槽位不作为持久身份。

- [ ] **Step 1: 写容器和身份测试**

  覆盖稳定 ID 到槽位映射、删除/复用槽位、revision、未知 actor、重启重建、字段默认值和读写隔离。

- [ ] **Step 2: 只放入同构热字段**

  初始字段限于 `last_update_tick`、活动阶段、疲劳/需求数值、下次到期 tick、starvation credit 等已批准字段；不放姓名、记忆、对白、完整背包或权限对象。

- [ ] **Step 3: 接入只读投影**

  `WorldContinuityRuntime.build_population_projections(...)` 可从热状态产生投影；热状态只在既有 Owner/Character Core 确认后更新。

- [ ] **Step 4: 加入基线等价性检查**

  同一 cadence 用旧字典/Pydantic路径和热状态路径执行，比较 projection digest、candidate 顺序、deferred 顺序和 receipt 输入。

- [ ] **Step 5: Commit**

  提交信息：`增加群体热状态紧凑存储`。

### Task 11：让连续规则和候选评估批量读取热字段

**Files:**
- Modify: `backend/app/population_continuity/decision_surface.py:242-365`
- Modify: `backend/app/services/siming_population_capability.py:209-491`
- Modify: `backend/app/population_continuity/seed_planner.py:38-145`
- Test: `backend/tests/test_population_hot_state.py`
- Create: `backend/tests/test_population_hot_state_equivalence.py`

**Interfaces:**
- Consumes: `PopulationHotState` 只读数组/索引、固定 cadence 和 capability catalog。
- Produces: 现有 `PopulationDecision`、`CharacterSimulationSeed`、Owner bound intent 类型；不向外暴露数组地址或槽位。

- [ ] **Step 1: 写结果等价性和冲突测试**

  对 54/100/1,000/10,000 人比较旧路径和热路径的结果；覆盖相同分数的稳定排序、budget、deferred、starvation、actor revision conflict 和未知 capability。

- [ ] **Step 2: 批量读取字段**

  每个 system 显式声明读取列；只在需要构造协议边界时创建 Pydantic 对象。不要先生成包含全部嵌套 JSON 的 projection 再丢弃大部分字段。

- [ ] **Step 3: 处理稀疏关系**

  社会关系使用边表和 actor/组织邻接索引；局部事件只访问受影响边。禁止默认构造 N×N 关系矩阵。

- [ ] **Step 4: 运行基准和等价性测试**

  Run: `python -m pytest -q tests/test_population_hot_state.py tests/test_population_hot_state_equivalence.py tests/test_siming_population_decision_planner.py`

- [ ] **Step 5: Commit**

  提交信息：`让群体候选评估批量读取热字段`。

### Task 12：合并同 Owner 批次并保留逐 actor 结果

**Files:**
- Modify: `backend/app/services/siming_population_capability.py:300-775`
- Modify: 具体 Domain Owner 实现文件（仅涉及已测批量路径的 Owner）
- Modify: `backend/app/gameplay/settlement_plan.py`
- Test: `backend/tests/test_siming_population_production_boundaries.py`
- Test: `backend/tests/test_siming_population_inventory_vertical.py`
- Test: `backend/tests/test_siming_population_domain_owner_runtime.py`
- Create: `backend/tests/test_population_batch_settlement_equivalence.py`

**Interfaces:**
- Consumes: 同一 read set 的结构化 owner-bound intents、source revision vector 和现有 Owner receipt。
- Produces: 已有 receipt/settlement result；批次内部合并事件，外部仍能按 actor/candidate 查询成功、失败、requeue 和 zero-write。

- [ ] **Step 1: 写批量等价性测试**

  单条提交和同 Owner 批量提交使用相同输入，比较事件顺序、revision vector、idempotency status、owner receipt 和 Character Core seed。

- [ ] **Step 2: 只合并安全批次**

  仅合并相同 Owner、相同 scope、相同 policy/ruleset、互不冲突或能按稳定顺序解决的 intents；库存、席位、金钱等竞争仍由 Owner 检查。

- [ ] **Step 3: 保留失败局部性**

  一个 actor 失败不得静默吞掉其他 actor 的结果；批次结果必须能标识 committed、duplicate、requeue、rejected 和 zero-write。

- [ ] **Step 4: 运行领域回归和 replay**

  Run: `python -m pytest -q tests/test_population_batch_settlement_equivalence.py tests/test_siming_population_production_boundaries.py tests/test_siming_population_inventory_vertical.py`

- [ ] **Step 5: Commit**

  提交信息：`合并同领域群体结算批次`。

### 阶段四出口检查

- [ ] `python -m pytest -q backend/tests/test_population_hot_state.py backend/tests/test_population_hot_state_equivalence.py backend/tests/test_population_batch_settlement_equivalence.py`
- [ ] 运行阶段二增量 profile，确认数组化没有重新引入全历史序列化。
- [ ] 固定输入下旧路径与热路径的最终投影、Owner receipt、Character Core revision 和 replay hash 一致。
- [ ] 报告 CPU、RSS、对象分配、序列化字节和批次大小；如果收益只来自更少的历史读取，不宣称 SoA 已带来向量化收益。

## 阶段五：并行、原生/GPU 与 Godot 远景表现评估

阶段目标：只有在前四阶段后的真实瓶颈仍超出目标预算时，才迁移热循环或表现批处理；所有并行结果通过版本和 Owner 语义合并。

### Task 13：建立同一窗口的只读并行和确定性合并

**Files:**
- Modify: `backend/app/services/siming_population_capability.py`
- Modify: `backend/app/population_continuity/hot_state.py`
- Modify: `backend/app/gameplay/settlement_plan.py`
- Create: `backend/tests/test_population_parallel_determinism.py`

**Interfaces:**
- Consumes: immutable cadence/read set、只读热状态、结构化 candidate/intent。
- Produces: 与串行路径相同的有序 candidate、Owner settlement input 和 audit；不允许 worker 直接写 Owner、Event Store、Graph 或 Character Core。

- [ ] **Step 1: 写确定性测试**

  改变 worker 分片、完成顺序和重复执行顺序，断言 candidate 排序、随机 seed、事件顺序和 result digest 不变。

- [ ] **Step 2: 只并行纯计算**

  并行范围限于热字段读取、局部规则、候选打分和结构化结果；提交阶段回到稳定顺序的既有 Owner seam。

- [ ] **Step 3: 处理过期和冲突**

  batch result 携带 cadence/read-set digest、actor revision 和 source vector；变化后 requeue，禁止覆盖新版本。

- [ ] **Step 4: 测量全程收益**

  计入分片、序列化、线程/进程调度、合并、Owner 提交和恢复成本；不只测 worker kernel。

- [ ] **Step 5: Commit**

  提交信息：`增加群体纯计算确定性并行路径`。

### Task 14：原生代码或 GPU 的准入门槛与最小适配器

**Files:**
- Create: `scripts/verification/verify_population_native_gpu_gate.py`
- Create: `backend/tests/test_population_native_gpu_gate.py`
- Modify: `.harness/profiles/population-data-oriented-incremental-read.json`
- Optional only after gate: `backend/app/population_continuity/native_kernel_adapter.py` 或独立原生构建目录

**Interfaces:**
- Consumes: 阶段四/五基准、固定输入/输出 schema、热状态列布局。
- Produces: “继续 Python / 使用已安装数值库 / 原生模块 / GPU”决策证据；适配器只能返回结构化候选或状态增量，不能获得世界真相写权限。

- [ ] **Step 1: 写准入测试**

  测试明确报告 CPU 热循环占比、数据打包/传输/合并占比、目标倍速下 p95、RSS 和结果等价；未超过预算时断言不启用额外模块。

- [ ] **Step 2: 先测现有依赖和标准库基线**

  不新增依赖；比较 Python 热状态、已有依赖可用路径和原生候选。记录多局并行与单局并行分别的收益。

- [ ] **Step 3: 若门槛满足，再实现最小适配器**

  只搬运实际访问列；输入输出带 schema/revision/digest；CPU/GPU 不直接写 Event Store、Graph、Owner 或 Character Core。

- [ ] **Step 4: 验证失败回退**

  模块缺失、设备不可用、传输失败、kernel 错误、版本不匹配时回退到阶段四路径并保留可审计错误；回退不得改变事件结果。

- [ ] **Step 5: Commit only if gate passes**

  未达到门槛时只提交准入证据和“不迁移”结论；达到门槛才提交适配器，提交信息：`接入经基准证明的群体热循环适配器`。

### Task 15：Godot 远景实例与数据输出分层

**Files:**
- Inspect/Modify only if needed: existing Godot scene and scripts under `scenes/` and `scripts/`
- Create: `scripts/verification/verify_population_presentation_lod.py`
- Modify: `.harness/profiles/population-data-oriented-incremental-read.json`
- Test: existing Godot runtime/headless verification path, if available

**Interfaces:**
- Consumes: 后端结构化 presentation seed/增量和观察范围。
- Produces: 远景批量表现或 MultiMesh/RenderingServer 的本地实例更新；不产生或修改世界真相，不从表现位置推断交互成功。

- [ ] **Step 1: 写表现分层验收条件**

  明确近景完整角色、远景重复实例、不可见人口三类数量；断言远景切换不改变后端状态、Owner receipt、角色 revision 或 replay hash。

- [ ] **Step 2: 先测当前场景成本**

  记录实例数、帧时间、CPU、GPU、网络消息和资源加载；没有 Godot executable 时只记录 `godot_unverified`。

- [ ] **Step 3: 仅对重复远景采用批量表现**

  可以按区域使用 MultiMesh/RenderingServer；保留近景骨骼、独立交互和必要裁剪。MultiMesh 的整组可见性限制要在 profile 中记录。

- [ ] **Step 4: 验证跨边界语义**

  Run: `python scripts/verification/harness.py --profile population-data-oriented-incremental-read` 及可用 Godot headless probe；检查一条真实增量从后端到表现的路径。

- [ ] **Step 5: Commit only after Godot evidence**

  没有 Godot 运行证据时不提交表现实现；若已验证，提交信息：`优化群体远景表现实例`。

### 阶段五出口检查

- [ ] `python -m pytest -q backend/tests/test_population_parallel_determinism.py backend/tests/test_population_native_gpu_gate.py`
- [ ] `python scripts/verification/harness.py --profile population-data-oriented-incremental-read`
- [ ] 运行 `python scripts/verification/harness.py --profile all`；Godot 缺失时保留 `godot_unverified`，不提升后端结论。
- [ ] 并行/原生/GPU 结果与串行结果等价，过期结果会 requeue，Owner 竞争仍由 Owner 解决。
- [ ] 表现优化没有把客户端变成世界真相 authority。

## 各阶段详细实现卡

### 阶段一实现卡：把“完整快照写入”拆成“变化行 + 恢复锚点”

1. **先建立可观察的写入边界。** 在 `SQLiteHeavenlyGraphAdapter.write_batch()` 外层记录本批 `node_ids`、`relation_ids`、scope、旧/新 revision 和幂等键；SQL trace 只用于测试，不进入生产日志。测试固定三组数据：100、1,000、10,000 个历史节点，分别追加新节点、追加同一节点 revision 2、追加关系。
2. **普通 graph batch 只写 delta。** `write_batch()` 成功后只执行：本批 `graph_nodes`/`graph_relations` INSERT、当前 scope 的 `graph_stream_revisions` upsert、当前幂等键 INSERT。任何历史行都不能被 DELETE 或重新 INSERT。branch lifecycle、correction、checkpoint 继续使用独立的低频事务函数，并在测试中证明不会误走普通 batch 的 delta 函数。
3. **失败必须是双回滚。** SQL 事务失败先 rollback；内存 adapter 恢复到 batch 前快照；再次打开数据库时不能看到半批节点、幂等记录或 stream revision。测试分别注入 SQL exception、commit exception 和重复幂等键。事件追加成功才是提交锚点，current state/checkpoint 不能在事件未确认时推进游标。
4. **当前态/历史/检查点使用三个明确载体。** `CharacterGraphContinuityStore` 的 current-state node 只保存 dynamic/need/supervision/goal/revision/receipt/pending-candidate/seed projection；session store 追加单条 timeline event；完整 checkpoint 每 16 个 timeline event 或显式恢复点生成，保存 `simulation_tick_cursor`、`last_applied_global_sequence`、source revision vector 和 schema version。恢复流程从最后一个已提交事件序号读取 tail，重建 current state，再验证 checkpoint digest；发现缺口只能返回 `requeue`/`projection_gap`，不能静默使用未确认 current state。
5. **阶段一完整出口。** 10,000 节点改单节点的 SQL 行数必须是常数级；写入失败、同 source event 重放、character revision conflict、scope 拒绝、checkpoint+tail replay 的 hash 全部与基线一致；证据必须包含行数、payload 字节、p50/p95 和重启结果。

### 阶段二实现卡：让每个窗口只消费 source cursor 之后的数据

1. **事件索引设计。** `GameplayEventStore` 维护 `_events_by_stream[stream_id]` 和 `_transaction_end_sequences`；global sequence 仍由 `_events` 作为唯一顺序来源。`append_batch()` 先生成 committed events，再一次性更新所有索引；`from_snapshot()` 从事件列表重建索引，不把索引写进外部协议。
2. **读取契约。** `read_events(global_sequence_after=x, limit=n)` 从 `x+1` 起切片；`read_stream(from_revision=a, to_revision=b)` 使用 stream revision 切片；两者都返回 deep copy。空 tail、缺失 stream、limit=0、snapshot 恢复和内部伪造测试必须保留原语义。
3. **投影 cursor。** 为每个 projection 保存 `last_applied_global_sequence`、`source_stream_revision`、`checkpoint_schema_version`、`projection_digest`。读取时检查 source revision 是否仍等于 cadence pin；不等时返回 `stale_read_set`。cursor 之后存在序号缺口时返回 `projection_gap`，不能跳过缺口继续组装。
4. **cadence 复用。** `WorldContinuityRuntime` 以 `(window_start, window_end, source_revision, policy_revision, selector_revision, ruleset_revision, scope)` 为缓存键。同一键只构造一次 `PopulationCadenceInput`、一次 source digest 和一次 projection tuple；publisher、authorized cadence 和 assembler 只能接收该实例，不能重新读取全历史。
5. **full/tail 等价性。** 每组固定输入同时执行 `full_replay(events)` 和 `checkpoint_plus_tail_replay(checkpoint, tail)`，比较 projection hash、revision vector、Owner receipt 输入和 candidate 顺序；任何差异都阻止阶段出口。
6. **阶段二完整出口。** 1,000、10,000、50,000 条历史下，tail 的扫描事件数和序列化字节只随 tail 增长；重复 cadence 构造计数为 1；stale、gap、scope mismatch、checkpoint schema mismatch 都返回明确错误或 requeue。

### 阶段三实现卡：把 B0 连续世界推进与 L2/L3/LLM 选择彻底分频

1. **B0 输入和输出固定。** B0 只读取 `actor_ref`、`last_update_tick`、数值需求/疲劳、`next_due_tick`、starvation credit、source revision vector；输出 `state_deltas`、`presentation_seed` 或 `deferred`、`from_tick/to_tick`、`simulation_tick_cursor` 和 `idempotency_key`。输入中出现 `memory_candidates`、`llm_request`、完整 profile 或私有知识时直接拒绝；B0 输出不得直接进入 Character Core 或 Owner 写入。
2. **连续推进算法。** 对每个 actor 计算 `elapsed = window_end - last_update_tick`，按规则表执行数值积分和到期阈值检测；结果必须是确定性纯函数。跨多个窗口时一次积分到 window end，但每个阈值事件保留 source window 和 idempotency key。
3. **昂贵候选独立预算。** `PopulationDecisionPlanner` 只接收 B1/B2 候选；`max_candidates`、token budget、LLM budget 与 B0 actor 数量分开统计。无 exposure evidence 不得创建 memory candidate；B0 dormant actor 不进入 L2/L3/LLM。
4. **B0 无写权限，授权路径独立提交。** B0 增量只能作为 presentation/deferred 结果追加；每个结果保存 `from_tick`、`to_tick`、`simulation_tick_cursor`、actor revision、source revisions、scope 和幂等键。只有 B1/B2 授权路径才生成 `CharacterContinuityCommand` 或 Owner-bound intent，并保存 before/after revision、source owner receipt、failure/requeue reason。批量计算不能直接写 graph、event store 或 character state。
5. **到期堆。** 在 `PopulationDueIndex` 中使用 `(due_tick, actor_id, obligation_id, revision)`；更新同一 obligation 时旧 token 失效，pop 时丢弃过期 token。driver 只 pop `due_tick <= window_end` 的昂贵/阈值项目，发布失败不推进确认 cursor 并重新挂回；非 due actor 仍按时间区间推进客观游标。
6. **阶段三完整出口。** N=12、54、1,000 的所有已注册 B0 actor 都以独立 `simulation_tick_cursor` 推进到窗口末端；due-only 工作只处理到期项；暂停/恢复、catch-up、重复窗口、actor revision conflict、LLM 过期结果均有测试；深度认知调用数不超过预算，且可观测 queued/completed/expired/requeue。N=1,000 前必须有 roster/continuity 注册与恢复证据。

### 阶段四实现卡：将已证明字段放入热表，并验证批量结算等价

1. **热表字段白名单。** 初始只允许 `last_update_tick`、`activity_phase`、`fatigue`、`need_pressure`、`next_due_tick`、`starvation_credit` 和内部 revision。姓名、对白、记忆、背包、权限、Owner receipt、完整 Pydantic profile 均禁止进入热表。`list[dict]` 只作为基线容器；没有端到端门禁证据，不得称为 SoA。
2. **稳定身份和槽位。** `actor_id -> slot` 只用于当前进程；删除 actor 释放槽位，加入新 actor 可复用槽位；持久身份仍是 actor ID。`read()` 返回副本或只读 Mapping，任何 worker 都不能拿到内部数组引用。
3. **等价路径。** 同一 cadence 同时跑旧 projection path 和 hot-state path，比较 projection digest、candidate 顺序、deferred 顺序、B0 delta、Owner intent、Character Core revision 和 replay hash。任意差异先修字段读取顺序或默认值，再谈性能。若 1× 门禁已通过，则保留当前 seam，不继续引入 SoA。
4. **稀疏关系。** 社会关系、组织成员和局部影响使用边表/邻接索引；每个规则声明读取列和关系集合，禁止构造 N×N 矩阵。热表只保存受影响 actor 的数值更新。
5. **Owner 批次。** 仅将相同 `owner_ref`、scope、policy/ruleset、source vector 且无资源竞争的 intents 合批；库存、支付、席位、占用等竞争由 Owner 再校验。批次结果必须按 actor/candidate 返回 `committed`、`duplicate`、`requeue`、`rejected`、`zero_write`，单个失败不能吞掉其他结果。
6. **阶段四完整出口。** 54、100、1,000、10,000 人旧路径与热路径结果完全一致；报告 CPU、RSS、对象分配、序列化字节、批次大小；只有在这些证据通过后才允许进入并行或原生评估。

### 阶段五实现卡：只并行纯计算，原生/GPU/Godot 全部采用准入门槛

1. **并行边界。** worker 只接收 immutable cadence、read set 和热字段快照，只能做规则、排序、候选评分和结构化 delta；worker 不得调用 Owner、Event Store、Graph、Character Core 或修改热表。主线程按 `(priority, actor_id, candidate_ref)` 稳定合并。
2. **确定性和过期。** 每个并行结果携带 cadence/read-set digest、actor revision、source vector、seed。合并前重新检查版本；不匹配返回 requeue。改变 worker 数、分片顺序和完成顺序，结果 hash 必须一致。
3. **原生/GPU gate。** 先测 Python kernel、数据打包、传输、同步、合并、Owner 提交和恢复的完整 p50/p95。100/1,000/10,000 人的 1× 窗口必须连续 30 个窗口满足 p95 不超过墙钟预算 80%、backlog 不增长且最大推进延迟不超过 1 个窗口；10× 只做独立压测。只有 1× 未通过且 Python 热循环占端到端耗时至少 60% 时才允许适配器；否则证据明确记录“继续 Python”。
4. **适配器契约。** 原生/GPU 只接收固定列布局和 schema version，返回结构化候选/delta；设备不可用、模块缺失、传输失败、schema mismatch 都回退阶段四串行路径，且回退结果 hash 必须一致。
5. **Godot 远景。** 只有 Godot editor/runtime/headless 证据可用时才做 MultiMesh/RenderingServer 远景实例；近景角色、交互和音频保持现有路径。远景表现只消费 presentation seed，绝不写世界真相或根据位置推断成功。
6. **阶段五完整出口。** 并行与串行结果、Owner receipt、Character revision、replay hash 完全一致；native/GPU 是否启用有基准证据；Godot 若未运行，必须保持 `godot_unverified`，不提交表现迁移实现。

## 阶段出口报告格式

每个阶段结束时必须新增一个 JSON 和 Markdown 报告，至少包含：

- `stage`、`git_head`、Python/依赖版本、输入数据 digest、固定 seed；
- 人口档位 `54/100/1,000/10,000`，历史长度和窗口长度；
- p50/p95、峰值 RSS、对象分配或序列化字节、SQL 行数、事件扫描数、投影数量；
- `full_hash`、`tail_hash`、Owner receipt digest、Character revision vector；
- 写入失败、重复恢复、stale、gap、scope 拒绝和过期结果的错误码；
- `implementation_status` 与 `godot_status`。Godot 只能是有真实证据时的 `godot_verified`，否则必须是 `godot_unverified`。

没有上述报告、出口测试或恢复证据的阶段，不能在计划中勾选完成。

## 最终验收清单

- [ ] **正确性**：固定输入下完整事件、当前态、Owner receipt、Character Core revision、memory scope 和 replay hash 与基线一致。
- [ ] **恢复**：进程重启、checkpoint+tail、重复 cadence、断点、写入失败、设备失败均有明确结果。
- [ ] **复杂度**：热路径不重新扫描全部历史；修改一个图节点不重写整库；社会关系按稀疏边和局部影响更新。
- [ ] **调度**：B0 连续状态和昂贵认知预算分离；所有居民的最大推进延迟、backlog 和 starvation 可观测。
- [ ] **数据布局**：热数组只有明确 owner；稳定 actor ID 与内部槽位分离；异步结果带版本和幂等信息。
- [ ] **边界**：无第二事件总线、无第二时钟、无客户端世界真相、无隐式 fixture fallback、无常驻全量记忆扫描。
- [ ] **性能报告**：每阶段报告 p50/p95、峰值 RSS、对象分配、序列化/持久化字节、SQL 行数、事件读取数、投影数和端到端耗时。
- [ ] **验证**：focused pytest、相关 Harness profile、`git diff --check` 和最终 `harness.py --profile all` 均有新鲜证据；Godot 状态单独标注。

## 执行约定

每个 task 按“先写失败测试 → 运行确认失败 → 最小实现 → focused 测试 → Harness/基准 → 检查差异”执行；阶段出口通过后再将该阶段 task 合并为一个中文 commit。任何行为不等价、恢复缺口或写入放大未解决时停止推进，不用 SoA、GPU 或异步并行掩盖问题。

计划本身不授权直接修改运行时代码。执行时应先以本计划对应阶段创建/确认正式 spec，使用隔离 worktree（若工作流要求），每阶段只提交请求范围内文件，并把 `docs/superpowers/` 排除在代码提交之外。
