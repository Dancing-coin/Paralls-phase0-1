# System L6 事件总线

状态：当前运行时模块文档

本文记录当前仓库已经落地的 `System L6`：跨层基础设施层。它包含 authority event
统一信封、事件总线、路由、回放/审计辅助边界，并连接下游前端投影适配器。它不是新的感知层、角色脑、
ESM 或 world truth owner。

## 可视化架构图

```text
┌────────────────────────────── System L6：跨层基础设施层 ──────────────────────────────┐
│                                                                                       │
│  L6 core 职责：统一 authority envelope、发布/订阅、路由、回放/审计辅助                │
│  L6 不拥有：perception semantics、角色推理、ESM 结算、world truth、Godot 本地表现       │
│                                                                                       │
│  ┌──────────────────────┐       ┌─────────────────────────────┐                       │
│  │ 事件生产者            │       │ AuthorityEvent               │                       │
│  │                      │       │ event_id / event_type        │                       │
│  │ L1 visual facts      │──────>│ source / routing             │                       │
│  │ ESM world results    │       │ priority / durability / ttl  │                       │
│  │ conversation events  │       │ causation / correlation      │                       │
│  │ Siming outputs       │       │ payload                      │                       │
│  └──────────┬───────────┘       └──────────────┬──────────────┘                       │
│             │                                  │                                      │
│             │ Phase0AuthorityEventAdapter      v                                      │
│             │                     ┌─────────────────────────────┐                      │
│             └────────────────────>│ InMemoryAuthorityEventBus   │                      │
│                                   │ publish / subscribe         │                      │
│                                   │ list_events                 │                      │
│                                   └──────────────┬──────────────┘                      │
│                                                  │                                     │
│                ┌─────────────────────────────────┼────────────────────────────────┐    │
│                │                                 │                                │    │
│                v                                 v                                v    │
│  ┌──────────────────────────┐     ┌──────────────────────────┐     ┌──────────────────┐ │
│  │ FrontendAuthorityEvent    │     │ SimingEventConsumer      │     │ 审计 / replay    │ │
│  │ Projector                 │     │                           │     │                  │ │
│  │ world_result              │     │ global situation input   │     │ verification     │ │
│  │ state_machine_transition  │     │ fairness / catalyst path │     │ run evidence     │ │
│  │ siming_output projection  │     └────────────┬─────────────┘     └──────────────────┘ │
│  └────────────┬─────────────┘                  │                                      │
│               │                                │ SimingEventProducer                    │
│               v                                v                                      │
│       Godot 可消费消息                 siming.* authority event                         │
│       不等于 Godot authority owner      回到同一 L6 bus                                  │
│                                                                                       │
└───────────────────────────────────────────────────────────────────────────────────────┘
```

## 当前 owner

| 区域 | 文件 |
| --- | --- |
| Authority event 契约 | `backend/app/models/authority_event.py` |
| Authority event bus port / in-memory bus | `backend/app/services/authority_event_bus.py` |
| Phase 0 事件适配 | `backend/app/services/phase0_authority_event_adapter.py` |
| 前端兼容投影适配器 | `backend/app/services/frontend_authority_event_projection.py` |
| Siming 消费与生产 | `backend/app/services/siming_event_consumer.py`, `backend/app/services/siming_event_producer.py` |
| Siming 审计 | `backend/app/services/siming_audit_writer.py` |

## 事件族

当前主线中已经进入 L6 authority path 的事件族包括：

- `visual_fact_event`
- `esm_result_event`
- `constraint_state_event`
- `conversation_resolution_event`
- `state_machine_transition_event`
- `siming.fact_reveal`
- `siming.visual_observability_request`

## 边界

L6 可以：

- 统一跨层 authority event envelope。
- 承载 publish / subscribe / list_events。
- 把 ESM、L1、conversation、Siming 输出纳入同一 authority event path。
- 连接 `FrontendAuthorityEventProjector`，由该适配器投影出 Godot 可消费的 `world_result`、`state_machine_transition`、`siming_output`。
- 为 replay、audit、harness proof 提供事件证据。

L6 不能：

- 生成感知语义；感知语义属于 L1 / provider / VLA / 角色私有感知消费方。
- 选择角色 intent；角色 intent 属于角色智能体。
- 结算世界真相；结算属于 ESM 与交互编排。
- 直接控制 Godot 表现；Godot 只消费投影消息。
- 把 provider readiness 当成真实 provider 成功调用。

## 验证

- `python scripts/verification/harness.py --profile backend-contract`
- `python scripts/verification/harness.py --profile boundaries`
- `python scripts/verification/harness.py --profile mainline-unified-runtime`
- `python scripts/verification/harness.py --profile siming-backend-chain`

说明：`siming-backend-chain` 需要 live model-provider credentials，不包含在默认 `all` profile 中。
