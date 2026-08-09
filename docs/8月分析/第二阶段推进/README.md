# 第二阶段推进：已有角色的多智能体组织协作

状态：`incremental guidance; formal SDD implemented-and-verified; this directory remains non-authorizing`

## 1. 阶段定位

第二阶段承接已完成的第一阶段 Gameplay Foundation、`bakery-single-owner` 和异质样板门禁。
它不开始 Population Simulation，也不把面包店扩展为动态市场或完整商业社会。唯一的
目标是验证：**多个已经存在的 CharacterProfile/CharacterAgent 能否以不同组织岗位，通过
同一条 Gameplay authority 事实链协作经营。**

本目录称此参考配置为 `bakery-authored-agents`。它对应
[Econ-1 商业生态与多角色经营实现方案](../第一阶段推进/05-Econ-1商业生态与多角色经营实现方案.md)
中的 E2，不等同于架构审计里历史语境的 P2 编号，也不授权创建新的并行 runtime。

```text
已完成：bakery-single-owner
  -> P2A：正式角色引用、岗位和受控工作协作 contract
  -> P2B：排班/工作订单/设施争用与工作证据
  -> P2C：工资义务、角色状态约束与组织期末结算
  -> P2D：多角色投影、回放、Godot mirror 和 Harness 垂直闭环
  -> 后置：Population Simulation 接入，再进入真实商业生态
```

## 2. 继承的现实基线

| 已实现并可复用 | 第二阶段不能假装已有 | 第二阶段需增量补齐 |
| --- | --- | --- |
| CharacterProfile registry、CharacterAgent L1-L4、角色本地记忆与后台 cognition | Population Simulation、NPC materialization、家庭/职业连续性 | profile-backed actor reference bridge 与角色行动到 Gameplay command 的受控适配 |
| GameplayEventStore、append batch、idempotency、revision、replay、outbox、mirror | 第二个 event store、组织总 coordinator、全局 SimulationClock | Organization 的岗位/班次/工作订单生命周期与只读投影 |
| Inventory reservation、production run、facility acquisition、账户、简单债务、合同、permit/tax | payroll、完整雇佣合同、个人日程、动态供需定价 | 以工作证据驱动的工资应计/逾期义务和有限经营窗口 |
| `bakery-single-owner`、聚合需求、固定 quote、公开竞争 profile | 顾客/供应商/竞争对手 NPC 状态与个人账户 | 多角色协作 reference package、冲突/拒绝/恢复矩阵与 actor-scoped mirror |

当前仓库的 `RoleAssignment` 只证明岗位引用可由既有角色承担；`ProductionRun` 尚不表达
实际 worker contribution；CharacterAgent L4 也尚未成为任意 Gameplay command writer。第二阶段
必须把这些缺口显式变成受限 contract，不能用测试脚本直接改组织、角色或经济结果。

P1D focused tests 与 `phase1d-econ1-bakery` Harness 已 fresh-green；Phase Two 的 focused
tests、四个 phase2 Harness 和全量 pytest 也已通过。实现证据只认主线 formal spec/plan 与
`.harness/verification/` 报告，不把本目录的分析文字当作运行时 API。

## 3. 本阶段范围

### Included

- 2-4 个已存在 CharacterProfile 对应的 `character:<profile_id>` 引用；
- 一个商业 Organization 的岗位、班次、工作订单、接受/拒绝/缺勤和完成证据；
- worker skill/body/survival 可用性作为 authority 验证输入；
- facility slot 与 inventory reservation 冲突；
- 基于已提交工作证据的工资应计、支付或逾期义务；
- 每角色受限的组织/工作/薪酬 projection，以及 committed-only Godot mirror；
- 显式经营窗口和有界到期义务处理，不建立全局后台世界时钟；
- full/checkpoint-tail replay、权限过滤、重复/stale/失败零写入和多角色 Harness。

### Excluded

- Population Simulation Authority、NPC 创建/唤醒、人口账户、家庭预算或离线批量生活；
- 顾客、供应商、竞争对手、检查员的角色化决策；
- 动态市场、订单簿、拍卖、价格发现、跨区贸易、金融信用和公司制；
- 关系/声望/知识传播的通用运行时；
- 新 event store、bus、scheduler、世界真相 owner 或让 CharacterAgent 直接 `append_batch`；
- 把现有 `char_a/char_b/char_c` 的原始人设覆盖成正式面包店 NPC。

## 4. 参考配置

`bakery-authored-agents` 的内容包目标是 3 个真实角色：经营者、烘焙/维护者、柜台/采购者。
当前仓库的 `char_a`、`char_b`、`char_c` 可作为 **profile-backed contract harness** 引用，
但不能被设计文档重写身份或职业。可玩内容包必须提供其自身已经授权的角色档案；岗位是组织
关系，不是对角色档案的覆写。

顾客仍使用 `CustomerDemandAggregate`，供应商仍使用固定公开 quote，竞争对手仍使用公开
profile。它们可影响同一经营结果，但绝不拥有角色私有需求、记忆、账户或库存。

## 5. 文档导航

1. [01-第二阶段范围与正式收口路径.md](01-第二阶段范围与正式收口路径.md)
2. [02-多角色组织协作与结算契约.md](02-多角色组织协作与结算契约.md)
3. [03-角色智能体工作意图与经营窗口.md](03-角色智能体工作意图与经营窗口.md)
4. [04-多角色面包店参考包与验证门禁.md](04-多角色面包店参考包与验证门禁.md)

## 6. 正式 SDD 与 plan

本目录继续保留“增量设计指导、非直接实现授权”的定位。正式设计和 matching plan 已迁移到
主线 spec/plan tree：

- [Phase Two spec tree](../../superpowers/specs/world-character-siming-authority-mainline/phase-two-bakery-authored-agents/README.md)
- [Phase Two plan tree](../../superpowers/plans/world-character-siming-authority-mainline/phase-two-bakery-authored-agents/README.md)
- [P2A Actor-to-Gameplay Participation spec](../../superpowers/specs/world-character-siming-authority-mainline/phase-two-bakery-authored-agents/2026-08-09-p2a-actor-to-gameplay-participation-design.md)
- [P2B Organization Work Lifecycle spec](../../superpowers/specs/world-character-siming-authority-mainline/phase-two-bakery-authored-agents/2026-08-09-p2b-organization-work-lifecycle-design.md)
- [P2C Payroll and Operating Window spec](../../superpowers/specs/world-character-siming-authority-mainline/phase-two-bakery-authored-agents/2026-08-09-p2c-payroll-and-operating-window-design.md)
- [P2D Authored-Agents Bakery Vertical Slice spec](../../superpowers/specs/world-character-siming-authority-mainline/phase-two-bakery-authored-agents/2026-08-09-p2d-authored-agents-bakery-vertical-slice-design.md)

## 7. 正式化路径

本目录只在八月分析中冻结下一阶段的增量边界。对应的 matching P2 formal spec/plan 已在
`docs/superpowers/specs/world-character-siming-authority-mainline/phase-two-bakery-authored-agents/`
和 `docs/superpowers/plans/world-character-siming-authority-mainline/phase-two-bakery-authored-agents/`
中形成 `implemented-and-verified` 收口。这里仍只是增量设计指导、非直接实现授权；正式实现
证据必须继续引用当前代码 owner 与 fresh Harness reports，不得把本目录中的候选名称直接当作
现有 API 或存储结构。Population Simulation 仍未授权。
