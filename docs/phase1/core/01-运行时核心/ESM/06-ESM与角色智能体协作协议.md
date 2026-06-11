# 06-ESM与角色智能体协作协议

## 1. 文档目标

本文档冻结 `ESM` 输出如何进入角色智能体，以及哪些路径必须区分“自身身体事实”和“外部世界事实”。

## 2. 核心定义

`ESM` 提供：

- 身体和环境事实

角色智能体负责：

- 对这些事实做主观解释
- 决定接下来如何反应

## 3. 两条正式承接路径

### 3.1 自身身体承接路径

以下结果允许优先走：

- `BodyStateResult`
  -> `SelfBodyPerceivedEvent`

适用：

- 疼痛
- 缺氧
- 失衡
- 乏力

### 3.2 外部世界承接路径

以下结果必须走：

- `ObjectStateResult`
- `EnvironmentStateResult`
- `ActionResolutionResult`

路径：

`ESM Result -> Event Bus -> Per-Character Filter -> CharacterPerceivedEvent`

## 4. 边界禁令

- `ESM` 不能直接写角色心理
- 角色不能改写 `ESM` 物理事实
- 角色不能把未结算请求伪装成成功

## 5. 最小对齐对象

建议角色侧统一对齐：

- `BodyStateResult`
- `ActionResolutionResult`
- `EnvironmentStateResult`
- `ConstraintStateResult`

## 6. 一句话收束

`ESM` 和角色智能体之间最关键的不是“有没有交互”，而是必须把“自身身体事实直通承接”和“外部世界事实走完整感知链”这两条路分开写死。
