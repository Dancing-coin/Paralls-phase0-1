# 当前项目智能体与世界交互增量专题总实施计划

> 适用范围：`docs/superpowers/specs/current-project-intelligence-upgrade/`

**目标：** 把已闭合 mainline 之外的增量感知、多模态、局部世界协议、双通道交互、具身身体状态和非运行时工具链能力组织成可执行路线图。

**架构定位：** 本计划不重做 `world-character-siming-authority-mainline` 已闭合范围，而是把专题树里的能力拆成有依赖关系的增量任务组。

**建议执行顺序：**

1. `Perception Query Frame` 与感知结果协议
2. `Godot` 取样前端与 Providers
3. `L1` 世界事实层与空间底座
4. 角色智能体多模态链与 `Actor Scene Knowledge`
5. 司命多模态链与全局态势理解
6. `Interaction Orchestration Layer`
7. `ESM` 双通道世界作用层
8. `Embodied Skeletal State Provider`
9. 非运行时多模态工具链与生产工具链

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

- [ ] 完成 `Perception Query Frame` 与感知结果协议的实现设计与最小契约测试
- [ ] 明确 `Modality Interpretation Result`
- [ ] 明确 `Cross-Modal Understanding Result`
- [ ] 明确 `Canonical Percept Bundle`

### 任务组 B：Godot 取样前端

- [ ] 定义 `Visual Patch Provider`
- [ ] 定义 `Spatial Patch Provider`
- [ ] 定义 `Auditory Context Provider`
- [ ] 定义 `Embodied State Provider`
- [ ] 保证所有 provider 不承担重推理

### 任务组 C：世界空间底座

- [ ] 明确 `Scene 3D Space Model` 的抽取来源和对象类型
- [ ] 明确 `Runtime Spatial Occupancy Field` 的静态/动态分层
- [ ] 明确结构化事实上抛从底座导出的边界

### 任务组 D：角色侧多模态增强

- [ ] 让角色专属多模态栈接入统一感知协议
- [ ] 引入 `Actor Scene Knowledge`
- [ ] 设计主动感知回推路径

### 任务组 E：司命侧多模态增强

- [ ] 让司命专属多模态栈接入统一感知协议
- [ ] 设计司命版感知包
- [ ] 明确其与 `FairnessStateSnapshot` 的关系

### 任务组 F：交互与世界作用升级

- [ ] 定义 `Interaction Orchestration Layer`
- [ ] 定义 `ESM` 双通道世界作用层边界
- [ ] 明确语义通道和物理通道的统一结果协议

### 任务组 G：具身身体状态升级

- [ ] 定义 `Embodied Skeletal State Provider`
- [ ] 划分高层具身状态、中层骨架参数、低层骨骼快照
- [ ] 明确进入感知链与调试链的位置

### 任务组 H：非运行时工具链

- [ ] 定义 `Non-Runtime Tool Stack`
- [ ] 定义 `Non-Runtime Production Stack`
- [ ] 设计自动抽取、多模态识别、人工审核的工作流

## 一句话收束

这份总实施计划的作用，是给当前项目的增量专题规格树提供统一执行顺序和边界，让后续每一份专题 plan 都有明确落点，而不是各自扩张。
