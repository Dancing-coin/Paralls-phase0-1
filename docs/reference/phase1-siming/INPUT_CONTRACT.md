# 司命输入契约

当前实现以 `SimingRuntime.tick()`（司命轮次入口）及其异步阶段协议作唯一决策路径。字段定义见 `backend/app/models/authority_event.py`、`siming_event.py`、`siming_runtime_state.py`；图与边界图见 [STATE_MODEL.md](STATE_MODEL.md)。

## 信封和订阅

`AuthorityEvent`（权威事件）要求 `event_id/event_type/producer_ts/room_id/scene_id/zone_id/source/routing/priority/durability/causation_id/correlation_id/payload`。`source` 标明生产系统，`routing` 标明受众和目标；`payload` 是类型相关对象，不是统一的世界事实结构。

| FactType（事实类型） | 事件名 | 当前消费语义 |
|---|---|---|
| WORLD_FACT | world_fact_event | 世界事实投影 |
| VISUAL_FACT | visual_fact_event | 已成立视觉事实、可见性 |
| ESM_RESULT | esm_result_event | 实体状态机结算结果 |
| CHARACTER_BEHAVIOR | character_behavior_event | 角色行为结果 |
| CONVERSATION_RESOLUTION | conversation_resolution_event | 对话候选与关系结果 |
| CONSTRAINT_STATE | constraint_state_event | 约束与恢复压力 |
| POPULATION_CADENCE | population_cadence_event | 群体节律输入 |
| 已注册 gameplay 类型 | gameplay.* | 按玩法结构声明注册 |

`SimingEventConsumer`（事件消费者）接收总线事件，转换为 `SimingInput(input_type, source_event)`；`SimingObservePipeline`（观测管线）再检查类型及 `siming` 路由或广播。注册不自动授予可见性、实体资格或决策权。启动校验防止玩法结构漏注册。

聚合载荷的 `target_actor_id/target_environment_id/target_object_id/established_fact_id` 通过 `SimingPayloadSchema`（载荷字段契约）读取。未声明的玩法载荷不猜测这些字段。视觉协议还处理可见角色与证据投影；群体输入走独立能力校验，不能假定每种输入都更新三个状态模型。

Phase 2: 从 Owner（权威归属域）的类型声明读取结构和可见性；本轮不实现 OwnerFactQuery（权威事实查询）。B0 六字段归属不变。
