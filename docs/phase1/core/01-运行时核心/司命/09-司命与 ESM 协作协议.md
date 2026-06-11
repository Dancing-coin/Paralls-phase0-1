# 09-司命与 ESM 协作协议

## 1. 文档目标

本文档冻结司命与 `ESM` 之间的正式协作边界：

- 司命能向 `ESM` 请求什么
- `ESM` 会向司命回什么
- 哪些东西属于高层叙事请求
- 哪些东西属于底层物理真值

它不重写：

- `ESM` 内部状态机
- 材料模板与物理规则
- 事件总线公共信封细节
- 角色如何感知 `ESM` 结果

它只定义**司命与 `ESM` 的平行协作协议**。

## 2. 核心定义

司命负责：

- 判断是否值得推动
- 评估局势失衡
- 选择最小叙事干预

`ESM` 负责：

- 检查物理可行性
- 执行状态机
- 结算环境 / 物体 / 身体事实
- 上报确定性结果

一句话：

> 司命决定“叙事上值不值得推动”，`ESM` 决定“物理上能不能发生、具体怎么发生”。

## 3. 协作总原则

### 3.1 高层请求原则

司命发给 `ESM` 的只能是高层环境请求，不能是已完成结果。

### 3.2 物理权威原则

最终环境 / 物体 / 身体事实是否成立，以 `ESM` 结算结果为准。

### 3.3 回流闭环原则

司命发出的环境相关请求，必须经过：

`environment_request -> ESM resolution -> world fact event`

重新回到总线。

### 3.4 叙事不越物理原则

司命可以想推动戏，但不能跳过材质、空间、状态机、冷却和资源约束去强写结果。

## 4. 司命允许给 `ESM` 的对象

`Phase 1` 正式允许的主要对象固定为：

1. `environment_request`
2. `constraint_probe`（预留）
3. `feasibility_query`（预留）

### 4.1 `environment_request`

作用：

- 请求在规则允许范围内触发环境或物体变化
- 为 `opportunity`、`fact_reveal`、`visual_fact_path` 打开自然落地点

典型例子：

- 让某扇半开的门在条件允许时进一步打开
- 让一处遮挡减少
- 让噪音、灯光、烟雾等条件在合理范围内变化

### 4.2 `constraint_probe`

预留给：

- 在不真正执行的前提下询问“当前是否存在某类物理机会”

### 4.3 `feasibility_query`

预留给：

- 编排层在高价值场景中做低成本可行性试探

`Phase 1` 可以只落 `environment_request`。

## 5. `ESM` 回给司命的对象

`ESM` 回给司命的不是“叙事解释”，而是结构化物理结果：

1. `EnvironmentStateResult`
2. `ObjectStateResult`
3. `BodyStateResult`
4. `ActionResolutionResult`
5. `ConstraintStateResult`

### 5.1 `EnvironmentStateResult`

回答：

- 环境参数是否变化
- 变化了多少
- 当前稳定态是什么

### 5.2 `ObjectStateResult`

回答：

- 物体位置、开合、破损、燃烧、潮湿、可见性等是否变化

### 5.3 `BodyStateResult`

回答：

- 角色身体事实是否进入某状态

### 5.4 `ActionResolutionResult`

回答：

- 某个请求动作是否物理成功
- 若失败，失败在何种约束

### 5.5 `ConstraintStateResult`

回答：

- 当前约束面是什么
- 为什么某个请求不可执行

## 6. 司命不能要求 `ESM` 做什么

司命不能向 `ESM` 直接要求：

1. 违背物理规则的结果
2. 违背材质模板的结果
3. 违背空间边界的结果
4. 直接生成证据解释
5. 直接写角色心理结论

典型禁令包括：

- `door_is_open_now` 作为既定真值写回
- `fire_spreads_everywhere_now`
- `object_becomes_evidence_now`
- `target_panics_now`

## 7. `ESM` 不替司命做什么

`ESM` 不能替司命做：

1. 公平失衡判断
2. 信息 / 会话 / 怀疑态评估
3. 证据侦探意义判断
4. 干预强度选择
5. 叙事窗口价值排序

`ESM` 负责“发生了什么”，不是“这件事戏不戏剧化”。

## 8. 标准执行闭环

标准闭环必须固定为：

```text
FairnessStateSnapshot
-> InterventionCandidate
-> InterventionDecision
-> environment_request
-> ESM Resolution
-> World Fact Event
-> Siming Re-evaluation
```

也就是说：

- 司命先选干预
- `ESM` 再决定是否成立
- 司命不能把“请求”伪装成“世界已发生”

## 9. 最小字段建议

### 9.1 `environment_request`

建议最小字段：

- `request_id`
- `candidate_ref`
- `decision_ref`
- `room_id`
- `scene_id`
- `target_entity_refs`
- `goal`
- `requested_change_type`
- `requested_strength`
- `ttl`
- `reason_tag`

### 9.2 `ESM` 结果对象

建议最小字段：

- `result_id`
- `request_ref`
- `resolution_status`
- `resolved_entities`
- `applied_state_changes`
- `rejected_constraints`
- `stable_state_summary`
- `producer_ts`

## 10. replay / audit 链要求

最小可回放链必须支持：

```text
InterventionDecision
-> environment_request
-> ESM Resolution
-> Observed State Change
-> FairnessState After
```

最少要回答：

1. 司命请求了什么
2. `ESM` 为什么允许或拒绝
3. 实际环境变成了什么
4. 这是否真的缓解了局势失衡

## 11. 与工作台的关系

司命工作台应能看到：

- 本次 `environment_request` 来源于哪条 `InterventionDecision`
- `ESM` 是否批准
- `ESM` 用了哪些约束拒绝或降级

`ESM` 工作台应能回跳：

- 本次物理结算是普通世界交互，还是来自司命请求

关键联跳字段：

- `request_id`
- `decision_ref`
- `candidate_ref`
- `result_id`
- `causation_id`
- `correlation_id`

## 12. `Phase 1` 最小实现要求

必做：

1. 司命通过 `environment_request` 请求环境变化
2. `ESM` 返回结构化 resolution 结果
3. 请求与结果必须重新回流总线
4. 司命不得直接写物理结果
5. replay / audit 链必须能串起来

后补：

- 更细的可行性预判对象
- 批量组合环境请求
- 更复杂的多实体联动请求

## 13. 一句话收束

司命与 `ESM` 的正确关系，不是“司命让世界照剧本演”，而是“司命提出值得推动的高层环境请求，`ESM` 在物理规则允许范围内决定是否以及如何把它真正变成世界事实”。
