# 12-Embodiment Binder v0.1 规范

## 1. 定义

`Embodiment Binder` 是角色智能体与角色资产之间的强边界层：上接 `FACS/SACS` 语义表达，下接 canonical rig 与运行时约束系统，负责把“角色想怎么被看见”稳定编译成“身体实际上如何动”。

## 2. 核心职责

1. `Semantic Compilation`
2. `Layer Resolution`
3. `Conflict Resolution`
4. `Constraint Injection`
5. `Temporal Shaping`
6. `Asset Agnostic Mapping`
7. `Runtime Safety`

## 3. 输入合同

输入包括：

- `Expression Plan`
- `FACS Activation Set`
- `SACS Activation Set`
- `Contextual Constraints`

## 4. 输出合同

输出包括：

- `Canonical Face Channels`
- `Canonical Body Channels`
- `Constraint Targets`
- `Timing Envelope`
- `Mixer Directives`

## 5. Canonical Schema 要求

Binder 只允许输出到：

- `canonical face schema`
- `canonical body schema`

不允许直接写具体资产骨骼名或 blendshape 名。

## 6. 分层执行模型

内部至少按：

1. Face Layer
2. Head/Neck Layer
3. Torso Layer
4. Arm/Hand Layer
5. Balance Layer
6. Locomotion Style Layer
7. Constraint Pass
8. Safety Clamp

顺序处理。

## 7. 冲突消解规则

只允许四类：

- `exclusive`
- `dominance`
- `suppression`
- `gated`

## 8. 约束注入

Binder 不直接做 IK 解算，但必须声明：

- look-at target
- hand target
- prop preservation
- foot stabilization
- injury-driven suppression

## 9. 与资产的边界

Binder 不知道角色具体骨骼名，也不负责资产特定的重映射。那属于 `Asset Adapter` 层。

## 10. Phase 1 范围

Phase 1 冻结：

- `FACS + SACS` 联动
- canonical schema 最小集
- 六层 body/face 组合
- 基础冲突规则
- 基础持物/伤病/注视约束
- Godot 最小接口合同

## 11. 一句话收束

`Embodiment Binder` 是语义表达层到统一具身控制层的编译器，不是动画选择器，不是骨骼播放器，也不是角色高层决策者。
