# Harness 验证证据

状态：当前运行时模块文档

本文记录 runtime 文档如何对应 Harness profile 和证据产物。

## 责任边界

Harness 拥有：

- profile 入口
- verification report
- run-id evidence archive
- docs/boundary/drift/static checks
- backend/Godot/runtime proof scripts

Harness 不拥有：

- 运行时行为本身
- world truth
- ESM authority
- 角色认知
- Siming 判断

## 可视化架构图

```text
┌──────────────────────────── Harness 验证证据 ────────────────────────────┐
│                                                                           │
│  文档 / 代码 / Godot / 后端 / 集成路径                                    │
│        │                                                                  │
│        v                                                                  │
│  ┌──────────────────────────────────┐                                     │
│  │ harness profile registry          │                                     │
│  │ .harness/profiles / rules         │                                     │
│  └───────────────┬──────────────────┘                                     │
│                  │                                                        │
│                  v                                                        │
│  ┌──────────────────────────────────┐                                     │
│  │ scripts/verification/harness.py   │                                     │
│  │ profile dispatcher                │                                     │
│  └───────────────┬──────────────────┘                                     │
│                  │                                                        │
│     ┌────────────┼────────────┬─────────────┬────────────────────┐       │
│     v            v            v             v                    v       │
│   docs       backend       Godot       mainline proof       provider proof│
│   freshness  contract      project     runtime aggregate    readiness/live│
│     │            │            │             │                    │       │
│     └────────────┴────────────┴─────────────┴────────────────────┘       │
│                  │                                                        │
│                  v                                                        │
│  .harness/verification/*-report.json / *.md / runs/run-* evidence archive │
│                                                                           │
│  证明“文档和实现状态”，不替代运行时行为、不替代真实 provider 成功调用      │
└───────────────────────────────────────────────────────────────────────────┘
```

## 主要入口

| 需求 | 命令 |
| --- | --- |
| 文档索引和 freshness | `python scripts/verification/harness.py --profile docs` |
| 主线聚合证明 | `python scripts/verification/harness.py --profile mainline-unified-runtime` |
| Phase 0 smoke path | `python scripts/verification/harness.py --profile phase0` |
| System L1 proof | `python scripts/verification/harness.py --profile l1-world-fact-runtime` |
| 角色执行 proof | `python scripts/verification/harness.py --profile character-agent-execution` |
| ESM / physical channel proof | `python scripts/verification/harness.py --profile esm-physical-channel-world-actuation` |
| VLA proof | `python scripts/verification/harness.py --profile vla-provider-backend` |
| 模型服务 readiness | `python scripts/verification/harness.py --profile model-provider-readiness` |

## 证据产物

| 产物 | 说明 |
| --- | --- |
| `.harness/verification/*-report.json` | 机器可读 report |
| `.harness/verification/*-report.md` | 人类可读 report |
| `.harness/verification/runs/` | run-id evidence archive |
| `.harness/profiles/` | profile manifest |
| `.harness/rules/` | rule-to-evidence manifest |

## 使用规则

- 文档声称“已验证”前，必须指向具体 profile。
- 运行时 milestone 不能只靠 docs profile 证明。
- 真实 provider proof 不能只靠 readiness profile 证明。
- Godot runtime 相关结论应优先使用 Godot profile 或 Phase 0 profile。

## 验证

- `python scripts/verification/harness.py --profile docs`
- `python scripts/verification/harness.py --profile all`
