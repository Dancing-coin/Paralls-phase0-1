# Godot 表现与角色入口

状态：当前运行时模块文档

本文记录 Godot 侧的输入、表现、角色入口和本地具身边界。

## 责任边界

Godot 拥有：

- 玩家输入终端
- 本地可见/音频表现
- 角色副本和 skin 驱动
- 本地高频具身与表现状态
- provider 采样节点

Godot 不拥有：

- world truth authority
- ESM settlement
- 角色语义 intent 选择
- Siming 全局判断
- VLA 或模型输出的直接执行权

## 可视化架构图

```text
┌──────────────────────────── Godot 表现与角色入口 ────────────────────────────┐
│                                                                               │
│  玩家 / 场景 / 角色节点                                                        │
│       │                                                                       │
│       ├──────────────> 玩家输入：dialogue / move / interact / focus           │
│       ├──────────────> raw_fact_event emitters                                │
│       └──────────────> provider refs：visual / spatial / auditory / body      │
│                         skeletal / environment                                │
│                         │                                                     │
│                         v                                                     │
│  ┌──────────────────────────────────┐                                         │
│  │ BackendBridge.gd                  │                                         │
│  │ WebSocket structured envelopes    │──────────────────────┐                  │
│  └──────────────────────────────────┘                      │                  │
│                         ^                                  │                  │
│                         │ backend projected messages       │                  │
│                         │                                  v                  │
│  ┌──────────────────────────────────┐          后端 Authority Runtime          │
│  │ LocalPresentationBus.gd           │<──────── world_result / character_exec  │
│  │ 本地表现分发                      │          siming_output / state transition│
│  └───────────────┬──────────────────┘                                         │
│                  │                                                            │
│                  v                                                            │
│  ┌──────────────────────────────────┐                                         │
│  │ CharacterReplica / RuntimeState   │                                         │
│  │ AgentControllerAdapter            │                                         │
│  └───────────────┬──────────────────┘                                         │
│                  │                                                            │
│                  v                                                            │
│  KnightRoleSkin / voice stub / object state / visible feedback                 │
│                                                                               │
│ 禁止：Godot 本地伪造 authority 成功、选择角色语义 intent、直接执行模型/VLA 输出 │
└───────────────────────────────────────────────────────────────────────────────┘
```

## 主要 owner

| 区域 | 文件 |
| --- | --- |
| Backend bridge | `scripts/autoload/BackendBridge.gd` |
| 本地表现总线 | `scripts/autoload/LocalPresentationBus.gd` |
| Phase 0 demo 控制 | `scripts/phase0/MainDemoController.gd` |
| 玩家输入 | `scripts/player/*` |
| 角色副本 | `scripts/character/CharacterReplica.gd` |
| 角色运行时状态 | `scripts/character/CharacterRuntimeState.gd` |
| Agent 适配器 | `scripts/character/AgentControllerAdapter.gd` |
| Provider 节点 | `scripts/character/*Provider.gd` |
| 交互适配 | `scripts/interaction/*` |

## 输入与输出

| 方向 | 契约 |
| --- | --- |
| Godot 到后端 | `player_input`, `raw_fact_event`, provider refs, `interact_intent` |
| 后端到 Godot | `dialogue_response`, `world_result`, `character_agent_execution`, `siming_output` |
| Godot 内部 | `LocalPresentationBus` signals, `CharacterRuntimeState`, `CharacterPresentationInput` |

## 角色入口链路

```text
backend/app/main.py
-> BackendBridge.gd
-> LocalPresentationBus.gd
-> CharacterReplica.gd
-> AgentControllerAdapter
-> CharacterRuntimeState
-> CharacterPresentationInput
-> KnightRoleSkin / 本地表现
```

## 验证

- `python scripts/verification/harness.py --profile godot-project`
- `python scripts/verification/harness.py --profile character-agent-execution`
- `python scripts/verification/harness.py --profile godot-sampling-production-grade-providers`
- `python scripts/verification/harness.py --profile phase0`
