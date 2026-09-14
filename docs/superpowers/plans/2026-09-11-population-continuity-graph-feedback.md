# 群体连续性与图谱反馈闭环 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 让最小 12 人居民集由 World Runtime 提供模拟窗口、由 Siming 进行世界线治理、由 Domain Owner 结算事实、由 Heavenly Graph 反馈上下文，并持续写入人物客观连续状态。

**Architecture:** World Runtime 产生有边界的 cadence window；`SimingRuntime` 在窗口内选择和限制群体计划；`PopulationSimulationCapability` 把计划交给现有 Owner/Character Core 链路。Heavenly Graph 只投影已提交事实并提供因果、认知和故事线查询，下一轮读取这些反馈，不负责时钟、调度或领域结算。

**Tech Stack:** Python 3、Pydantic、SQLite Heavenly Graph、现有 `pytest` 与 Harness profiles。

**Spec:**
- `docs/superpowers/specs/world-character-siming-authority-mainline/2026-08-29-siming-led-population-simulation-design.md`
- `docs/8月分析/司命与群体世界补充设计/02-知识图谱记忆与故事线桥.md`
- `docs/superpowers/specs/current-project-intelligence-upgrade/2026-08-23-heavenly-graph-semantic-foundation-design.md`

## Global Constraints

- 居民规模先固定为 12 人；其中 3–5 人可进入近场/激活路径，其余保持 B0/B1/B2 连续推进。
- cadence 由 World Runtime 提供模拟窗口；Owner receipt 回流不自动等价于下一次调度。
- Heavenly Graph 是派生认知层，不拥有领域事实，也不成为群体调度器。
- 未参与人物可以更新客观连续状态；没有暴露证据时不得生成记忆候选。
- 活跃角色与群体模拟发生修订冲突时，以已提交的 Owner/Character Core 事实为准，过期计划重新排队。
- `docs/superpowers/` 只保存本地设计和实施过程文档，不纳入提交。

---

### Task 1: 统一群体 cadence 路由

**Files:**
- Modify: `backend/app/main.py`（population cadence 发布入口）
- Modify: `backend/app/services/siming_runtime.py`（selector 路由）
- Modify: `backend/app/population_continuity/decision_surface.py`（通用 descriptor 输出约束）
- Test: `backend/tests/test_siming_population_decision_routing.py`、`backend/tests/test_siming_population_authorized_cadence_publication.py` 及现有 population Harness profile

**Interfaces:**
- Consumes: World Runtime 提交的 `window_id`、时间坐标、scope、selector revision 和预算。
- Produces: 一个明确 selector 下的 `PopulationDecision`，后续交给现有 `PopulationSimulationCapability`。

- [ ] 将旧 fixture 明确标记为 `selector:cohort-bakery:v1`，通用居民路径固定使用 `selector:generic:population:v1`；未知 selector 直接拒绝。
- [ ] 保留现有 `publish_authorized_population_cadence` 的授权校验和幂等语义，增加 window 坐标校验，禁止用 Owner receipt 隐式制造 cadence。
- [ ] 让通用 routine candidate 进入现有 Character Core continuity command 路径；只允许已经声明的输出类型，禁止直接写领域事实或人物私有记忆。
- [ ] 增加路由测试：fixture 和 generic 各自进入唯一执行路径；旧 selector 不得误入 generic；重复 window 不重复执行；revision 过期时返回结构化拒绝。

### Task 2: 接入 World Runtime 的持续模拟窗口

**Files:**
- Modify: `backend/app/world_runtime/scheduling.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/services/siming_runtime.py`
- Test: `backend/tests/test_siming_population_authorized_cadence_publication.py`（补充 World Runtime window contract）

**Interfaces:**
- Consumes: World Runtime 的离散 simulation tick 或 committed world window。
- Produces: 可重放的 cadence envelope，包含 `window_id`、`valid_at`、`recorded_at`、scope、selector 和预算。

- [ ] 从现有 World Runtime 调度入口提交离散窗口；默认按小时或日级推进，不在帧循环内运行。
- [ ] 每个窗口只生成一次授权人口计划；窗口没有变化时返回幂等结果，不创建新 Owner 事实。
- [ ] 将窗口的时间和 revision 传入现有 `PopulationDecisionPlanner`，保留 budget、max_candidates 和 deferred/rejected 结果。
- [ ] 验证多条故事线可在同一窗口并行产生 candidate；只有共享 Owner 资源、地点或 actor revision 时才串行冲突。

### Task 3: 建立 12 人居民连续性闭环

**Files:**
- Modify/Create: `assets/characters/profiles/` 下的最小居民 profile 集，使注册表可枚举 12 名居民
- Modify: `backend/app/population_continuity/batch.py`
- Modify: `backend/app/population_continuity/seed_planner.py`
- Modify: `backend/app/services/siming_population_capability.py`
- Test: `backend/tests/test_population_continuity.py`、`backend/tests/test_siming_led_population_seed_continuity.py`

**Interfaces:**
- Consumes: 12 名居民的 profile、cadence window 和 Owner receipt。
- Produces: 每名居民可重建的 continuity snapshot/seed cursor，以及按暴露条件生成的 memory candidate。

- [ ] 将 12 名居民全部纳入候选池；按现有预算分批处理，并记录 deferred/priority，避免长期饥饿。
- [ ] 未激活居民至少持续推进任务、日程、位置趋势、压力或疲劳等客观状态；这些更新写入现有 Character Core continuity command。
- [ ] 未参与事件不得生成记忆候选；参与、观察或明确获知时才把候选交给 Character Core。
- [ ] 活跃角色出现 actor revision 冲突时丢弃过期计划并重新排队，不能覆盖已提交事实。
- [ ] 测试连续多个窗口后 12 名居民均有 cursor/revision；验证未暴露事件无记忆候选、暴露事件有候选、冲突计划可重排。

### Task 4: 将 Heavenly Graph 接入下一轮反馈并完成准入证据

**Files:**
- Modify: `backend/app/services/authority_graph_projector.py`（仅补齐群体 Owner 事件映射所需的投影）
- Modify: `backend/app/services/siming_context_compiler.py`（确保按 scope/revision 编译群体反馈）
- Modify: `.harness/profiles/` 中对应 population/graph profile
- Test: `backend/tests/test_authority_graph_projection.py`、`backend/tests/test_siming_population_decision_routing.py`

**Interfaces:**
- Consumes: 已提交 Owner events、图谱 projection、角色受控视角摘要。
- Produces: 下一 cadence 的 bounded Siming context；图谱不可用时返回 `graph_unavailable`/`graph_degraded`，不伪造完整事实。

- [ ] 验证群体 Owner receipt 先进入 World Truth，再由 `HeavenlyAuthorityEventProjector` 投影；projection 保留 source event refs、revision 和时间坐标。
- [ ] 让下一轮 Siming 读取因果链、故事义务、角色认知差异和冲突集合；不得读取 actor-private 原始记忆。
- [ ] 验证图谱查询结果只影响下一轮计划和解释，不直接提交领域事实。
- [ ] 运行 `authority-graph-projection`、`siming-heavenly-graph-foundation`、群体连续性相关 Harness；只有 focused tests、Harness 和依赖环境均通过后，才把 SGC-1/SGC-3 标记为 admitted。SGC 总树保持未完全完成状态。

### Final verification

- [ ] 使用项目声明的 Python 环境安装 `backend/pyproject.toml` 所需依赖。
- [ ] 运行四个任务的 focused pytest。
- [ ] 运行 `python scripts/verification/harness.py --profile siming-led-population-seed-continuity`。
- [ ] 运行 `python scripts/verification/harness.py --profile siming-generalized-population-decision`。
- [ ] 运行 `python scripts/verification/harness.py --profile authority-graph-projection`。
- [ ] 运行 `python scripts/verification/harness.py --profile all`，检查最终 diff，只保留本计划范围内的文件。
