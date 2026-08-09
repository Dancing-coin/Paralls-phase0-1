# ESM 与交互编排

状态：`current-code module; scoped to world/object/environment interaction settlement`

本文记录 ESM、交互编排和物理通道在当前运行时中的责任边界。

## 责任边界

ESM 与交互编排拥有：

- 结构化交互请求的策略选择
- semantic / physical 通道选择
- 对象、环境与物理交互的 ESM authority settlement
- 成功、失败、降级和约束结果合并
- 输出可适配为 `AuthorityEvent` 的 `world_result` 与 `constraint_state_result`

它们不拥有：

- 角色认知
- Siming 全局判断
- Godot 本地伪造成功
- VLA 或模型输出直接改写世界
- System L6 authority event bus
- FrontendAuthorityEventProjector
- Gameplay Foundation 的账户、库存、装备、状态、产权、债务和合同 stream

## 可视化架构图

```text
┌──────────────────────────── ESM 与交互编排 ────────────────────────────┐
│                                                                         │
│ 输入                                                                     │
│  Godot interact_intent / actor action request / projected facts / context│
│        │                                                                │
│        v                                                                │
│  ┌──────────────────────────────────┐                                   │
│  │ InteractionOrchestrationService   │                                   │
│  │ policy selection / channel choice │                                   │
│  └───────────────┬──────────────────┘                                   │
│                  │                                                       │
│       ┌──────────┴──────────┐                                            │
│       v                     v                                            │
│  ┌──────────────┐     ┌──────────────────────────────┐                  │
│  │ semantic path │     │ physical channel             │                  │
│  │ intent/result │     │ contact/body/object/env refs │                  │
│  └──────┬───────┘     └──────────────┬───────────────┘                  │
│         │                            │                                  │
│         └──────────────┬─────────────┘                                  │
│                        v                                                │
│  ┌──────────────────────────────────┐                                   │
│  │ ESMService authority settlement   │                                   │
│  │ success / denied / constraint     │                                   │
│  └───────────────┬──────────────────┘                                   │
│                  │                                                       │
│                  v                                                       │
│  ┌──────────────────────────────────┐                                   │
│  │ unified result merge              │                                   │
│  │ world_result / constraint_state   │                                   │
│  └───────────────┬──────────────────┘                                   │
│                  │ AuthorityEvent                                       │
│                  v                                                       │
│  ┌──────────────────────────────────┐                                   │
│  │ System L6 AuthorityEventBus       │                                   │
│  │ route / replay / audit helper     │                                   │
│  └───────────────┬──────────────────┘                                   │
│                  │ AuthorityEvents                                       │
│                  v                                                       │
│  ┌──────────────────────────────────┐                                   │
│  │ FrontendAuthorityEventProjector   │───> Godot 可见对象/环境/UI 反馈   │
│  └──────────────────────────────────┘                                   │
│                                                                         │
│ 禁止：成为角色 cognition、让 VLA/模型直写世界、让 Godot 本地伪造成功      │
└─────────────────────────────────────────────────────────────────────────┘
```

上图是 ESM 所拥有的 world/object/environment interaction 路径，不表示所有玩法命令都
经过 ESM。账户、背包、装备、身体/状态、产权、债务、合同和 Patch 生命周期由各
Gameplay authority 验证并通过 `GameplayEventStore.append_batch` 提交；详见
[Gameplay Foundation 与领域结算](GameplayFoundation与领域结算.md)。当前没有一个
已实现的通用 coordinator 可以夺取两边的领域写入权。

## 主要文件与归属

| 区域 | 文件 | 归属 |
| --- | --- | --- |
| ESM 结算 | `backend/app/services/esm_service.py` | ESM |
| 交互编排 | `backend/app/services/interaction_orchestration_service.py` | ESM/交互编排 |
| 物理通道 | `backend/app/services/physical_interaction_channel.py` | ESM/交互编排 |
| L6 authority event 适配 | `backend/app/services/phase0_authority_event_adapter.py`, `backend/app/services/authority_event_bus.py` | 下游 L6 依赖，非 ESM owner |
| L6 下游前端投影适配器 | `backend/app/services/frontend_authority_event_projection.py` | 下游投影依赖，非 ESM owner |
| Godot 物理交互适配 | `scripts/interaction/*` | Godot/交互适配 |
| Gameplay domain authority | `backend/app/gameplay/*` | 相邻 authority substrate，非 ESM owner |

## 数据契约

| 契约 | 说明 |
| --- | --- |
| `interact_intent` | Godot 发起的结构化交互意图 |
| `world_result` | authority 结算后的世界/对象/环境结果 |
| `constraint_state_result` | 失败或约束结果 |
| physical effect refs | 物理通道的受控观察/效果引用 |

## 与 Gameplay Foundation 的边界

当一次交互只改变对象、环境或物理 world result 时，ESM 沿本文路径结算。当一个
typed command 的 canonical fact 属于 Gameplay domain 时，它由对应 authority 直接提交
原子 batch。未来的跨域 vertical slice 可以在正式 spec/plan 授权后协调两类结果，但必须：

- 保留每个事实的现有 owner；
- 在 commit 前完成所有验证，任何一个 domain 拒绝时零提交；
- 复用 Gameplay event-store/outbox 和已有 ESM result contract，而不是新建总线、store 或
  让 ESM 成为通用账本。

## 时序

```mermaid
sequenceDiagram
    participant Godot as Godot 交互输入
    participant Backend as 后端入口
    participant Orchestration as 交互编排
    participant Physical as 物理通道
    participant ESM as ESM 结算
    participant L6 as System L6 AuthorityEventBus
    participant Projection as FrontendAuthorityEventProjector
    participant Presentation as Godot 对象/环境/UI

    Godot->>Backend: interact_intent
    Backend->>Orchestration: 选择策略和通道
    Orchestration->>Physical: 可选物理 observation/effect refs
    Physical-->>Orchestration: 物理通道结果
    Orchestration->>ESM: authority settlement
    ESM-->>Orchestration: success / constraint / degraded result
    Orchestration-->>Backend: unified result
    Backend->>L6: result family -> AuthorityEvent
    L6->>Projection: AuthorityEvents for frontend projection
    Projection-->>Presentation: world_result / constraint feedback / state transition
```

## 验证

- `python scripts/verification/harness.py --profile interaction-orchestration-service`
- `python scripts/verification/harness.py --profile esm-physical-channel-world-actuation`
- `python scripts/verification/harness.py --profile backend-contract`
- `python scripts/verification/harness.py --profile phase0`
