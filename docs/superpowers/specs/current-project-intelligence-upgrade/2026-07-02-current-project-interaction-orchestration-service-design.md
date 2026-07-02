# 当前项目 Interaction Orchestration Service 子规格

- 日期：`2026-07-02`
- 状态：`planned`
- 上位规格：[2026-06-29-current-project-interaction-orchestration-layer-design.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/specs/current-project-intelligence-upgrade/2026-06-29-current-project-interaction-orchestration-layer-design.md)

## 1. 目标

把当前 `orchestrate_interaction(...)` contract/helper 扩展为 backend service、route 和策略执行层。

## 2. 定位

`InteractionOrchestrationService` 是交互意图到世界作用通道的编排服务。

它不是：

- 角色主脑
- 司命主脑
- ESM 替代品
- 物理引擎

它负责：

- 接收 structured interaction intent
- 选择 semantic / physical / mixed channel
- 生成 channel execution plan
- 调用 ESM semantic settlement 或 physical channel adapter
- 合并统一 result
- 记录 trace

## 3. 输入输出

输入：

- `InteractionIntentFrame`
- actor state refs
- target refs
- local percept refs
- world constraint refs
- requested gameplay mode

输出：

- `InteractionOrchestrationPlan`
- channel requests
- merged world result family
- failure/degrade reason
- trace refs

## 4. 策略层

策略至少覆盖：

- semantic only
- physical only
- semantic goal + physical effect merge
- denied by constraint
- requires active perception
- requires authority confirmation

## 5. Runtime Route

需要 runtime route 或 service entry：

- receives structured intent
- validates actor/target refs
- invokes orchestration policy
- invokes channel services
- returns unified result

不得从 raw keyboard/mouse/camera 噪声直接进入业务层。

## 6. Verification 要求

必须证明：

- semantic-only 仍走现有 ESM
- push/pull/carry 类意图走 mixed 或 physical path
- channel merge 不产生两套 world result
- constraint failure 可结构化返回
- orchestration 不替角色做最终心智选择

## 7. 一句话收束

`InteractionOrchestrationService` 是结构化意图进入 semantic/physical 世界作用通道的 runtime 编排层，而不是新主脑或新 authority。
