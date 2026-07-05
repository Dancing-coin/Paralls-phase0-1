# 当前项目智能体与世界交互增量专题总实施计划

> 适用范围：`docs/superpowers/specs/current-project-intelligence-upgrade/`

**状态：** `implemented-and-subsequent-topic-profiles-verified-parent-plan`

**实际核对：** 本 parent plan 的后续 L1、VLA、ASK、Siming、interaction、ESM、skeletal、provider readiness、perception identity profiles 已核对通过；具体报告见各子计划。

**目标：** 把已闭合 mainline 之外的增量感知、多模态、局部世界协议、双通道交互、具身身体状态和非运行时工具链能力组织成可执行路线图。

**架构定位：** 本计划不重做 `world-character-siming-authority-mainline` 已闭合范围，而是把专题树里的能力拆成有依赖关系的增量任务组。

**状态纠偏：** 2026-06-30 本计划已完成的是协议、manifest、静态 provider 和 focused proof 切片。它不满足完整规格的运行时能力完成口径。

原 C2 未完成项已迁移到并由以下完整计划收口：

- [2026-07-01-current-project-l1-world-fact-runtime-full-implementation-plan.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/current-project-intelligence-upgrade/2026-07-01-current-project-l1-world-fact-runtime-full-implementation-plan.md)

2026-07-02 拆出的后续完整能力计划继续承接 VLA、ASK、司命态势、交互编排、物理世界作用、骨骼回放、生产工具链和 Godot production-grade provider 等非 L1 能力。

**建议执行顺序：**

1. `Perception Query Frame` 与感知结果协议
2. `Godot` 取样前端与 Providers
3. `L1` 世界事实层与空间底座
4. `System L1 world fact subsystem` 集成
5. 角色智能体多模态链与 `Actor Scene Knowledge`
6. 司命多模态链与全局态势理解
7. `Interaction Orchestration Layer`
8. `ESM` 双通道世界作用层
9. `Embodied Skeletal State Provider`
10. `VLA` 与多模态慢通路
11. 非运行时多模态工具链与生产工具链

**约束：**

- 不破坏 mainline 已闭合的运行时真相与验证面
- 不把 `Godot` 变成重推理宿主
- 不污染角色与司命的多模态运行时上下文
- 所有新能力都必须通过 focused proof 或新增验证面落地

**验证总要求：**

- 所有增量工作应至少新增对应静态测试或 focused verifier
- 不得弱化 `mainline-unified-runtime` 现有证明
- 新 plan 落地后应能说明：
  - 新增了什么
  - 不新增什么
  - 依赖主线什么
  - 如何与现有代码共存

## 任务组

### 任务组 A：统一感知协议

- [x] 完成 `Perception Query Frame` 与感知结果协议的实现设计与最小契约测试
- [x] 明确 `Modality Interpretation Result`
- [x] 明确 `Cross-Modal Understanding Result`
- [x] 明确 `Canonical Percept Bundle`

### 任务组 B：Godot 取样前端

- [x] 定义 `Visual Patch Provider`
- [x] 定义 `Spatial Patch Provider`
- [x] 定义 `Auditory Context Provider`
- [x] 定义 `Embodied State Provider`
- [x] 保证所有 provider 不承担重推理

### 任务组 C：世界空间底座

- [x] 明确 `Scene 3D Space Model` 的抽取来源和对象类型
- [x] 明确 `Spatial Occupancy Field runtime state` 的静态/动态分层
- [x] 明确结构化事实上抛从底座导出的边界

### 任务组 C2：`System L1 world fact subsystem` 集成迁移记录

以下原未完成项不再在本总计划中直接执行，已迁移到并由 `2026-07-01-current-project-l1-world-fact-runtime-full-implementation-plan.md` 收口：

- [x] 从当前 Godot 主场景真实抽取 `Scene3DSpaceModel`
- [x] 维护 `SpatialOccupancyField` 并支持 dirty-zone/event-driven 增量更新
- [x] 将 `EnvironmentFieldState` 合流进 L1 projection 输入
- [x] 实现 runtime-facing `FactProjectionLayer`
- [x] 从空间/环境底座投影 LOS、可达性、affordance、失败/负事实
- [x] 组装真实 `PerceptionQueryFrame`
- [x] 让角色或司命 runtime 消费 `CanonicalPerceptBundle`
- [x] 保留并通过兼容验证入口 `l1-world-fact-runtime`

### 任务组 D：角色侧多模态增强

- [x] 让角色专属多模态栈接入统一感知协议
- [x] 引入 `Actor Scene Knowledge`
- [x] 设计主动感知回推路径

### 任务组 E：司命侧多模态增强

- [x] 让司命专属多模态栈接入统一感知协议
- [x] 设计司命版感知包
- [x] 明确其与 `FairnessStateSnapshot` 的关系

### 任务组 F：交互与世界作用升级

- [x] 定义 `Interaction Orchestration Layer`
- [x] 定义 `ESM` 双通道世界作用层边界
- [x] 明确语义通道和物理通道的统一结果协议

### 任务组 G：具身身体状态升级

- [x] 定义 `Embodied Skeletal State Provider`
- [x] 划分高层具身状态、中层骨架参数、低层骨骼快照
- [x] 明确进入感知链与调试链的位置

### 任务组 H：VLA 与慢通路多模态

- [x] 定义 `VLA` 作为空间视觉理解子链而非主脑
- [x] 定义慢通路多模态顾问触发条件
- [x] 证明慢通路不反压当前主循环

### 任务组 I：非运行时工具链

- [x] 定义 `Non-Runtime Tool Stack`
- [x] 定义 `Non-Runtime Production Stack`
- [x] 设计自动抽取、多模态识别、人工审核的工作流

## 执行证据

- 聚合落地文件：
  - `backend/app/world_runtime/intelligence_upgrade.py`
  - `scripts/character/VisualPatchProvider.gd`
  - `scripts/character/SpatialPatchProvider.gd`
  - `scripts/character/AuditoryContextProvider.gd`
  - `scripts/character/EmbodiedStateProvider.gd`
  - `scripts/character/EmbodiedSkeletalStateProvider.gd`
  - `backend/tests/test_current_project_intelligence_upgrade.py`
  - `scripts/verification/verify_current_project_intelligence_upgrade.py`
- 聚合验证：
  - `python -m pytest backend/tests/test_current_project_intelligence_upgrade.py -v`
  - `python scripts/verification/verify_current_project_intelligence_upgrade.py`
- 证据报告：
  - `.harness/verification/current-project-intelligence-upgrade-report.json`
  - `.harness/verification/current-project-intelligence-upgrade-report.md`
- 剩余风险：
  - 当前计划树的 2026-06-30 切片闭合在协议、manifest、静态 provider 和 focused proof 层。
  - `L1` subsystem integration 已由 `2026-07-01-current-project-l1-world-fact-runtime-full-implementation-plan.md` 承接并收口。
  - 真实 VLA provider、production-grade Godot provider、连续物理作用、骨骼 debug replay 和生产工具流水线等能力已拆入 2026-07-02 子计划，不能用本总计划宣称完成。

## 一句话收束

这份总实施计划的作用，是给当前项目的增量专题规格树提供统一执行顺序和边界，让后续每一份专题 plan 都有明确落点，而不是各自扩张。
