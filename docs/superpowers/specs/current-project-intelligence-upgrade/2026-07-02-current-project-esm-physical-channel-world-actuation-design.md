# 当前项目 ESM Physical Channel World Actuation 子规格

- 日期：`2026-07-02`
- 状态：`implemented-and-runtime-verified`
- 上位规格：[2026-06-29-current-project-esm-dual-channel-world-actuation-design.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/specs/current-project-intelligence-upgrade/2026-06-29-current-project-esm-dual-channel-world-actuation-design.md)

## 1. 目标

在保留 ESM semantic authority settlement 的基础上，补齐 physical interaction channel 的世界作用设计。

## 2. 定位

Physical channel 是世界作用通道，不是 ESM 新主脑。

它负责：

- 连续接触
- push / pull
- carry / grab
- blocking
- body-object contact
- physical effect observation

它必须回流统一 result family：

- `world_result`
- `object_state_result`
- `environment_state_result`
- `body_state_result`
- `constraint_state_result`

## 3. Authority 边界

Physical channel 可以报告和执行被批准的物理效果，但不能绕过 authority。

规则：

- semantic channel 仍负责规则/意图/约束结算
- physical channel 负责连续物理效果和局部接触结果
- mixed channel 由 interaction orchestration 合并
- 最终 world truth 只通过统一 result 协议回流

## 4. Godot 边界

Godot 可以执行局部物理表现和接触采样。

Godot 不应：

- 自行决定语义成功
- 绕过 backend 结算写剧情状态
- 把 raw physics stream 全量发送到业务层

## 5. Verification 要求

必须证明：

- semantic-only 行为不退化
- physical effect 有 structured result
- mixed result 只有一套统一输出
- constraint failure 能阻止 physical application
- object/environment/body state 可被 L1/ESM 回流观察

## 6. 一句话收束

ESM physical channel world actuation 是对连续物理作用的受控补充：它让推拉、携带、阻挡和接触有结构化结果，但仍服从 semantic authority 和统一 world result 协议。
