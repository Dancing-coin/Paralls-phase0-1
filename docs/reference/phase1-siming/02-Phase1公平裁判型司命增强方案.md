# 02-Phase1公平裁判型司命增强方案

## 1. 文档目标

本文档在现有 [司命设计文档.md](/d:/Projects/Paralls/docs/phase1/core/01-运行时核心/司命设计文档.md) 基础上，补齐《开本》在角色智能体、事件总线、Godot 本地执行、视觉事实系统都已复杂化之后，`Phase 1` 单局司命仍缺失的运行时骨架。

本稿不推翻现有司命设计，而是：

- 保留现有 `Phase 1` 单局导演定位
- 强化工程可执行性
- 为未来从 **A：公平裁判型** 升级到 **B：公平导演型** 预留路径

## 2. 当前不足

现有司命设计已经具备：

- 事实核心
- 天平系统
- 冲突与案件生成器
- 高阶知识图谱
- 干预执行器
- 分级治理与子智能体方向

但在角色智能体和事件总线都被压实后，还缺：

1. 显式运行时状态对象
2. 从“公平失衡”到“最小干预”的映射层
3. `Godot` 可执行性层
4. 检查点 / 审计链 / 只读叙事表面

## 3. 设计目标

`Phase 1` 司命先不追求“最会写戏”，而先追求：

1. 信息博弈公平
2. 角色参与窗口公平
3. 会话接入公平
4. 证据可见性不过度垄断
5. 所有干预都能 replay / audit / 工作台解释

一句话：

> `Phase 1` 的司命先做成“公平裁判型运行时导演”。

## 4. 六层结构

```text
输入层
  -> 事实核心
  -> 公平状态模型
  -> 干预策略引擎
  -> Godot 可执行性层
  -> 干预执行器
  -> 检查点 / 审计层
  -> 只读叙事表面
```

### 4.1 输入层

输入包括：

- 原始/结构化世界事件
- `ESM` 状态变化
- 角色关键行为回写
- 会话与知识状态变化
- 视觉事实事件
- 证据链关键事件
- 房间阶段 / 世界时钟

### 4.2 事实核心

继续负责：

- `T0-T3` 锁定
- 时间线一致性
- 证据一致性检查
- 越界输出拦截

### 4.3 公平状态模型

这里不再停留在泛化“天平”概念，而是显式维护：

1. `information_distribution`
2. `participation_distribution`
3. `conversation_access_fairness`
4. `suspicion_heat_distribution`
5. `evidence_visibility_distribution`

输出对象：

- `FairnessStateSnapshot`

### 4.4 干预策略引擎

把失衡类型映射成固定干预带：

- `none`
- `impulse`
- `opportunity`
- `fact_reveal`
- `environment_request`

并遵守“最小干预”原则。

### 4.5 `Godot` 可执行性层

负责判断：

- 物理上能否成立
- 在 `Godot/L1/ESM/L3` 中能否自然表现
- 应走哪条执行路径
- 当前表现预算是否允许
- 是否要降级

这是当前最需要补上的一层。

### 4.6 干预执行器

对外只发高层对象：

- `impulse`
- `opportunity`
- `fact_reveal`
- `environment_request`

不直接控角，不直接写物理结果。

### 4.7 检查点 / 审计层

记录：

- 干预前公平快照
- 干预候选
- 干预决策
- 干预后公平快照
- 预期效果
- 实际效果

### 4.8 只读叙事表面

给：

- 工作台
- 大玩家控制台
- QA / 运营 / 复盘

展示：

- 当前失衡
- 热点角色
- 热点会话
- 热点证据
- 最近干预
- 当前 summary

## 5. 如何从 A 升级到 B

当前采用：

### A：公平裁判型
- 先修公平
- 再做最小催化
- 不主动追求戏剧最大化

未来升级为：

### B：公平导演型

在当前 6 层之上新增：

1. `Narrative Arc Model`
2. `Event Chain Composer`
3. `Dramatic Priority Model`

也就是说：

- A 不被推翻
- B 是在 A 之上的叠加升级

## 6. 与 PlotPilot 的关系

借的不是“写小说流程”，而是：

1. `stateful narrative model`
2. `checkpoint`
3. `guardrail`
4. `read facade`
5. `orchestrator / daemon`
6. `quality monitor` 思路

对应到司命：

- `Fact Core` + `High-Order Knowledge Graph`
- `FairnessStateSnapshot`
- `Checkpoint / Audit`
- `NarrativeReadModel`
- `Siming Orchestrator`

## 7. 与 Godot 上位约束的关系

这份增强方案明确受：

- [Godot源码底层基础设施与运行时约束.md](/d:/Projects/Paralls/docs/phase1/core/00-总纲/Godot源码底层基础设施与运行时约束.md)

约束。

关键原则：

1. `Godot` 客户端不是认知宿主
2. 司命不能假设任何干预都能立即在引擎里自然落地
3. 必须区分：
   - 后端权威总线
   - Godot 本地表现总线
4. 干预最终必须经 `Execution Feasibility Layer` 选路与降级

## 8. Phase 1 最小优先级

建议先实现：

1. `FairnessStateSnapshot`
2. `InterventionCandidate`
3. `InterventionDecision`
4. `InterventionAuditRecord`
5. `NarrativeReadModel`

## 9. 一句话收束

`Phase 1` 的司命增强，不是把它变成更会写戏的作者，而是把它变成一个真正有运行时状态、能判断公平失衡、能选择最小干预、能确认 Godot 可执行、还能被 replay 和工作台解释的裁判型导演。
