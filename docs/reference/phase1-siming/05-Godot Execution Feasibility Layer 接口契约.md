# 05-Godot Execution Feasibility Layer 接口契约

## 1. 文档目标

本文档把 `Godot Execution Feasibility Layer` 固定成一层正式接口契约，明确它在司命运行链中的位置、输入、输出、判定维度与五条可执行路径。

## 2. 核心定义

这层不负责判断“该不该干预”，只负责判断：

- 司命已经选好的干预能不能在当前 `Godot/L1/ESM/L3` 现实里自然落地
- 应该走哪条执行路径
- 是否需要降级

一句话：它把“叙事上想做”筛成“引擎里也能自然做”。

## 3. 输入对象

### 3.1 `InterventionCandidate`

最小字段：

- `intervention_candidate_id`
- `snapshot_ref`
- `imbalance_type`
- `band`
- `strength`
- `target_actor_ids`
- `goal`
- `fallback_band`
- `priority`

### 3.2 `ExecutionContextSnapshot`

最小字段：

- `world_ts`
- `room_id`
- `scene_ids`
- `active_actor_ids`
- `active_object_ids`
- `environment_capabilities`
- `presentation_budget`
- `runtime_pressure`
- `cooldowns`

## 4. 输出对象

### `InterventionDecision`

最小字段：

- `intervention_decision_id`
- `candidate_ref`
- `decision`
- `selected_path`
- `fallback_path`
- `physical_feasibility`
- `semantic_naturalness`
- `role_autonomy_safety`
- `presentation_capacity`
- `traceability`
- `cross_system_dependency_cost`
- `dispatch_target`
- `execution_notes`

## 5. 五条可执行路径

### `character_input_path`

适用于：

- `impulse`
- 某些 `fact_reveal`
- 某些 `opportunity`

### `environment_change_path`

适用于：

- 门、灯、遮挡、烟雾、噪音等环境变化

### `visual_fact_path`

适用于：

- 让本来已成立但不够显著的可见变化变得“足以被看见”

### `l3_highlight_path`

适用于：

- 已成立高价值事实的镜头/特写/高光增强

### `no_action`

适用于：

- 当前没有自然落地方式
- 强做会显得系统味太重

## 6. 判定维度

固定 6 个维度：

1. `physical_feasibility`
2. `semantic_naturalness`
3. `role_autonomy_safety`
4. `presentation_capacity`
5. `traceability`
6. `cross_system_dependency_cost`

## 7. 必备方法

建议至少定义：

- `evaluate_candidate(candidate, context) -> InterventionDecision`
- `score_paths(candidate, context) -> Dictionary`
- `select_best_path(path_scores) -> String`
- `select_fallback_path(path_scores) -> String`
- `build_decision(candidate, path, fallback, scores) -> InterventionDecision`

## 8. 硬规则

### `impulse`

- 默认优先 `character_input_path`
- 不应优先走 `environment_change_path`

### `opportunity`

- 默认优先 `character_input_path` 或 `environment_change_path`
- 需要让别人“看见机会”时可走 `visual_fact_path`

### `fact_reveal`

- 优先 `character_input_path` 或 `visual_fact_path`
- 只有必须先改环境才能看见时才走 `environment_change_path`

### `environment_request`

- 只能优先走 `environment_change_path`

### `l3_highlight_path`

只有在：

- 事实已成立
- 不改变业务真值
- 当前预算允许
- replay 可解释

时才允许选用。

## 9. 降级规则

1. 物理不可行：优先降到 `visual_fact_path` 或 `character_input_path`
2. 表现预算不足：优先从 `l3_highlight_path` 降到 `visual_fact_path`
3. 抢角色自主性：降到更弱的 `impulse` 或 `none`
4. replay 不可解释：禁止该路径

## 10. 与 Godot 上位约束的关系

本层明确受：

- [Godot源码底层基础设施与运行时约束](/d:/Projects/Paralls/docs/phase1/core/00-总纲/Godot源码底层基础设施与运行时约束.md)

约束：

- `AnimationTree` 是主动作轨
- `SkeletonModifier3D` 是本地具身精修轨
- `MessageQueue / deferred` 是线程安全底层
- 客户端不承载认知真值

## 11. Phase 1 最小实现

必做：

- `evaluate_candidate`
- 5 路 path score
- `approve / downgrade / reject`
- `selected_path / fallback_path`
- 6 个 feasibility score
- `execution_notes`

不做：

- 历史成功率学习
- per-room 自适应权重
- 更复杂的路径搜索

## 12. 一句话收束

`Godot Execution Feasibility Layer` 不是一个技术附录，而是司命真正从“叙事上想做什么”过渡到“当前引擎里怎么做、或者干脆不要做”的关键转换层。
