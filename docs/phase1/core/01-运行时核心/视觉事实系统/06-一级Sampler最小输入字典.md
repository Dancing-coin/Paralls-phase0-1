# 06-一级Sampler最小输入字典

## 1. 文档目标

本文档冻结四个一级视觉源域本地采样器的最小输入字典，目标是“足够支撑语义抽取”，而不是“全量复制执行层状态”。

## 2. CharacterSampler

对象名：`CharacterStateSampleFrame`

最小字段：

- `sample_id`
- `character_id`
- `local_ts`
- `world_ts`
- `root_transform`
- `body_pose_summary`
- `head_face_summary`
- `facs_state`
- `sacs_state`
- `body_condition_summary`
- `interaction_state`
- `revision_seq`

## 3. ObjectSampler

对象名：`ObjectStateSampleFrame`

最小字段：

- `sample_id`
- `object_id`
- `local_ts`
- `world_ts`
- `object_class`
- `owner_actor_id`
- `transform`
- `visibility_state`
- `support_relation`
- `state_flags`
- `proximity_relation`
- `revision_seq`

## 4. EnvironmentSampler

对象名：`EnvironmentStateSampleFrame`

最小字段：

- `sample_id`
- `environment_id`
- `local_ts`
- `world_ts`
- `light_state`
- `particle_state`
- `surface_trace_state`
- `door_window_state`
- `global_visibility_modifiers`
- `revision_seq`

## 5. SpatialRelationSampler

对象名：`SpatialRelationSampleFrame`

最小字段：

- `sample_id`
- `local_ts`
- `world_ts`
- `actor_pairs`
- `occlusion_relations`
- `anchor_relations`
- `group_relations`
- `revision_seq`

## 6. 一句话收束

四个一级 Sampler 的职责是提供“足够抽语义事实的最小状态”，而不是把执行层所有底层数据全量搬出来。
