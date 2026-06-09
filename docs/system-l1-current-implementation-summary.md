# System L1 当前实现总结

日期：`2026-06-10`

这份文档是当前仓库 `System L1` 的 repo-local 实现总结。

它不重复主项目理想架构，而是回答四件事：

1. 当前 `System L1` 到底已经实现到什么程度
2. 它现在能支撑什么真实能力
3. 一个完整案例在当前仓库里会怎样流转
4. 距离主项目理想态还差在哪

---

## 1. 一句话结论

当前仓库里的 `System L1` 已经不是“只有骨架的 demo 线”，而是：

- 有统一事实上抛出口
- 有 authority backend 结算
- 有最小角色私有感知入口
- 有运行时验证闭环

按当前仓库自己的 repo-local 计划目标，`System L1` 已经完成并验证通过。

但按主项目的 full-volume 理想态来看，它还不是最终生产级 `System L1`。

---

## 2. 当前完成状态

### 已经成立的部分

当前仓库的 `System L1` 已经具备：

- 统一 `raw_fact_event` 事实出口
- `player_input -> backend route -> result/runtime/siming` 的最小执行链
- 视觉事实系统
- 听觉 raw fact 最小链
- 触觉 / 热感 / 嗅觉 / 生理 / 角色状态这五类剩余 emitter
- `ESM` 的 deterministic 结算层
- `L1 -> candidate percept -> per-character filter -> character perceived` 的最小桥
- reconnect / zone reseed / privacy reseed / environment cycle runtime proof

### 已验证结果

当前工作树上的关键验证结果：

- `python -m pytest -v` -> `187 passed`
- `python scripts/verification/verify_phase1_slice.py` -> `overall_phase1_slice_passed=True`
- `python scripts/verification/verify_phase0.py` -> `overall_strict_phase0_passed=True`
- `python scripts/verification/verify_l1_runtime_edges.py` -> `overall_l1_runtime_edges_passed=True`

---

## 3. 现在能做什么

### 3.1 玩家输入与执行

当前 `System L1` 已经能把这些玩家侧输入做成结构化执行消息：

- `move_intent`
- `focus_target_change`
- `dialogue_submit`
- `interact_intent`

这意味着当前仓库不再只是本地 Godot 动画或按钮逻辑，而是已经形成：

`player input -> backend route -> world/runtime response`

### 3.2 视觉层

当前已经成立的视觉事实面包括：

- `actor_looks_at_actor`
- `actor_looks_at_object`
- `actor_near_object`
- `environment_light_drop`
- `visual_evidence_projection`

这些事实不只是打印日志，而是会进入：

- backend authority
- runtime state projection
- candidate generation
- Siming 输出链

### 3.3 听觉层

当前听觉最小链已经成立：

- `speaker_active`
- `auditory_reachability_changed`
- `ambient_noise_changed`

但注意：当前仓库里听觉被明确冻结成 `L1-only`。

也就是说：

- 系统能收到听觉 raw fact
- authority 路由和验证都存在
- 但它不会继续进入 candidate percept / per-character perceived

### 3.4 ESM 层

当前 `ESM` 已经能稳定处理：

- 交互成功
- 交互失败（constraint）
- 环境状态变化
- 状态机 transition
- coarse 环境场更新

当前 repo-local 已显式支持的环境请求包括：

- `light_level_drop`
- `light_level_restore`
- `thermal_level_rise`
- `smoke_density_rise`
- `noise_level_rise`

对不支持的请求，当前实现会明确拒绝，不会伪装成功。

### 3.5 角色私有输入侧

当前最小角色私有感知入口已经成立：

- `CandidatePerceptEvent`
- `PerCharacterPerceptFilter`
- `CharacterPerceivedEvent`
- `SelfBodyPerceivedEvent`

这意味着当前仓库不再只有“系统知道发生了什么”，而是已经有：

- 某个角色会收到一条角色私有输入
- 某个角色会收到一条身体私有输入

---

## 4. 当前真实边界

### 4.1 `System L1` 已经足够的部分

如果目标是：

- 玩家控制 `CharacterC`
- `CharacterA/B` 作为其他角色壳存在
- 基于视觉事实形成最小互相感知
- 基于 authority 结果发生交互和反应

那么当前 `System L1` 已经够用。

### 4.2 `System L1` 还不够的部分

#### 听觉

听觉当前还没有进入角色私有感知。

代码里最关键的现实边界在：

- [backend/app/services/candidate_percept_service.py](/d:/Users/User/Documents/paralls-phase-0-demo/backend/app/services/candidate_percept_service.py)

当前行为是：

- `auditory_fact` 会进入系统
- 但 `compile_candidate_percepts(...)` 对听觉直接返回空

所以当前缺的不是“角色智能体没听懂”而已，
而是：

**`System L1` 目前还没有把听觉推进到角色私有输入链。**

#### 视觉精度

视觉已经进了角色侧，但精度还比较粗。

当前问题不是视觉链不存在，而是：

- 过滤上下文较薄
- 还不是严格 LOS / 朝向 / 遮挡 / 几何裁剪系统

所以当前视觉是：

- 有最小闭环
- 但还不是生产级精细感知

### 4.3 角色智能体层还没完成的部分

更高层的角色智能体还没有完整实现，所以当前还做不到：

- 基于感知的复杂自主理解
- 稳定多轮自主交流
- 完整社会意义判断
- 多角色长期策略性互动

这些不完全是 `System L1` 的锅。

更准确地说：

- `System L1` 负责把事实、候选、结算和最小私有输入送到边界
- 角色智能体负责“真正听懂 / 看懂 / 形成动机 / 主动决策”

---

## 5. 一个当前仓库里真实成立的完整案例

下面这个案例是按当前代码真实能力推演的。

### 案例描述

玩家控制 `CharacterC` 进入场景，先看向 `CharacterA`，再对 `A` 说话，然后转向桌上的 `obj_letter` 调查，交互成功后环境变化触发 `CharacterB` 的注意。

### 阶段 1：玩家进入并控制 `C`

- 玩家实际控制的是 `CharacterC` 对应的世界角色壳
- `A/B` 保持为 AI-driven shell
- `System L1` 持续处理：
  - `move_intent`
  - locomotion state
  - spatial access
  - 当前 focus

### 阶段 2：`C` 看向 `A`

- Godot 发出 `focus_target_change`
- 同时发出视觉事实：
  - `fixed_gaze_on_target`
  - `actor_looks_at_actor`

后端会：

- 更新 `C` 的 focus/runtime snapshot
- 基于视觉事实生成 candidate
- 将一条最小 `CharacterPerceivedEvent` 写给 `A`

### 阶段 3：`C` 对 `A` 说话

- 玩家发出 `dialogue_submit(target_actor_id="char_a")`
- backend `CharacterService` 返回 `dialogue_response(actor_id="char_a")`

于是形成：

- 玩家 `C -> A` 的显式交流
- `A` 的回应回到 Godot 表现层

### 阶段 4：听觉事实同时存在，但还只在系统层

如果当前对话链伴随听觉 raw fact：

- `speaker_active`
- `auditory_reachability_changed`
- `ambient_noise_changed`

那么当前系统会：

- 记录这些听觉事实
- 走 authority / verifier

但不会：

- 把它们编译成 candidate percept
- 把它们写成角色私有“我听到了什么”

### 阶段 5：`C` 调查 `obj_letter`

- 玩家靠近物体
- 发出 `actor_near_object`
- 玩家触发 `interact_intent`

`ESM` 会发出：

- `action_request`
- `action_resolution_result`
- `object_state_result`
- `body_state_result`
- `environment_state_result`
- `state_machine_transition`

Godot 侧还会继续发：

- `visual_evidence_projection`
- tactile fact
- thermal fact
- olfactory fact

### 阶段 6：`B` 被拉进注意链

物体状态和环境状态变化会进入：

- `ConversationRelationService`
- `CharacterRuntimeStateService`
- `SimingService`

结果是：

- `C` 自己的 runtime/candidate 会更新
- `B` 会收到一条 attention prompt
- 场景上会表现为“`B` 注意到了变化”

这就是当前仓库最真实的一条：

**玩家 -> 视觉感知 -> 交流 -> 交互 -> 世界结算 -> 他人注意**

的最小闭环。

---

## 6. 时序图

### 6.1 视觉主导的最小互感 -> 交流 -> 交互闭环

```text
玩家
  |
  v
Player / CharacterC
  |
  | focus_target_change / move_intent / dialogue_submit / interact_intent
  v
PlayerIntentMapper / MainDemoController
  |
  | visual_fact / spatial_access_fact
  v
System L1 统一出口
  |
  v
backend/main.py
  |
  +--> SessionRuntime
  |      - 接受 move/focus/interact/dialogue 路由
  |
  +--> ConversationRelationService
  |      - 维护 focus / visual / world relation
  |
  +--> CandidatePerceptService
  |      - visual_fact / spatial_access_fact -> candidate percept
  |
  +--> PerCharacterPerceptFilter
  |      - candidate -> CharacterPerceivedEvent
  |
  +--> CharacterPerceivedInputService
  |      - 写入 A 的私有感知输入
  |
  +--> CharacterRuntimeStateService
  |      - 生成 C 的 snapshot / delta
  |
  +--> CharacterService
  |      - 处理 A 的对话响应
  |
  +--> ESMService
  |      - 处理交互成功/失败和环境变化
  |
  +--> SimingService
         - 基于 visual/world/candidate 生成 attention prompt
```

### 6.2 听觉链当前到哪

```text
Godot AuditoryFactEmitter
  |
  v
raw_fact_event (auditory_fact)
  |
  v
backend authority route
  |
  +--> verifier / audit / debug proof
  |
  +--> candidate_percept_service
         - 当前策略: AUDITORY_CANDIDATE_POLICY = "l1_only"
         - 返回 []
  |
  x
不会继续进入:
  - CandidatePerceptEvent
  - CharacterPerceivedEvent
  - conversation candidate
  - 角色私有“听到”输入
```

---

## 7. `room / scene / zone` 的当前实现情况

当前仓库里三者都存在，但成熟度不同。

### `room`

现在主要是：

- 顶层会话/容器标识
- 广泛出现在模型、消息、结果对象里

当前现实情况：

- 有这个字段
- 但还没有复杂的多房间 runtime 管理逻辑

### `scene`

现在主要是：

- 当前 Godot 场景上下文标识
- 用来稳定 envelope / state / result 的上下文

当前现实情况：

- 有结构意义
- 但还不是完整的多场景切换/迁移系统

### `zone`

`zone` 是三者里当前最像真实运行边界的一个。

当前已经真实承担：

- 当前区域标识
- `current_zone_id`
- `privacy_band`
- zone reseed
- privacy reseed
- 环境场按 zone 维度挂载

对应现实实现可以看：

- [backend/app/services/fact_handlers/spatial_access_fact_handler.py](/d:/Users/User/Documents/paralls-phase-0-demo/backend/app/services/fact_handlers/spatial_access_fact_handler.py)
- [backend/app/models/runtime_state.py](/d:/Users/User/Documents/paralls-phase-0-demo/backend/app/models/runtime_state.py)
- [scripts/l1/facts/emitters/SpatialAccessFactEmitter.gd](/d:/Users/User/Documents/paralls-phase-0-demo/scripts/l1/facts/emitters/SpatialAccessFactEmitter.gd)

当前默认上下文基本是：

- `room_id = "room_demo"`
- `scene_id = "scene_demo"`
- `zone_id = "zone_focus"`

所以大白话说：

- `room`：现在更像 ID 容器
- `scene`：现在更像场景标签
- `zone`：现在已经是最小可工作的空间边界单位

但三者都还不是主项目理想中的 full-volume 空间运行系统。

---

## 8. 理想态是什么

理想态的 `System L1` 会比当前版本更深：

- 视觉不是最小可验证 slice，而是更精细的几何/遮挡/朝向感知层
- 听觉不仅有 raw fact，还能进入 candidate percept 和角色私有输入
- `ESM` 不只是当前 coarse field / minimal workbench，而是更完整的 settlement matrix 和工作台
- `room / scene / zone` 不只是标识和最小边界，而是更完整的空间 runtime 拓扑
- 多感官到候选感知编译会有更完整、统一的策略

---

## 9. 当前差距总结

### 不是 `System L1` 的主要差距

这些更偏角色智能体未完整实现：

- 真正“听懂 / 看懂 / 形成社会理解”
- 多轮自主对话
- 稳定角色动机与策略
- 复杂角色间博弈

### 是 `System L1` 当前自己的差距

这些是 `System L1` 本身仍然没铺满的：

- 听觉没有进入角色私有感知
- 视觉过滤精度不高
- `ESM` 的工作台、模板丰富度、settlement breadth 仍是 repo-local 有界 slice
- `room / scene / zone` 还是最小运行上下文，不是完整空间系统

---

## 10. 未来实现建议

如果下一阶段继续沿着当前仓库推进，建议顺序是：

### 第一优先级

1. 让 `auditory_fact` 进入 `CandidatePerceptEvent`
2. 增加听觉的 `PerCharacterPerceptFilter`
3. 建立角色私有“听觉已感知”输入链

原因：

- 这一步完成后，才能说角色之间在 `System L1` 层同时具备最小视觉与听觉互感

### 第二优先级

1. 让视觉 filter 的 context 变真实
2. 不再默认 `is_facing_target=True`
3. 逐步接入更真实的朝向 / 可见性 / 遮挡判断

### 第三优先级

1. 扩展 `ESM` settlement matrix
2. 丰富环境/对象模板
3. 扩展 workbench / replay / debug surface

### 第四优先级

1. 把 `room / scene / zone` 从上下文标签推进为真正空间 runtime
2. 做更明确的 zone topology / multi-zone propagation / multi-room boundary

---

## 11. 结语

当前仓库里的 `System L1` 已经完成了“从 demo 骨架到可信运行时层”的跃迁。

它现在已经足够支撑：

- 玩家控制一个角色
- 其他角色壳在同一世界里存在
- 基于视觉产生最小互感
- 基于 authority 做交流、交互、结算和反应

但如果目标是：

- 多角色智能体真正基于视觉和听觉都互相理解
- 并在复杂社会语境下自主交流与互动

那么下一步最关键的缺口不是重新写一套 `System L1`，
而是：

- 把听觉补进 `System L1` 角色私有感知链
- 把视觉感知精度做深
- 再把角色智能体层真正接起来

