# 司命输出契约

`SimingOutput`（司命输出）由 `SimingEventProducer`（事件生产器）转换为 `AuthorityEvent`（权威事件）。字段定义以 `backend/app/models/siming_event.py` 为准：`output_type/room_id/scene_id/zone_id/causation_id/correlation_id/producer_ts/selected_path/intervention_band/payload`。完整边界与顺序见 [状态模型图表](STATE_MODEL.md)。

| 输出或路径 | AuthorityEvent.event_type | 订阅/处理边界 |
|---|---|---|
| fairness_snapshot | siming.fairness_snapshot | 公平快照记录 |
| intervention_candidate | siming.intervention_candidate | 候选记录 |
| intervention_decision | siming.intervention_decision | 决策记录 |
| staging_request | siming.staging_request | 资源暂存协议 |
| audit_record / no_action | siming.audit_recorded / siming.no_action_recorded | 审计，无下游执行 |
| visual_fact_path | siming.visual_observability_request | 已成立事实的可见性请求 |
| l3_highlight_path | siming.presentation_highlight_request | 表现请求 |
| environment_change_path | siming.environment_request | 主组合订阅，转交 ESM（实体状态机）校验结算 |
| character_input_path | siming.impulse / siming.opportunity / siming.fact_reveal | 角色投递适配器，角色保留自治 |

`character_input_path` 要求非空合格 `target_actor_id`；环境和物品目标独立检查资格。视觉请求要求 `established_fact_id`。无合格名册不得回退到演示角色；`physical_success`（物理成功）字段和 `siming.dispatch_requested` 事件族被生产器拒绝。

输出只表达高层催化或请求，不能直接修改世界真相。表现动画归 Godot（游戏引擎），角色认知归角色运行时，环境结算归 ESM。下游结果通过权威事件反馈；不得用本地成功回执代替结算。

Phase 2: Owner 查询和完整版本向量对账不会由输出协议绕过。
