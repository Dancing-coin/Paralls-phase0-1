# Godot源码底层基础设施与运行时约束

## 1. 文档目标

本文档基于项目内已拉取的 Godot 源码仓库 `/.tmp/godot/`，抽取与《开本》所有系统相关的 Godot C++ 底层基础设施，并给出它们在本项目中的推荐用途与运行时约束。

这里的“所有系统”当前至少覆盖：

- 角色智能体
- 事件总线
- 司命
- 视觉事实系统
- `ESM`
- Godot 本地表现总线
- 调试 / 回放 / 工作台相关运行时支撑层

## 2. 审查范围

本次审查重点围绕当前最可能影响《开本》全系统落地的 Godot 基础设施：

1. `Object / ObjectID / ObjectDB`
2. `Signal / Callable`
3. `CallQueue / MessageQueue`
4. `Node` 线程组与线程安全入口
5. `WorkerThreadPool / Mutex / Semaphore / SafeRefCount`
6. `Skeleton3D`
7. `SkeletonModifier3D`
8. `AnimationTree / AnimationMixer / BlendSpace / StateMachine`
9. `RetargetModifier3D / IKModifier3D / AimModifier3D`
10. `SceneTree / SceneTreeTimer / MainLoop`
11. `MultiplayerAPI / SceneMultiplayer / PacketPeer / WebSocketPeer / HTTPRequest`
12. `FileAccess / DirAccess / ResourceLoader / JSON / ConfigFile`
13. `OS / Time / Engine / EngineDebugger`

## 3. Object / ObjectID / ObjectDB

关键文件：

- `core/object/object.h`
- `core/object/object.cpp`
- `core/object/object_id.h`

作用：

- Godot 所有运行时对象都建立在 `Object` 体系上
- `ObjectID` 提供对象弱引用式标识
- `ObjectDB` 提供按 `ObjectID` 查找实例与生命周期校验

对项目的意义：

- 客户端角色副本、采样器、modifier、调试对象不应通过强引用链硬耦合
- 本地视觉事实系统、工作台和副通道优先使用稳定 ID，而不是直接在业务层传播裸节点引用

## 4. Signal / Callable

关键文件：

- `core/variant/callable.h`
- `core/object/object.h`

源码层事实：

- `Callable` 是 16 字节对齐的可调用目标封装
- `Signal` 是对象信号的底层抽象
- `Object` 提供 `emit_signalp()`、`connect()`、`call_deferred()` 等接口
- `CONNECT_DEFERRED` 是正式标志，而非脚本层魔法语法

对项目的意义：

- Godot 客户端内部局部总线不需要自己发明，`Autoload + typed signals + Callable` 已足够
- 它适合做“本地表现总线 / 调试总线 / 副通道”
- 它不适合替代后端的世界级事实总线

## 5. CallQueue / MessageQueue

关键文件：

- `core/object/message_queue.h`

源码层事实：

- `CallQueue` 使用分页内存，默认页大小 `4096 bytes`
- `MessageQueue` 同时维护 `main_singleton` 与 `thread_local thread_singleton`
- 负责 deferred call / deferred notification / deferred set 的安全排队与 flush

对项目的意义：

- 任何来自网络线程、后台线程、Python bridge 的场景树修改，都应通过 deferred queue 回主线程安全执行
- 这层非常适合作为 Godot 本地“高频输入 -> 主线程安全应用”的基础
- 它不是后端业务事件总线替代品，只是本地执行安全层

## 6. Node 线程组与线程安全入口

关键文件：

- `scene/main/node.h`
- `scene/main/node.cpp`
- `scene/main/scene_tree.cpp`

源码层事实：

- `Node` 支持 `process_thread_group`
- 提供 `call_deferred_thread_group()` 与 `call_thread_safe()`
- 有 `ERR_THREAD_GUARD / ERR_MAIN_THREAD_GUARD / ERR_READ_THREAD_GUARD` 等线程守卫宏

对项目的意义：

- Godot 已明确区分“可在主线程外做的事”和“只能在安全线程改的事”
- 你们可以把客户端的局部预处理、特征计算、采样整理放在线程组/worker 中
- 但真正修改 `Skeleton3D`、`AnimationTree`、Node 树时，仍需回到安全时机

## 7. WorkerThreadPool / Mutex / Semaphore / SafeRefCount

关键文件：

- `core/object/worker_thread_pool.h`
- `core/object/worker_thread_pool.cpp`
- `core/templates/safe_refcount.h`
- `core/core_bind.h / cpp`

对项目的意义：

- 可以安全承载本地非场景树数据工作：
  - 网络包解码
  - 视觉事实特征预计算
  - 语义抽取前处理
  - 调试摘要预拼装
- 不建议在 worker 中直接修改角色 Node / `Skeleton3D` / `AnimationTree`

## 8. Skeleton3D

关键文件：

- `scene/3d/skeleton_3d.h`
- `scene/3d/skeleton_3d.cpp`

源码层事实：

- 提供 `set_bone_pose()`、`set_bone_pose_position()`、`set_bone_pose_rotation()`、`set_bone_pose_scale()`
- 内部维护 pose cache、global pose、modifier pose cache
- 提供 `ModifierCallbackModeProcess`：physics / idle / manual

对项目的意义：

- Godot 本地完全支持精确到骨骼层的姿态控制
- 这很适合做本地执行层、后处理层和调试采样层
- 但不适合做跨边界业务总线主协议

## 9. SkeletonModifier3D

关键文件：

- `scene/3d/skeleton_modifier_3d.h`

源码层事实：

- 支持 `active`、`influence`
- 通过 `_process_modification(double p_delta)` 在最终姿态提交前插入修改
- 内置了骨骼轴向、方向、旋转轴等辅助工具

对项目的意义：

- 这是《开本》本地具身后处理的最佳切入点之一
- 适合承载：
  - gaze 头颈修正
  - torso tension
  - pain guarding
  - injury compensation
  - hand intention overlays

## 10. AnimationTree / AnimationMixer / BlendSpace / StateMachine

关键文件：

- `scene/animation/animation_tree.h`
- `scene/animation/animation_mixer.h`
- `scene/animation/animation_blend_space_*.{h,cpp}`
- `scene/animation/animation_node_state_machine.*`

源码层事实：

- Godot 的动画系统天然就是图式混合系统
- 支持 filter、blend、state machine、sync mode、parameter slots
- `AnimationNode::ProcessState` 是 `thread_local`

对项目的意义：

- 主动作轨最适合承载 locomotion、状态过渡、基础手势族、上下半身大类混合
- 不建议废掉主轨改成纯逐骨骼远程驱动
- 更适合采取“AnimationTree 主轨 + SkeletonModifier3D 精修轨”双轨结构

## 11. Retarget / IK / Aim Modifier 体系

关键文件：

- `scene/3d/retarget_modifier_3d.cpp`
- `scene/3d/ik_modifier_3d.cpp`
- `scene/3d/aim_modifier_3d.cpp`

对项目的意义：

- Godot 已经有修改器链思路，不需要你们从零发明骨骼后处理框架
- `Canonical Rig / Asset Adapter / Binder` 方案与 Godot 底层方向是相容的
- gaze、look-at、retarget、脚步修正都能自然落到该层

## 12. SceneTree / SceneTreeTimer / MainLoop

关键文件：

- `scene/main/scene_tree.h`
- `scene/main/scene_tree.cpp`
- `scene/main/timer.h`

源码层事实：

- `SceneTree` 是客户端运行时主循环与节点生命周期的总宿主
- 内部直接持有 `MessageQueue`
- 自带 `SceneTreeTimer`
- 管理 `process_groups`
- 内含 `MultiplayerAPI` 挂载点

对项目的意义：

- 对角色智能体：本地副本、输入、表现、感知采样最终都落在 `SceneTree` 生命周期内
- 对事件总线：Godot 本地表现总线必须服从 `SceneTree` 的主循环和 flush 节奏
- 对司命：若本地保留任何“司命观察镜像 / 调试代理 / 最小验证版导演钩子”，都只能作为 `SceneTree` 内的只读观察者，而不是另起平行调度器
- 对回放 / 调试：`SceneTreeTimer` 适合做本地演示节奏、超时保护和调试面板刷新，但不应被误用为后端权威时钟

一句话：

- `SceneTree` 是 Godot 侧运行时主舞台，不是《开本》世界真值主脑

## 13. MultiplayerAPI / PacketPeer / WebSocket / HTTPRequest

关键文件：

- `scene/main/multiplayer_api.h`
- `modules/multiplayer/scene_multiplayer.h`
- `core/io/packet_peer.h`
- `modules/websocket/websocket_peer.h`
- `scene/main/http_request.h`

源码层事实：

- Godot 原生具备多人通信抽象层 `MultiplayerAPI`
- 底层网络通信抽象基于 `PacketPeer`
- `WebSocketPeer` 可承载实时链路
- `HTTPRequest` 适合非长连接请求

对项目的意义：

- 对 `Phase 0`：Godot ↔ Python 的最小实时打通可优先走 WebSocket 风格链路
- 对事件总线：Godot 侧只需要承担“客户端通信端点”，不需要把 `MultiplayerAPI` 误写成后端业务总线替代品
- 对司命：Godot 本地不应把 `MultiplayerAPI` 视为司命调度层；司命仍然是后端权威叙事/事实总线消费者
- 对角色智能体：角色输入 / 输出在 Godot 侧可通过网络端点收发，但角色认知与高阶知识真值不应落在 Godot 网络层

一句话：

- Godot 有通信能力，但这层是客户端接线能力，不是世界真值协调层

## 14. FileAccess / DirAccess / ResourceLoader / JSON / ConfigFile

关键文件：

- `core/io/file_access.h`
- `core/io/dir_access.h`
- `core/io/resource_loader.h`
- `core/io/json.h`
- `core/io/config_file.h`
- `core/core_bind.h`

源码层事实：

- `FileAccess` / `DirAccess` 提供本地文件与目录访问
- `ResourceLoader` 提供资源加载与线程化加载入口
- `JSON` 提供原生解析 / stringify
- `ConfigFile` 提供结构化 ini 风格配置读写

对项目的意义：

- 对司命：适合本地只读加载 demo 剧情片段、样板局部情境、工作台配置与观察镜像，不适合把司命权威状态直接长期写死在客户端文件里
- 对 ESM：适合本地演示时加载静态规则片段、物件配置和环境样板，但不替代后端规则真源
- 对视觉事实系统：适合加载阈值样板、工作台过滤条件、debug 开关和最小样板集
- 对回放 / 调试：适合本地暂存 debug dump、最小 replay 片段、演示脚本和联调配置
- 对 `Phase 0`：`JSON / ConfigFile` 很适合快速搭 demo 样板配置，而不必先上完整数据库

一句话：

- Godot 原生 I/O 很适合做本地配置、样板、调试与演示支撑，但不应反客为主替代后端权威数据层

## 15. OS / Time / Engine / EngineDebugger

关键文件：

- `core/os/os.h`
- `core/os/time.h`
- `core/config/engine.h`
- `core/debugger/engine_debugger.h`
- `core/debugger/engine_profiler.h`

源码层事实：

- `OS` 提供进程、环境变量、系统信息、外部程序调用等能力
- `Time` 提供系统时间与时间转换
- `Engine` 提供引擎状态、时间缩放、运行模式等全局信息
- `EngineDebugger / EngineProfiler` 提供调试与性能观测入口

对项目的意义：

- 对司命：适合本地演示模式下的时间戳生成、基础运行模式判断和调试观察，但不应作为剧情世界时间真源
- 对回放 / 调试：`EngineDebugger / EngineProfiler` 是本地工作台、性能采样、调试摘要和演示模式观测的重要基础
- 对 `Phase 0`：`OS / Time` 适合做 demo 录制、日志打点、外部进程联动和最小运行环境判断
- 对事件总线：`Engine.time_scale` 一类引擎级时间特性会影响本地表现与短定时器行为，不能直接等同于后端权威时间

一句话：

- Godot 全局单例很适合支撑本地调试和运行环境控制，但不能替代后端世界级时间、审计与导演逻辑

## 16. 对司命的直接约束

基于以上基础设施，司命在 Godot 侧的正确落位应明确为：

- 可有本地观察镜像
- 可有本地演示钩子
- 可有调试工作台联动
- 不应有本地主导的世界真值调度器

因此：

- 司命的权威判断、会话确认事件、高阶知识图谱真值仍以后端为准
- Godot 侧若存在最小司命演示实现，也应被视为 demo 驱动器或观察代理，而不是正式单局导演本体

## 17. 对 ESM / 视觉事实 / 回放调试的直接约束

### ESM

- Godot 侧可以承接最小环境 / 物体状态变化表现
- 但 `ESM` 的权威规则结算仍不应下沉为 Godot 本地唯一真源

### 视觉事实系统

- Godot 侧非常适合做高频采样、姿态规范化、特征提取前处理和 `Visual Fact Emitter`
- 原始骨骼 / 表情流止步于本地，不应直接跨边界广播

### 回放 / 调试 / 工作台

- 适合在 Godot 本地做：
  - 调试面板
  - debug dump
  - 演示脚本
  - 工作台只读观察
- 不适合在 Godot 本地做：
  - 后端 replay / audit 真源
  - 全局高阶知识图谱真值保存
  - 世界级事实回放主库

## 18. 总结

从 Godot 源码层看，最值得用的不是“拿 Python 每帧直接遥控所有骨骼”，而是：

1. 用 `MessageQueue / deferred` 保证本地线程安全
2. 用 `Signal / Callable` 搭建 Godot 本地表现总线
3. 用 `AnimationTree` 承担主动作轨
4. 用 `SkeletonModifier3D` 承担本地具身精修轨
5. 用 `Skeleton3D` 提供骨骼级执行与采样能力
6. 用 `FileAccess / JSON / ConfigFile / ResourceLoader` 支撑本地样板、配置与调试
7. 用 `OS / Time / EngineDebugger` 支撑本地运行环境判断、日志、性能与工作台观测

一句话：Godot 底层非常适合做《开本》的本地高频具身执行器、视觉事实提取器、调试工作台与 demo 支撑层，但不适合替代后端世界级事件总线、司命真值判断和角色认知系统。
