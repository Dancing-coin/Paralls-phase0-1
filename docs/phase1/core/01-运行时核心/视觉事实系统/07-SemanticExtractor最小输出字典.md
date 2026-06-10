# 07-SemanticExtractor最小输出字典

## 1. 文档目标

本文档冻结 `sampler -> emitter` 中间层：四个 `SemanticExtractor` 的最小输出字典。

## 2. 总原则

`SemanticExtractor` 层要做到：

- 脱离具体资产细节
- 还没变成总线事件
- 但足够让 `VisualFactEmitter` 做阈值判断和事实发射

## 3. CharacterSemanticFrame

最小字段包括：

- `semantic_frame_id`
- `character_id`
- `local_ts`
- `world_ts`
- `revision_seq`
- `posture_semantics`
- `balance_semantics`
- `gesture_semantics`
- `gaze_semantics`
- `face_semantics`
- `condition_semantics`
- `observability`

## 4. ObjectSemanticFrame

最小字段包括：

- `semantic_frame_id`
- `object_id`
- `local_ts`
- `world_ts`
- `revision_seq`
- `visibility_semantics`
- `support_semantics`
- `containment_semantics`
- `interaction_semantics`
- `integrity_semantics`
- `open_close_semantics`
- `observability`

## 5. EnvironmentSemanticFrame

最小字段包括：

- `semantic_frame_id`
- `environment_id`
- `local_ts`
- `world_ts`
- `revision_seq`
- `light_semantics`
- `particle_semantics`
- `trace_semantics`
- `aperture_semantics`
- `visibility_context`
- `observability`

## 6. SpatialRelationSemanticFrame

最小字段包括：

- `semantic_frame_id`
- `local_ts`
- `world_ts`
- `revision_seq`
- `pair_relation_semantics`
- `occlusion_semantics`
- `anchor_semantics`
- `group_semantics`
- `observability`

## 7. 一句话收束

`SemanticExtractor` 层的意义，是把本地采样数据先转成“资产无关、事实前置、事件未发射”的语义状态帧，让视觉事实发射器只做阈值和发射，而不重新承担整套姿态理解工作。
