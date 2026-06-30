# 当前项目 Godot 取样前端与 Provider 设计

- 日期：`2026-06-29`
- 状态：`implemented-and-verified`
- 上位规格：[2026-06-29-current-project-intelligence-upgrade-master-design.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/specs/current-project-intelligence-upgrade/2026-06-29-current-project-intelligence-upgrade-master-design.md)

## 1. 目标

把 `Godot` 从“事实上抛器宿主”进一步升级为“主体视角取样前端”。

## 2. 设计原则

- `Godot` 负责取样，不负责重理解
- 不做重体素化
- 不做大模型推理
- 不做重扫描
- 尽量按需、局部、节流

## 3. Provider 列表

### A. `Visual Patch Provider`

输出：

- 主体当前视野截图
- 目标局部截图
- 多角度局部截图
- camera pose 元数据

### B. `Spatial Patch Provider`

输出：

- occupancy patch
- voxel patch
- BEV patch
- 局部障碍/通路/遮挡引用

### C. `Auditory Context Provider`

输出：

- 听觉时间窗
- 声源引用
- 听觉可达性
- 背景噪声等级

### D. `Embodied State Provider`

输出：

- 身体位姿
- locomotion state
- grounded
- LOS 失败
- reachability 失败
- 接触状态

## 4. 与 `Perception Query Frame` 的关系

这四类 Provider 不直接给角色智能体，而是先被收束进：

- `Perception Query Frame`

## 5. 一句话收束

这份规格的目标，是把当前项目中的 `Godot` 明确定位成多模态链的取样前端，而不是重推理宿主。
