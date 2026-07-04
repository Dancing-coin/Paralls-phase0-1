# System L1

状态：当前运行时模块文档

本文是当前仓库 `System L1` 实现的维护者文档。它说明 L1 当前拥有什么、
哪些路径是真实运行时路径、哪些文件提供证明，以及哪些说法仍需要谨慎。

更大的主线架构从这里开始：

- `docs/superpowers/specs/world-character-siming-authority-mainline/README.md`
- `docs/superpowers/specs/world-character-siming-authority-mainline/2026-06-29-world-character-siming-authority-mainline-master-design.md`
- `docs/架构/运行时/运行时覆盖矩阵.md`

## 边界

`System L1` 是面向世界的事实、采样和投影上下文边界。它拥有本地 sampling input、
结构化事实发射、事实投影、粗粒度空间/世界状态，以及下游可引用的事实/空间上下文。

它不拥有：

- 角色认知
- Siming 全局判断
- model-provider 推理
- ESM authority
- `world_result` 或 `constraint_state_result` 结算
- 长时间运行的编排 loop
- 独立 L1 运行时、scheduler、event bus 或 authority host

硬规则：L1 服务集成必须继续走已有面向运行时的 service 和消息族，尤其是：

```text
Godot provider/sample/fact
-> raw_fact_event / provider refs
-> 后端 L1 services
-> candidate percept / PQF / canonical bundle
-> CharacterAgentRuntime 或 SimingRuntime 消费
```

不要绕过：

```text
raw_fact_event -> candidate percept -> CharacterPerceivedEvent
```

## 可视化架构图

```text
┌──────────────────────────────────── System L1 ─────────────────────────────────────┐
│                                                                                    │
│  Godot 输入                                                                         │
│  raw_fact_event / provider refs / visual-spatial-auditory-body-skeletal refs       │
│        │                                                                           │
│        v                                                                           │
│  ┌──────────────────────────────┐                                                  │
│  │ fact_router / fact handlers  │                                                  │
│  │ visual / auditory / spatial  │                                                  │
│  └──────────────┬───────────────┘                                                  │
│                 │                                                                  │
│                 v                                                                  │
│  ┌────────────────────────────────────────────────────────────────────────────┐    │
│  │ world_runtime L1 services                                                  │    │
│  │ Scene3DSpaceModel / SpatialOccupancyField / FactProjectionLayer            │    │
│  │ L1RuntimePerceptionBridge / PerceptionQueryFrame                           │    │
│  └──────────────┬───────────────────────────────┬─────────────────────────────┘    │
│                 │                               │                                  │
│                 v                               v                                  │
│  ┌──────────────────────────────┐    ┌────────────────────────────────────────┐    │
│  │ CandidatePerceptEvent         │    │ PQF / CanonicalPerceptBundle           │    │
│  │ 角色私有过滤前候选事件        │    │ 统一感知 query frame                   │    │
│  └──────────────┬───────────────┘    └──────────────┬─────────────────────────┘    │
│                 │ per-character filter              │                              │
│                 v                                   v                              │
│  ┌──────────────────────────────┐    ┌────────────────────────────────────────┐    │
│  │ CharacterPerceivedEvent       │    │ Character / Siming / authority context │    │
│  │ actor-private input           │    │ 只作为下游输入，不写 world truth       │    │
│  └──────────────────────────────┘    └────────────────────────────────────────┘    │
│                                                                                    │
│  禁止：L1 main loop / L1 event bus / L1 scheduler / L1 authority host              │
└────────────────────────────────────────────────────────────────────────────────────┘
```

## 当前运行时数据流

```text
Godot scene and character nodes
  |
  +--> Raw fact emitters
  |      scripts/l1/facts/*
  |      scripts/l1/facts/emitters/*
  |
  +--> Sampling providers
  |      scripts/character/VisualPatchProvider.gd
  |      scripts/character/SpatialPatchProvider.gd
  |      scripts/character/AuditoryContextProvider.gd
  |      scripts/character/EmbodiedStateProvider.gd
  |      scripts/character/EmbodiedSkeletalStateProvider.gd
  |      scripts/character/EnvironmentFieldProvider.gd
  |
  +--> Player and interaction intent
         scripts/player/*
         scripts/phase0/MainDemoController.gd
         scripts/interaction/*

BackendBridge / WebSocket
  |
  v
backend/app/main.py
  |
  +--> fact_router / fact handlers
  |      backend/app/services/fact_router.py
  |      backend/app/services/fact_handlers/*
  |
  +--> L1 space and projection services
  |      backend/app/world_runtime/l1_space_model.py
  |      backend/app/world_runtime/l1_occupancy.py
  |      backend/app/world_runtime/l1_fact_projection.py
  |      backend/app/world_runtime/l1_runtime_perception_bridge.py
  |
  +--> Perception protocol
  |      backend/app/world_runtime/intelligence_upgrade.py
  |      backend/app/world_runtime/l1_perception_frame.py
  |
  +--> Consumer-facing context
         CharacterAgentRuntime
         SimingRuntime / SimingGlobalSituationLayer
          authority context refs for downstream settlement
```

## 主要数据对象

| 对象或消息 | 作用 | 主要文件 |
| --- | --- | --- |
| `raw_fact_event` | Godot 到后端的跨边界事实 envelope | `scripts/l1/facts/FactEnvelopeBuilder.gd`, `scripts/l1/facts/RawFactEmitter.gd`, `backend/app/main.py` |
| Provider refs | PQF 输入用仅采样 refs | `scripts/character/*Provider.gd`, `backend/app/world_runtime/intelligence_upgrade.py` |
| `Scene3DSpaceModel` | 静态/已审核 scene-space model | `backend/app/world_runtime/l1_space_model.py`, `backend/app/world_runtime/intelligence_upgrade.py` |
| `SpatialOccupancyField` | 动态 occupancy state | `backend/app/world_runtime/l1_occupancy.py`, `backend/app/world_runtime/intelligence_upgrade.py` |
| `FactProjectionLayer` | LOS/reachability/negative fact projection | `backend/app/world_runtime/l1_fact_projection.py` |
| `PerceptionQueryFrame` | 面向角色或 Siming consumer 的统一 query frame | `backend/app/world_runtime/l1_perception_frame.py`, `backend/app/world_runtime/intelligence_upgrade.py` |
| `CanonicalPerceptBundle` | consumer-facing percept bundle | `backend/app/world_runtime/intelligence_upgrade.py` |
| `CandidatePerceptEvent` | actor-private filtering 之前的候选 percept | `backend/app/models/candidate_percept.py`, `backend/app/services/candidate_percept_service.py` |
| `CharacterPerceivedEvent` | actor-private perceived input | `backend/app/models/character_perceived.py`, `backend/app/services/per_character_percept_filter.py` |
| authority context refs | 面向 ESM/L6 的事实引用、投影上下文和 evidence refs | `backend/app/world_runtime/l1_fact_projection.py`, `backend/app/world_runtime/intelligence_upgrade.py` |

## L1 领域

### 视觉

当前范围：

- 从 Godot 发射 visual fact
- visual fact 通过后端 authority path 路由
- 投影到候选/私有 percept 路径
- Siming 通过 authority events 和全局态势 inputs 消费

关键文件：

- `scripts/visual/VisualFactEmitter.gd`
- `scripts/l1/facts/emitters/ObjectVisualFactEmitter.gd`
- `scripts/l1/facts/emitters/EnvironmentVisualFactEmitter.gd`
- `scripts/l1/facts/emitters/CharacterVisualFactEmitter.gd`
- `backend/app/services/fact_handlers/visual_fact_handler.py`

当前注意：

- visual filtering 相比生产级 LOS、lighting、occlusion、geometry truth 仍偏粗。

### 空间

当前范围：

- zone/scene/room context
- actor/object spatial refs
- occupancy dirty-zone updates
- reachability 和 negative fact projection

关键文件：

- `scripts/l1/space/SceneSpaceModelExtractor.gd`
- `scripts/l1/space/RuntimeOccupancySampler.gd`
- `scripts/l1/space/FactProjectionBridge.gd`
- `backend/app/world_runtime/l1_space_model.py`
- `backend/app/world_runtime/l1_occupancy.py`
- `backend/app/world_runtime/l1_fact_projection.py`

当前注意：

- 这是面向运行时的 L1 service integration，不是新的 product 运行时 loop。

### 听觉

当前范围：

- targeted auditory facts 可以进入候选/私有 percept 路径
- ambient environmental auditory context 仍是 system-level，除非未来通过
  actor-private hearing design 显式提升

关键文件：

- `scripts/character/AuditoryContextProvider.gd`
- `scripts/l1/facts/emitters/AuditoryFactEmitter.gd`
- `backend/app/services/fact_handlers/auditory_fact_handler.py`

当前注意：

- ambient hearing attribution 还不是完整 actor-private perception。

### 具身与骨骼

当前范围：

- high-level body state 和 mid-level skeletal refs 可以进入 perception payload
- low-level bone snapshots 只保留 debug-replay 用途

关键文件：

- `scripts/character/EmbodiedStateProvider.gd`
- `scripts/character/EmbodiedSkeletalStateProvider.gd`
- `scripts/character/SkeletalStateProviderRefEmitter.gd`
- `scripts/verification/EmbodiedSkeletalRuntimeProbe.gd`

当前注意：

- L1 不能把 full-bone high-frequency pose streams 发送给后端业务逻辑。

### 环境与物理通道

当前范围：

- environment field provider refs
- physical contact/body/object/environment observation refs
- physical channel 使用这些 observation refs；L1 不生成 structured effects 或 ESM result

关键文件：

- `scripts/character/EnvironmentFieldProvider.gd`
- `scripts/interaction/PhysicalInteractionAdapter.gd`
- `scripts/interaction/PhysicalInteractionProbe.gd`
- `backend/app/services/interaction_orchestration_service.py`
- `backend/app/services/physical_interaction_channel.py`

当前注意：

- physical channel 证明不等于完整生产级 physics gameplay。

## 验证覆盖

| 说法 | 验证 |
| --- | --- |
| Phase 0 主 L1 smoke loop 可运行 | `python scripts/verification/harness.py --profile phase0` |
| 静态边界规则成立 | `python scripts/verification/harness.py --profile boundaries` |
| Godot project refs/autoloads 有效 | `python scripts/verification/harness.py --profile godot-project` |
| L1 world fact subsystem 集成成立 | `python scripts/verification/harness.py --profile l1-world-fact-runtime` |
| Godot provider refs 进入 PQF | `python scripts/verification/harness.py --profile godot-sampling-production-grade-providers` |
| Embodied/skeletal debug replay 边界成立 | `python scripts/verification/harness.py --profile embodied-skeletal-debug-replay` |
| Interaction orchestration channel choice 成立 | `python scripts/verification/harness.py --profile interaction-orchestration-service` |
| Physical channel world actuation 证明成立 | `python scripts/verification/harness.py --profile esm-physical-channel-world-actuation` |
| 主线聚合证明成立 | `python scripts/verification/harness.py --profile mainline-unified-runtime` |

## 完成标准

一个 L1 feature 的文档只有记录下面内容才算完整：

1. source node 或后端 producer
2. message/data object
3. 后端 route 或 service owner
4. downstream consumer
5. forbidden ownership
6. harness profile 与 report artifact
7. 已知 degraded 或 unverified state

## 已知缺口

- Ambient auditory context 仍需要更严格的 actor-private hearing design。
- Visual precision 需要更丰富的 LOS、occlusion、lighting 和 geometry 证明。
- Physical channel 证明是受控且结构化的，但不是完整连续生产级 gameplay。
- Provider/model readiness 与运行时证明分离；model output 不能直接写 world truth、
  ESM authority 或 actor control。
