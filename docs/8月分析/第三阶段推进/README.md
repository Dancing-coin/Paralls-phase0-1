# 第三阶段推进：Population Simulation 与持续世界运行

状态：`phase-three workbench; incremental guidance; non-authorizing until formal spec/plan`

第三阶段承接 `bakery-authored-agents`。目标是让员工、顾客、供应商、竞争对手和监管
角色可以由人口/世界模式机制激活，并以同一 `CharacterRecord` 和 Gameplay authority
持续参与世界。它不是新的 NPC runtime，也不是把 `world_runtime/scheduling.py` 直接
升级成经济结算器。

```text
P2 authored agents
  -> P3A profile-backed activation and population identity
  -> P3B world mode / operating cadence / obligation progression
  -> P3C batch intent and continuity merge
  -> P3D bakery district population vertical slice
  -> P4 dynamic market and institutional economy
```

## 1. 现实基线

| 可复用基础 | 当前缺口 | P3 增量 |
| --- | --- | --- |
| CharacterProfile registry、CharacterAgent L1-L4、角色记忆和 actor-local perception | Population materialization、家庭/职业连续性和批量 planner | 激活 proposal、同一角色记录绑定、连续性 merge receipt |
| `RuntimePopulationPolicy` 的已有唤醒批次/负载降级 | 它不拥有世界人口、组织计划或经济结算 | 受 profile 和 world revision 约束的批量意图入口 |
| GameplayEventStore、revision、idempotency、replay、checkpoint、outbox | 日级/长周期 obligation 的统一处理和 catch-up | 扩展现有调度/义务入口，不建第二个 store 或 bus |
| P2 shift/work/evidence、Survival profile、组织和经济投影 | 多模式消费策略、暂停恢复、pending change merge | 游戏/模拟/推演 mode profile 与确定性恢复契约 |

## 2. 本阶段包含与排除

### 包含

- 已授权角色的 materialize/activate/suspend/requeue 生命周期；
- 个人、家庭、职业和组织关系的受限 projection；
- 游戏、持续模拟、推演三种消费模式的时间精度和智能体唤醒策略；
- 批量 planner 产生 typed `GameplayCommandEnvelope`，由现有 authority 验证和提交；
- bakery district 中多角色员工、顾客、供应商、竞争对手、监管角色的连续性样板；
- full/checkpoint-tail replay、暂停恢复、catch-up、隐私和负载降级证据。

### 排除

- 动态订单簿、拍卖、价格发现、跨区贸易和宏观经济；
- 文明能力、政治军事、法院和反事实分支；
- 让 planner、模型或司命直接写角色、库存、账户或政府事实；
- 新建 `NpcState`、人口账户副本、家庭总 coordinator 或全局万能 scheduler。

## 3. 正式化路径

开始实现前需在 `docs/superpowers/specs/world-character-siming-authority-mainline/` 建立
matching P3A-P3D spec，再建立 plan 与 focused Harness profile。P3 spec 必须引用 P1/P2
fresh evidence 和现有 `world_runtime`、Character Core、Gameplay Foundation owner；不得
把本目录的逻辑名称直接当作已存在 API。

文档导航：

1. [01-第三阶段范围与运行模式边界.md](01-第三阶段范围与运行模式边界.md)
2. [02-角色激活、批量意图与连续性契约.md](02-角色激活、批量意图与连续性契约.md)
3. [03-面包店人口样板与第三阶段门禁.md](03-面包店人口样板与第三阶段门禁.md)

正式 SDD 入口：
[Phase Three Population Continuity Specification Tree](../../superpowers/specs/world-character-siming-authority-mainline/phase-three-population-continuity/README.md)
；对应实施计划见同名 plan tree。当前仍为 `design-only; implementation not authorized`。
