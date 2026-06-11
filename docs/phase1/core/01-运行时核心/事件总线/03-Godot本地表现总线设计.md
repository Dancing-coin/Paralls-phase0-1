# 03-Godot本地表现总线设计

## 状态

- 状态：第一轮迁移稿
- 作用：承载 Godot 客户端内部高频表现更新、安全 deferred 执行与具身精修边界
- 上游约束：
  - [Godot源码底层基础设施与运行时约束.md](/d:/Projects/Paralls/docs/phase1/core/00-总纲/Godot源码底层基础设施与运行时约束.md)
  - [02-角色驱动方案A-B裁决与双总线架构.md](/d:/Projects/Paralls/docs/phase1/core/01-运行时核心/视觉事实系统/02-角色驱动方案A-B裁决与双总线架构.md)
- 下游关联：
  - [07-视觉事实系统接入总线规范.md](/d:/Projects/Paralls/docs/phase1/core/01-运行时核心/事件总线/07-视觉事实系统接入总线规范.md)

## 1. 文档定位

本文件只负责一件事：

冻结 Godot 客户端内部“高频表现更新如何安全执行”的边界。

它不负责：

- 世界真值判断
- 业务总线 replay / audit
- 角色认知推理
- 视觉事实系统内部特征规则

## 2. 统一定义

Godot 本地表现总线不是后端业务总线的本地镜像，而是 Godot 客户端内部的：

- 高速表现更新层
- 主线程安全应用层
- 具身精修触发层

它的存在是因为：

- 后端总线负责权威事实
- Godot 侧需要高频、低抖动、安全地把这些结果落到 `AnimationTree`、`SkeletonModifier3D`、Node 树和 UI 上

## 3. 基础设施约束

当前必须显式采用下列 Godot 底层基础设施与约束：

- `Signal / Callable`
- `MessageQueue`
- `call_deferred()`
- `call_thread_safe()`
- `process_thread_group`
- `WorkerThreadPool`

固定边界：

- worker / 线程组可做预处理、采样整理、特征提取前处理
- 真正修改 `Skeleton3D`、`AnimationTree`、Node 树时，必须回到安全时机
- `CONNECT_DEFERRED`、`call_deferred()` 等属于本地安全执行层，而不是业务事件总线替代品

## 4. 主执行结构

当前固定采用：

- `AnimationTree` 主轨
- `SkeletonModifier3D` 精修轨
- 面部独立轨（`FACS -> face runtime`）

一句话：

> `AnimationTree` 负责主动作轨，`SkeletonModifier3D` 负责本地具身精修。

因此不采用：

- 外部 Python / 后端每帧全骨骼直接遥控 Godot 角色作为主方案
- 以网络高频骨骼流替代本地动画图和修改器链

## 5. 适合留在本地表现总线的消息

当前适合留在 Godot 本地表现总线中的内容包括：

- 角色副本更新
- 表达计划 `revision`
- `AnimationTree` 参数更新
- `SkeletonModifier3D` 精修触发
- UI 提示
- 本地安全 deferred 执行

当前不应上后端业务总线的内容包括：

- 原始骨骼 `(x,y,z)` 高频流
- 全 `AU` 高频流
- `AnimationTree` 内部瞬时参数抖动
- 纯本地骨骼修正中间态

## 6. 与业务总线的关系

Godot 本地表现总线只消费：

- 后端总线回来的高层结果
- 本地输入与本地安全应用信号

它不生产：

- 权威事实
- 成员资格确认结果
- 知识状态确认结果

它与后端总线的正确关系是：

- 后端总线给“要表达什么”
- Godot 本地表现总线决定“如何安全、平滑、高频地把它表现出来”

## 7. Phase 1 当前冻结边界

当前先冻结：

- `Signal / Callable / MessageQueue / deferred / thread group` 作为基础设施
- `AnimationTree + SkeletonModifier3D` 双轨本地执行
- 角色副本更新 / revision / 参数更新 / 本地 UI 提示留在本地总线
- 原始骨骼 / AU 高频流不上业务总线

当前不冻结：

- 具体节点命名
- 具体场景树结构
- 具体 face runtime 选型
- 具体线程调度实现细节

## 8. 一句话收束

Godot 本地表现总线的正确定位不是“另一条业务总线”，而是：

> 在 Godot 客户端内部，用源码层允许的安全机制把后端高层结果落到 `AnimationTree`、`SkeletonModifier3D`、Node 树和 UI 上的高频执行层。
