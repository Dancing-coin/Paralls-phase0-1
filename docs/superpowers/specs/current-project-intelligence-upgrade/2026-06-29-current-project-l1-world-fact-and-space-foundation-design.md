# 当前项目 `L1` 世界事实层与空间底座设计

- 日期：`2026-06-29`
- 状态：`awaiting-user-review`
- 上位规格：[2026-06-29-current-project-intelligence-upgrade-master-design.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/specs/current-project-intelligence-upgrade/2026-06-29-current-project-intelligence-upgrade-master-design.md)

## 1. 目标

把当前项目的 `L1` 从“事实上抛器集合”升级为“世界事实层”。

这里不新造一个世界，而是把当前 `Godot` 场景中已经存在的：

- 几何
- 角色
- 物体
- 碰撞体
- 导航
- 区域
- 环境节点

收成 `L1` 内部统一可计算的空间语义底座，再由 `L1` 稳定导出结构化事实上抛。

## 2. 组成

`L1` 由四块组成：

1. `Scene 3D Space Model`
2. `Runtime Spatial Occupancy Field`
3. `Environment Field Model`
4. `Fact Projection Layer`

## 3. `Scene 3D Space Model`

这是静态空间真相底稿。

它应描述：

- `zone`
- `portal`
- `static_obstacle`
- `occluder`
- `environment_anchor`
- `interaction_object`
- `navigation_lane`

生成方式：

- 建模命名语义提取
- 节点树结构提取
- 碰撞体与导航区扫描
- 多模态自动补语义
- 人工仅审核

不允许人工逐模型逐字段补表。

## 4. `Runtime Spatial Occupancy Field`

这是动态空间真相层。

它应维护：

- 占据
- 可通行状态
- 遮挡变化
- 临时阻挡
- 环境场变化

采用混合生成策略：

- 静态基底离线生成
- 动态部分运行时增量更新

## 5. `Environment Field Model`

统一维护：

- `light_level`
- `noise_level`
- `thermal_level`
- `smoke_density`
- `visibility_level`

这些字段同时服务于：

- 角色智能体
- 司命
- 感知融合
- 场景知识更新

## 6. `Fact Projection Layer`

`L1` 继续向外输出结构化事实上抛，但事实来源改为依赖统一底座，而不是零散局部脚本判断。

事实族包括：

- `raw_fact_event`
- `visual_fact`
- `auditory_fact`
- `spatial_access_fact`
- `world_result`
- `state_machine_transition`

未来要补齐的关键事实族：

- 环境变化事实
- 遮挡/LOS/可达性事实
- 对象可供性事实
- 失败与负事实

## 7. 输出边界

`L1` 输出的是：

- 世界真相
- 结构化事实
- 运行时空间与环境状态

`L1` 不输出：

- 角色私有理解
- 司命判断
- 高层语义策略

## 8. 与其他规格关系

- 与 `Godot` 取样前端规格协作：提供 patch 和局部世界引用底稿
- 与 `Perception Query Frame` 规格协作：提供结构化 fact refs 和空间参考
- 与 `ESM` 双通道规格协作：承载世界状态底座和结果回流

## 9. 一句话收束

这份规格的目标，是让当前项目的 `L1` 真正成为“世界事实层”，而不只是“能发一些事实的脚本集合”。
