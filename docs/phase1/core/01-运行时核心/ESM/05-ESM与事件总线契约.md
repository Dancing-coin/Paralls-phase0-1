# 05-ESM与事件总线契约

## 1. 文档目标

本文档冻结 `ESM` 通过事件总线收什么、发什么，以及哪些对象属于 `ESM` 的正式输出家族。

## 2. 核心定义

`ESM` 在总线中的正确身份是：

> 确定性物理事实结算者 + 结构化状态结果回写者

它不是：

- 总线解释层
- 总线调度器
- 司命附属执行脚本

## 3. `ESM` 接收的对象

`ESM` 正式接收：

1. 精确世界事件
2. `ActionRequest`
3. `environment_request`
4. 环境参数更新
5. 系统时钟

## 4. `ESM` 回写的对象

当前正式输出家族固定为：

1. `ActionResolutionResult`
2. `ObjectStateResult`
3. `EnvironmentStateResult`
4. `BodyStateResult`
5. `ConstraintStateResult`

## 5. 总线公共信封要求

`ESM` 输出必须采用公共信封 canonical：

- `event_id`
- `event_type`
- `producer_ts`
- `room_id`
- `scene_id`
- `zone_id`
- `source`
- `routing`
- `priority`
- `durability`
- `causation_id`
- `correlation_id`
- `payload`

推荐：

- `source.layer = L1`
- `source.system = esm`

## 6. `ESM` 不应回写什么

`ESM` 不应直接回写：

- 证据解释
- 角色心理真值
- 司命公平判断
- 高阶知识确认结果

## 7. replay / audit 最小要求

`ESM` 输出至少要支持：

```text
ActionRequest
-> ActionResolutionResult / ConstraintStateResult
-> ObjectStateResult / EnvironmentStateResult / BodyStateResult
```

## 8. 一句话收束

`ESM` 与事件总线的关系，不是“总线里的一个普通节点”，而是“把动作和环境请求结算成权威物理结果，并以结构化事件家族重新回写总线”的确定性事实层。
