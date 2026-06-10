# 12-M1-M2 Godot端类接口契约

## 状态

- 状态：实现前接口契约文档
- 作用：为 `M1-M2` 阶段最关键的 Godot 本地类，冻结职责、输入、输出、生命周期与禁止越权范围
- 上游约束：
  - [Godot源码底层基础设施与运行时约束](/d:/Projects/Paralls/docs/phase1/core/00-总纲/Godot源码底层基础设施与运行时约束.md)
  - [03-视觉事实系统总纲.md](/d:/Projects/Paralls/docs/phase1/core/01-运行时核心/视觉事实系统/03-视觉事实系统总纲.md)
  - [10-M1-M2最小开发任务清单.md](/d:/Projects/Paralls/docs/phase1/core/01-运行时核心/视觉事实系统/10-M1-M2最小开发任务清单.md)
- 非职责：本文件不提供完整代码实现，只定义实现边界

## 1. 文档目标

本文档用于保证后续无论由谁实现 `M1-M2` 的 Godot 端类，都不会把：

- 角色认知
- 本地表现
- 采样
- 语义抽取
- 视觉事实上抛

写混。

## 2. 适用范围

本文件只覆盖 `M1-M2` 最小闭环需要的 12 个 Godot 端类：

1. `CharacterReplicaRoot`
2. `CharacterReplicaState`
3. `GazeCommand`
4. `GazeRuntimeState`
5. `GazeController`
6. `GazeModifier3D`
7. `AnimationRuntimeBridge`
8. `ExpressionPacketApplier`
9. `CharacterSampler`
10. `CharacterSemanticExtractor`
11. `CharacterVisualFactEmitter`
12. `ObjectSampler`
13. `ObjectSemanticExtractor`
14. `ObjectVisualFactEmitter`
15. `EnvironmentSampler`
16. `EnvironmentSemanticExtractor`
17. `EnvironmentVisualFactEmitter`
18. `ReplayTraceBuffer`
19. `VisualFactDebugPanel`

注：对象总数多于 12，是因为前文的“4 个关键类”已扩展为完整 `M1-M2` 最小闭环所需集合。后续若继续扩展 `SpatialRelation*` 链，请单独增补文档，而不是回改本稿范围。

## 3. 公共原则

所有 `M1-M2` Godot 本地类统一遵守：

1. 不直接持有后端业务真值
2. 不直接修改角色认知与知识状态
3. 不把原始骨骼流直接广播到后端业务总线
4. 只通过 `LocalPresentationBus` 做本地表现链路同步
5. 只通过结构化 `VisualFactEvent` 上抛视觉事实
6. 一切 revision-sensitive 行为都必须受 `revision_seq` 保护

## 4. 类接口契约

### 4.1 `CharacterReplicaRoot`

职责：

- 单个角色副本的总接线节点
- 接收后端 `ExecutionPacket`
- 持有关键子节点引用
- 驱动本地采样链
- 向 `ReplicaRegistry` 注册/注销自己

输入：

- `character_id`
- `scene_id`
- `zone_id`
- `ExecutionPacket`
- `world_ts`

输出：

- 本地子模块更新
- `CharacterStateSampleFrame`
- `CharacterSemanticFrame`
- `VisualFactEvent`

生命周期：

1. `_ready()` 注册副本
2. `apply_execution_packet()` 接收执行包
3. `tick_local_sampling()` 驱动采样
4. `_exit_tree()` 注销副本

禁止：

- 不做角色认知判断
- 不做事件总线业务真值更新
- 不直接做 gaze 语义分类
- 不直接发 `PerceptibleCandidateEvent`

### 4.2 `CharacterReplicaState`

职责：

- 保存角色副本当前表现态
- 只做客户端表现态容器，不做业务真值容器

输入：

- `ExecutionPacket`
- `GazeRuntimeState`
- 本地表现状态切换

输出：

- 给 `CharacterSampler`、`AnimationRuntimeBridge`、`GazeController` 提供当前表现态引用

最小字段：

- `locomotion_state`
- `active_expression_packet_id`
- `active_gaze_target_actor_id`
- `autonomy_mode`
- `last_visual_fact_event_id`

禁止：

- 不保存知识态
- 不保存角色信念
- 不保存司命结果真值

### 4.3 `GazeCommand`

职责：

- 承载后端下发的 gaze 指令对象

字段：

- `target_actor_id`
- `mode`
- `weight`
- `duration_ms`
- `revision_seq`

禁止：

- 不带具体骨骼参数
- 不带世界真值解释
- 不带心理结论

### 4.4 `GazeRuntimeState`

职责：

- Godot 本地 gaze 执行态容器

字段：

- `target_actor_id`
- `target_node`
- `mode`
- `weight`
- `current_head_weight`
- `current_eye_weight`
- `hold_started_msec`
- `expires_at_msec`
- `revision_seq`

禁止：

- 不判断这是不是 `fixed_gaze_on_target`
- 不保存角色长期状态

### 4.5 `GazeController`

职责：

- 接收 `GazeCommand`
- 查目标副本节点
- 更新 `GazeRuntimeState`
- 推送给 `GazeModifier3D`
- 维护过期与 revision

输入：

- `GazeCommand`
- `ReplicaRegistry`
- 当前时间

输出：

- `GazeRuntimeState`
- 对 `GazeModifier3D` 的更新调用

必备方法：

- `setup(replica_root, gaze_modifier, replica_state)`
- `apply_command(cmd)`
- `update_runtime(now_msec)`
- `clear_state()`
- `get_state()`

禁止：

- 不直接改 `Skeleton3D`
- 不做视觉事实发射
- 不做 gaze 语义解释

### 4.6 `GazeModifier3D`

职责：

- 在动画树结果之后，对 `head / neck / 可选 eye bones` 做 gaze 精修
- 保证 look-at 自然、限幅、可平滑过渡

输入：

- `GazeRuntimeState`
- `Skeleton3D`
- 当前动画姿态

输出：

- 修正后的本地骨骼姿态

必备方法：

- `set_gaze_state(state)`
- `_process_modification(delta)`

禁止：

- 不做目标选择
- 不做角色级 gaze 推理
- 不自己生成 `VisualFactEvent`

### 4.7 `AnimationRuntimeBridge`

职责：

- 把表现层状态映射给 `AnimationTree`
- 控制主动作轨参数切换

输入：

- `ExecutionPacket`
- `CharacterReplicaState`

输出：

- `AnimationTree` 参数更新
- 主状态切换

禁止：

- 不做精修轨
- 不直接处理骨骼级 gaze
- 不做角色语义分类

### 4.8 `ExpressionPacketApplier`

职责：

- 客户端执行包总接线器
- 把后端表达/执行对象分发给各本地子模块

输入：

- `ExecutionPacket`

输出：

- 给：
  - `AnimationRuntimeBridge`
  - `GazeController`
  - `FaceRuntimeController`（后续）

禁止：

- 不改写 `ExecutionPacket`
- 不自己产生新意图
- 不自己做采样

### 4.9 `CharacterSampler`

职责：

- 采角色副本当前表现态
- `M2` 先只做 gaze 最小链

输入：

- `CharacterReplicaRoot`
- `Skeleton3D`
- `AnimationTree`
- `GazeRuntimeState`
- `CharacterReplicaState`

输出：

- `CharacterStateSampleFrame`

`M2` 最小输出字段：

- `character_id`
- `local_ts`
- `world_ts`
- `root_transform.forward`
- `head_forward`
- `eye_target_actor_id`
- `locomotion_state`
- `revision_seq`

禁止：

- 不直接输出视觉事实
- 不做心理推断
- 不做 object / environment 采样

### 4.10 `CharacterSemanticExtractor`

职责：

- 从 `CharacterStateSampleFrame` 提取角色视觉语义
- `M2` 先只支持 gaze 相关

输入：

- 当前 sample
- 短时间窗口 sample 历史

输出：

- `CharacterSemanticFrame`

`M2` 最小语义输出：

- `fixed_gaze`
- `checking_gaze`
- `gaze_stability`
- `observability`

禁止：

- 不发事件
- 不做角色认知结论
- 不做 posture / face / condition 全量语义

### 4.11 `CharacterVisualFactEmitter`

职责：

- 从 `CharacterSemanticFrame` 发角色视觉事实
- `M2` 先只发 `fixed_gaze_on_target`

输入：

- `CharacterSemanticFrame`
- 上一帧 / 上一 semantic frame（可选）

输出：

- `VisualFactEvent`

必备方法：

- `setup(...)`
- `process_character_semantic(curr_semantic)`

禁止：

- 不做 `PerceptibleCandidateEvent`
- 不做角色私有过滤
- 不做证据投影

### 4.12 `ObjectSampler`

职责：

- 采物体状态
- 为 `M1` 提供 object 视觉事实原料

输入：

- `object_id`
- `object_node`
- `world_ts`

输出：

- `ObjectStateSampleFrame`

最小字段：

- `object_id`
- `transform`
- `visibility_state`
- `support_relation`
- `state_flags`
- `proximity_relation`
- `revision_seq`

禁止：

- 不做事实判断
- 不做角色相关解释

### 4.13 `ObjectSemanticExtractor`

职责：

- 从 `ObjectStateSampleFrame` 提取物体语义

输入：

- 当前 object sample
- 上一 object sample

输出：

- `ObjectSemanticFrame`

`M1` 最小语义：

- `removed_from_surface`
- `opened_partial`

禁止：

- 不发事件
- 不做证据投影

### 4.14 `ObjectVisualFactEmitter`

职责：

- 从 `ObjectSemanticFrame` 发：
  - `object_removed_from_surface`
  - `door_opened_partial`

输入：

- `ObjectSemanticFrame`

输出：

- `VisualFactEvent`

禁止：

- 不做 object bias 判断
- 不做后端总线发送
- 不做 candidate 编译

### 4.15 `EnvironmentSampler`

职责：

- 采场景级环境状态

输入：

- `environment_id`
- `scene_root`
- `world_ts`

输出：

- `EnvironmentStateSampleFrame`

`M1` 最小字段：

- `light_state`
- `particle_state`
- `surface_trace_state`
- `door_window_state`
- `global_visibility_modifiers`

禁止：

- 不做环境语义分类
- 不直接发视觉事实

### 4.16 `EnvironmentSemanticExtractor`

职责：

- 从环境 sample 提取环境语义

输入：

- 当前 env sample
- 上一 env sample

输出：

- `EnvironmentSemanticFrame`

`M1` 最小语义：

- `light_drop`

后续扩展：

- `smoke_visible`
- `bloodstain_visible`

禁止：

- 不做证据意义解释
- 不做角色级感知过滤

### 4.17 `EnvironmentVisualFactEmitter`

职责：

- 发环境类视觉事实

输入：

- `EnvironmentSemanticFrame`

输出：

- `VisualFactEvent`

`M1-M1.5` 先支持：

- `light_level_drop`

后续支持：

- `smoke_visible`
- `bloodstain_visible`

### 4.18 `ReplayTraceBuffer`

职责：

- 本地缓存最近 N 条：
  - sample
  - semantic
  - fact

输入：

- `LocalPresentationBus` 事件

输出：

- debug 读取
- 工作台临时查看

禁止：

- 不当成正式 replay 库
- 不替代后端审计系统

### 4.19 `VisualFactDebugPanel`

职责：

- 显示最小调试链：
  - sample
  - semantic
  - fact

输入：

- `ReplayTraceBuffer`

输出：

- 本地 UI debug 面板

禁止：

- 不做业务判断
- 不替代正式工作台

## 5. 最小实现原则

`M1-M2` 阶段统一遵守：

1. 允许先 stub
2. 允许先返回保守值
3. 但不允许职责错位
4. 不允许客户端越权持有业务真值
5. 不允许把采样、语义抽取和事实发射混成一个 Godot 脚本

## 6. 一句话收束

这份接口契约的价值，不是帮你把代码直接写完，而是确保后续无论由谁实现 `M1-M2` 的 Godot 端类，都不会把角色认知、本地表现、采样、语义抽取和视觉事实上抛写混。\n*** End Patch
