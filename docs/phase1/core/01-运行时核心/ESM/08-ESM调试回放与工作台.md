# 08-ESM调试回放与工作台

## 1. 文档目标

本文档冻结工程师、策划、QA 如何实际观察、解释、定位和回放 `ESM` 的运行过程。

## 2. 核心定位

`ESM` 工作台不是日志页，而是“世界物理事实链与约束链的可视化解释台”。

它必须能回答：

- 这次动作请求有没有真正进入 `ESM`
- 为什么成功 / 为什么失败
- 状态机从哪个状态转到了哪个状态
- 哪个环境场值改变了
- 这些变化后来被谁承接了

## 3. 用户角色

至少服务：

- 工程师
- 策划 / 系统设计师
- QA / 验收人员

## 4. 六个主面板

1. 世界概览面板
2. 动作请求与结算面板
3. 状态机转移面板
4. 区域环境场面板
5. 结果事实上抛面板
6. 回放与对比面板

## 5. 三种视图模式

- `Engineering View`
- `System Design View`
- `Replay View`

### 5.1 `Engineering View`

重点看：

- `ActionRequest`
- `ActionResolutionResult`
- `ConstraintStateResult`
- `ObjectStateResult / EnvironmentStateResult / BodyStateResult`

### 5.2 `System Design View`

重点看：

- 状态机是不是太死
- 约束是不是太严
- 某类材料模板是不是太强 / 太弱
- 区域环境场是不是不自然

### 5.3 `Replay View`

重点看：

- 某次世界变化的完整前后链
- 它有没有正确回流给司命、角色和总线

## 6. 必须能追踪的链路

`ESM` 工作台最小必须能追踪：

```text
ActionRequest
-> Constraint Check
-> ActionResolutionResult / ConstraintStateResult
-> StateMachine Transition
-> World Field Delta
-> ObjectStateResult / EnvironmentStateResult / BodyStateResult
-> Event Bus Dispatch
-> Downstream Consumption
```

## 7. 各面板最小字段

### 7.1 世界概览面板

最少展示：

- `room_id`
- `scene_id`
- `zone_id`
- 当前活跃实体数
- 当前活跃环境场值
- 最近约束失败次数

### 7.2 动作请求与结算面板

最少展示：

- `request_id`
- `request_type`
- `source`
- `target_entity_refs`
- `resolution_status`
- `constraint_type`
- `constraint_code`

### 7.3 状态机转移面板

最少展示：

- `entity_id`
- `machine_id`
- `from_state`
- `to_state`
- `trigger_type`
- `transition_reason`

### 7.4 区域环境场面板

最少展示：

- `temperature`
- `humidity`
- `smoke_density`
- `noise_level`
- `light_level`
- `visibility_level`

### 7.5 结果事实上抛面板

最少展示：

- `ActionResolutionResult`
- `ObjectStateResult`
- `EnvironmentStateResult`
- `BodyStateResult`
- `ConstraintStateResult`

### 7.6 回放与对比面板

最少展示：

- `before / after`
- 同一实体多次状态变化对比
- 同一区域多次场值变化对比

## 8. 高亮规则

工作台至少高亮：

1. `impossible_request`
2. `unexpected_rejection`
3. `unstable_state_loop`
4. `field_spike`
5. `dispatch_without_resolution`
6. `resolution_without_downstream_effect`

## 9. 联跳能力

`ESM` 工作台必须支持跳到：

- 事件总线回放
- 司命工作台
- 角色工作台

最小联跳字段：

- `request_id`
- `result_id`
- `event_id`
- `causation_id`
- `correlation_id`
- `entity_id`
- `zone_id`

## 10. `Phase 1` 最小实现要求

必做：

1. 动作请求与结算
2. 约束失败解释
3. 状态机前后状态
4. 环境场值变化
5. 单次回放
6. 人类可读结果摘要

后补：

- 多实体链式变化对比
- 多房间环境健康视图
- 更复杂传播热力图

## 11. 一句话收束

`ESM` 工作台不是把物理日志摊出来，而是把“这次请求为什么成立 / 为什么失败、状态机怎么变、环境场值怎么变、这些结果后来有没有被系统正确承接”这一整条世界事实链翻译成工程、策划和 QA 都能共同使用的解释界面。
